"""Re-run every PORTER+R leg after refinement was stacked on horizon selection.

`compile_porter.run_refinement_passes` defaults to ``selection=True`` since
2026-08-31: the horizon is chosen once on the first forward pass and held for
the rest of the schedule, so pass 1 IS PORTER's own selected route and the
best-forward-pass rule makes PORTER+R incapable of reporting more EPR than
PORTER.  Every `*_refined` leg therefore has to be recomputed.

`run_layout_search` stacks the same way (its phase 2 calls
`run_refinement_passes`), so the `search` section re-runs PORTER+S and
PORTER+SR as well.  Legs that do NOT change and are carried over untouched:
every dSABRE and TeleSABRE leg, and every single-pass PORTER leg.

    python rerun_refined_legs.py              # every section
    python rerun_refined_legs.py main         # main suite only
    python rerun_refined_legs.py scaleup heavyhex
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent   # repo root
sys.path.insert(0, str(_ROOT))

import compare_routers as cr
import compile_porter as cdr

PAPER = _ROOT / "paper"


def _circuit_of(row):
    spec = cr.SUITES[row["suite"]]
    _, hw = cdr.hardware_for_name(spec["arch_name"])
    fname = next(f for f in spec["files"]
                 if f.split("_nativegates")[0].replace(".qasm", "") in
                 (row["circuit"], row["circuit"] + "_OLD_DEEP")
                 or f.startswith(row["circuit"] + "_"))
    qasm = spec["circuit_dir"] / fname
    circuit, num_logical = cdr.parse_qasm2(qasm)
    return circuit, hw, num_logical, qasm


def section_main() -> None:
    """sfc_refined, sfc_on_dse_layout_refined, sfc_shared_refined,
    sfc_pytket_refined -- the four refined legs of the main suite."""
    out = PAPER / "compare_results_selection.json"
    rows = json.loads(out.read_text())
    shared = json.loads((PAPER / "shared_layouts.json").read_text())
    pyt = json.loads((PAPER / "pytket_placements.json").read_text())
    for row in rows:
        key = f"{row['suite']}_{row['circuit']}"
        circuit, hw, num_logical, qasm = _circuit_of(row)
        qc, dag = cr.load_qasm(qasm)
        arch = cr.sfc_hardware_to_dsabre_architecture(hw)
        cr.verify_topology_match(hw, arch)
        t0 = time.perf_counter()
        old = {k: (row.get(k) or {}).get("epr") for k in
               ("sfc_refined", "sfc_on_dse_layout_refined",
                "sfc_shared_refined", "sfc_pytket_refined")}

        row["sfc_refined"] = cr.run_sfc_refined(circuit, hw, num_logical)
        layouts = cr.dsabre_layout_candidates(qc, dag, arch, seed=0)
        row["sfc_on_dse_layout_refined"] = cr.run_sfc_sabre_layout_refined(
            circuit, hw, num_logical, dag, layouts)

        ent = shared.get(key)
        if ent and ent.get("phys_to_virt") and ent.get("reproduces"):
            row["sfc_shared_refined"] = cr.run_sfc_shared_layout_refined(
                circuit, hw, num_logical, ent["phys_to_virt"])
        ent = pyt.get(key)
        if ent and ent.get("placement") and ent.get("reproduces"):
            try:
                row["sfc_pytket_refined"] = cr.run_sfc_pytket_layout_refined(
                    circuit, hw, num_logical, dag, arch,
                    {int(k): v for k, v in ent["placement"].items()},
                    set(ent["corner_nodes"]))
            except (RuntimeError, ValueError) as exc:
                print(f"[{key}] pytket refined FAILED: {type(exc).__name__}",
                      flush=True)
        g = lambda k: (row.get(k) or {}).get("epr")
        print(f"[{key}] +R {old['sfc_refined']}->{g('sfc_refined')} "
              f"onDSE+R {old['sfc_on_dse_layout_refined']}->{g('sfc_on_dse_layout_refined')} "
              f"shared+R {old['sfc_shared_refined']}->{g('sfc_shared_refined')} "
              f"pytket+R {old['sfc_pytket_refined']}->{g('sfc_pytket_refined')} "
              f"| PORTER={g('sfc')} dSE={g('dSE')}  [{time.perf_counter()-t0:.0f}s]",
              flush=True)
        out.write_text(json.dumps(rows, indent=2))
    out.write_text(json.dumps(rows, indent=2))
    print(f"\nwrote {out}", flush=True)


def section_scaleup() -> None:
    """SKIPPED since 2026-08-31.

    Table V (`tab:scaleup`) reports each compiler under its own layout and
    own protocol only: the PORTER+R columns and the PORTER-on-dSABRE-layout
    control were removed, so no refined scale-up leg appears in the paper.
    PORTER+R / +S / +SR are measured on the main suite alone.  The columns
    the table still shows (`dSE`, `sfc`) do not involve refinement and are
    unaffected by stacking, so nothing here needs recomputing.
    """
    print("scaleup: skipped -- tab:scaleup carries no refined column", flush=True)
    return


def _section_scaleup_unused() -> None:
    import bench_scaleup as bs
    out = PAPER / "scaleup_results_selection.json"
    rows = json.loads(out.read_text())
    for row in rows:
        spec = bs.SUITES[row["suite"]]
        _, hw = cdr.hardware_from_device_json(
            _ROOT.parent / "other" / "telesabre" / "devices" / f"{spec['device']}.json")
        fname = next(f for f in spec["files"] if f.startswith(row["circuit"] + "_"))
        qasm = spec["circuit_dir"] / fname
        circuit, num_logical = cdr.parse_qasm2(qasm)
        qc, dag = cr.load_qasm(qasm)
        arch = cr.sfc_hardware_to_dsabre_architecture(hw)
        cr.verify_topology_match(hw, arch)
        t0 = time.perf_counter()
        old = {k: (row.get(k) or {}).get("epr")
               for k in ("sfc_refined", "sfc_on_dse_layout_refined")}
        row["sfc_refined"] = cr.run_sfc_refined(circuit, hw, num_logical)
        layouts = cr.dsabre_layout_candidates(qc, dag, arch, seed=0)
        row["sfc_on_dse_layout_refined"] = cr.run_sfc_sabre_layout_refined(
            circuit, hw, num_logical, dag, layouts)
        g = lambda k: (row.get(k) or {}).get("epr")
        print(f"[{row['suite']} {row['circuit']}] +R {old['sfc_refined']}->{g('sfc_refined')} "
              f"onDSE+R {old['sfc_on_dse_layout_refined']}->{g('sfc_on_dse_layout_refined')} "
              f"| PORTER={g('sfc')} dSE={g('dSE')}  [{time.perf_counter()-t0:.0f}s]", flush=True)
        out.write_text(json.dumps(rows, indent=2))
    out.write_text(json.dumps(rows, indent=2))
    print(f"\nwrote {out}", flush=True)


def section_heavyhex() -> None:
    import compare_heavyhex as ch
    out = PAPER / "heavyhex_results_selection.json"
    rows = json.loads(out.read_text())
    hw_by_topo = {}
    for row in rows:
        topo = row["topology"]
        if topo not in hw_by_topo:
            arch = ch.build_heavy_hex_architecture(ch.NUM_CORES, topo)
            hw = ch.dsabre_architecture_to_porter_hardware(arch)
            cr.verify_topology_match(hw, arch)
            hw_by_topo[topo] = (arch, hw)
        arch, hw = hw_by_topo[topo]
        cname = row["circuit"]
        qf = ch.CIRCUIT_DIR / (ch.QNN_FILE if cname == "qnn" else cname + ch.SUFFIX)
        circuit, num_logical = cdr.parse_qasm2(qf)
        qc, dag = cr.load_qasm(qf)
        layouts = ch.sabre_locked_boundary_layout(qc, dag, arch, seed=0)
        cfg = cr.dr.RouterConfig(random_seed=0)
        t0 = time.perf_counter()
        old = {k: (row.get(k) or {}).get("epr")
               for k in ("porter_refined", "porter_on_dse_refined")}
        try:
            state, info = cdr.run_refinement_passes(
                hw, cfg, circuit,
                cdr.build_initial_layout(circuit, hw, num_logical,
                                         min_free_per_core=cfg.min_free_before_teleport),
                passes=cr.PORTER_REFINE_PASSES,
                pass_guard=cr._compiler_time_limit,
                pass_exceptions=(RuntimeError, ValueError, cr.CompilerTimeout))
            row["porter_refined"] = (
                {"error": "first forward pass failed"} if state is None else
                dict(epr=state.stats.epr, swaps=state.stats.local_swap_count,
                     teleports=state.stats.teleport_count,
                     telegates=state.stats.telegate_count,
                     packets=state.stats.telegate_packet_count,
                     depth=state.stats.depth,
                     chosen_horizon=info.get("chosen_horizon"),
                     chosen_pass=info.get("chosen_pass"),
                     seconds=round(time.perf_counter() - t0, 3)))
        except (RuntimeError, ValueError, cr.CompilerTimeout) as exc:
            row["porter_refined"] = {"error": f"{type(exc).__name__}: {str(exc)[:120]}"}
        row["porter_on_dse_refined"] = cr.run_sfc_sabre_layout_refined(
            circuit, hw, num_logical, dag, layouts)
        g = lambda k: (row.get(k) or {}).get("epr")
        print(f"[{topo} {cname}] +R {old['porter_refined']}->{g('porter_refined')} "
              f"onDSE+R {old['porter_on_dse_refined']}->{g('porter_on_dse_refined')} "
              f"| PORTER={g('porter')} dSE={g('dSE')}  [{time.perf_counter()-t0:.0f}s]", flush=True)
        out.write_text(json.dumps(rows, indent=2))
    out.write_text(json.dumps(rows, indent=2))
    print(f"\nwrote {out}", flush=True)


def section_search() -> None:
    """sfc_search (PORTER+S) and sfc_selection_and_search (PORTER+SR).

    `run_layout_search` phase 2 now selects a horizon too, and its seed list
    always contains the gamma=0.99 layout -- which IS `build_initial_layout`'s
    default -- so PORTER+S now contains PORTER's own selected route and cannot
    report more EPR than it.  PORTER+SR, the better of selection and this
    search, therefore can no longer differ from PORTER+S; this section
    re-measures both so that redundancy is a measurement, not an inference.
    """
    out = PAPER / "compare_results_selection.json"
    rows = json.loads(out.read_text())
    for row in rows:
        key = f"{row['suite']}_{row['circuit']}"
        circuit, hw, num_logical, _ = _circuit_of(row)
        t0 = time.perf_counter()
        old = {k: (row.get(k) or {}).get("epr")
               for k in ("sfc_search", "sfc_selection_and_search")}
        row["sfc_search"] = cr.run_sfc_search(circuit, hw, num_logical)
        row["sfc_selection_and_search"] = cr.run_sfc_selection_and_search(
            circuit, hw, num_logical)
        g = lambda k: (row.get(k) or {}).get("epr")
        print(f"[{key}] +S {old['sfc_search']}->{g('sfc_search')} "
              f"(routes={(row.get('sfc_search') or {}).get('routes')}) "
              f"+SR {old['sfc_selection_and_search']}->{g('sfc_selection_and_search')} "
              f"({(row.get('sfc_selection_and_search') or {}).get('chosen_schedule')}) "
              f"| PORTER={g('sfc')} +R={g('sfc_refined')} dSE={g('dSE')}  "
              f"[{time.perf_counter()-t0:.0f}s]", flush=True)
        out.write_text(json.dumps(rows, indent=2))
    out.write_text(json.dumps(rows, indent=2))
    print(f"\nwrote {out}", flush=True)


SECTIONS = {"main": section_main, "scaleup": section_scaleup,
            "heavyhex": section_heavyhex, "search": section_search}

if __name__ == "__main__":
    want = [a for a in sys.argv[1:] if a in SECTIONS] or list(SECTIONS)
    for name in want:
        print(f"===== {name} =====", flush=True)
        SECTIONS[name]()
