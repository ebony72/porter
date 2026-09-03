"""Re-measure the 3x3 portfolio's cost against HEAD's router.

The EPR side of the portfolio decision was settled on the frozen grid; its cost
was not, because that grid predates the stall guard and the collector fix, and
the guard alone took 1.58x out of the shipped protocol.  A frozen route in the
portfolio now aborts in seconds instead of burning a 300 s share, and the
portfolio is exactly where frozen routes concentrate, so the 1.98x figure has
to be re-derived rather than assumed.

Routes each instance at all nine (schedule, horizon) pairs of
{4,16,128} x w_min {0.5, 0.25, 0} under HEAD's router, records EPR and wall
time per cell, and compares the portfolio's EPR and total time with the shipped
three-route protocol measured the same way, in the same process, on the same
machine.
"""
import json, time, argparse, math
import multiprocessing as mp
import hz_head as H

OUT = H.HERE / "portfolio_head.jsonl"
HORIZONS = (4, 16, 128)
FLOORS = (0.5, 0.25, 0.0)
GUARD = 300


def one(key):
    hw, gates, n = H.load(key)
    rec = {"key": key, "cells": {}}
    for w in FLOORS:
        for L in HORIZONS:
            cfg = H.porter.RouterConfig(dag_extended_max_layers=L,
                                        teleport_lookahead_weight_floor=w)
            lay = H.cp.build_initial_layout(gates, hw, n,
                                            min_free_per_core=cfg.min_free_before_teleport)
            t0 = time.perf_counter()
            try:
                with H.cp._horizon_time_limit(GUARD):
                    st, _ = H.cp.route(hw, cfg, list(gates), lay, selection=False)
                epr, status = st.stats.epr, "completed"
            except Exception as e:                              # noqa: BLE001
                epr, status = None, type(e).__name__
            rec["cells"][f"{w}@{L}"] = {"epr": epr, "status": status,
                                        "seconds": round(time.perf_counter() - t0, 2)}
    # the shipped protocol, same process and machine
    cfg = H.porter.RouterConfig()
    lay = H.cp.build_initial_layout(gates, hw, n, min_free_per_core=cfg.min_free_before_teleport)
    t0 = time.perf_counter()
    try:
        st, info = H.cp.route(hw, cfg, list(gates), lay, selection=True)
        rec["shipped"] = {"epr": st.stats.epr, "seconds": round(time.perf_counter() - t0, 2),
                          "horizon": info.get("chosen_horizon")}
    except Exception as e:                                      # noqa: BLE001
        rec["shipped"] = {"epr": None, "status": type(e).__name__,
                          "seconds": round(time.perf_counter() - t0, 2)}
    return rec


def report(rows):
    def gm(v):
        return math.exp(sum(math.log(max(x, 1)) for x in v) / len(v))
    nt = [r for r in rows if not H.is_trivial(r["key"])]
    ship = [r["shipped"]["epr"] for r in nt if r["shipped"]["epr"]]
    port, t_port, t_ship, worse = [], 0.0, 0.0, []
    for r in nt:
        vals = [c["epr"] for c in r["cells"].values() if c["epr"]]
        if not vals or not r["shipped"]["epr"]:
            continue
        port.append(min(vals))
        t_port += sum(c["seconds"] for c in r["cells"].values())
        t_ship += r["shipped"]["seconds"]
        if min(vals) > r["shipped"]["epr"]:
            worse.append((r["key"], r["shipped"]["epr"], min(vals)))
    print(f"\n## 3x3 portfolio vs the shipped 3-route protocol, HEAD's router, {len(port)} instances")
    print(f"  shipped   gmean {gm(ship):7.1f}   total {t_ship:8.1f}s")
    print(f"  portfolio gmean {gm(port):7.1f}   total {t_port:8.1f}s   "
          f"({100*(gm(port)/gm(ship)-1):+.1f}% EPR, {t_port/max(t_ship,1e-9):.2f}x time)")
    print(f"  instances the portfolio is worse on: {len(worse)}")
    for k, a, b in worse:
        print(f"    {k:<26} shipped {a} -> portfolio {b}")
    fails = [(r["key"], k) for r in nt for k, c in r["cells"].items() if c["epr"] is None]
    print(f"  cells that did not complete: {len(fails)} of {9*len(nt)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--report-only", action="store_true")
    a = ap.parse_args()
    if not a.report_only:
        done = set()
        if OUT.exists():
            done = {json.loads(l)["key"] for l in OUT.read_text().splitlines() if l.strip()}
        keys = [k for k in H.instance_keys() if k not in done]
        print(f"{len(keys)} instances x 10 routes", flush=True)
        with mp.get_context("spawn").Pool(a.workers) as pool, OUT.open("a") as f:
            for i, r in enumerate(pool.imap_unordered(one, keys), 1):
                f.write(json.dumps(r) + "\n"); f.flush()
                best = min([c["epr"] for c in r["cells"].values() if c["epr"]], default=None)
                print(f"[{i}/{len(keys)}] {r['key']:<26} shipped={r['shipped']['epr']} "
                      f"portfolio={best} "
                      f"({sum(c['seconds'] for c in r['cells'].values()):.0f}s vs "
                      f"{r['shipped']['seconds']:.0f}s)", flush=True)
        print("PORTFOLIO RUN DONE", flush=True)
    report([json.loads(l) for l in OUT.read_text().splitlines() if l.strip()])


if __name__ == "__main__":
    main()
