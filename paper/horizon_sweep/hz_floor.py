"""Analyse the weight-floor factorial (horizon_grid.jsonl) arm by arm.

Questions (Phase 6 of the instructions):
  1. does the schedule change EPR at the shipped horizon (L=16) and under the
     shipped 3-route protocol and the oracle?
  2. does a lower floor reduce horizon sensitivity (fewer local minima,
     smaller spread across L)?
  3. does it change completion / timeout incidence?
Every comparison is paired on instances completed by BOTH arms being compared.
"""
import json, math, argparse, statistics
from pathlib import Path
import hz_common as H
from hz_offline import load_jsonl, epr, best_of, oracle, density_sets, H6, load_prev

ARMS = ["base", "floor0", "floor25", "flat"]
RHO = {}
for p in ("sweep_2026-09-01_main.json", "sweep_2026-09-01_heavyhex.json"):
    for k, r in json.loads((H.HERE / p).read_text()).items():
        RHO[k] = r["rho"]


def gm(v):
    return math.exp(sum(math.log(max(x, 1)) for x in v) / len(v)) if v else float("nan")


def spread(grid, k):
    v = [epr(grid, k, L) for L in H6 if epr(grid, k, L) is not None]
    return (max(v) / min(v)) if len(v) >= 2 else None


def local_minima(grid, k):
    v = [epr(grid, k, L) for L in H6]
    v = [x for x in v if x is not None]
    return sum(1 for i in range(len(v)) if (i == 0 or v[i] < v[i-1]) and (i == len(v)-1 or v[i] < v[i+1]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default=",".join(ARMS))
    a = ap.parse_args()
    arms = a.arms.split(",")
    grids = {arm: load_jsonl(arm) for arm in arms}
    keys = [k for k in H.instance_keys() if not H.is_trivial(k)]
    groups = {
        "main25": lambda k: k.startswith("main/25"), "main64": lambda k: k.startswith("main/64"),
        "main80": lambda k: k.startswith("main/80"), "scaleup": lambda k: k.startswith("scaleup"),
        "ring": lambda k: "ring" in k, "star": lambda k: "star" in k, "all": lambda k: True,
    }

    # completeness of the data
    print("## data coverage (cells per arm over H6 x 48 instances)")
    for arm in arms:
        g = grids[arm]
        cells = sum(1 for k in H.instance_keys() for L in H6 if L in g.get(k, {}))
        st = {}
        for k in g:
            for L, c in g[k].items():
                if L in H6:
                    st[c["status"]] = st.get(c["status"], 0) + 1
        ver = sum(1 for k in g for L, c in g[k].items() if c["status"] == "completed" and c.get("verified") is not True)
        print(f"  {arm:<8} cells={cells}/288 status={st} unverified_completions={ver}")
    print()

    policies = {
        "fixed L=16": lambda k: [16],
        "fixed L=4": lambda k: [4],
        "fixed L=128": lambda k: [128],
        "shipped rule (3 routes)": lambda k: density_sets(RHO[k]),
        "global {4,16,128}": lambda k: (4, 16, 128),
        "oracle over H6": lambda k: H6,
    }
    print("## paired gmean EPR by policy: each arm vs base, on instances both complete")
    for pname, pf in policies.items():
        print(f"### {pname}")
        for gname, gf in groups.items():
            ks = [k for k in keys if gf(k)]
            row = []
            for arm in arms:
                if arm == "base":
                    continue
                pairs = []
                for k in ks:
                    b = best_of(grids["base"], k, pf(k))[0]
                    x = best_of(grids[arm], k, pf(k))[0]
                    if b is not None and x is not None:
                        pairs.append((b, x))
                if not pairs:
                    row.append(f"{arm}: n=0"); continue
                gb, gx = gm([p[0] for p in pairs]), gm([p[1] for p in pairs])
                w = sum(x < b for b, x in pairs); l = sum(x > b for b, x in pairs)
                nb = sum(1 for k in ks if best_of(grids['base'], k, pf(k))[0] is not None)
                nx = sum(1 for k in ks if best_of(grids[arm], k, pf(k))[0] is not None)
                row.append(f"{arm}: n={len(pairs)} base={gb:.1f} arm={gx:.1f} ({100*(gx/gb-1):+.1f}%) W/L={w}/{l} completes {nx} vs {nb}")
            print(f"  {gname:<8} " + " | ".join(row))
    print()
    print("## horizon sensitivity per arm (non-trivial instances with >=2 completed horizons)")
    for arm in arms:
        g = grids[arm]
        sp = [spread(g, k) for k in keys]; sp = [s for s in sp if s]
        lm = [local_minima(g, k) for k in keys if spread(g, k)]
        uni = sum(1 for x in lm if x == 1)
        best = {}
        for k in keys:
            o, oL = oracle(g, k, H6)
            if oL is not None:
                best[oL] = best.get(oL, 0) + 1
        to = sum(1 for k in keys for L in H6 if L in g.get(k, {}) and g[k][L]["status"] == "timeout")
        lv = sum(1 for k in keys for L in H6 if L in g.get(k, {}) and g[k][L]["status"] == "livelock")
        print(f"  {arm:<8} n={len(sp)} spread max/min: median {statistics.median(sp):.2f} gmean {gm(sp):.2f} | "
              f"unimodal {uni}/{len(lm)} mean minima {sum(lm)/len(lm):.2f} | best-L histogram {dict(sorted(best.items()))} | timeouts {to} livelocks {lv}")
    print()
    print("## per-horizon gmean per arm (instances completed at that L in ALL arms)")
    for L in H6:
        ks = [k for k in keys if all(epr(grids[a_], k, L) is not None for a_ in arms)]
        print(f"  L={L:<4} n={len(ks):>2} " + " ".join(f"{arm}={gm([epr(grids[arm],k,L) for k in ks]):8.1f}" for arm in arms))
    print()
    print("## per-instance oracle (best over H6) per arm")
    print(f"  {'key':<26}" + "".join(f"{arm:>16}" for arm in arms))
    for k in keys:
        cells = []
        for arm in arms:
            o, oL = oracle(grids[arm], k, H6)
            cells.append(f"{o}@{oL}" if o is not None else "-")
        print(f"  {k:<26}" + "".join(f"{c:>16}" for c in cells))
    # old-key vs new-key check on the base arm against the 2026-09-01 sweep
    prev = load_prev()
    diffs = []
    for k in H.instance_keys():
        for L in H6:
            a_, b_ = epr(prev, k, L), epr(grids["base"], k, L)
            if a_ is not None and b_ is not None and a_ != b_:
                diffs.append((k, L, a_, b_))
    print(f"\n## base arm vs 2026-09-01 sweep (old selection key): {len(diffs)} differing completed cells")
    for d in diffs[:40]:
        print("  ", d)


if __name__ == "__main__":
    main()
