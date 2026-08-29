"""Regenerate the four numeric main-text tables from the results JSONs.

`gen_tables.py` predates the 2026-08-28 restructure (three per-suite
own-protocol tables merged into one `tab:main`, per-circuit rows moved to the
appendix), so it no longer matches the LaTeX.  This module emits exactly the
row blocks the current tables use and splices them in between `\\midrule` and
`\\bottomrule`, leaving captions, headers and column specs untouched.

    python paper/gen_tables_selection.py            # print the blocks
    python paper/gen_tables_selection.py --write    # splice into sfc.tex

Reads the `*_results_selection.json` files by default; pass --released to read
the currently released `*_results.json` instead, which must reproduce the
tables as they stand and is therefore a self-test of this generator.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
SUFFIX = "_selection" if "--released" not in sys.argv else ""


def load(name):
    return json.loads((_HERE / f"{name}_results{SUFFIX}.json").read_text())


def gmean(xs):
    xs = [x for x in xs if x]
    return math.exp(sum(math.log(x) for x in xs) / len(xs)) if xs else None


def epr(rec, key):
    return (rec.get(key) or {}).get("epr")


def i(v, star="$^{\\ast}$"):
    return star if v is None else str(v)


def pct(a, b):
    return "---" if (a is None or not b) else f"${100*(a-b)/b:+.1f}$".replace("+", "+")


def tab_main():
    rows = load("compare")
    by = {}
    for r in rows:
        by.setdefault(r["suite"], []).append(r)
    out = []
    for si, suite in enumerate(("25", "64", "80")):
        if si:
            out.append("\\midrule")
        matched = {k: [] for k in ("telesabre", "dSE", "sfc", "sfc_refined")}
        for r in by[suite]:
            c = r["circuit"].replace("_OLD_DEEP", "")
            ts, dse = epr(r, "telesabre"), epr(r, "dSE")
            sfc, ref = epr(r, "sfc"), epr(r, "sfc_refined")
            if ts is not None:
                for k, v in zip(matched, (ts, dse, sfc, ref)):
                    matched[k].append(v)
            # Delta is against PORTER's BETTER protocol: horizon selection
            # overtakes refinement on some circuits, so pinning it to +R
            # would understate the compiler.
            best = None if None in (sfc, ref) else min(sfc, ref)
            d = "---" if ts is None else f"${100*(best-ts)/ts:.1f}$"
            out.append(f"{suite}q & {c:<11} & {i(ts):>10} & {i(dse):>5} & "
                       f"{i(sfc):>5} & {i(ref):>5} & {d:>9} \\\\")
        g = {k: gmean(v) for k, v in matched.items()}
        n = len(matched["telesabre"])
        gbest = min(g["sfc"], g["sfc_refined"])
        dg = 100 * (gbest - g["telesabre"]) / g["telesabre"]
        # Bold whichever PORTER protocol is stronger on this suite.
        cs = (f"\\textbf{{{g['sfc']:.1f}}}" if g["sfc"] <= g["sfc_refined"]
              else f"{g['sfc']:.1f}")
        cr = (f"\\textbf{{{g['sfc_refined']:.1f}}}" if g["sfc_refined"] < g["sfc"]
              else f"{g['sfc_refined']:.1f}")
        out.append(f"\\multicolumn{{2}}{{@{{}}l}}{{\\quad\\textbf{{gmean}} ({n})}} & "
                   f"{g['telesabre']:.1f} & {g['dSE']:.1f} & {cs} & "
                   f"{cr} & $\\mathbf{{{dg:.1f}}}$ \\\\")
    return "\n".join(out)


def tab_shared():
    rows = load("compare")
    out, allm = [], {k: [] for k in ("telesabre", "dSE_shared", "sfc_shared_refined")}
    for suite in ("25", "64", "80"):
        m = {k: [] for k in allm}
        for r in rows:
            if r["suite"] != suite:
                continue
            ts, ds = epr(r, "telesabre"), epr(r, "dSE_shared")
            sr = epr(r, "sfc_shared_refined") or epr(r, "sfc_shared")
            if None in (ts, ds, sr):
                continue
            for k, v in zip(m, (ts, ds, sr)):
                m[k].append(v); allm[k].append(v)
        g = {k: gmean(v) for k, v in m.items()}
        out.append(f"{suite}q ({len(m['telesabre'])}) & {g['telesabre']:.1f} & "
                   f"{g['dSE_shared']:.1f} & ${100*(g['dSE_shared']-g['telesabre'])/g['telesabre']:.1f}$ & "
                   f"\\textbf{{{g['sfc_shared_refined']:.1f}}} & "
                   f"$\\mathbf{{{100*(g['sfc_shared_refined']-g['telesabre'])/g['telesabre']:.1f}}}$ \\\\")
    g = {k: gmean(v) for k, v in allm.items()}
    out.append(f"\\textbf{{all}} ({len(allm['telesabre'])}) & {g['telesabre']:.1f} & "
               f"{g['dSE_shared']:.1f} & ${100*(g['dSE_shared']-g['telesabre'])/g['telesabre']:.1f}$ & "
               f"\\textbf{{{g['sfc_shared_refined']:.1f}}} & "
               f"$\\mathbf{{{100*(g['sfc_shared_refined']-g['telesabre'])/g['telesabre']:.1f}}}$ \\\\")
    return "\n".join(out)


def tab_scaleup():
    rows = load("scaleup")
    ARCH = {"100": (150, 6), "200": (300, 12), "360": (500, 20)}
    out, cols = [], {k: [] for k in ("dSE", "sfc", "sfc_refined",
                                     "sfc_on_dse_layout", "sfc_on_dse_layout_refined")}
    for r in rows:
        n = r["suite"]; P, K = ARCH[n]
        cx = f"{r['cx']:,}".replace(",", "{,}")
        vals = [epr(r, k) for k in cols]
        for k, v in zip(cols, vals):
            cols[k].append(v)
        # The caption defines t as ONE dSABRE attempt, not the complete
        # protocol, so seconds_best_attempt is the right field here.
        t = (r.get("dSE") or {}).get("seconds_best_attempt")
        out.append(f"{r['circuit'].upper().replace('QPEEXACT','QPEexact'):<8} & {cx:>9} & "
                   f"{n:>3} & {P:>3} & {K:>2} & {vals[0]:>4} & {t:>4.1f} & "
                   f"{vals[1]:>4} & {vals[2]:>4} & {vals[3]:>4} & {vals[4]:>4} \\\\")
    g = {k: gmean(v) for k, v in cols.items()}
    out.append("\\midrule")
    # dSABRE's gmean is bolded as the baseline; among PORTER's four variants
    # only the best is bolded, as in the released table.
    porter_keys = ["sfc", "sfc_refined", "sfc_on_dse_layout",
                   "sfc_on_dse_layout_refined"]
    best = min(porter_keys, key=lambda k: g[k])
    cells = " & ".join(
        (f"\\textbf{{{g[k]:.1f}}}" if k == best else f"{g[k]:.1f}")
        for k in porter_keys)
    out.append(f"\\textbf{{gmean}} (6) & & & & & \\textbf{{{g['dSE']:.1f}}} & & "
               f"{cells} \\\\")
    return "\n".join(out)


def tab_heavyhex():
    rows = load("heavyhex")
    def sel(topo, need_all):
        rs = [r for r in rows if r["topology"] == topo]
        if not need_all:
            rs = [r for r in rs if epr(r, "porter")]
        return rs
    out = []
    # The released table carried a "star (8)" row because PORTER could not
    # complete star/Multiplier under its own layout.  Horizon selection
    # completes it, so that row is emitted only while it still differs from
    # the full-suite row.
    variants = [("ring", True), ("star", True)]
    star_all = [r for r in rows if r["topology"] == "star"]
    if any(epr(r, "porter") is None for r in star_all):
        variants.append(("star", False))
    for topo, need_all in variants:
        rs = sel(topo, need_all)
        # A gmean over a column with a missing entry would silently be taken
        # over fewer circuits than the row claims, so such a column is "---".
        def col(k):
            vs = [epr(r, k) for r in rs]
            return None if any(v is None for v in vs) else gmean(vs)
        g = {k: col(k) for k in
             ("dSE", "porter", "porter_refined", "porter_on_dse", "porter_on_dse_refined")}
        f = lambda v: "---" if v is None else f"{v:.1f}"
        out.append(f"{topo} ({len(rs)})".ljust(17) +
                   f" & {f(g['dSE']):>5} & {f(g['porter']):>5} & {f(g['porter_refined']):>4} & "
                   f"{f(g['porter_on_dse']):>5} & \\textbf{{{f(g['porter_on_dse_refined'])}}} \\\\")
    m = next(r for r in rows if r["topology"] == "star" and r["circuit"] == "multiplier")
    f = lambda v: "---" if v is None else str(v)
    out.append("\\midrule")
    out.append(f"star Multiplier   & {f(epr(m,'dSE')):>5} & {f(epr(m,'porter')):>5} & "
               f"{f(epr(m,'porter_refined')):>4} & {f(epr(m,'porter_on_dse')):>5} & "
               f"\\textbf{{{f(epr(m,'porter_on_dse_refined'))}}} \\\\")
    return "\n".join(out)


def app_heavyhex():
    """Per-circuit heavy-hex rows in the appendix."""
    rows = load("heavyhex")
    order = ["ae", "ghz", "graphstate", "qft", "qnn", "random",
             "qpeexact", "qaoa", "multiplier"]
    out = []
    for ti, topo in enumerate(("ring", "star")):
        if ti:
            out.append("\\midrule")
        by = {r["circuit"]: r for r in rows if r["topology"] == topo}
        for c in order:
            r = by[c]
            v = [epr(r, k) for k in ("dSE", "porter", "porter_refined",
                                     "porter_on_dse", "porter_on_dse_refined")]
            f = lambda x: "$^{\\ast}$" if x is None else str(x)
            out.append(f"{topo:<5} & {c:<11} & {f(v[0]):>5} & {f(v[1]):>5} & "
                       f"{f(v[2]):>5} & {f(v[3]):>5} & {f(v[4]):>5} \\\\")
        # gmean rows: over all nine, plus over the subset PORTER+R completes
        # while that subset is still smaller.
        keys = ("dSE", "porter", "porter_refined", "porter_on_dse",
                "porter_on_dse_refined")
        subsets = [[by[c] for c in order]]
        partial = [by[c] for c in order if epr(by[c], "porter_refined")]
        if len(partial) < len(order):
            subsets.append(partial)
        for rs in subsets:
            def colg(k):
                vs = [epr(r, k) for r in rs]
                return None if any(v is None for v in vs) else gmean(vs)
            g = [colg(k) for k in keys]
            fg = lambda x: "---" if x is None else f"{x:.1f}"
            out.append(f"\\multicolumn{{2}}{{@{{}}l}}{{\\quad\\textbf{{gmean}} "
                       f"({len(rs)})}} & {fg(g[0])} & {fg(g[1])} & {fg(g[2])} & "
                       f"{fg(g[3])} & \\textbf{{{fg(g[4])}}} \\\\")
    return "\n".join(out)


def app_shared():
    """Per-circuit TeleSABRE-shared-layout rows in the appendix."""
    rows = load("compare")
    out, acc = [], []
    for si, suite in enumerate(("25", "64", "80")):
        for r in rows:
            if r["suite"] != suite:
                continue
            ts, ds, sf = r.get("telesabre"), r.get("dSE_shared"), r.get("sfc_shared")
            sr = epr(r, "sfc_shared_refined")
            if not (ts and ds and sf):
                continue
            c = r["circuit"].replace("_OLD_DEEP", "")
            best = sr if sr is not None else sf["epr"]
            out.append(
                f"{suite}q & {c:<11} & {ts['epr']:>4} & {ts['swaps']:>5} & "
                f"{ds['epr']:>4} & {ds['swaps']:>5} & "
                f"${100*(ds['epr']-ts['epr'])/ts['epr']:.1f}$ & "
                f"{sf['epr']:>4} & {('---' if sr is None else sr):>5} & "
                f"${100*(best-ts['epr'])/ts['epr']:.1f}$ \\\\")
        acc.append(suite)
    # per-suite and overall gmean rows
    def gmrow(rs, label, bold_sfc=False):
        ts = gmean([epr(r, "telesabre") for r in rs])
        ds = gmean([epr(r, "dSE_shared") for r in rs])
        sf = gmean([epr(r, "sfc_shared") for r in rs])
        sr = gmean([epr(r, "sfc_shared_refined") or epr(r, "sfc_shared") for r in rs])
        srx = f"\\textbf{{{sr:.1f}}}" if bold_sfc else f"{sr:.1f}"
        return (f"\\multicolumn{{2}}{{@{{}}l}}{{{label}}} & {ts:.1f} & & {ds:.1f} & & "
                f"$\\mathbf{{{100*(ds-ts)/ts:.1f}}}$ & {sf:.1f} & {srx} & "
                f"$\\mathbf{{{100*(sr-ts)/ts:.1f}}}$ \\\\")
    out2, all_rs = [], []
    for si, suite in enumerate(("25", "64", "80")):
        if si:
            out2.append("\\midrule")
        rs = [r for r in rows if r["suite"] == suite and epr(r, "telesabre")
              and epr(r, "dSE_shared") and epr(r, "sfc_shared")]
        all_rs += rs
        block = [l for l in out if l.startswith(f"{suite}q &")]
        out2 += block
        out2.append(gmrow(rs, f"\\quad\\textbf{{gmean}} ({len(rs)})"))
    out2.append("\\midrule")
    out2.append(gmrow(all_rs, f"\\textbf{{gmean, all}} ({len(all_rs)})", True))
    return "\n".join(out2)


TABLES = {"tab:main": tab_main, "tab:shared": tab_shared,
          "tab:scaleup": tab_scaleup, "tab:heavyhex": tab_heavyhex}
def app_pytket():
    """Per-circuit pytket-shared-layout rows in the appendix:
    ebits, then dSABRE (EPR, SWAP) and PORTER (EPR, SWAP) on that partition."""
    rows = load("compare")
    out = []
    for suite in ("25", "64", "80"):
        for r in rows:
            if r["suite"] != suite:
                continue
            ds, sf = r.get("dSE_pytket"), r.get("sfc_pytket")
            eb = r.get("pytket_ebits")
            c = r["circuit"].replace("_OLD_DEEP", "")
            f = lambda x: "---" if x is None else str(x)
            out.append(
                f"{suite}q & {c:<10} & {f(eb):>4} & "
                f"{f(epr(r, 'dSE_pytket')):>4} & {f((ds or {}).get('swaps')):>4} & "
                f"{f(epr(r, 'sfc_pytket')):>4} & {f((sf or {}).get('swaps')):>4} \\\\")
    return "\n".join(out)


# NOTE: `tab:pytket` is deliberately NOT regenerated.  Running app_pytket()
# against the RELEASED results file does not reproduce the released table --
# it is missing 64q qpeexact/qaoa/multiplier and its dSABRE column differs --
# so that table predates the current compare_results.json and its basis is
# unclear.  Regenerating it would silently change a table on a basis nobody
# has established.  app_pytket() is kept for whoever settles that question.
def app_timing():
    """tab:timing: median-of-three complete-protocol compile seconds."""
    rows = json.loads((_HERE / f"timing_results{SUFFIX}.json").read_text())
    out = []
    for r in rows:
        f = lambda v: "$^{\\ast}$" if v is None else f"{v:.2f}"
        out.append(f"{r['circuit']} ({r['suite']}q)".ljust(12) +
                   f" & {r['cx']:>5} & {f(r['telesabre']):>6} & "
                   f"{f(r['dsabre']):>6} & {f(r['porter']):>6} & "
                   f"{f(r['porter_refined']):>6} \\\\")
    return "\n".join(out)


APP_TABLES = {"tab:heavyhex": app_heavyhex, "tab:shared": app_shared,
              "tab:timing": app_timing}


def splice(tex: str, label: str, block: str) -> str:
    """Replace the row body of `label` between the header \\midrule and
    \\bottomrule, leaving caption, header and column spec alone."""
    start = tex.index(f"\\label{{{label}}}")
    top = tex.index("\\midrule", start) + len("\\midrule")
    bot = tex.index("\\bottomrule", top)
    return tex[:top] + "\n" + block + "\n" + tex[bot:]


if __name__ == "__main__":
    n = 0
    for fname, tabs in (("sfc.tex", TABLES), ("sfc_appendix.tex", APP_TABLES)):
        path = _HERE / fname
        tex = path.read_text()
        for label, fn in tabs.items():
            block = fn()
            if "--write" in sys.argv:
                tex = splice(tex, label, block)
                n += 1
            else:
                print(f"\n%% ==== {fname}:{label} ====\n{block}")
        if "--write" in sys.argv:
            path.write_text(tex)
    if "--write" in sys.argv:
        print(f"spliced {n} tables")
