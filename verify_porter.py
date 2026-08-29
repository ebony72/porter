"""Independent replay verifier for PorterRouter output.

The verifier re-executes the emitted CompiledOp stream against its own copy of
the physical layout and checks, without trusting any router-internal state:

  1. every original gate is executed exactly once (single / local_cx / cat_cx);
  2. execution order respects the per-qubit dependency DAG of the circuit;
  3. every physical operation is legal on the hardware:
       - local_swap / local_cx act on intra-core coupling edges,
       - teleports use free adjacent-core ports and land on the target port,
       - telegates (single and packet) satisfy the port-adjacency rules and
         never disturb the live cat communication qubits;
  4. emitted stats (epr, swap/teleport/telegate counts) match the op stream.

Usage:
  python verify_porter.py                      # built-in fuzz suite
  python verify_porter.py --qasm foo.qasm -a A # verify one circuit
"""

from __future__ import annotations

import argparse
import random
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import porter as dr


class VerificationError(AssertionError):
    pass


class _Replay:
    def __init__(self, hw: dr.Hardware, initial_layout: dr.Layout, circuit: List[dr.Gate]):
        self.hw = hw
        self.num_logical = initial_layout.num_logical
        # phys -> logical (real logicals only; free positions map to None)
        self.phys_of: Dict[int, Optional[int]] = {p: None for p in hw.phys_to_core}
        for q, p in initial_layout.logical_to_physical.items():
            if q < self.num_logical:
                self.phys_of[p] = q
        self.pos_of: Dict[int, int] = {
            q: p for p, q in self.phys_of.items() if q is not None
        }
        # Per-qubit pending gate queues enforce the dependency DAG exactly.
        gates = dr.assign_gate_ids(circuit)
        self.queue_of: Dict[int, deque] = {}
        self.gate_by_id = {g.gid: g for g in gates}
        for g in gates:
            for q in g.qubits:
                self.queue_of.setdefault(q, deque()).append(g.gid)
        self.executed: Set[int] = set()
        self.adj: Dict[int, Set[int]] = {}
        for cid, core in hw.cores.items():
            for p, ns in core.local_adjacency().items():
                self.adj[p] = set(ns)
        # Open cat section: (control, control_core, target_core, ports frozenset, role)
        self.section: Optional[Tuple[int, int, int, frozenset, str]] = None
        self.counts = {
            "epr": 0, "teleport": 0, "telegate": 0, "telegate_packet": 0,
            "local_swap": 0, "local_cx": 0, "single": 0,
        }

    # -- helpers ----------------------------------------------------------
    def _fail(self, index: int, op: dr.CompiledOp, msg: str) -> None:
        raise VerificationError(f"op[{index}] {op.op_type}: {msg}")

    def _check_gate_ready(self, index, op, gate: dr.Gate) -> None:
        if gate.gid in self.executed:
            self._fail(index, op, f"gate {gate} executed twice")
        for q in gate.qubits:
            queue = self.queue_of.get(q)
            if not queue or queue[0] != gate.gid:
                head = queue[0] if queue else None
                self._fail(index, op, f"gate {gate} violates dependency order on q{q} (head={head})")

    def _pop_gate(self, gate: dr.Gate) -> None:
        for q in gate.qubits:
            self.queue_of[q].popleft()
        self.executed.add(gate.gid)

    def _expect_at(self, index, op, q: int, p: int) -> None:
        if self.pos_of.get(q) != p:
            self._fail(index, op, f"logical q{q} expected at phys {p}, actually at {self.pos_of.get(q)}")

    def _coupled(self, a: int, b: int) -> bool:
        return b in self.adj.get(a, ())

    # -- op handlers ------------------------------------------------------
    def run(self, emitted: List[dr.CompiledOp]) -> None:
        for index, op in enumerate(emitted):
            handler = getattr(self, f"_op_{op.op_type}", None)
            if handler is None:
                self._fail(index, op, "unknown op type")
            handler(index, op)

        if self.section is not None:
            raise VerificationError("cat section left open at end of op stream")
        missing = [gid for gid, g in self.gate_by_id.items() if gid not in self.executed]
        if missing:
            raise VerificationError(f"{len(missing)} gates never executed, e.g. {self.gate_by_id[missing[0]]}")

    def _in_section_check(self, index, op) -> None:
        if self.section is None:
            return
        ports = self.section[3]
        if op.op_type == "local_swap":
            if op.metadata.get("reason") != "packet_target_route":
                self._fail(index, op, "non-packet swap inside live cat section")
            if set(op.physical_qubits) & ports:
                self._fail(index, op, "swap touches live cat communication qubit")
        elif op.op_type == "single":
            if op.metadata.get("reason") != "packet_target_single":
                self._fail(index, op, "non-packet single inside live cat section")
            if set(op.physical_qubits) & ports:
                self._fail(index, op, "single gate on live cat communication qubit")
        elif op.op_type in {"local_cx", "teleport", "cat_entangler"}:
            self._fail(index, op, "illegal op inside live cat section")

    def _op_single(self, index, op) -> None:
        self._in_section_check(index, op)
        (gate,) = op.gates
        if not gate.is_single_qubit():
            self._fail(index, op, f"not a single-qubit gate: {gate}")
        self._check_gate_ready(index, op, gate)
        self._expect_at(index, op, gate.qubits[0], op.physical_qubits[0])
        self._pop_gate(gate)
        self.counts["single"] += 1

    def _op_local_cx(self, index, op) -> None:
        self._in_section_check(index, op)
        (gate,) = op.gates
        if not gate.is_cx():
            self._fail(index, op, f"not a CX gate: {gate}")
        self._check_gate_ready(index, op, gate)
        q0, q1 = gate.qubits
        p0, p1 = op.physical_qubits
        self._expect_at(index, op, q0, p0)
        self._expect_at(index, op, q1, p1)
        if self.hw.phys_to_core[p0] != self.hw.phys_to_core[p1]:
            self._fail(index, op, "local CX crosses cores")
        if not self._coupled(p0, p1):
            self._fail(index, op, f"phys {p0},{p1} not coupling-adjacent")
        self._pop_gate(gate)
        self.counts["local_cx"] += 1

    def _op_local_swap(self, index, op) -> None:
        self._in_section_check(index, op)
        p0, p1 = op.physical_qubits
        if self.hw.phys_to_core[p0] != self.hw.phys_to_core[p1]:
            self._fail(index, op, "swap crosses cores")
        if not self._coupled(p0, p1):
            self._fail(index, op, f"phys {p0},{p1} not coupling-adjacent")
        q0, q1 = self.phys_of[p0], self.phys_of[p1]
        self.phys_of[p0], self.phys_of[p1] = q1, q0
        if q0 is not None:
            self.pos_of[q0] = p1
        if q1 is not None:
            self.pos_of[q1] = p0
        self.counts["local_swap"] += 1

    def _op_teleport(self, index, op) -> None:
        self._in_section_check(index, op)
        (q,) = op.qubits
        src_phys, src_port, dst_phys = op.physical_qubits
        src_core, dst_core = op.cores
        if not self.hw.are_adjacent_cores(src_core, dst_core):
            self._fail(index, op, f"cores {src_core},{dst_core} not adjacent")
        want_src_port, want_dst_port = self.hw.inter_core_ports(src_core, dst_core)
        if src_port != want_src_port or dst_phys != want_dst_port:
            self._fail(index, op, "teleport does not use the inter-core ports")
        self._expect_at(index, op, q, src_phys)
        if self.phys_of[src_port] is not None:
            self._fail(index, op, f"source port {src_port} occupied")
        if self.phys_of[dst_phys] is not None:
            self._fail(index, op, f"destination port {dst_phys} occupied")
        if src_phys != src_port and not self._coupled(src_phys, src_port):
            self._fail(index, op, f"moving qubit not adjacent to source port")
        if op.epr_cost != 1:
            self._fail(index, op, f"teleport epr_cost {op.epr_cost} != 1")
        self.phys_of[src_phys] = None
        self.phys_of[dst_phys] = q
        self.pos_of[q] = dst_phys
        self.counts["epr"] += 1
        self.counts["teleport"] += 1

    def _op_cat_entangler(self, index, op) -> None:
        self._in_section_check(index, op)
        if self.section is not None:
            self._fail(index, op, "nested cat section")
        (control,) = op.qubits
        control_phys, control_port, target_port = op.physical_qubits
        control_core, target_core = op.cores
        if not self.hw.are_adjacent_cores(control_core, target_core):
            self._fail(index, op, "cat cores not adjacent")
        want_cp, want_tp = self.hw.inter_core_ports(control_core, target_core)
        if control_port != want_cp or target_port != want_tp:
            self._fail(index, op, "cat section does not use the inter-core ports")
        self._expect_at(index, op, control, control_phys)
        if self.phys_of[control_port] is not None or self.phys_of[target_port] is not None:
            self._fail(index, op, "cat ports not free")
        if not self._coupled(control_phys, control_port):
            self._fail(index, op, "control not adjacent to control port")
        if op.epr_cost != 1:
            self._fail(index, op, f"cat_entangler epr_cost {op.epr_cost} != 1")
        role = op.metadata.get("cat_role")
        if role == "packet_start":
            self.counts["telegate_packet"] += 1
        elif role != "single_telegate_start":
            self._fail(index, op, f"unknown cat_role {role!r}")
        self.section = (control, control_core, target_core, frozenset((control_port, target_port)), role)
        self.counts["epr"] += 1

    def _op_cat_cx(self, index, op) -> None:
        if self.section is None:
            self._fail(index, op, "cat_cx outside cat section")
        (gate,) = op.gates
        if not gate.is_cx():
            self._fail(index, op, f"not a CX gate: {gate}")
        self._check_gate_ready(index, op, gate)
        control, target = gate.qubits
        section_control, control_core, target_core, ports, role = self.section
        if control != section_control:
            self._fail(index, op, f"cat_cx control q{control} != section control q{section_control}")
        cat_comm, target_phys = op.physical_qubits
        _, want_tp = self.hw.inter_core_ports(control_core, target_core)
        if cat_comm != want_tp:
            self._fail(index, op, "cat_cx does not use target-side communication qubit")
        self._expect_at(index, op, target, target_phys)
        if self.hw.phys_to_core[target_phys] != target_core:
            self._fail(index, op, "cat_cx target not in target core")
        if not self._coupled(cat_comm, target_phys):
            self._fail(index, op, "cat_cx target not adjacent to communication qubit")
        self._pop_gate(gate)
        if role == "single_telegate_start":
            self.counts["telegate"] += 1

    def _op_cat_disentangler(self, index, op) -> None:
        if self.section is None:
            self._fail(index, op, "cat_disentangler without open section")
        self.section = None


def verify_state(
    hw: dr.Hardware,
    initial_layout: dr.Layout,
    circuit: List[dr.Gate],
    state: dr.RouterState,
) -> None:
    """Raise VerificationError if the compiled op stream is not a faithful,
    physically legal execution of ``circuit`` from ``initial_layout``."""
    replay = _Replay(hw, initial_layout, circuit)
    replay.run(state.emitted)

    stats = state.stats
    expected = {
        "epr": stats.epr,
        "teleport": stats.teleport_count,
        "telegate": stats.telegate_count,
        "telegate_packet": stats.telegate_packet_count,
        "local_swap": stats.local_swap_count,
        "local_cx": stats.local_cx_count,
        "single": stats.single_count,
    }
    for key, want in expected.items():
        got = replay.counts[key]
        if got != want:
            raise VerificationError(f"stats mismatch for {key}: ops say {got}, stats say {want}")
    if state.remaining:
        raise VerificationError(f"{len(state.remaining)} gates left in state.remaining")


# ---------------------------------------------------------------------------
# Fuzz suite
# ---------------------------------------------------------------------------

def random_circuit(num_logical: int, num_gates: int, rng: random.Random) -> List[dr.Gate]:
    gates: List[dr.Gate] = []
    for _ in range(num_gates):
        r = rng.random()
        if r < 0.35:
            gates.append(dr.Gate("rz", (rng.randrange(num_logical),), (rng.random(),)))
        elif r < 0.5:
            gates.append(dr.Gate(rng.choice(["sx", "x"]), (rng.randrange(num_logical),)))
        else:
            q0, q1 = rng.sample(range(num_logical), 2)
            gates.append(dr.Gate("cx", (q0, q1)))
    return gates


def fuzz(trials: int, verbose: bool = True) -> None:
    import compile_porter as cdr

    failures = 0
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
        router = dr.PorterRouter(hw, cfg)
        try:
            state = router.compile(circuit, layout)
            verify_state(hw, layout, circuit, state)
            if verbose:
                print(
                    f"[ok] trial={trial} arch={arch} q={num_logical} gates={num_gates} "
                    f"epr={state.stats.epr} swaps={state.stats.local_swap_count} depth={state.stats.depth}",
                    flush=True,
                )
        except Exception as exc:  # noqa: BLE001 - report and continue fuzzing
            failures += 1
            print(f"[FAIL] trial={trial} arch={arch} q={num_logical} gates={num_gates}: {exc}", flush=True)
    if failures:
        raise SystemExit(f"{failures}/{trials} fuzz trials failed")
    print(f"all {trials} fuzz trials passed", flush=True)


def verify_qasm(qasm: Path, architecture: str, seed: int, passes: int = 1,
                gamma_search: bool = False) -> None:
    import compile_porter as cdr

    circuit, num_logical = cdr.parse_qasm2(qasm)
    _, hw = cdr.hardware_for_name(architecture)
    cfg = dr.RouterConfig(random_seed=seed)
    layout = cdr.build_initial_layout(
        circuit, hw, num_logical,
        min_free_per_core=cfg.min_free_before_teleport,
    )
    if gamma_search:
        state, info = cdr.run_layout_search(hw, cfg, circuit, num_logical,
                                            passes=passes)
        if state is None:
            raise AssertionError(f"no gamma routed: {info}")
        start = info["start_layout"]
        extra = (f" gamma_search best_gamma={info['best_gamma']} "
                 f"routes={info['routes']}")
    elif passes == 1:
        # PORTER's protocol is horizon selection; every candidate horizon
        # routes from the SAME layout, so the winning stream replays against
        # the layout built above.
        state, sel = cdr.route(hw, cfg, circuit, layout)
        start = layout
        extra = f" L={sel.get('chosen_horizon')} horizons={sel.get('horizon_eprs')}"
    else:
        state, info = cdr.run_refinement_passes(hw, cfg, circuit, layout,
                                                passes=passes)
        if state is None:
            raise AssertionError(f"first forward pass failed: {info}")
        # The emitted stream belongs to the WINNING pass, so it must be
        # replayed against that pass's own starting layout.
        start = info["start_layout"]
        extra = (f" passes={passes} chosen=p{info['chosen_pass']} "
                 f"fwd={info['forward_eprs']}")
    verify_state(hw, start, circuit, state)
    print(
        f"[ok] {qasm.name} arch={architecture} seed={seed} "
        f"epr={state.stats.epr} swaps={state.stats.local_swap_count} "
        f"depth={state.stats.depth}{extra}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qasm", type=Path, default=None)
    parser.add_argument("--architecture", "-a", default="A", choices=("A", "H"))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--trials", type=int, default=60)
    parser.add_argument("--passes", type=int, default=1,
                        help="routing passes for --qasm (odd; see compile_porter)")
    parser.add_argument("--gamma-search", action="store_true",
                        help="verify the best-of-gamma layout search result")
    args = parser.parse_args()

    if args.qasm is not None:
        verify_qasm(args.qasm, args.architecture, args.seed, args.passes,
                    args.gamma_search)
    else:
        fuzz(args.trials)


if __name__ == "__main__":
    main()
