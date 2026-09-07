"""Re-run every PORTER leg after the adjacent-seed relief cap was removed.

Overlays PORTER's legs onto the RELEASED selection files, leaving every
non-PORTER leg byte-identical.  Written fresh rather than reusing
``rerun_porter_legs.py``, which carries three traps documented in CLAUDE.md:
its main section short-circuits on cached rows, it builds dSABRE's candidate
layouts with the retired ``sabre_two_corner_layout``, and its scaleup and
heavyhex sections read the PRE-selection files as their base, which reverts
later legs.  Here every section reads and writes ``*_results_selection.json``
and each row is saved as soon as it is computed.

    python3 rerun_porter_uncapped.py main 25
    python3 rerun_porter_uncapped.py scaleup heavyhex
"""
import json
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repo root
sys.path.insert(0, _ROOT)

import compile_porter as cdr
import compare_routers as cr

PAPER = os.path.join(_ROOT, "paper")
MAIN = os.path.join(PAPER, "compare_results_selection.json")
SCALEUP = os.path.join(PAPER, "scaleup_results_selection.json")
HEAVYHEX = os.path.join(PAPER, "heavyhex_results_selection.json")


def _save(path, rows):
    with open(path, "w") as fh:
        json.dump(rows, fh, indent=2)


def _epr(row, leg):
    return (row.get(leg) or {}).get("epr")


def section_main(want):
    rows = json.load(open(MAIN))
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
        circuit, n = cdr.parse_qasm2(qasm)
        qc, dag = cr.load_qasm(qasm)
        arch = cr.sfc_hardware_to_dsabre_architecture(hw)
        cr.verify_topology_match(hw, arch)
        # dSABRE's OWN rule, per the 2026-08-31 decision -- not the retired
        # two-corner family rerun_porter_legs.py still calls.
        layouts = cr.dsabre_layout_candidates(qc, dag, arch, seed=0)

        t0 = time.perf_counter()
        before = _epr(row, "sfc")
        row["sfc"] = cr.run_sfc(circuit, hw, n)
        row["sfc_refined"] = cr.run_sfc_refined(circuit, hw, n)
        row["sfc_search"] = cr.run_sfc_search(circuit, hw, n)
        row["sfc_selection_and_search"] = cr.run_sfc_selection_and_search(circuit, hw, n)
        row["sfc_on_dse_layout"] = cr.run_sfc_sabre_layout(circuit, hw, n, dag, layouts)
        row["sfc_on_dse_layout_refined"] = cr.run_sfc_sabre_layout_refined(
            circuit, hw, n, dag, layouts)
        print(f"[{key}] sfc {before} -> {_epr(row,'sfc')}  +R={_epr(row,'sfc_refined')} "
              f"+S={_epr(row,'sfc_search')} onDSE={_epr(row,'sfc_on_dse_layout')} "
              f"[{time.perf_counter()-t0:.0f}s]", flush=True)
        _save(MAIN, rows)
    _save(MAIN, rows)


def section_scaleup():
    import bench_scaleup as bs
    rows = json.load(open(SCALEUP))
    for row in rows:
        key = f"scaleup/{row['suite']}/{row['circuit']}"
        spec = bs.SUITES[str(row["suite"])]
        _, hw = cdr.hardware_from_device_json(bs.DEVICES / f"{spec['device']}.json")
        fname = next(f for f in spec["files"] if f.startswith(row["circuit"] + "_"))
        qasm = spec["circuit_dir"] / fname
        circuit, n = cdr.parse_qasm2(qasm)
        qc, dag = cr.load_qasm(qasm)
        arch = cr.sfc_hardware_to_dsabre_architecture(hw)
        cr.verify_topology_match(hw, arch)
        layouts = cr.dsabre_layout_candidates(qc, dag, arch, seed=0)
        t0 = time.perf_counter()
        before = _epr(row, "sfc")
        row["sfc"] = cr.run_sfc(circuit, hw, n)
        row["sfc_on_dse_layout"] = cr.run_sfc_sabre_layout(circuit, hw, n, dag, layouts)
        print(f"[{key}] sfc {before} -> {_epr(row,'sfc')}  "
              f"onDSE={_epr(row,'sfc_on_dse_layout')} [{time.perf_counter()-t0:.0f}s]",
              flush=True)
        _save(SCALEUP, rows)
    _save(SCALEUP, rows)


def section_heavyhex():
    import compare_heavyhex as ch
    rows = json.load(open(HEAVYHEX))
    hw_by_topo = {}
    for topo in ("ring", "star"):
        arch = ch.build_heavy_hex_architecture(ch.NUM_CORES, topo)
        hw_by_topo[topo] = (arch, ch.dsabre_architecture_to_porter_hardware(arch))
    for row in rows:
        topo = row["topology"]
        arch, hw = hw_by_topo[topo]
        key = f"hh-{topo}/{row['circuit']}"
        cname = row["circuit"]
        qf = ch.CIRCUIT_DIR / (ch.QNN_FILE if cname == "qnn" else cname + ch.SUFFIX)
        circuit, n = cdr.parse_qasm2(qf)
        qc, dag = cr.load_qasm(qf)
        layouts = ch.sabre_locked_boundary_layout(qc, dag, arch, seed=0)
        t0 = time.perf_counter()
        before = _epr(row, "porter")
        row["porter"] = cr.run_sfc(circuit, hw, n)
        row["porter_on_dse"] = cr.run_sfc_sabre_layout(circuit, hw, n, dag, layouts)
        print(f"[{key}] porter {before} -> {_epr(row,'porter')}  "
              f"onDSE={_epr(row,'porter_on_dse')} [{time.perf_counter()-t0:.0f}s]", flush=True)
        _save(HEAVYHEX, rows)
    _save(HEAVYHEX, rows)


if __name__ == "__main__":
    args = sys.argv[1:]
    todo = [a for a in args if a in ("main", "scaleup", "heavyhex")] or \
           ["main", "scaleup", "heavyhex"]
    suites = set(a for a in args if a in cr.SUITES) or set(cr.SUITES)
    if "main" in todo:
        section_main(suites)
    if "scaleup" in todo:
        section_scaleup()
    if "heavyhex" in todo:
        section_heavyhex()
    print("done", flush=True)
