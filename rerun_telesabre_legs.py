"""Re-run only the TeleSABRE-dependent legs of compare_results.json.

Fixing the `init_layout_hun_min_free_qubit` config key (compare_routers
2026-08-28) changes TeleSABRE's routing AND its reported initial layout, so
exactly four legs move:

    telesabre            TeleSABRE's own protocol
    dSE_shared           dSABRE started from TeleSABRE's initial layout
    sfc_shared           PORTER  started from TeleSABRE's initial layout
    sfc_shared_refined   PORTER+R started from TeleSABRE's initial layout

Every other leg (sfc, sfc_refined, sfc_search, dSE, dSE_on_porter_layout,
sfc_on_dse_layout*, and all pytket legs) is independent of the TeleSABRE
config and is carried over untouched, so the paper's other tables do not
shift under an unrelated re-measurement.

This calls compare_routers' own functions and replicates run_suite's setup
verbatim, so the protocol is identical to a full re-run of those legs.

Writes paper/compare_results.json in place (a .bak copy is kept) and prints
an old-vs-new diff for every leg it touched.
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import compare_routers as cr
import compile_porter as cdr
from qiskit.converters import circuit_to_dag

RESULTS = _HERE / "paper" / "compare_results.json"
TOUCHED = ("telesabre", "dSE_shared", "sfc_shared", "sfc_shared_refined")


def main() -> None:
    rows = json.loads(RESULTS.read_text())
    by = {(r["suite"], r["circuit"]): r for r in rows}
    shutil.copy(RESULTS, RESULTS.with_suffix(".json.bak"))
    print(f"backed up -> {RESULTS.with_suffix('.json.bak')}\n", flush=True)

    changes = []
    for suite_key, spec in cr.SUITES.items():
        _, hw = cdr.hardware_for_name(spec["arch_name"])
        arch = cr.sfc_hardware_to_dsabre_architecture(hw)
        cr.verify_topology_match(hw, arch)
        hw_cfg = cr.HardwareConfig(
            deadlock_limit=None, max_backup_attempts=None, max_iterations=None
        )
        for fname in spec["files"]:
            qasm_path = spec["circuit_dir"] / fname
            cname = (fname.split("_nativegates")[0]
                     .replace(".qasm.bak", "").replace(".qasm", ""))
            rec = by.get((suite_key, cname))
            if rec is None:
                print(f"[{suite_key}q] {cname}: NOT IN RESULTS -- skipped", flush=True)
                continue
            print(f"[{suite_key}q] {cname} ...", flush=True)

            circuit, num_logical = cdr.parse_qasm2(qasm_path)
            qc, dag = cr.load_qasm(qasm_path)
            rev_dag = circuit_to_dag(qc.reverse_ops())

            t0 = time.perf_counter()
            ts = cr.run_telesabre(qasm_path, spec["device_json"])
            ts_p2v = ts.pop("initial_phys_to_virt", None) if ts else None
            new = {"telesabre": ts, "dSE_shared": None,
                   "sfc_shared": None, "sfc_shared_refined": None}

            if ts_p2v is not None:
                try:
                    new["dSE_shared"] = cr.run_dsabre_shared_layout(
                        arch, hw_cfg, dag, rev_dag, ts_p2v, num_logical)
                except ValueError as exc:
                    print(f"    dSE  (TS layout)  : skipped ({exc})", flush=True)
                new["sfc_shared"] = cr.run_sfc_shared_layout(
                    circuit, hw, num_logical, ts_p2v)
                new["sfc_shared_refined"] = cr.run_sfc_shared_layout_refined(
                    circuit, hw, num_logical, ts_p2v)
            else:
                print("    (TeleSABRE did not converge; shared-layout legs cleared)",
                      flush=True)

            for leg in TOUCHED:
                old_e = (rec.get(leg) or {}).get("epr")
                new_e = (new[leg] or {}).get("epr")
                if old_e != new_e:
                    changes.append((suite_key, cname, leg, old_e, new_e))
                rec[leg] = new[leg]
            print(f"    " + "  ".join(
                f"{leg}={(new[leg] or {}).get('epr')}" for leg in TOUCHED)
                + f"   [{time.perf_counter()-t0:.1f}s]", flush=True)

            RESULTS.write_text(json.dumps(rows, indent=2))

    print(f"\n=== {len(changes)} leg values changed ===", flush=True)
    print(f"{'suite':>6} {'circuit':<14} {'leg':<20} {'old':>8} {'new':>8}")
    for suite, circ, leg, o, n in changes:
        print(f"{suite:>6} {circ:<14} {leg:<20} {str(o):>8} {str(n):>8}")
    print(f"\nWrote {RESULTS}", flush=True)


if __name__ == "__main__":
    main()
