"""Does ``RouterConfig.dag_front_limit`` (96) ever bind, and does it matter?

Sec. III-D of the paper states the observed maximum DAG front size per
instance and asserts that the cap, where it binds, is output-neutral.  Both
figures come from here.

The earlier claim -- that the cap never binds "since front gates are pairwise
qubit-disjoint" -- was wrong: disjointness bounds the front by the logical
qubit count, not by 96, and single-qubit gates are not excluded.  On 360q
QPEexact the front reaches 360 and the cap does bind.  It is inert there
because truncation is by ascending gate index and directly executable gates
drain before any routing decision, so the discarded gates return next
iteration; this script checks that by re-routing with the cap removed.

    python paper/probe_front_limit.py
"""
import os
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent))

import compile_porter as cdr          # noqa: E402
import porter                         # noqa: E402

CIRC = _HERE.parent.parent / "other" / "telesabre" / "circuits"
DEV = _HERE.parent.parent / "other" / "telesabre" / "devices"

CASES = [
    ("25q/random",  "A",              "qasm_25/random_nativegates_ibm_qiskit_opt3_25.qasm"),
    ("64q/qft",     "H",              "qasm_64/qft_nativegates_ibm_qiskit_opt3_64.qasm"),
    ("64q/random",  "H",              "qasm_64/random_nativegates_ibm_qiskit_opt3_64.qasm"),
    ("80q/qft",     "H",              "qasm_80/qft_nativegates_ibm_qiskit_opt3_80.qasm"),
    ("100q/qft",    "H_grid_2_3_5_5", "qasm_100/qft_nativegates_ibm_qiskit_opt3_100.qasm"),
    ("100q/qpe",    "H_grid_2_3_5_5", "qasm_100/qpeexact_nativegates_ibm_qiskit_opt3_100.qasm"),
    ("200q/qft",    "H_grid_3_4_5_5", "qasm_200/qft_nativegates_ibm_qiskit_opt3_200.qasm"),
    ("200q/qpe",    "H_grid_3_4_5_5", "qasm_200/qpeexact_nativegates_ibm_qiskit_opt3_200.qasm"),
    ("360q/qft",    "H_grid_4_5_5_5", "qasm_360/qft_nativegates_ibm_qiskit_opt3_360.qasm"),
    ("360q/qpe",    "H_grid_4_5_5_5", "qasm_360/qpeexact_nativegates_ibm_qiskit_opt3_360.qasm"),
]

_MAX = {}
_orig = porter.router.PorterRouter._current_dag_front


def _probe(self, state):
    _MAX[_probe.key] = max(_MAX.get(_probe.key, 0), len(state.dag_frontier))
    return _orig(self, state)


def hardware(arch):
    if arch in ("A", "H"):
        return cdr.hardware_for_name(arch)[1]
    return cdr.hardware_from_device_json(DEV / f"{arch}.json")[1]


def route_at(hw, gates, n, cap):
    cfg = porter.RouterConfig(dag_front_limit=cap)
    layout = cdr.build_initial_layout(gates, hw, n,
                                      min_free_per_core=cfg.min_free_before_teleport)
    st, _ = cdr.route(hw, cfg, list(gates), layout, selection=False)
    s = st.stats
    return (s.teleport_count + s.telegate_count + s.telegate_packet_count,
            s.local_swap_count)


def main():
    porter.router.PorterRouter._current_dag_front = _probe
    print(f"{'instance':<12}{'n':>5}{'max|front|':>12}{'cap 96':>10}"
          f"{'EPR':>8}{'EPR uncapped':>14}")
    binds = []
    for name, arch, rel in CASES:
        path = CIRC / rel
        if not path.exists():
            print(f"{name:<12}  -- circuit not found: {path}")
            continue
        _probe.key = name
        hw = hardware(arch)
        gates, n = cdr.parse_qasm2(path)
        porter.assign_gate_ids(gates)
        capped = route_at(hw, gates, n, 96)
        m = _MAX.get(name, 0)
        # Re-route without the cap only where it actually bound.
        free = route_at(hw, gates, n, 0) if m > 96 else capped
        if m > 96:
            binds.append((name, m, capped, free))
        print(f"{name:<12}{n:>5}{m:>12}{('BINDS' if m > 96 else '-'):>10}"
              f"{capped[0]:>8}{free[0]:>14}")
    print()
    if not binds:
        print("cap never bound on any probed instance")
    for name, m, capped, free in binds:
        same = "IDENTICAL" if capped == free else "*** DIFFERS ***"
        print(f"{name}: front reached {m} > 96; capped vs uncapped "
              f"(EPR, SWAP) = {capped} vs {free} -- {same}")
    return 0 if all(c == f for _, _, c, f in binds) else 1


if __name__ == "__main__":
    raise SystemExit(main())
