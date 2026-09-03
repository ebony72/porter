"""Does normalising the teleport lookahead term decouple horizon from weight?

The scorer sets `total = direct_gain + lookahead_gain`, where `lookahead_gain`
is a SUM over the gates the lookahead walk collects (up to
min(dag_extended_max_layers, teleport_lookahead_cx_count) of them) and
`direct_gain` counts only front and latent-direct gates.  Every core graph in
this corpus is bipartite, so each collected gate contributes +-w(layer) and,
past the weight floor, the term is a signed count whose magnitude grows roughly
linearly in the horizon.  Deepening the horizon therefore samples more of the
future AND silently re-weights the objective away from retiring gates now.

`teleport_lookahead_scaling` separates the two: `mean` divides the sum by the
weight it accumulated, `sqrt` by its square root, and
`teleport_lookahead_coefficient` then sets the weight explicitly.  `sum` with
coefficient 1.0 is the shipped scorer.

Usage:
  python3 paper/horizon_sweep/hz_scale.py --arms sqrt1 --out scale_cells.jsonl
"""
import argparse, json, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hz_common as hc                                     # noqa: E402
import porter                                              # noqa: E402
import compile_porter as cp                                # noqa: E402
import verify_porter as vp                                 # noqa: E402

ARMS = {                       # name -> (scaling, coefficient)
    "sum":    ("sum",  1.0),
    "mean1":  ("mean", 1.0),
    "mean2":  ("mean", 2.0),
    "mean4":  ("mean", 4.0),
    "sqrt1":  ("sqrt", 1.0),
    "sqrt2":  ("sqrt", 2.0),
    "sqrt4":  ("sqrt", 4.0),
}
HORIZONS = [4, 8, 16, 32, 64, 128, 256]
GUARD = 300


def route_cell(hw, gates, n, L, scaling, coef):
    cfg = porter.RouterConfig(dag_extended_max_layers=L,
                              teleport_lookahead_scaling=scaling,
                              teleport_lookahead_coefficient=coef)
    lay = cp.build_initial_layout(gates, hw, n,
                                  min_free_per_core=cfg.min_free_before_teleport)
    lay0 = lay.clone()
    rec = {"L": L, "scaling": scaling, "coefficient": coef}
    t0 = time.perf_counter()
    try:
        with cp._horizon_time_limit(GUARD):
            st, _ = cp.route(hw, cfg, list(gates), lay, selection=False)
        rec["status"] = "completed"
        rec["epr"] = st.stats.epr
        rec["stats"] = {k: v for k, v in vars(st.stats).items()
                        if isinstance(v, (int, float))}
        try:
            vp.verify_state(hw, lay0, list(gates), st)
            rec["verified"] = True
        except Exception as e:                              # noqa: BLE001
            rec["verified"] = f"FAIL:{type(e).__name__}:{str(e)[:100]}"
    except cp.HorizonTimeout:
        rec["status"], rec["epr"] = "timeout", None
    except RuntimeError as e:
        rec["status"] = "stalled" if "retired no gate" in str(e) else "livelock"
        rec["epr"] = None
        rec["error"] = str(e)[:160]
    except Exception as e:                                  # noqa: BLE001
        rec["status"], rec["epr"] = f"error:{type(e).__name__}", None
        rec["error"] = str(e)[:160]
    rec["seconds"] = round(time.perf_counter() - t0, 2)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="sqrt1", help="comma-separated names from ARMS")
    ap.add_argument("--horizons", default=",".join(map(str, HORIZONS)))
    ap.add_argument("--out", default=str(HERE / "scale_cells.jsonl"))
    args = ap.parse_args()
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    hz = [int(x) for x in args.horizons.split(",")]

    out = Path(args.out)
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                done.add((r["key"], r["L"], r["arm"]))
    fh = out.open("a")
    for key in hc.instance_keys():
        hw, gates, n = hc.load(key)
        for arm in arms:
            scaling, coef = ARMS[arm]
            for L in hz:
                if (key, L, arm) in done:
                    continue
                rec = {"key": key, "arm": arm, "n": n}
                rec.update(route_cell(hw, gates, n, L, scaling, coef))
                fh.write(json.dumps(rec) + "\n"); fh.flush()
                print(f"{key:28s} {arm:6s} L={L:4d} {rec['status']:10s} "
                      f"epr={rec['epr']} {rec['seconds']:7.1f}s", flush=True)
    fh.close()


if __name__ == "__main__":
    main()
