"""Single-set portfolios: exhaustive search over (schedule, horizon) routes.

Replaces the shipped rho-branch (dense {4,8,16} / sparse {8,16,128}) with ONE
set applied to every circuit.  A candidate route is a (schedule, horizon) pair
drawn from the 2,256-cell grid; a portfolio is a set of routes, and its result
per instance is the lowest EPR any member reaches.

Two universes are searched:
  horizon-only  -- every route at the shipped schedule (the paper's current axis)
  joint         -- any schedule x any horizon

Constraints, both defensible as shipping rules:
  * the portfolio must complete every instance;
  * optionally it must contain the configured route (base @ L=16), which is what
    makes the protocol provably no worse than routing at cfg alone.

Reported in-sample and under two grouped hold-outs (refitting the whole
portfolio inside each fold), with wall-clock cost relative to the shipped rule.
"""
import json, math, itertools, argparse
import numpy as np
import hz_common as H
from hz_offline import load_jsonl, epr, best_of, density_sets

ARMS = ["base", "floor0", "floor25", "flat", "slow95", "slow97", "slow99"]
LS = [4, 8, 16, 32, 48, 64, 128, 256]
CFG_ROUTE = ("base", 16)
DSE = {"main24": 171.9, "scaleup": 705.7, "ring": 85.2, "star": 101.1}
GROUPS = {
    "main25": lambda k: k.startswith("main/25"), "main64": lambda k: k.startswith("main/64"),
    "main80": lambda k: k.startswith("main/80"), "scaleup": lambda k: k.startswith("scaleup"),
    "ring": lambda k: "ring" in k, "star": lambda k: "star" in k,
}

RHO = {}
for p in ("sweep_2026-09-01_main.json", "sweep_2026-09-01_heavyhex.json"):
    for k, r in json.loads((H.HERE / p).read_text()).items():
        RHO[k] = r["rho"]


def build():
    g = {a: load_jsonl(a) for a in ARMS}
    keys = [k for k in H.instance_keys() if not H.is_trivial(k)]
    allk = H.instance_keys()
    routes = [(a, L) for a in ARMS for L in LS
              if any(L in g[a].get(k, {}) for k in allk)]
    # EPR matrix over the FULL 48 so any basis can be sliced; inf = no result
    idx = {k: i for i, k in enumerate(allk)}
    M = np.full((len(routes), len(allk)), np.inf)
    T = np.zeros((len(routes), len(allk)))
    for ri, (a, L) in enumerate(routes):
        for k in allk:
            c = g[a].get(k, {}).get(L)
            if c is None:
                continue
            T[ri, idx[k]] = c["seconds"]
            if c["status"] == "completed":
                M[ri, idx[k]] = c["epr"]
    ref = np.array([best_of(g["base"], k, density_sets(RHO[k]))[0] or np.inf for k in allk])
    reft = np.array([sum(g["base"][k][x]["seconds"] for x in density_sets(RHO[k])
                         if x in g["base"].get(k, {})) for k in allk])
    return g, allk, keys, idx, routes, M, T, ref, reft


def lgm(v):
    return float(np.mean(np.log(np.maximum(v, 1.0))))


def search(M, cols, pool, r, must=None, top=6):
    """Exhaustive: best subsets of size r over `pool` (indices into M)."""
    sub = M[:, cols]
    out = []
    fixed = [must] if must is not None else []
    rest = [p for p in pool if p != must]
    for combo in itertools.combinations(rest, r - len(fixed)):
        rows = fixed + list(combo)
        best = sub[rows].min(axis=0)
        if not np.isfinite(best).all():
            continue
        out.append((lgm(best), tuple(rows)))
    out.sort()
    return out[:top]


def name(routes, rows):
    return "{" + ", ".join(f"{routes[i][0]}@{routes[i][1]}" for i in rows) + "}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-r", type=int, default=5)
    a = ap.parse_args()
    g, allk, keys, idx, routes, M, T, ref, reft = build()
    nt = [idx[k] for k in keys]                       # 38 non-trivial
    base_pool = [i for i, (arm, _) in enumerate(routes) if arm == "base"]
    cfg = routes.index(CFG_ROUTE)
    ref_lgm = lgm(ref[nt])
    print(f"universe: {len(routes)} candidate routes "
          f"({len(base_pool)} at the shipped schedule); basis = {len(nt)} non-trivial instances")
    print(f"shipped rho-branch rule (3 routes): gmean {math.exp(ref_lgm):.1f}\n")

    print("## single-set portfolios, in-sample (regret-free view: gmean over the 38)")
    for label, pool in (("horizon only", base_pool), ("joint (schedule x horizon)", list(range(len(routes))))):
        for must, mlabel in ((cfg, "contains base@16"), (None, "unconstrained")):
            print(f"### {label}, {mlabel}")
            for r in range(3, a.max_r + 1):
                res = search(M, nt, pool, r, must=must, top=3)
                for s, rows in res[:3]:
                    v = math.exp(s)
                    t = T[list(rows)][:, nt].sum() / reft[nt].sum()
                    print(f"  r={r}  {v:7.1f}  ({100*(v/math.exp(ref_lgm)-1):+5.1f}%)  "
                          f"{t:4.2f}x time  {name(routes, rows)}")
            print()

    print("## grouped hold-out: refit the whole portfolio per fold, score the held-out group")
    for gname, gf in (("leave-one-suite-out", H.coarse_group_of),
                      ("leave-one-family-out", H.family_of)):
        print(f"### {gname}")
        groups = sorted({gf(k) for k in keys})
        for label, pool in (("horizon only", base_pool), ("joint", list(range(len(routes))))):
            for r in range(3, a.max_r + 1):
                vals, refs, picks = [], [], []
                for grp in groups:
                    tr = [idx[k] for k in keys if gf(k) != grp]
                    te = [idx[k] for k in keys if gf(k) == grp]
                    res = search(M, tr, pool, r, must=cfg, top=1)
                    if not res:
                        continue
                    rows = list(res[0][1])
                    best = M[rows][:, te].min(axis=0)
                    if not np.isfinite(best).all():      # portfolio fails held-out group
                        picks.append(f"{grp}:FAIL"); continue
                    vals += list(best); refs += list(ref[te])
                    picks.append(name(routes, rows))
                if not vals:
                    continue
                v = math.exp(lgm(np.array(vals))); rv = math.exp(lgm(np.array(refs)))
                w = sum(x < y for x, y in zip(vals, refs)); l = sum(x > y for x, y in zip(vals, refs))
                uniq = len(set(picks))
                print(f"  {label:<13} r={r}  {v:7.1f} vs {rv:7.1f} ({100*(v/rv-1):+5.1f}%)  "
                      f"W/L={w}/{l}  n={len(vals)}  {uniq} distinct picks")
        print()

    print("## recommended sets, per suite and against dSABRE")
    cands = {}
    for label, pool, r in (("horizon-only r=4", base_pool, 4), ("horizon-only r=5", base_pool, 5),
                           ("joint r=4", list(range(len(routes))), 4),
                           ("joint r=5", list(range(len(routes))), 5)):
        res = search(M, nt, pool, r, must=cfg, top=1)
        if res:
            cands[label] = list(res[0][1])
    cands["shipped rho-branch"] = None
    B = {"main24": [idx[k] for k in allk if k.startswith("main/")],
         "scaleup": [idx[k] for k in allk if k.startswith("scaleup")],
         "ring": [idx[k] for k in allk if "ring" in k],
         "star": [idx[k] for k in allk if "star" in k]}
    print(f"  {'portfolio':<22}" + "".join(f"{b:>16}" for b in B) + f"{'time':>7}")
    print(f"  {'dSABRE':<22}" + "".join(f"{DSE[b]:>16.1f}" for b in B))
    for label, rows in cands.items():
        cells = []
        for b, cols in B.items():
            v = math.exp(lgm(ref[cols] if rows is None else M[rows][:, cols].min(axis=0)))
            cells.append(f"{v:.1f} ({v/DSE[b]:.2f}x)")
        t = 1.0 if rows is None else T[rows][:, nt].sum() / reft[nt].sum()
        print(f"  {label:<22}" + "".join(f"{c:>16}" for c in cells) + f"{t:>6.2f}x")
    print()
    for label, rows in cands.items():
        if rows is not None:
            print(f"  {label}: {name(routes, rows)}")


if __name__ == "__main__":
    main()
