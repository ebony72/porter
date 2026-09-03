"""A single fixed horizon set, chosen without the density branch.

The rho branch is the one fitted quantity in PORTER's own protocol that has no
justification beyond the corpus it was fitted on.  A single set applied to
every circuit removes it.  Three routes were not enough (measured: the best
three-set is +0.3% against the branch and 1.31x its time); four might be.

Stage 1 measures every horizon in {4,8,16,32,48,64,128} at the shipped weight
schedule on all 48 instances, under HEAD's router.
Stage 2 enumerates every 4-subset and scores it, budgeting each candidate the
way the protocol does, on the main suite and on all 48.
Stage 3 runs PORTER+R over the chosen set (select on pass 1 among four, refine
at the winner: 4 + P - 1 = 8 routes).
"""
import json, time, argparse, math, itertools
import multiprocessing as mp
import hz_head as H

OUT = H.HERE / "four_horizon_cells.jsonl"
OUT_R = H.HERE / "four_horizon_refined.jsonl"
HORIZONS = (4, 8, 16, 32, 48, 64, 128)
GUARD = 300
PASSES = 5


def cell(task):
    key, L = task
    hw, gates, n = H.load(key)
    cfg = H.porter.RouterConfig(dag_extended_max_layers=L)
    lay = H.cp.build_initial_layout(gates, hw, n, min_free_per_core=cfg.min_free_before_teleport)
    t0 = time.perf_counter()
    try:
        with H.cp._horizon_time_limit(GUARD):
            st, _ = H.cp.route(hw, cfg, list(gates), lay, selection=False)
        r = {"epr": st.stats.epr, "status": "completed"}
    except Exception as e:                                    # noqa: BLE001
        r = {"epr": None, "status": type(e).__name__}
    r.update(key=key, L=L, seconds=round(time.perf_counter() - t0, 3))
    return r


def refined(task):
    key, horizons = task
    hw, gates, n = H.load(key)
    cfg = H.porter.RouterConfig()
    lay = H.cp.build_initial_layout(gates, hw, n, min_free_per_core=cfg.min_free_before_teleport)
    t0 = time.perf_counter()
    try:
        st, info = H.cp.run_refinement_passes(hw, cfg, list(gates), lay, passes=PASSES,
                                              horizons=tuple(horizons), selection=True)
        r = {"epr": st.stats.epr if st else None, "status": "completed" if st else "failed",
             "routes": info.get("routes"), "forward_eprs": info.get("forward_eprs")}
    except Exception as e:                                    # noqa: BLE001
        r = {"epr": None, "status": type(e).__name__}
    r.update(key=key, horizons=list(horizons), seconds=round(time.perf_counter() - t0, 2))
    return r


def load_cells():
    cells = {}
    if OUT.exists():
        for l in OUT.read_text().splitlines():
            if l.strip():
                r = json.loads(l); cells.setdefault(r["key"], {})[r["L"]] = r
    # reuse w=0.5 cells already measured for the portfolio study
    p = H.HERE / "portfolio_head.jsonl"
    if p.exists():
        for l in p.read_text().splitlines():
            if not l.strip():
                continue
            r = json.loads(l)
            for L in (4, 16, 128):
                c = r["cells"].get(f"0.5@{L}")
                if c and L not in cells.get(r["key"], {}):
                    cells.setdefault(r["key"], {})[L] = {
                        "epr": c["epr"], "status": c["status"], "seconds": c["seconds"]}
    return cells


def score(cells, keys, sub, budget=True):
    """Best EPR within `sub`, with each non-default candidate capped the way the
    protocol caps it: max(5, 4x the configured horizon's own time)."""
    eprs, secs = [], 0.0
    for k in keys:
        c = cells.get(k, {})
        first = c.get(16)
        if not first or first["status"] != "completed":
            continue
        best = first["epr"]; secs += first["seconds"]
        for L in sub:
            if L == 16:
                continue
            x = c.get(L)
            if not x:
                continue
            cap = max(5.0, 4.0 * first["seconds"]) if budget else float("inf")
            secs += min(x["seconds"], cap)
            if x["status"] == "completed" and x["seconds"] <= cap and x["epr"] < best:
                best = x["epr"]
        eprs.append(best)
    return eprs, secs


def gm(v):
    return math.exp(sum(math.log(max(x, 1)) for x in v) / len(v)) if v else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["cells", "pick", "refine"], default="cells")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--set", default="")
    a = ap.parse_args()

    if a.stage == "cells":
        have = load_cells()
        tasks = [(k, L) for k in H.instance_keys() for L in HORIZONS
                 if L not in have.get(k, {})]
        print(f"{len(tasks)} cells to measure", flush=True)
        with mp.get_context("spawn").Pool(a.workers) as pool, OUT.open("a") as f:
            for i, r in enumerate(pool.imap_unordered(cell, tasks), 1):
                f.write(json.dumps(r) + "\n"); f.flush()
                if i % 20 == 0:
                    print(f"  [{i}/{len(tasks)}] {r['key']} L={r['L']}", flush=True)
        print("CELLS DONE", flush=True)

    elif a.stage == "pick":
        cells = load_cells()
        main24 = [k for k in H.instance_keys() if k.startswith("main/")]
        all48 = H.instance_keys()
        rho = {k: H.cp.select_horizons(*H.load(k)[1:])[0] for k in all48}
        be, bs = score(cells, main24, None or [], budget=True)   # placeholder
        # the shipped branch, evaluated the same way
        br_e, br_s = [], 0.0
        for k in main24:
            e, s = score(cells, [k], rho[k])
            br_e += e; br_s += s
        print(f"  shipped rho branch, main 24: gmean {gm(br_e):.1f}, {br_s:.1f}s\n")
        rows = []
        for sub in itertools.combinations(HORIZONS, 4):
            if 16 not in sub:
                continue                      # the configured horizon must compete
            e, s = score(cells, main24, sub)
            if len(e) != len(main24):
                continue
            rows.append((gm(e), s, sub))
        rows.sort()
        print(f"  {'four-value set':<24}{'gmean':>9}{'vs branch':>11}{'time':>9}{'vs branch':>11}")
        for g, s, sub in rows[:8]:
            print(f"  {str(sub):<24}{g:>9.1f}{100*(g/gm(br_e)-1):>10.1f}%{s:>8.1f}s{s/br_s:>10.2f}x")
        print("\n  the same sets over all 48 instances:")
        for g, s, sub in rows[:5]:
            e2, s2 = score(cells, all48, sub)
            br2 = []
            t2 = 0.0
            for k in all48:
                e, ss = score(cells, [k], rho[k]); br2 += e; t2 += ss
            print(f"  {str(sub):<24}{gm(e2):>9.1f}{100*(gm(e2)/gm(br2)-1):>10.1f}%{s2:>8.1f}s{s2/t2:>10.2f}x")

    else:
        sub = tuple(int(x) for x in a.set.split(","))
        keys = [k for k in H.instance_keys() if k.startswith("main/")]
        done = set()
        if OUT_R.exists():
            done = {json.loads(l)["key"] for l in OUT_R.read_text().splitlines()
                    if l.strip() and json.loads(l)["horizons"] == list(sub)}
        tasks = [(k, sub) for k in keys if k not in done]
        print(f"{len(tasks)} instances, +R over {sub}", flush=True)
        with mp.get_context("spawn").Pool(a.workers) as pool, OUT_R.open("a") as f:
            for i, r in enumerate(pool.imap_unordered(refined, tasks), 1):
                f.write(json.dumps(r) + "\n"); f.flush()
                print(f"  [{i}/{len(tasks)}] {r['key']:<26} +R={r['epr']} "
                      f"routes={r.get('routes')} [{r['seconds']}s]", flush=True)
        print("REFINE DONE", flush=True)


if __name__ == "__main__":
    main()
