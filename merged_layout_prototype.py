"""Benchmark harness for PORTER's temporal locality-greedy initial layout
(now the canonical ``compile_porter.build_initial_layout``; this module
originally prototyped it as a replacement for the balanced-first-layer and
seeded locality-greedy heuristics and their best-of-6 search).

Construction (no seeds anywhere; one layout per circuit):
  1. Temporally discounted interaction weights: each CX contributes
     gamma**layer to its qubit pair, layer = ASAP level in the CX-only DAG
     (gamma=0.99 default).  Early interactions weigh more, which subsumes
     balanced-first-layer's first-CX-layer co-location; accumulated
     multiplicity subsumes locality-greedy's chain tracking.
  2. Visit logical qubits in order of first CX appearance in the circuit
     (deterministic, replaces the seeded random order).  Place each qubit in
     the core of its heaviest already-placed neighbour if that core has
     headroom above f_min, else in the core with most remaining reserved
     capacity.  The f_min-per-core reservation of the existing heuristics is
     kept, so the router's teleport precondition holds by construction.
  3. Within each core, place logicals deterministically: descending total
     interaction weight onto physical slots by ascending intra-core
     centrality (sum of local distances), replacing the seeded shuffle.

Benchmark result (2026-07-12, this machine, RouterConfig(random_seed=0),
single run per circuit, all compilations replay-verified on a 7-instance
spot-check): over the 16 paper instances where the recorded best-of-6 EPR
exists, gmean EPR 55.4 vs best-of-6's 92.0, beating the best-of-6 on 14/16
rows; per-suite own-protocol gmeans become 43.1 / 86.4(5-common) / 11.1
(3-common) vs dSABRE's 45.7 / 95.5 / 22.2 -- i.e. a single deterministic
layout + single routing pass beats dSABRE's best-of-3 SabreLayout +
forward/backward/forward protocol on all three suite gmeans.

Ingredient ablation: the temporal visit order is load-bearing (randomizing
it: gmean 55.4 -> 103.3); the centrality slot placement is minor (-> 56.4).

Held-out validation (2026-07-12): 15 circuits never used for tuning --
the six qasm_36 families (bv, dj, qaoa, qpeexact, vqe_su2, wstate on
architecture H) and the QFT fill-sweep at n=16/24 (A) and
n=32/36/48/56/60/72/84 (H).  gamma=0.99 gmean EPR 71.3 vs the old
best-of-6 protocol's 109.6 (-35%), <= best-of-6 on 14/15 (only qft_n48
regresses, 235 vs 214); all 45 compilations replay-verified; gamma
0.95/0.99/1.0 all behave (no deadlocks, no max_iterations trips).

Known caveats:
  * gamma=0.99 was picked on the 18 paper instances; most rows are
    gamma-insensitive; 64q QNN prefers 1.0 (604 vs 864; best-of-6 was 642
    -- the one clear regression vs the old protocol).
  * 80q Random: 11040 EPR vs best-of-6's 10855 (+1.7%), still ~37 s.  At
    gamma=0.9 that instance hits the max_iterations oscillation guard.

Usage:
    python merged_layout_prototype.py            # bench all 18 instances
    python merged_layout_prototype.py 0.99       # specific gamma(s)
"""
from __future__ import annotations

import json
import signal
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import porter
from compile_porter import parse_qasm2, hardware_for_name

TELESABRE_CIRCUITS = _HERE.parent / "other" / "telesabre" / "circuits"

SUITES = [
    ("25", "A", TELESABRE_CIRCUITS / "qasm_25"),
    ("64", "H", TELESABRE_CIRCUITS / "qasm_64"),
    ("80", "H", TELESABRE_CIRCUITS / "qasm_80"),
]
FILES = {
    "64": {"qnn": "qnn_OLD_DEEP_nativegates_ibm_qiskit_opt3_64.qasm.bak"},
    "80": {"qnn": "qnn_nativegates_ibm_qiskit_opt3_80_DEEP.qasm"},
}
CIRCUITS = ["ae", "ghz", "graphstate", "qft", "qnn", "random"]


# The heuristic was promoted to PORTER's canonical initial layout on
# 2026-07-12; the single source of truth is compile_porter.build_initial_layout.
# This module keeps only the benchmarking harness.
from compile_porter import build_initial_layout as build_merged_layout


class _Timeout(Exception):
    pass


def main() -> None:
    gammas = [float(x) for x in (sys.argv[1:] or ["0.99"])]
    signal.signal(signal.SIGALRM, lambda s, f: (_ for _ in ()).throw(_Timeout()))
    rows = []
    for suite, arch, cdir in SUITES:
        _, hw = hardware_for_name(arch)
        for circ in CIRCUITS:
            fname = FILES.get(suite, {}).get(circ)
            fname = fname or f"{circ}_nativegates_ibm_qiskit_opt3_{suite}.qasm"
            path = cdir / fname
            if not path.exists():
                print(f"MISSING {path}", flush=True)
                continue
            gates, num_logical = parse_qasm2(path)
            cfg = porter.RouterConfig(random_seed=0)
            res = {}
            for gamma in gammas:
                layout = build_merged_layout(
                    gates, hw, num_logical,
                    min_free_per_core=cfg.min_free_before_teleport, gamma=gamma,
                )
                router = porter.PorterRouter(hw, porter.RouterConfig(random_seed=0))
                t0 = time.perf_counter()
                signal.alarm(900)
                try:
                    state = router.compile(gates, layout)
                    res[gamma] = dict(
                        epr=state.stats.epr,
                        swaps=state.stats.local_swap_count,
                        depth=state.stats.depth,
                        seconds=round(time.perf_counter() - t0, 3),
                    )
                except (RuntimeError, _Timeout) as e:
                    res[gamma] = dict(error=str(e)[:100])
                finally:
                    signal.alarm(0)
            rows.append(dict(suite=suite, circuit=circ,
                             merged={str(g): v for g, v in res.items()}))
            print(f"{suite:>3}q {circ:<11} "
                  + " ".join(f"g={g}:{v.get('epr', 'ERR')}" for g, v in res.items()),
                  flush=True)
    out = _HERE / "merged_layout_prototype_results.json"
    out.write_text(json.dumps(rows, indent=1))
    print(f"wrote {out}", flush=True)


if __name__ == "__main__":
    main()
