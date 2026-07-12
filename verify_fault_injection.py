"""Fault-injection validation of the replay verifier (verify_porter.py).

Takes op streams that PASS verification, applies one targeted corruption at a
time, and asserts the verifier rejects every mutant.  Each mutation class
targets one legality rule (DAG order, coupling edges, port rules, cat-section
isolation, EPR accounting, stats consistency), so a pass certifies that the
verifier actually enforces the rule -- not merely that PORTER never violates it.

Usage:
  python verify_fault_injection.py                 # toy stream + fuzz circuits
  python verify_fault_injection.py --qasm f.qasm -a A --seed 0
"""

from __future__ import annotations

import argparse
import copy
import os
import random
import sys
from typing import Callable, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import porter as dr
from verify_porter import VerificationError, random_circuit, verify_state


def _clone_ops(ops: List[dr.CompiledOp]) -> List[dr.CompiledOp]:
    return copy.deepcopy(ops)


def _first(ops: List[dr.CompiledOp], op_type: str, **meta) -> Optional[int]:
    for i, op in enumerate(ops):
        if op.op_type != op_type:
            continue
        if all(op.metadata.get(k) == v for k, v in meta.items()):
            return i
    return None


# Each mutation: name, targeted rule, function(ops, hw) -> mutated ops or None
# (None = stream has no site for this mutation; skipped, not failed).
def _drop_disentangler(ops, hw):
    i = _first(ops, "cat_disentangler")
    if i is None:
        return None
    out = _clone_ops(ops)
    del out[i]
    return out


def _swap_teleport_ports(ops, hw):
    i = _first(ops, "teleport")
    if i is None:
        return None
    out = _clone_ops(ops)
    src_phys, src_port, dst_phys = out[i].physical_qubits
    out[i].physical_qubits = (src_phys, dst_phys, src_port)
    return out


def _zero_teleport_epr(ops, hw):
    i = _first(ops, "teleport")
    if i is None:
        return None
    out = _clone_ops(ops)
    out[i].epr_cost = 0
    return out


def _duplicate_gate_op(ops, hw):
    i = _first(ops, "local_cx") or _first(ops, "single")
    if i is None:
        return None
    out = _clone_ops(ops)
    out.insert(i + 1, copy.deepcopy(out[i]))
    return out


def _drop_gate_op(ops, hw):
    i = _first(ops, "local_cx") or _first(ops, "single")
    if i is None:
        return None
    out = _clone_ops(ops)
    del out[i]
    return out


def _reorder_dependent_gates(ops, hw):
    # Swap two gate-carrying ops that share a logical qubit.
    carriers = [
        (i, op) for i, op in enumerate(ops)
        if op.op_type in {"single", "local_cx", "cat_cx"} and op.gates
    ]
    for a in range(len(carriers)):
        ia, opa = carriers[a]
        qa = set(opa.gates[0].qubits)
        for b in range(a + 1, len(carriers)):
            ib, opb = carriers[b]
            if qa & set(opb.gates[0].qubits):
                out = _clone_ops(ops)
                out[ia], out[ib] = out[ib], out[ia]
                return out
    return None


def _swap_noncoupled(ops, hw):
    i = _first(ops, "local_swap")
    if i is None:
        return None
    out = _clone_ops(ops)
    p0, _ = out[i].physical_qubits
    core = hw.cores[hw.phys_to_core[p0]]
    adjacent = set(core.local_adjacency()[p0])
    for p in core.physical_qubits:
        if p != p0 and p not in adjacent:
            out[i].physical_qubits = (p0, p)
            return out
    return None


def _strip_packet_reason(ops, hw):
    i = _first(ops, "local_swap", reason="packet_target_route")
    if i is None:
        return None
    out = _clone_ops(ops)
    out[i].metadata["reason"] = "local_route"
    return out


def _swap_onto_live_port(ops, hw):
    i = _first(ops, "local_swap", reason="packet_target_route")
    if i is None:
        return None
    out = _clone_ops(ops)
    port = out[i].metadata["target_port"]
    neighbor = next(iter(hw.cores[hw.phys_to_core[port]].local_adjacency()[port]))
    out[i].physical_qubits = (port, neighbor)
    return out


MUTATIONS: List[Tuple[str, str, Callable]] = [
    ("drop_disentangler", "cat section left open", _drop_disentangler),
    ("swap_teleport_ports", "teleport must use the core pair's ports", _swap_teleport_ports),
    ("zero_teleport_epr", "teleport must cost exactly 1 EPR", _zero_teleport_epr),
    ("duplicate_gate_op", "each gate executes exactly once", _duplicate_gate_op),
    ("drop_gate_op", "every gate must be executed", _drop_gate_op),
    ("reorder_dependent_gates", "per-qubit DAG order", _reorder_dependent_gates),
    ("swap_noncoupled", "SWAP needs a coupling edge", _swap_noncoupled),
    ("strip_packet_reason", "only packet ops inside a live cat section", _strip_packet_reason),
    ("swap_onto_live_port", "live cat ports are untouchable", _swap_onto_live_port),
    ("stats_drift", "stats must match the op stream", None),  # handled specially
]


def check_stream(
    label: str,
    hw: dr.Hardware,
    layout: dr.Layout,
    circuit: List[dr.Gate],
    state: dr.RouterState,
) -> Tuple[int, int]:
    verify_state(hw, layout, circuit, state)  # sanity: pristine stream passes
    caught = skipped = 0
    for name, rule, fn in MUTATIONS:
        if fn is None:  # stats_drift
            mutant_state = copy.deepcopy(state)
            mutant_state.stats.epr += 1
        else:
            mutated = fn(state.emitted, hw)
            if mutated is None:
                skipped += 1
                print(f"  [skip] {name}: no site in this stream", flush=True)
                continue
            mutant_state = copy.deepcopy(state)
            mutant_state.emitted = mutated
        try:
            verify_state(hw, layout, circuit, mutant_state)
        except VerificationError as exc:
            caught += 1
            print(f"  [caught] {name} ({rule}): {exc}", flush=True)
        else:
            raise SystemExit(f"[MISSED] {label}: mutation {name} was NOT rejected")
    print(f"[ok] {label}: {caught} mutations rejected, {skipped} skipped", flush=True)
    return caught, skipped


def toy_stream() -> Tuple[str, dr.Hardware, dr.Layout, List[dr.Gate], dr.RouterState]:
    """The Sec III-G running example: packet + teleport + local work."""
    import compile_porter as cdr

    _, hw = cdr.hardware_for_name("A")
    l2p = {0: 3, 4: 4, 6: 6, 1: 10, 2: 14, 3: 15, 5: 13, 7: 9, 8: 11, 9: 16, 10: 17}
    layout = dr.Layout(
        logical_to_physical=dict(l2p),
        logical_to_core={q: hw.phys_to_core[p] for q, p in l2p.items()},
        physical_to_logical={p: q for q, p in l2p.items()},
        num_logical=11,
    )
    circuit = [
        dr.Gate("cx", (0, 1)),
        dr.Gate("cx", (0, 2)),
        dr.Gate("cx", (0, 3)),
        dr.Gate("cx", (4, 5)),
        dr.Gate("cx", (0, 6)),
    ]
    state = dr.PorterRouter(hw, dr.RouterConfig(random_seed=0)).compile(
        circuit, layout.clone()
    )
    return "toy-running-example", hw, layout, circuit, state


def fuzz_streams(trials: int):
    import compile_porter as cdr

    for trial in range(trials):
        rng = random.Random(trial)
        arch = rng.choice(["A", "H"])
        _, hw = cdr.hardware_for_name(arch)
        capacity = sum(len(c.physical_qubits) for c in hw.cores.values())
        cfg = dr.RouterConfig(random_seed=trial)
        max_logical = capacity - cfg.min_free_before_teleport * len(hw.cores)
        num_logical = rng.randrange(4, max_logical + 1)
        num_gates = rng.randrange(20, 600)
        circuit = random_circuit(num_logical, num_gates, rng)
        layout = cdr.build_initial_layout(
            circuit, hw, num_logical,
            min_free_per_core=cfg.min_free_before_teleport,
        )
        state = dr.PorterRouter(hw, cfg).compile(circuit, layout.clone())
        yield f"fuzz-{trial}-{arch}-q{num_logical}-g{num_gates}", hw, layout, circuit, state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qasm", default=None)
    parser.add_argument("-a", "--architecture", default="A")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--trials", type=int, default=10)
    args = parser.parse_args()

    total_caught = total_skipped = streams = 0
    if args.qasm:
        from pathlib import Path

        import compile_porter as cdr

        _, hw = cdr.hardware_for_name(args.architecture)
        circuit, num_logical = cdr.parse_qasm2(Path(args.qasm))
        cfg = dr.RouterConfig(random_seed=args.seed)
        layout = cdr.build_initial_layout(
            circuit, hw, num_logical,
            min_free_per_core=cfg.min_free_before_teleport,
        )
        state = dr.PorterRouter(hw, cfg).compile(circuit, layout.clone())
        c, s = check_stream(args.qasm, hw, layout, circuit, state)
        total_caught += c
        total_skipped += s
        streams += 1
    else:
        c, s = check_stream(*toy_stream())
        total_caught += c
        total_skipped += s
        streams += 1
        for stream in fuzz_streams(args.trials):
            c, s = check_stream(*stream)
            total_caught += c
            total_skipped += s
            streams += 1

    print(
        f"\nall mutants rejected: {total_caught} caught / {total_skipped} skipped "
        f"across {streams} streams x {len(MUTATIONS)} mutation classes",
        flush=True,
    )


if __name__ == "__main__":
    main()
