"""Re-measure the PORTER columns of paper/timing_results.json.

`timing_results.json` is a dedicated median-of-three timing run on an idle
machine, kept separate from the single-run `seconds` fields in
compare_results.json.  `bench_telesabre_timing.py` refreshes its TeleSABRE
column; this refreshes `porter`, `porter_refined` AND `dsabre` after PORTER's
routing protocol changed to horizon selection.  dSABRE is re-measured even
though its router is untouched, because a timing table that compares columns
measured in different sessions on different machine states is not sound --
the paper's own comparison is PORTER against dSABRE, so those two must at
least come from the same run.  The TeleSABRE column is NOT re-measured here
(it does not converge on 80q Random, so a rep costs the full 900 s timeout);
that column remains from the original session and is flagged as such.  Same convention as the file records:
the COMPLETE protocol -- layout generation plus every routing pass, including
every candidate horizon, not the winning attempt alone.

Writes paper/timing_results_selection.json; the released file is untouched.

    python bench_porter_timing.py [suite ...]
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from qiskit.converters import circuit_to_dag

import compare_routers as cr
import compile_porter as cdr
from config import HardwareConfig

REPS = 3
SRC = _HERE / "paper" / "timing_results.json"
OUT = _HERE / "paper" / "timing_results_selection.json"


def main() -> None:
    want = set(sys.argv[1:]) or set(cr.SUITES)
    rows = json.loads(SRC.read_text())
    for row in rows:
        if row["suite"] not in want:
            continue
        spec = cr.SUITES[row["suite"]]
        _, hw = cdr.hardware_for_name(spec["arch_name"])
        fname = next(f for f in spec["files"]
                     if f.split("_nativegates")[0].replace(".qasm", "") in
                     (row["circuit"], row["circuit"] + "_OLD_DEEP")
                     or f.startswith(row["circuit"] + "_"))
        circuit, n = cdr.parse_qasm2(spec["circuit_dir"] / fname)
        qc, dag = cr.load_qasm(spec["circuit_dir"] / fname)
        rev_dag = circuit_to_dag(qc.reverse_ops())
        arch = cr.sfc_hardware_to_dsabre_architecture(hw)
        cr.verify_topology_match(hw, arch)
        hw_cfg = HardwareConfig(deadlock_limit=None, max_backup_attempts=None,
                                max_iterations=None)

        def _dsabre():
            layouts = cr.dsabre_layout_candidates(qc, dag, arch, seed=0)
            return cr.run_dsabre(cr.dSE, arch, hw_cfg, dag, rev_dag, layouts)

        for leg, fn in (("porter", lambda: cr.run_sfc(circuit, hw, n)),
                        ("porter_refined", lambda: cr.run_sfc_refined(circuit, hw, n)),
                        ("dsabre", _dsabre)):
            samples = []
            for _ in range(REPS):
                t0 = time.perf_counter()
                rec = fn()
                samples.append(time.perf_counter() - t0)
                if rec is None:
                    samples = []
                    break
            row[leg] = round(statistics.median(samples), 2) if samples else None
        row["timing_session"] = ("porter/porter_refined/dsabre re-measured "
                                 "together; telesabre from the original run")
        print(f"[{row['suite']}_{row['circuit']}] porter={row['porter']} "
              f"+R={row['porter_refined']} dsabre={row['dsabre']}", flush=True)
        OUT.write_text(json.dumps(rows, indent=1))
    OUT.write_text(json.dumps(rows, indent=1))
    print(f"\nwrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
