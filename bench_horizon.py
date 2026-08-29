"""Best-of-3 teleport-lookahead-horizon selection across the whole benchmark.

PORTER's `dag_extended_max_layers` (how many DAG layers the teleport-benefit
lookahead peels; see `compile_porter.run_horizon_selection`) ships at 16.
That value is well tuned for the 25q/64q suites but far too short above ~64
logical qubits and too long for near-all-to-all interaction graphs.  This
harness runs `run_horizon_selection` over PORTER_HORIZONS on every instance
the paper uses -- 24 main + 6 scale-up + 18 heavy-hex = 48 -- keeps the best
by EPR, replay-verifies the winning stream, and reports against the baselines
already recorded in paper/{compare,scaleup,heavyhex}_results.json.

Nothing here mutates those files; output goes to paper/horizon_results.json.

    python bench_horizon.py                # everything
    python bench_horizon.py main scaleup   # named sections only
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import porter as dr
import compile_porter as cdr
import verify_porter as vp
from compile_porter import PORTER_HORIZONS, run_horizon_selection

OUT = _HERE / "paper" / "horizon_results.json"
TELESABRE = _HERE.parent / "other" / "telesabre"


def gmean(v):
    v = [x for x in v if x]
    return math.exp(sum(math.log(x) for x in v) / len(v)) if v else float("nan")


def _run(tag, hw, circuit, num_logical, baselines):
    """Route `circuit` at every horizon, keep the best, replay-verify it."""
    cfg = dr.RouterConfig(random_seed=0)
    t0 = time.perf_counter()
    layout = cdr.build_initial_layout(
        circuit, hw, num_logical, min_free_per_core=cfg.min_free_before_teleport)
    layout_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    state, info = run_horizon_selection(hw, cfg, circuit, layout)
    route_s = time.perf_counter() - t0

    rec = dict(baselines)
    rec.update(horizon_eprs={str(k): v for k, v in info["horizon_eprs"].items()},
               horizon_seconds={str(k): v for k, v in info["horizon_seconds"].items()},
               default_horizon=info["default_horizon"],
               interaction_density=info.get("interaction_density"),
               horizons_requested=info["horizons_requested"],
               failed_horizons=info["failed_horizons"],
               chosen_horizon=info["chosen_horizon"],
               layout_seconds=round(layout_s, 3),
               seconds=round(layout_s + route_s, 3))
    if state is None:
        rec.update(epr=None, error="every horizon failed")
        print(f"  {tag:>22}  ALL HORIZONS FAILED {info['failed_horizons']}", flush=True)
        return rec

    # Every horizon starts from the same layout, so the winning stream replays
    # against exactly the layout that was passed in -- no start_layout to thread.
    try:
        vp.verify_state(hw, layout, circuit, state)
        verified = True
    except Exception as exc:                                  # noqa: BLE001
        verified = False
        rec["verify_error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
    rec.update(epr=state.stats.epr, swaps=state.stats.local_swap_count,
               teleports=state.stats.teleport_count,
               telegates=state.stats.telegate_count,
               packets=state.stats.telegate_packet_count,
               depth=state.stats.depth, verified=verified)

    base = rec.get("sfc")
    delta = f"{100 * (rec['epr'] - base) / base:+6.1f}%" if base else "     --"
    print(f"  {tag:>22}  best={rec['epr']:>6} @L={rec['chosen_horizon']:<4} "
          f"d={rec['interaction_density']} {dict(info['horizon_eprs'])}  vs sfc={base} {delta}  "
          f"{'ok' if verified else 'VERIFY FAILED'}  {rec['seconds']}s", flush=True)
    return rec


def section_main(out):
    import compare_routers as cr
    prev = {f"{r['suite']}_{r['circuit']}": r
            for r in json.load(open(_HERE / "paper" / "compare_results.json"))}
    for key, spec in cr.SUITES.items():
        _, hw = cdr.hardware_for_name(spec["arch_name"])
        print(f"\n=== main {key}q ({spec['arch_name']}) ===", flush=True)
        for fname in spec["files"]:
            cname = (fname.split("_nativegates")[0]
                     .replace(".qasm.bak", "").replace(".qasm", ""))
            cname = "qnn" if cname.startswith("qnn") else cname
            circuit, n = cdr.parse_qasm2(spec["circuit_dir"] / fname)
            b = prev.get(f"{key}_{cname}", {})
            base = {k: (b.get(k) or {}).get("epr")
                    for k in ("dSE", "telesabre", "sfc", "sfc_refined", "sfc_search")}
            out[f"main/{key}/{cname}"] = _run(f"{key}q {cname}", hw, circuit, n, base)
            json.dump(out, open(OUT, "w"), indent=1)


def section_scaleup(out):
    import bench_scaleup as bs
    prev = {f"{r['suite']}_{r['circuit']}": r
            for r in json.load(open(_HERE / "paper" / "scaleup_results.json"))}
    for key, spec in bs.SUITES.items():
        _, hw = cdr.hardware_from_device_json(
            _HERE.parent / "other" / "telesabre" / "devices" / f"{spec['device']}.json")
        print(f"\n=== scaleup {key}q ({len(hw.cores)} cores, "
              f"{len(hw.phys_to_core)} physical) ===", flush=True)
        for fname in spec["files"]:
            cname = fname.split("_nativegates")[0]
            circuit, n = cdr.parse_qasm2(spec["circuit_dir"] / fname)
            b = prev.get(f"{key}_{cname}", {})
            base = {k: (b.get(k) or {}).get("epr")
                    for k in ("dSE", "sfc", "sfc_refined", "sfc_on_dse_layout")}
            out[f"scaleup/{key}/{cname}"] = _run(f"{key}q {cname}", hw, circuit, n, base)
            json.dump(out, open(OUT, "w"), indent=1)


def section_heavyhex(out):
    import compare_heavyhex as ch
    prev = {f"{r['topology']}_{r['circuit']}": r
            for r in json.load(open(_HERE / "paper" / "heavyhex_results.json"))}
    for topo in ("ring", "star"):
        arch = ch.build_heavy_hex_architecture(ch.NUM_CORES, topo)
        hw = ch.dsabre_architecture_to_porter_hardware(arch)
        ch.cr.verify_topology_match(hw, arch)
        print(f"\n=== heavy-hex {topo} ===", flush=True)
        for cname in ch.CIRCUITS:
            qf = ch.CIRCUIT_DIR / (ch.QNN_FILE if cname == "qnn" else cname + ch.SUFFIX)
            circuit, n = cdr.parse_qasm2(qf)
            b = prev.get(f"{topo}_{cname}", {})
            base = {k: (b.get(k) or {}).get("epr")
                    for k in ("dSE", "porter", "porter_refined", "porter_on_dse")}
            base["sfc"] = base.pop("porter")
            out[f"heavyhex/{topo}/{cname}"] = _run(f"{topo} {cname}", hw, circuit, n, base)
            json.dump(out, open(OUT, "w"), indent=1)


def summarize(out):
    print("\n\n================ SUMMARY ================", flush=True)
    groups = {}
    for k, r in out.items():
        groups.setdefault("/".join(k.split("/")[:2]), []).append(r)
    for name, rows in sorted(groups.items()):
        ok = [r for r in rows if r.get("epr") and r.get("sfc")]
        if not ok:
            continue
        b, h = [r["sfc"] for r in ok], [r["epr"] for r in ok]
        w = sum(1 for r in ok if r["epr"] < r["sfc"])
        l = sum(1 for r in ok if r["epr"] > r["sfc"])
        line = (f"{name:>16} n={len(ok):<3} sfc={gmean(b):8.1f} -> best-of-3={gmean(h):8.1f} "
                f"({100 * (gmean(h) - gmean(b)) / gmean(b):+6.1f}%)  W/L/T={w}/{l}/{len(ok) - w - l}")
        for other in ("dSE", "sfc_refined", "sfc_search", "porter_refined"):
            vals = [(r.get(other), r["epr"]) for r in ok if r.get(other)]
            if len(vals) == len(ok):
                line += f"   {other}={gmean([v for v, _ in vals]):.1f}"
        print(line, flush=True)
    bad = [k for k, r in out.items() if r.get("epr") and not r.get("verified")]
    print(f"\nreplay-verified: {sum(1 for r in out.values() if r.get('verified'))}"
          f"/{sum(1 for r in out.values() if r.get('epr'))}"
          + (f"   FAILURES: {bad}" if bad else ""), flush=True)
    chosen = {}
    for r in out.values():
        if r.get("chosen_horizon"):
            chosen[r["chosen_horizon"]] = chosen.get(r["chosen_horizon"], 0) + 1
    sets = {}
    for r in out.values():
        key = tuple(r.get("horizons_requested") or ())
        sets[key] = sets.get(key, 0) + 1
    print(f"horizon chosen: {dict(sorted(chosen.items()))}", flush=True)
    print(f"candidate sets used: "
          f"{ {tuple(sorted(k)): v for k, v in sets.items()} }", flush=True)


if __name__ == "__main__":
    want = sys.argv[1:] or ["main", "scaleup", "heavyhex"]
    out = json.load(open(OUT)) if OUT.exists() else {}
    for name in want:
        {"main": section_main, "scaleup": section_scaleup,
         "heavyhex": section_heavyhex}[name](out)
    json.dump(out, open(OUT, "w"), indent=1)
    summarize(out)
