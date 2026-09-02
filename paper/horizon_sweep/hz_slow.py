"""Test 1: does a slow decay with no floor remove the horizon parameter?

The shipped schedule floors the weight at 0.5 from layer 7, so L is a hard
window and the best L varies by a factor of 32 across instances -- which is why
PORTER routes three candidate horizons.  If the discount itself bounds the
reach, one deep route should do: EPR should go flat in L, and a single slow
route should match the three-route portfolio.

Decisive comparisons, all paired on jointly completed instances:
  A. one slow route at each L   vs  the shipped 3-route rule (base arm)
  B. flatness of EPR in L within each arm (max/min per instance)
  C. scale-up, where floor0 (gamma 0.9, no floor) lost 62%
  D. completion
"""
import json, math, statistics
from collections import defaultdict
import hz_common as H
from hz_offline import load_jsonl, epr, best_of, density_sets, H6

SLOW = ["slow95", "slow97", "slow99"]
ALL_L = [4, 8, 16, 32, 64, 128, 256]
RHO = {}
for p in ("sweep_2026-09-01_main.json", "sweep_2026-09-01_heavyhex.json"):
    for k, r in json.loads((H.HERE / p).read_text()).items():
        RHO[k] = r["rho"]

GROUPS = {
    "main25": lambda k: k.startswith("main/25"), "main64": lambda k: k.startswith("main/64"),
    "main80": lambda k: k.startswith("main/80"), "scaleup": lambda k: k.startswith("scaleup"),
    "ring": lambda k: "ring" in k, "star": lambda k: "star" in k, "all": lambda k: True,
}


def gm(v):
    return math.exp(sum(math.log(max(x, 1)) for x in v) / len(v)) if v else float("nan")


def main():
    arms = ["base", "floor0"] + SLOW
    g = {a: load_jsonl(a) for a in arms}
    keys = [k for k in H.instance_keys() if not H.is_trivial(k)]

    # the reference PORTER actually ships: 3 routes at the base schedule
    ref = {k: best_of(g["base"], k, density_sets(RHO[k]))[0] for k in keys}
    ref3 = {k: v for k, v in ref.items() if v is not None}

    print("## coverage")
    for a in arms:
        Ls = ALL_L if a in SLOW else H6
        cells = [(k, L) for k in H.instance_keys() for L in Ls if L in g[a].get(k, {})]
        st = defaultdict(int)
        for k, L in cells:
            st[g[a][k][L]["status"]] += 1
        bad = [f"{k}@{L}" for k, L in cells if g[a][k][L]["status"] == "completed"
               and g[a][k][L].get("verified") is not True]
        print(f"  {a:<8} {len(cells):>4} cells  {dict(st)}  unverified={len(bad)}")
    print()

    print("## A. ONE slow route at each L vs the shipped 3-route rule (paired, non-trivial)")
    print(f"  {'arm/L':<14}{'n':>4}{'ref(3rt)':>10}{'slow(1rt)':>11}{'delta':>9}  W/L/T   completes")
    best_single = None
    for a in SLOW:
        for L in ALL_L:
            pairs = [(ref3[k], epr(g[a], k, L)) for k in keys
                     if k in ref3 and epr(g[a], k, L) is not None]
            if not pairs:
                continue
            gr, gs = gm([p[0] for p in pairs]), gm([p[1] for p in pairs])
            w = sum(s < r for r, s in pairs); l = sum(s > r for r, s in pairs)
            t = len(pairs) - w - l
            comp = sum(1 for k in keys if epr(g[a], k, L) is not None)
            row = (gs / gr - 1, a, L, gs, gr, len(pairs))
            if comp == len(keys) and (best_single is None or row < best_single):
                best_single = row
            print(f"  {a+'/'+str(L):<14}{len(pairs):>4}{gr:>10.1f}{gs:>11.1f}"
                  f"{100*(gs/gr-1):>+8.1f}%  {w}/{l}/{t}   {comp}/{len(keys)}")
    if best_single:
        d, a, L, gs, gr, n = best_single
        print(f"\n  best single route completing every instance: {a} at L={L} "
              f"-> {gs:.1f} vs {gr:.1f} ({100*d:+.1f}%) on n={n}")
    print()

    print("## A2. per suite, best slow single route vs the 3-route rule")
    print(f"  {'group':<9}{'ref(3rt)':>10}" + "".join(f"{a:>22}" for a in SLOW))
    for gname, gf in GROUPS.items():
        ks = [k for k in keys if gf(k)]
        base_v = [ref3[k] for k in ks if k in ref3]
        cells = []
        for a in SLOW:
            best = None
            for L in ALL_L:
                pairs = [(ref3[k], epr(g[a], k, L)) for k in ks
                         if k in ref3 and epr(g[a], k, L) is not None]
                if len(pairs) != len(ks):
                    continue
                gs = gm([p[1] for p in pairs]); gr = gm([p[0] for p in pairs])
                if best is None or gs < best[0]:
                    best = (gs, L, gs / gr - 1)
            cells.append(f"{best[0]:.1f}@L{best[1]} ({100*best[2]:+.1f}%)" if best else "-")
        print(f"  {gname:<9}{gm(base_v):>10.1f}" + "".join(f"{c:>22}" for c in cells))
    print()

    print("## B. flatness of EPR in L (per-instance max/min over completed horizons)")
    print(f"  {'arm':<9}{'median':>8}{'gmean':>8}{'>1.5x':>7}{'>2x':>6}   best-L histogram")
    for a in arms:
        Ls = ALL_L if a in SLOW else H6
        sp, hist = [], defaultdict(int)
        for k in keys:
            v = [(epr(g[a], k, L), L) for L in Ls if epr(g[a], k, L) is not None]
            if len(v) >= 2:
                sp.append(max(x for x, _ in v) / max(1, min(x for x, _ in v)))
                hist[min(v)[1]] += 1
        print(f"  {a:<9}{statistics.median(sp):>8.2f}{gm(sp):>8.2f}"
              f"{sum(s > 1.5 for s in sp):>7}{sum(s > 2 for s in sp):>6}   {dict(sorted(hist.items()))}")
    print()

    print("## B2. flatness restricted to deep horizons only (L >= 32)")
    for a in arms:
        Ls = [L for L in (ALL_L if a in SLOW else H6) if L >= 32]
        sp = []
        for k in keys:
            v = [epr(g[a], k, L) for L in Ls if epr(g[a], k, L) is not None]
            if len(v) >= 2:
                sp.append(max(v) / max(1, min(v)))
        print(f"  {a:<9} median {statistics.median(sp):.2f}  gmean {gm(sp):.2f}  n={len(sp)}")
    print()

    print("## C. scale-up detail (where floor0 lost 62%)")
    sk = [k for k in keys if k.startswith("scaleup")]
    print(f"  {'instance':<24}{'3-route':>9}" + "".join(f"{a[-2:]+'@'+str(L):>10}"
          for a in SLOW for L in (64, 128, 256)))
    for k in sk:
        cells = "".join(f"{str(epr(g[a],k,L) or '-'):>10}" for a in SLOW for L in (64, 128, 256))
        print(f"  {k:<24}{ref3.get(k, '-'):>9}" + cells)
    print()

    print("## D. best-of-3 within each slow arm (is a portfolio still needed?)")
    for a in SLOW:
        for cand in ((16, 64, 256), (32, 128, 256), (16, 128, 256)):
            pairs = [(ref3[k], best_of(g[a], k, cand)[0]) for k in keys
                     if k in ref3 and best_of(g[a], k, cand)[0] is not None]
            gs = gm([p[1] for p in pairs]); gr = gm([p[0] for p in pairs])
            print(f"  {a:<8} best-of-{cand}  n={len(pairs)}  {gs:.1f} vs {gr:.1f} "
                  f"({100*(gs/gr-1):+.1f}%)")
    print()

    print("## E. per-instance: shipped 3-route vs the best single slow route")
    if best_single:
        _, a, L, _, _, _ = best_single
        print(f"  (single route = {a} at L={L})")
        print(f"  {'instance':<26}{'3-route':>9}{'single':>9}{'delta':>9}")
        for k in keys:
            r, s = ref3.get(k), epr(g[a], k, L)
            if r and s:
                print(f"  {k:<26}{r:>9}{s:>9}{100*(s/r-1):>+8.1f}%")
    print()

    print("## F. wall time: one slow route vs three base routes")
    for a in SLOW:
        for L in (64, 128, 256):
            t1 = sum(g[a][k][L]["seconds"] for k in keys if L in g[a].get(k, {}))
            t3 = sum(sum(g["base"][k][x]["seconds"] for x in density_sets(RHO[k])
                         if x in g["base"].get(k, {})) for k in keys)
            print(f"  {a} at L={L}: {t1:.0f}s for one route over {len(keys)} instances "
                  f"vs {t3:.0f}s for the 3-route rule ({t1/t3:.2f}x)")


if __name__ == "__main__":
    main()
