"""Re-run the legs that depend on dSABRE's candidate-layout set.

Until 2026-08-30 `compare_routers.dsabre_layout_candidates` handed dSABRE TWO
families of initial layouts and took its best: its own
`sabre_locked_boundary_layout` (adaptive per-core corner reservation) and
`sabre_two_corner_layout`, the same rule with the count pinned to 2.  The
second family is OURS -- added when an older dSABRE reserved four corners
chip-wide, putting all four in core 0 -- and the current adaptive rule fixes
that at source.  Benchmarking the union meant benchmarking a configuration
dSABRE does not ship, so the candidate set is now its own rule alone: three
layouts, nine routes.

Three legs consume that set and therefore change:

    dSE                        dSABRE's own protocol
    sfc_on_dse_layout          PORTER routing dSABRE's candidates
    sfc_on_dse_layout_refined  the same with backward refinement

Everything else is independent and is carried over untouched: TeleSABRE, the
shared- and pytket-layout legs (which supply their own layouts), PORTER's own
protocol, and `dSE_on_porter_layout` (which consumes PORTER's layout).

Writes the `*_results_selection.json` files in place.

    python rerun_dsabre_default_layouts.py                # every section
    python rerun_dsabre_default_layouts.py main
    python rerun_dsabre_default_layouts.py scaleup heavyhex
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent   # repo root
sys.path.insert(0, str(_ROOT.parent / "dsabre" / "code"))
sys.path.insert(0, str(_ROOT))

import compare_routers as cr          # noqa: E402
import compile_porter as cdr          # noqa: E402
from config import HardwareConfig     # noqa: E402
from qiskit.converters import circuit_to_dag  # noqa: E402


def _refresh(row, qc, dag, rev_dag, arch, hw_cfg, circuit, hw, num_logical,
             dse_key="dSE", porter_key="sfc_on_dse_layout",
             porter_refined_key="sfc_on_dse_layout_refined"):
    """Recompute the three candidate-set-dependent legs for one row."""
    t0 = time.perf_counter()
    lay_t = time.perf_counter()
    layouts = cr.dsabre_layout_candidates(qc, dag, arch, seed=0)
    lay_s = time.perf_counter() - lay_t
    row[dse_key] = cr.run_dsabre(cr.dSE, arch, hw_cfg, dag, rev_dag, layouts,
                                 layout_seconds=lay_s)
    if porter_key is not None:
        try:
            row[porter_key] = cr.run_sfc_sabre_layout(
                circuit, hw, num_logical, dag, layouts)
        except Exception as e:
            row[porter_key] = {"error": f"{type(e).__name__}: {str(e)[:140]}"}
    if porter_refined_key is not None:
        try:
            row[porter_refined_key] = cr.run_sfc_sabre_layout_refined(
                circuit, hw, num_logical, dag, layouts)
        except Exception as e:
            row[porter_refined_key] = {"error": f"{type(e).__name__}: {str(e)[:140]}"}
    return len(layouts), time.perf_counter() - t0


def section_main() -> None:
    out = _ROOT / "paper" / "compare_results_selection.json"
    rows = json.loads(out.read_text())
    for row in rows:
        suite = row["suite"]
        spec = cr.SUITES[suite]
        _, hw = cdr.hardware_for_name(spec["arch_name"])
        arch = cr.sfc_hardware_to_dsabre_architecture(hw)
        cr.verify_topology_match(hw, arch)
        # dSABRE's own budget convention: derive all three from the architecture.
        hw_cfg = HardwareConfig(deadlock_limit=None, max_backup_attempts=None,
                                max_iterations=None)
        fname = next(f for f in spec["files"]
                     if f.split("_nativegates")[0] == row["circuit"])
        qasm = spec["circuit_dir"] / fname
        circuit, num_logical = cdr.parse_qasm2(qasm)
        qc, dag = cr.load_qasm(qasm)
        rev_dag = circuit_to_dag(qc.reverse_ops())
        n, secs = _refresh(row, qc, dag, rev_dag, arch, hw_cfg,
                           circuit, hw, num_logical)
        g = lambda k: (row.get(k) or {}).get("epr")
        print(f"[{suite}q {row['circuit']}] cands={n} dSE={g('dSE')} "
              f"onDSE={g('sfc_on_dse_layout')} "
              f"onDSE+R={g('sfc_on_dse_layout_refined')}  [{secs:.0f}s]", flush=True)
        out.write_text(json.dumps(rows, indent=2))
    print(f"\nwrote {out}", flush=True)


def section_main_refined() -> None:
    """Second pass: only `sfc_on_dse_layout_refined`, whose first run tripped a
    bad keyword in this script."""
    out = _ROOT / "paper" / "compare_results_selection.json"
    rows = json.loads(out.read_text())
    for row in rows:
        spec = cr.SUITES[row["suite"]]
        _, hw = cdr.hardware_for_name(spec["arch_name"])
        arch = cr.sfc_hardware_to_dsabre_architecture(hw)
        fname = next(f for f in spec["files"]
                     if f.split("_nativegates")[0] == row["circuit"])
        qasm = spec["circuit_dir"] / fname
        circuit, num_logical = cdr.parse_qasm2(qasm)
        qc, dag = cr.load_qasm(qasm)
        layouts = cr.dsabre_layout_candidates(qc, dag, arch, seed=0)
        t0 = time.perf_counter()
        try:
            row["sfc_on_dse_layout_refined"] = cr.run_sfc_sabre_layout_refined(
                circuit, hw, num_logical, dag, layouts)
        except Exception as e:
            row["sfc_on_dse_layout_refined"] = {
                "error": f"{type(e).__name__}: {str(e)[:140]}"}
        g = (row.get("sfc_on_dse_layout_refined") or {}).get("epr")
        print(f"[{row['suite']}q {row['circuit']}] onDSE+R={g}  "
              f"[{time.perf_counter()-t0:.0f}s]", flush=True)
        out.write_text(json.dumps(rows, indent=2))
    print(f"\nwrote {out}", flush=True)


def section_scaleup() -> None:
    import bench_scaleup as bs
    from qiskit.converters import circuit_to_dag as _c2d
    out = _ROOT / "paper" / "scaleup_results_selection.json"
    rows = json.loads(out.read_text())
    for row in rows:
        spec = bs.SUITES[row["suite"]]
        _, hw = cdr.hardware_from_device_json(
            _ROOT.parent / "other" / "telesabre" / "devices" / f"{spec['device']}.json")
        arch = cr.sfc_hardware_to_dsabre_architecture(hw)
        cr.verify_topology_match(hw, arch)
        hw_cfg = HardwareConfig(deadlock_limit=None, max_backup_attempts=None,
                                max_iterations=None)
        fname = next(f for f in spec["files"]
                     if f.split("_nativegates")[0] == row["circuit"])
        qasm = spec["circuit_dir"] / fname
        circuit, num_logical = cdr.parse_qasm2(qasm)
        qc, dag = cr.load_qasm(qasm)
        rev_dag = _c2d(qc.reverse_ops())
        n, secs = _refresh(row, qc, dag, rev_dag, arch, hw_cfg,
                           circuit, hw, num_logical)
        g = lambda k: (row.get(k) or {}).get("epr")
        print(f"[{row['suite']}q {row['circuit']}] cands={n} dSE={g('dSE')} "
              f"onDSE={g('sfc_on_dse_layout')} "
              f"onDSE+R={g('sfc_on_dse_layout_refined')}  [{secs:.0f}s]", flush=True)
        out.write_text(json.dumps(rows, indent=2))
    print(f"\nwrote {out}", flush=True)


def section_heavyhex() -> None:
    print("heavy-hex is unaffected: compare_heavyhex.py calls "
          "sabre_locked_boundary_layout directly, so it never used the second "
          "candidate family.  Nothing to re-run.", flush=True)


def main() -> None:
    args = [a for a in sys.argv[1:]] or ["main"]
    for name in args:
        fn = globals().get(f"section_{name}")
        if fn is None:
            sys.exit(f"unknown section {name!r}")
        print(f"===== {name} =====", flush=True)
        fn()


if __name__ == "__main__":
    main()
