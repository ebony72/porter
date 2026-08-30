"""Does backward refinement belong ON TOP of horizon selection?

The shipped PORTER+R runs all five passes at the CONFIGURED horizon
(`run_refinement_passes(selection=False)`), so it does not contain PORTER's
own route and cannot bound it -- which is why +R loses to PORTER at 80q, on
the scale-up series and on star Multiplier.

`run_refinement_passes(selection=True)` instead selects the horizon once, on
the first forward pass, and refines from there.  Pass 1 is then exactly
PORTER's route, and since the best forward pass by EPR is returned, the
schedule can NEVER report more EPR than PORTER.  Cost: 3 horizon routes +
(P-1)=4 refinement routes = 7, against PORTER's 3 and +R's 5.

This measures that leg over the 24 main instances and writes
paper/refine_on_selection_results.json.

    python bench_refine_on_selection.py            # all suites
    python bench_refine_on_selection.py 25 64      # named suites
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import compare_routers as cr
import compile_porter as cdr

OUT = _HERE / "paper" / "refine_on_selection_results.json"
SRC = _HERE / "paper" / "compare_results_selection.json"


def run(circuit, hw, num_logical):
    """PORTER+R with the horizon selected once on the first forward pass."""
    cfg = cr.dr.RouterConfig(random_seed=0)
    t0 = time.perf_counter()
    try:
        layout = cdr.build_initial_layout(
            circuit, hw, num_logical,
            min_free_per_core=cfg.min_free_before_teleport)
        state, info = cdr.run_refinement_passes(
            hw, cfg, circuit, layout,
            passes=cr.PORTER_REFINE_PASSES, selection=True,
            pass_guard=cr._compiler_time_limit,
            pass_exceptions=(RuntimeError, ValueError, cr.CompilerTimeout),
        )
    except (RuntimeError, ValueError, cr.CompilerTimeout) as exc:
        return {"error": f"{type(exc).__name__}: {str(exc)[:140]}"}
    if state is None:
        return {"error": "first forward pass failed"}
    return dict(
        epr=state.stats.epr, swaps=state.stats.local_swap_count,
        seconds=round(time.perf_counter() - t0, 3),
        chosen_horizon=info.get("chosen_horizon"),
        chosen_pass=info.get("chosen_pass"),
        passes_run=info.get("passes_run"),
        forward_eprs=info.get("forward_eprs"),
        # routes = horizon candidates routed + refinement passes after pass 1
        routes=info.get("horizon_routes", 0) + max(0, info.get("passes_run", 1) - 1),
    )


def main() -> None:
    want = set(a for a in sys.argv[1:] if a in cr.SUITES) or set(cr.SUITES)
    rows = json.loads(SRC.read_text())
    done = {f"{r['suite']}_{r['circuit']}": r
            for r in json.loads(OUT.read_text())} if OUT.exists() else {}
    out_rows = []
    for row in rows:
        key = f"{row['suite']}_{row['circuit']}"
        rec = {"suite": row["suite"], "circuit": row["circuit"],
               "sfc": (row.get("sfc") or {}).get("epr"),
               "sfc_refined": (row.get("sfc_refined") or {}).get("epr"),
               "dSE": (row.get("dSE") or {}).get("epr")}
        if row["suite"] not in want:
            # Carry a suite we are not running over from the previous file, so
            # a named-suite run never drops rows it did not recompute.
            if key in done and done[key].get("sfc_refined_on_selection"):
                rec["sfc_refined_on_selection"] = done[key]["sfc_refined_on_selection"]
                out_rows.append(rec)
            continue
        if key in done and done[key].get("sfc_refined_on_selection"):
            rec["sfc_refined_on_selection"] = done[key]["sfc_refined_on_selection"]
            out_rows.append(rec)
            print(f"[{key}] cached", flush=True)
            continue
        spec = cr.SUITES[row["suite"]]
        _, hw = cdr.hardware_for_name(spec["arch_name"])
        fname = next(f for f in spec["files"]
                     if f.split("_nativegates")[0].replace(".qasm", "") in
                     (row["circuit"], row["circuit"] + "_OLD_DEEP")
                     or f.startswith(row["circuit"] + "_"))
        circuit, num_logical = cdr.parse_qasm2(spec["circuit_dir"] / fname)
        t0 = time.perf_counter()
        rec["sfc_refined_on_selection"] = run(circuit, hw, num_logical)
        out_rows.append(rec)
        r = rec["sfc_refined_on_selection"]
        print(f"[{key}] +R/sel={r.get('epr')} (L={r.get('chosen_horizon')}, "
              f"pass {r.get('chosen_pass')}/{r.get('passes_run')}, "
              f"{r.get('routes')} routes) | PORTER={rec['sfc']} "
              f"+R={rec['sfc_refined']} dSE={rec['dSE']}  "
              f"[{time.perf_counter()-t0:.0f}s]", flush=True)
        OUT.write_text(json.dumps(out_rows, indent=2))
    OUT.write_text(json.dumps(out_rows, indent=2))
    print(f"\nwrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
