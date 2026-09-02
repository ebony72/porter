"""Offline analysis of a horizon grid: Phase 0 (validation), Phase 1
(exhaustive portfolios) and Phase 2 (simple architecture-aware rules, grouped
hold-out) of the vault instructions.  Needs no routing; reads either the
2026-09-01 sweep JSONs or one arm of horizon_grid.jsonl.

  python hz_offline.py --source prev            # the released-code sweep
  python hz_offline.py --source jsonl --arm base
"""
import json, math, argparse, itertools, statistics
from pathlib import Path
import hz_common as H

HERE = H.HERE
H6 = [4, 8, 16, 32, 64, 128]
H8 = [4, 8, 16, 32, 48, 64, 128, 256]
NAMED3 = {
    "{4,32,128}": (4, 32, 128), "{8,32,128}": (8, 32, 128),
    "{4,16,64}": (4, 16, 64), "{8,16,64}": (8, 16, 64),
    "{8,16,128} (sparse set alone)": (8, 16, 128),
    "{4,8,16} (dense set alone)": (4, 8, 16),
}
NAMED4 = {"{4,16,64,128}": (4, 16, 64, 128), "{8,16,48,128}": (8, 16, 48, 128)}
NAMED5 = {"{4,16,32,64,128}": (4, 16, 32, 64, 128)}


# ----------------------------------------------------------------- loading

def load_prev():
    grid = {}
    for p, Ls in ((HERE / "sweep_2026-09-01_main.json", H8),
                  (HERE / "sweep_2026-09-01_heavyhex.json", H6)):
        for key, r in json.loads(p.read_text()).items():
            cells = {}
            for L in Ls:
                v = r["epr"].get(str(L), "missing")
                s = r["seconds"].get(str(L))
                if v == "missing":
                    st = "not_run"
                elif v is None:
                    st = "timeout"
                elif isinstance(v, str):
                    st = "livelock" if "RuntimeError" in v else "error"
                    v = None
                else:
                    st = "completed"
                cells[L] = {"status": st, "epr": v, "seconds": s}
            grid[key] = cells
    return grid


def load_jsonl(arm):
    grid = {}
    p = HERE / "horizon_grid.jsonl"
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["arm"] != arm:
            continue
        grid.setdefault(r["key"], {})[r["L"]] = {
            "status": r["status"], "epr": r["epr"], "seconds": r["seconds"],
            "verified": r.get("verified")}
    return grid


def epr(grid, key, L):
    c = grid.get(key, {}).get(L)
    return c["epr"] if c and c["status"] == "completed" else None


def secs(grid, key, L, default=300.0):
    c = grid.get(key, {}).get(L)
    return c["seconds"] if c and c["seconds"] is not None else default


# ---------------------------------------------------------------- features

_FEAT = None


def features():
    global _FEAT
    if _FEAT is None:
        _FEAT = {}
        hw_cache = {}
        for key in H.instance_keys():
            arch = H.arch_of(key)
            if arch not in hw_cache:
                hw_cache[arch] = H.arch_features(H.hardware_for(key))
            hw, gates, n = H.load(key) if False else (None, None, None)
            f = dict(hw_cache[arch])
            f["arch"] = arch
            _FEAT[key] = f
        # circuit features (parse once per file)
        for key in H.instance_keys():
            _, gates, n = H.load(key)
            _FEAT[key].update(H.circuit_features(gates, n))
    return _FEAT


# ---------------------------------------------------------------- policies

def best_of(grid, key, Ls):
    vals = [(epr(grid, key, L), L) for L in Ls if epr(grid, key, L) is not None]
    return min(vals) if vals else (None, None)


def oracle(grid, key, Ls):
    return best_of(grid, key, Ls)


def density_sets(rho, thr=0.80, dense=(4, 8, 16), sparse=(8, 16, 128)):
    return dense if rho >= thr else sparse


def regret_stats(regs):
    regs = sorted(regs)
    n = len(regs)
    if n == 0:
        return {}
    p90 = regs[min(n - 1, int(math.ceil(0.9 * n)) - 1)]
    return {"n": n, "median": statistics.median(regs), "p90": p90, "max": regs[-1],
            ">5%": sum(r > 0.05 for r in regs), ">10%": sum(r > 0.10 for r in regs),
            ">25%": sum(r > 0.25 for r in regs), "exact": sum(r < 1e-9 for r in regs)}


def evaluate_portfolio(grid, keys, Ls, ref_Ls, routes_of=None):
    """Best completed EPR within `Ls` per instance; regret vs oracle over ref_Ls."""
    eprs, regs, cover, secs_total, orac = [], [], 0, 0.0, []
    for key in keys:
        e, _ = best_of(grid, key, Ls)
        o, _ = oracle(grid, key, ref_Ls)
        secs_total += sum(secs(grid, key, L) for L in Ls)
        if e is None:
            continue
        cover += 1
        eprs.append(e)
        orac.append(o)
        regs.append(e / o - 1)
    return {"cover": cover, "gmean": H.gmean(eprs) if eprs else None,
            "oracle_gmean": H.gmean(orac) if orac else None,
            "regret": regret_stats(regs), "seconds": secs_total}


# ---------------------------------------------------------------- phases

def phase0(grid, Ls_of):
    counts = {}
    attempted = 0
    for key, cells in grid.items():
        for L in Ls_of(key):
            c = cells.get(L)
            st = c["status"] if c else "not_run"
            counts[st] = counts.get(st, 0) + 1
            attempted += st != "not_run"
    lines = [f"attempted routes: {attempted}; by status: {counts}"]
    nontriv = [k for k in grid if not H.is_trivial(k)]
    no16 = [k for k in nontriv if epr(grid, k, 16) is None]
    lines.append(f"instances: {len(grid)}, horizon-sensitive (non GHZ/Graphstate): "
                 f"{len(nontriv)}; of those lacking a completed L=16 route: {no16}")
    fails = [(k, L, c["status"]) for k, cells in grid.items() for L, c in cells.items()
             if c["status"] not in ("completed", "not_run")]
    lines.append(f"non-completions ({len(fails)}): " +
                 ", ".join(f"{k}@{L}:{s}" for k, L, s in fails))
    return "\n".join(lines)


def headline(grid, keys, feat, Ls, live_budget=False):
    """The shipped density rule vs fixed 16 vs oracle."""
    rows = []
    for key in keys:
        rho = feat[key]["rho"]
        cand = [L for L in density_sets(rho) if L in Ls]
        if live_budget:
            t16 = secs(grid, key, 16)
            budget = max(5.0, 4.0 * t16)
            cand = [L for L in cand if L == 16 or secs(grid, key, L) <= budget]
        sel, selL = best_of(grid, key, cand)
        f16 = epr(grid, key, 16)
        orc, orcL = oracle(grid, key, Ls)
        rows.append((key, rho, sel, selL, f16, orc, orcL, cand))
    ok = [r for r in rows if r[2] is not None and r[5] is not None]
    ok16 = [r for r in ok if r[4] is not None]
    g_sel = H.gmean([r[2] for r in ok]); g_or = H.gmean([r[5] for r in ok])
    g16 = H.gmean([r[4] for r in ok16]); g_sel16 = H.gmean([r[2] for r in ok16])
    outside = [r[0] for r in ok if r[6] not in r[7]]
    found = sum(r[2] == r[5] for r in ok)
    return {
        "n_selected": len(ok), "n_fixed16": len(ok16),
        "gmean_rule": g_sel, "gmean_oracle": g_or,
        "gmean_fixed16": g16, "gmean_rule_on_fixed16_basis": g_sel16,
        "fixed16_penalty_pct": 100 * (g16 / g_sel16 - 1),
        "oracle_headroom_pct": 100 * (g_or / g_sel - 1),
        "gain_captured_pct": 100 * (1 - (math.log(g_sel) - math.log(g_or)) /
                                    (math.log(g16) - math.log(H.gmean([r[5] for r in ok16])))),
        "optimum_found": found, "optimum_outside_set": len(outside),
        "outside_keys": outside,
    }


def phase1(grid, keys, Ls, max_r=5, top=4):
    out = {}
    ref = Ls
    for r in range(1, max_r + 1):
        res = []
        for sub in itertools.combinations(Ls, r):
            ev = evaluate_portfolio(grid, keys, sub, ref)
            res.append((sub, ev))
        # lexicographic: coverage desc, gmean asc, seconds asc
        res.sort(key=lambda t: (-t[1]["cover"], t[1]["gmean"] or 1e9, t[1]["seconds"]))
        out[r] = res[:top]
        if r == 3:
            out["named3"] = {nm: evaluate_portfolio(grid, keys, s, ref)
                             for nm, s in NAMED3.items() if all(x in Ls for x in s)}
        if r == 4:
            out["named4"] = {nm: evaluate_portfolio(grid, keys, s, ref)
                             for nm, s in NAMED4.items() if all(x in Ls for x in s)}
        if r == 5:
            out["named5"] = {nm: evaluate_portfolio(grid, keys, s, ref)
                             for nm, s in NAMED5.items() if all(x in Ls for x in s)}
    return out


def rule_eval(grid, keys, feat, Ls, rule):
    """`rule(key) -> candidate horizons`.  Returns gmean, regret, coverage."""
    eprs, regs, cover = [], [], 0
    for key in keys:
        cand = [L for L in rule(key) if L in Ls]
        e, _ = best_of(grid, key, cand)
        o, _ = oracle(grid, key, Ls)
        if e is None or o is None:
            continue
        cover += 1
        eprs.append(e); regs.append(e / o - 1)
    return {"cover": cover, "gmean": H.gmean(eprs) if eprs else None,
            "mean_log_regret": (sum(math.log1p(r) for r in regs) / len(regs)) if regs else None,
            "regret": regret_stats(regs)}


def snap(L, Ls):
    return min(Ls, key=lambda x: abs(math.log(x) - math.log(max(L, 1))))


def fit_scaling(grid, train, feat, Ls, form):
    """Grid-search c (and alpha) for L = clip(round(c * f), 4, 128) snapped."""
    best = None
    cs = [2 ** (i / 4) for i in range(-8, 29)]          # 0.25 .. 128
    alphas = [0.0, 0.5, 1.0] if form == "KD" else [None]
    for a in alphas:
        for c in cs:
            def rule(key, c=c, a=a):
                f = feat[key]
                if form == "K":
                    v = c * f["K"]
                elif form == "D":
                    v = c * f["diameter"]
                else:
                    v = c * f["diameter"] * (f["K"] ** a)
                return [snap(min(128, max(4, round(v))), Ls)]
            ev = rule_eval(grid, train, feat, Ls, rule)
            score = (-ev["cover"], ev["mean_log_regret"] if ev["mean_log_regret"] is not None else 9)
            if best is None or score < best[0]:
                best = (score, c, a, rule)
    return best[1], best[2], best[3]


def fit_density_form(grid, train, feat, Ls, sets3):
    best = None
    thrs = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95]
    for dense in sets3:
        for sparse in sets3:
            for thr in thrs:
                def rule(key, d=dense, s=sparse, t=thr):
                    return d if feat[key]["rho"] >= t else s
                ev = rule_eval(grid, train, feat, Ls, rule)
                score = (-ev["cover"], ev["mean_log_regret"] if ev["mean_log_regret"] is not None else 9)
                if best is None or score < best[0]:
                    best = (score, dense, sparse, thr, rule)
    return best[1:]


def fit_global3(grid, train, feat, Ls, sets3):
    best = None
    for s in sets3:
        ev = rule_eval(grid, train, feat, Ls, lambda k, s=s: s)
        score = (-ev["cover"], ev["mean_log_regret"] if ev["mean_log_regret"] is not None else 9)
        if best is None or score < best[0]:
            best = (score, s)
    return best[1]


def phase2(grid, keys, feat, Ls):
    sets3 = list(itertools.combinations(Ls, 3))
    groupings = {
        "leave-one-suite-out": H.coarse_group_of,
        "leave-one-family-out": H.family_of,
    }
    policies = {
        "shipped density rule": lambda tr: (lambda k: density_sets(feat[k]["rho"])),
        "refit density form (2 sets + threshold)":
            lambda tr: fit_density_form(grid, tr, feat, Ls, sets3)[3],
        "best global 3-set": lambda tr: (lambda k, s=fit_global3(grid, tr, feat, Ls, sets3): s),
        "L(K)": lambda tr: fit_scaling(grid, tr, feat, Ls, "K")[2],
        "L(D)": lambda tr: fit_scaling(grid, tr, feat, Ls, "D")[2],
        "L(K,D)": lambda tr: fit_scaling(grid, tr, feat, Ls, "KD")[2],
        "fixed 16": lambda tr: (lambda k: [16]),
        "fixed 128": lambda tr: (lambda k: [128]),
    }
    out = {}
    for gname, gf in groupings.items():
        groups = sorted({gf(k) for k in keys})
        for pname, pf in policies.items():
            # held-out: fit on all other groups, evaluate on the held-out group
            eprs, regs, cover, n = [], [], 0, 0
            for g in groups:
                test = [k for k in keys if gf(k) == g]
                train = [k for k in keys if gf(k) != g]
                rule = pf(train)
                for key in test:
                    n += 1
                    cand = [L for L in rule(key) if L in Ls]
                    e, _ = best_of(grid, key, cand)
                    o, _ = oracle(grid, key, Ls)
                    if e is None or o is None:
                        continue
                    cover += 1; eprs.append(e); regs.append(e / o - 1)
            out[(gname, pname)] = {"n": n, "cover": cover, "gmean": H.gmean(eprs),
                                   "regret": regret_stats(regs)}
        # in-sample references
    ins = {}
    for pname, pf in policies.items():
        rule = pf(keys)
        ins[pname] = rule_eval(grid, keys, feat, Ls, rule)
    return out, ins


def cross_arch(grid, feat, Ls):
    fams = ["ae", "qft", "qnn", "random", "qpeexact", "qaoa", "multiplier"]
    rows = []
    for f in fams:
        row = [f]
        for pre in ("main/64/", "heavyhex/ring/", "heavyhex/star/"):
            key = next(k for k in grid if k.startswith(pre) and H.family_of(k) == f)
            o, oL = oracle(grid, key, Ls)
            row.append((oL, o, feat[key]["K"], feat[key]["diameter"], feat[key]["hub_ratio"]))
        rows.append(row)
    return rows


# ---------------------------------------------------------------- report

def fmt_ev(ev):
    r = ev["regret"]
    if not r:
        return f"cover={ev['cover']} gmean=-"
    return (f"cover={ev['cover']:>2} gmean={ev['gmean']:7.1f} "
            f"regret med={100*r['median']:4.1f}% p90={100*r['p90']:5.1f}% max={100*r['max']:5.1f}% "
            f">10%={r['>10%']:>2} exact={r['exact']:>2}"
            + (f" routes-time={ev['seconds']/60:6.1f}min" if "seconds" in ev else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="prev", choices=["prev", "jsonl"])
    ap.add_argument("--arm", default="base")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    grid = load_prev() if a.source == "prev" else load_jsonl(a.arm)
    feat = features()
    keys_all = [k for k in H.instance_keys() if k in grid]
    keys = [k for k in keys_all if not H.is_trivial(k)]
    main30 = [k for k in keys if not k.startswith("heavyhex")]

    def Ls_of(key):
        return H6 if key.startswith("heavyhex") else H8

    print(f"# Horizon grid analysis  (source={a.source}{'/'+a.arm if a.source=='jsonl' else ''})\n")
    print("## Phase 0: validation\n")
    print(phase0(grid, Ls_of if a.source == "prev" else (lambda k: sorted(grid[k]))))
    print()
    print("## Headline: shipped density rule vs fixed 16 vs oracle (non-trivial instances)\n")
    for label, ks, Ls in (("all, H6", keys, H6), ("main+scaleup, H8", main30, H8)):
        for live in (False, True):
            h = headline(grid, ks, feat, Ls, live_budget=live)
            tag = "live-budget-feasible" if live else "sweep-guard"
            print(f"- {label} [{tag}]: n={h['n_selected']} rule={h['gmean_rule']:.1f} "
                  f"oracle={h['gmean_oracle']:.1f} (headroom {h['oracle_headroom_pct']:+.1f}%), "
                  f"fixed16={h['gmean_fixed16']:.1f} on n={h['n_fixed16']} "
                  f"(penalty {h['fixed16_penalty_pct']:+.1f}%), gain captured "
                  f"{h['gain_captured_pct']:.0f}%, optimum found {h['optimum_found']}/{h['n_selected']}, "
                  f"optimum outside assigned set {h['optimum_outside_set']}")
            if not live:
                print(f"  outside: {h['outside_keys']}")
    print()
    print("## Phase 1: exhaustive portfolios over H6 = {4,8,16,32,64,128}, non-trivial instances (regret vs H6 oracle)\n")
    p1 = phase1(grid, keys, H6)
    for r in range(1, 6):
        print(f"### r = {r}")
        for sub, ev in p1[r]:
            print(f"  {str(sub):<22} {fmt_ev(ev)}")
    for nm in ("named3", "named4", "named5"):
        print(f"### named {nm[-1]}-sets")
        for name, ev in p1[nm].items():
            print(f"  {name:<32} {fmt_ev(ev)}")
    print("  shipped density rule           " + fmt_ev(rule_eval(grid, keys, feat, H6,
          lambda k: density_sets(feat[k]["rho"]))))
    print()
    print("## Phase 1b: same over H8 on the 30 main+scale-up instances (regret vs H8 oracle)\n")
    p1b = phase1(grid, main30, H8, top=3)
    for r in range(1, 6):
        print(f"### r = {r}")
        for sub, ev in p1b[r]:
            print(f"  {str(sub):<26} {fmt_ev(ev)}")
    print("  shipped density rule           " + fmt_ev(rule_eval(grid, main30, feat, H8,
          lambda k: density_sets(feat[k]["rho"]))))
    print()
    print("## Phase 2: instance-level rules, grouped hold-out (H6, non-trivial instances)\n")
    ho, ins = phase2(grid, keys, feat, H6)
    print("### in-sample (fit and evaluated on all instances)")
    for p, ev in ins.items():
        print(f"  {p:<42} {fmt_ev(ev)}")
    for g in ("leave-one-suite-out", "leave-one-family-out"):
        print(f"### {g}")
        for (gg, p), ev in ho.items():
            if gg == g:
                print(f"  {p:<42} {fmt_ev(ev)}")
    print()
    print("## Identical circuits across architectures: best horizon (EPR) with K, D, hub ratio\n")
    print(f"  {'family':<12}{'64q grid':<28}{'hh ring':<28}{'hh star':<28}")
    for row in cross_arch(grid, feat, H6):
        cells = [f"L={oL} ({o}) K={K} D={D} hub={hub:.2f}" for oL, o, K, D, hub in row[1:]]
        print(f"  {row[0]:<12}" + "".join(f"{c:<28}" for c in cells))
    print()
    print("## Per-instance oracle horizon and features\n")
    print(f"  {'key':<26}{'n':>5}{'K':>3}{'D':>3}{'hub':>5}{'rho':>6}{'depth':>7}{'cx':>7}{'bestL':>6}{'best':>7}{'@16':>7}")
    for key in keys:
        f = feat[key]; o, oL = oracle(grid, key, Ls_of(key))
        print(f"  {key:<26}{f['n']:>5}{f['K']:>3}{f['diameter']:>3}{f['hub_ratio']:>5.2f}{f['rho']:>6.2f}"
              f"{f['depth']:>7}{f['cx']:>7}{str(oL):>6}{str(o):>7}{str(epr(grid,key,16)):>7}")
    if a.out:
        dump = {"grid": {k: {str(L): c for L, c in v.items()} for k, v in grid.items()},
                "features": feat}
        Path(a.out).write_text(json.dumps(dump, indent=1))


if __name__ == "__main__":
    main()
