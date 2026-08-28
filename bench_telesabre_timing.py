"""Re-measure the TeleSABRE column of paper/timing_results.json.

Only the TeleSABRE column depends on the `init_layout_hun_min_free_qubit`
config fix; the dSABRE / PORTER / PORTER+R columns are untouched and are
carried over from the existing file.

Convention (unchanged): COMPLETE protocol wall time -- every seed attempted,
not just the winning one -- median of three repetitions, run serially.
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import compare_routers as cr

REPS = 3
ROWS = [("25", "ae", "qasm_25", "ae_nativegates_ibm_qiskit_opt3_25.qasm"),
        ("25", "random", "qasm_25", "random_nativegates_ibm_qiskit_opt3_25.qasm"),
        ("64", "ae", "qasm_64", "ae_nativegates_ibm_qiskit_opt3_64.qasm"),
        ("64", "qft", "qasm_64", "qft_nativegates_ibm_qiskit_opt3_64.qasm"),
        ("64", "qnn", "qasm_64", "qnn_OLD_DEEP_nativegates_ibm_qiskit_opt3_64.qasm.bak"),
        ("80", "random", "qasm_80", "random_nativegates_ibm_qiskit_opt3_80.qasm")]

def main() -> None:
    path = _HERE / "paper" / "timing_results.json"
    rows = json.loads(path.read_text())
    by = {(r["suite"], r["circuit"]): r for r in rows}

    for suite, circ, sub, fname in ROWS:
        spec = cr.SUITES[suite]
        qasm = cr.TELESABRE_DIR / "circuits" / sub / fname
        samples, epr = [], None
        for _ in range(REPS):
            t0 = time.perf_counter()
            res = cr.run_telesabre(qasm, spec["device_json"])
            samples.append(time.perf_counter() - t0)
            if res is None:
                epr = None
                break
            epr = res["epr"]
        rec = by[(suite, circ)]
        old = rec["telesabre"]
        rec["telesabre"] = None if epr is None else round(statistics.median(samples), 2)
        print(f"{suite}q {circ:<8} TS {str(old):>8} -> {str(rec['telesabre']):>8}"
              f"   (epr={epr}, samples={[round(s,2) for s in samples]})", flush=True)
        path.write_text(json.dumps(rows, indent=1))
    print(f"\nWrote {path}", flush=True)


if __name__ == "__main__":
    main()
