"""Re-measure dSABRE's own-protocol leg in the same session as PORTER's.

PORTER's legs were re-run after the capacity-relief change, so its `seconds`
come from this machine.  dSABRE's came from an earlier session on hardware
measured ~1.7x faster, and `tab:main`'s t column compares the two directly --
the cross-session mixing that killed the standalone timing table.  This
re-measures dSABRE with its own protocol unchanged (3 SabreLayout candidates x
3 passes, its own budgets), so EPR must reproduce exactly; only time moves.

    python3 rerun_dsabre_timing.py            # all three suites
    python3 rerun_dsabre_timing.py 25 64
"""
import json
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repo root
sys.path.insert(0, _ROOT)

import compare_routers as cr
import compile_porter as cdr

OUT = os.path.join(_ROOT, "paper", "compare_results_selection.json")


def main():
    want = set(a for a in sys.argv[1:] if a in cr.SUITES) or set(cr.SUITES)
    rows = json.load(open(OUT))
    moved = []
    for row in rows:
        if row["suite"] not in want:
            continue
        key = f"{row['suite']}/{row['circuit']}"
        spec = cr.SUITES[row["suite"]]
        _, hw = cdr.hardware_for_name(spec["arch_name"])
        fname = next(f for f in spec["files"]
                     if f.split("_nativegates")[0].replace(".qasm", "") in
                     (row["circuit"], row["circuit"] + "_OLD_DEEP")
                     or f.startswith(row["circuit"] + "_"))
        qasm = spec["circuit_dir"] / fname
        qc, dag = cr.load_qasm(qasm)
        rev_dag = cr.circuit_to_dag(qc.reverse_ops())
        arch = cr.sfc_hardware_to_dsabre_architecture(hw)
        cr.verify_topology_match(hw, arch)
        # dSABRE's own convention: derive every budget from the architecture.
        # A bare HardwareConfig() takes defaults, and a BINDING max_iterations
        # truncates the heuristic search and hands the remainder to _safe_drain,
        # which completes the route at a much worse EPR count (measured: 80q
        # Random 10,551 -> 17,514).  run_suite passes None for all three.
        hw_cfg = cr.HardwareConfig(
            deadlock_limit=None, max_backup_attempts=None, max_iterations=None
        )

        t0 = time.perf_counter()
        layouts = cr.dsabre_layout_candidates(qc, dag, arch, seed=0)
        layout_seconds = time.perf_counter() - t0
        before = (row.get("dSE") or {}).get("epr")
        before_s = (row.get("dSE") or {}).get("seconds")
        row["dSE"] = cr.run_dsabre(cr.dSE, arch, hw_cfg, dag, rev_dag, layouts,
                                   layout_seconds=layout_seconds)
        after = row["dSE"]["epr"]
        if before != after:
            moved.append((key, before, after))
        print(f"[{key}] dSE epr {before} -> {after}"
              f"{'  *** EPR MOVED ***' if before != after else ''}"
              f"   seconds {before_s:.2f} -> {row['dSE']['seconds']:.2f}", flush=True)
        with open(OUT, "w") as fh:
            json.dump(rows, fh, indent=2)
    with open(OUT, "w") as fh:
        json.dump(rows, fh, indent=2)
    if moved:
        print("\nWARNING: dSABRE EPR changed on", moved,
              "\n  Its protocol was not touched -- investigate before trusting this run.")
    else:
        print("\ndSABRE EPR reproduced exactly on every instance; only time moved.")


if __name__ == "__main__":
    main()
