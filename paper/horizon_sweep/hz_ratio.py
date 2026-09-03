"""A runtime test for 'is a deeper horizon worth a route?'

The scorer's lookahead term is a sum whose magnitude grows with the horizon,
while the direct term does not, so deepening re-weights the objective as well
as widening it.  How far that has already gone at the configured horizon is
measurable during the route the protocol runs first anyway: this records, over
every scored teleport candidate, the ratio of |lookahead_gain| to
|direct_gain|, plus how often dropping the lookahead term would change which
plan wins.

Both are joined with the measured EPR(L) curve, so a gate on them can be
evaluated the way a static feature would be.

Usage:  python3 paper/horizon_sweep/hz_ratio.py [--L 16]
"""
import argparse, json, statistics, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hz_common as hc                                     # noqa: E402
import porter                                              # noqa: E402
import compile_porter as cp                                # noqa: E402

GUARD = 300


def probe(hw, gates, n, L):
    cfg = porter.RouterConfig(dag_extended_max_layers=L)
    lay = cp.build_initial_layout(gates, hw, n,
                                  min_free_per_core=cfg.min_free_before_teleport)
    R = porter.PorterRouter(hw, cfg)
    la, di, flips, decisions, ncoll = [], [], 0, 0, []
    orig_choose = R._choose_best_remote_plan
    orig_collect = R._collect_teleport_post_latent_lookahead_gates

    def choose(plans, state, info, mf):
        nonlocal flips, decisions
        best, scored = orig_choose(plans, state, info, mf)
        tele = [s for s in scored if s[1].kind == "teleport"]
        if tele:
            for _, _, sc in tele:
                la.append(abs(sc.lookahead_gain)); di.append(abs(sc.direct_gain))
            with_la = min(scored, key=lambda t: (-t[0], t[2].prep))[1]
            without = min(scored, key=lambda t: (-t[2].direct_gain, t[2].prep))[1]
            flips += (with_la is not without); decisions += 1
        return best, scored

    def collect(*a, **k):
        out = orig_collect(*a, **k); ncoll.append(len(out)); return out

    R._choose_best_remote_plan = choose
    R._collect_teleport_post_latent_lookahead_gates = collect
    t0 = time.perf_counter()
    status, epr = "completed", None
    try:
        with cp._horizon_time_limit(GUARD):
            st = R.compile(list(gates), lay)
        epr = st.stats.epr
    except cp.HorizonTimeout:
        status = "timeout"
    except RuntimeError:
        status = "stalled"
    except Exception as e:                                   # noqa: BLE001
        status = f"error:{type(e).__name__}"
    mla = statistics.mean(la) if la else 0.0
    mdi = statistics.mean(di) if di else 0.0
    return {"L": L, "status": status, "epr": epr,
            "seconds": round(time.perf_counter() - t0, 2),
            "candidates": len(la), "decisions": decisions,
            "mean_abs_lookahead": round(mla, 4),
            "mean_abs_direct": round(mdi, 4),
            "domination": round(mla / mdi, 4) if mdi else None,
            "flip_rate": round(flips / decisions, 4) if decisions else None,
            "mean_collected": round(statistics.mean(ncoll), 3) if ncoll else 0.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--L", type=int, default=16)
    ap.add_argument("--out", default=str(HERE / "domination.jsonl"))
    args = ap.parse_args()
    out = Path(args.out)
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            if line.strip():
                r = json.loads(line); done.add((r["key"], r["L"]))
    fh = out.open("a")
    for key in hc.instance_keys():
        if (key, args.L) in done:
            continue
        hw, gates, n = hc.load(key)
        rec = {"key": key, "n": n}
        rec.update(probe(hw, gates, n, args.L))
        fh.write(json.dumps(rec) + "\n"); fh.flush()
        print(f"{key:28s} L={args.L:4d} {rec['status']:9s} "
              f"dom={rec['domination']} flip={rec['flip_rate']} "
              f"coll={rec['mean_collected']}", flush=True)
    fh.close()


if __name__ == "__main__":
    main()
