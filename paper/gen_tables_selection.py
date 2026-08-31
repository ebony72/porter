"""Regenerate the four numeric main-text tables from the results JSONs.

`gen_tables.py` predates the 2026-08-28 restructure (three per-suite
own-protocol tables merged into one `tab:main`, per-circuit rows moved to the
appendix), so it no longer matches the LaTeX.  This module emits exactly the
row blocks the current tables use and splices them in between `\\midrule` and
`\\bottomrule`, leaving captions, headers and column specs untouched.

    python paper/gen_tables_selection.py            # print the blocks
    python paper/gen_tables_selection.py --write    # splice into sfc.tex

Reads the `*_results_selection.json` files by default; pass --released to read
the currently released `*_results.json` instead.  Since the paper migrated to
the horizon-selecting protocol the released files are one protocol behind, so
--released no longer reproduces the tables as they stand: it prints the
single-pass numbers, which is useful for seeing what selection changed and is
NOT a self-test.
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


# Row label, then the (dSABRE, PORTER, PORTER+R) legs routed from that layout.
_GRID = (
    (r"\dSABRE{}'s \texttt{SabreLayout}",
     ("dSE", "sfc_on_dse_layout", "sfc_on_dse_layout_refined")),
    (r"\PORTER{}'s temporal locality-greedy",
     ("dSE_on_porter_layout", "sfc", "sfc_refined")),
    (r"\texttt{pytket-dqc}'s partition",
     ("dSE_pytket", "sfc_pytket", "sfc_pytket_refined")),
)


def tab_shared():
    """tab:shared in the main paper: layout source (rows) against routing
    loop (columns), geometric-mean EPR over all 24 instances.  Every leg
    must cover the whole suite -- the table's claim is that no instance is
    excluded -- so a missing value is an error, not a dash."""
    rows = load("compare")
    cells = []
    for label, legs in _GRID:
        vals = []
        for leg in legs:
            xs = [epr(r, leg) for r in rows]
            if len(xs) != 24 or not all(xs):
                sys.exit(f"tab:shared: leg {leg} covers {sum(1 for x in xs if x)}"
                         f" of {len(xs)} instances, expected 24")
            vals.append(gmean(xs))
        cells.append((label, vals))
    best = [min(c[1][j] for c in cells) for j in range(3)]
    out = []
    for label, vals in cells:
        f = lambda j: (f"\\textbf{{{vals[j]:.1f}}}" if abs(vals[j] - best[j]) < 5e-2
                       else f"{vals[j]:.1f}")
        out.append(f"{label:<36} & {f(0)} & {f(1)} & {f(2)} \\\\")
    return "\n".join(out)


def tab_ablation():
    r"""tab:ablation (Table IV): one mechanism disabled at a time.

    The basis is every circuit of all three suites, but only 80q --- the
    scale at which the mechanisms bite hardest --- is shown per circuit;
    25q and 64q are one summary line each, because what they contribute is
    the trend across scale, not individual rows.  Rows where every
    configuration coincides (no packets, no relief triggered, no telegates)
    are omitted.  A suite line is the geometric mean over the circuits all
    four EPR columns complete, so the line is comparable across itself.
    """
    A = {(r["suite"], r["circuit"]): r["out"]
         for r in json.loads((_HERE.parent / "ablation_results.json").read_text())}
    T = {(r["suite"], r["circuit"]): r["out"]
         for r in json.loads((_HERE / "teledata_ablation_basis.json").read_text())}
    order = ["ae", "ghz", "graphstate", "qft", "qnn", "random",
             "qpeexact", "qaoa", "multiplier"]
    def ep(d, k):
        return (d.get(k) or {}).get("epr")
    def cnt(k, f):
        return (T[k].get("full") or {}).get(f, 0) or 0
    def shown(suite):
        return [(suite, c) for c in order if (suite, c) in A
                and not (ep(A[(suite, c)], "full") == ep(A[(suite, c)], "no_packets")
                         == ep(A[(suite, c)], "no_relief")
                         and cnt((suite, c), "packets") == 0
                         and cnt((suite, c), "telegates") == 0)]
    def cols_of(k):
        return (ep(A[k], "full"), ep(A[k], "no_packets"), ep(A[k], "no_relief"),
                ep(T[k], "teledata_only_relief"))
    out = []
    # 25q and 64q: one paired summary line each.
    for suite in ("25", "64"):
        ks = [k for k in shown(suite) if all(v is not None for v in cols_of(k))]
        v = [gmean([cols_of(k)[i] for k in ks]) for i in range(4)]
        lo = min(v)
        f = lambda x: (f"\\textbf{{{x:.1f}}}" if abs(x - lo) < 5e-2 else f"{x:.1f}")
        out.append(f"\\multicolumn{{2}}{{@{{}}l}}{{{suite}q, gmean over {len(ks)}}} & "
                   + " & ".join(f(x) for x in v) + " & & \\\\")
    out.append("\\midrule")
    # 80q: per circuit.
    for k in shown("80"):
        a, t = A[k], T[k]
        td = ep(t, "teledata_only_relief")
        mark = "" if ep(t, "teledata_only") is not None else "$^{\\ddagger}$"
        g = lambda v: "$^{\\dagger}$" if v is None else str(v)
        tdc = ("$^{\\dagger}$" if td is None else
               (f"\\textbf{{{td}}}{mark}" if td < ep(a, "full") else f"{td}{mark}"))
        out.append(f"80q & {k[1]:<11} & {ep(a,'full'):>5} & {g(ep(a,'no_packets')):>5} & "
                   f"{g(ep(a,'no_relief')):>5} & {tdc} & {cnt(k,'packets'):>4} & "
                   f"{cnt(k,'telegates'):>4} \\\\")
    out.append("\\midrule")
    # Pooled paired gmeans over all three suites, one per comparison.
    allk = [k for s_ in ("25", "64", "80") for k in shown(s_)]
    p3 = [k for k in allk if all(ep(A[k], c) for c in ("full", "no_packets", "no_relief"))]
    p2 = [k for k in allk if ep(A[k], "full") and ep(T[k], "teledata_only_relief")]
    gm = lambda ks, d, c: gmean([ep(d[k], c) for k in ks])
    out.append(f"\\multicolumn{{2}}{{@{{}}l}}{{\\textbf{{all}}, paired $n{{=}}{len(p3)}$}} & "
               f"{gm(p3,A,'full'):.1f} & {gm(p3,A,'no_packets'):.1f} & "
               f"{gm(p3,A,'no_relief'):.1f} & & & \\\\")
    td_g, full_g = gm(p2, T, "teledata_only_relief"), gm(p2, A, "full")
    lo = ("\\textbf{%.1f}" % td_g) if td_g < full_g else ("%.1f" % td_g)
    out.append(f"\\multicolumn{{2}}{{@{{}}l}}{{\\textbf{{all}}, paired $n{{=}}{len(p2)}$}} & "
               f"{full_g:.1f} & & & {lo} & & \\\\")
    return "\n".join(out)


def tab_scaleup():
    """tab:scaleup (Table V): each compiler under its OWN initial layout and
    own protocol.  The PORTER+R and PORTER-on-dSABRE-layout columns were
    removed on 2026-08-31 -- PORTER+R / +S / +SR are measured on the main
    suite only (tab:main), and the fixed-layout control moved to the prose."""
    rows = load("scaleup")
    ARCH = {"100": (150, 6), "200": (300, 12), "360": (500, 20)}
    out, cols = [], {k: [] for k in ("dSE", "sfc")}
    for r in rows:
        n = r["suite"]; P, K = ARCH[n]
        cx = f"{r['cx']:,}".replace(",", "{,}")
        for k in cols:
            cols[k].append(epr(r, k))
        # Complete protocol cost for both, matching the paper's declared
        # timing metric -- NOT seconds_best_attempt, which is one dSABRE
        # route and is not comparable with PORTER's three-route protocol.
        td = (r.get("dSE") or {}).get("seconds")
        tp = (r.get("sfc") or {}).get("seconds")
        out.append(f"{r['circuit'].upper().replace('QPEEXACT','QPEexact'):<8} & {cx:>9} & "
                   f"{n:>3} & {P:>3} & {K:>2} & {epr(r, 'dSE'):>4} & {td:>5.1f} & "
                   f"\\textbf{{{epr(r, 'sfc')}}} & {tp:>5.1f} \\\\")
    g = {k: gmean(v) for k, v in cols.items()}
    tds = gmean([(r.get("dSE") or {}).get("seconds") for r in rows])
    tps = gmean([(r.get("sfc") or {}).get("seconds") for r in rows])
    out.append("\\midrule")
    out.append(f"\\textbf{{gmean}} (6) & & & & & {g['dSE']:.1f} & {tds:.1f} & "
               f"\\textbf{{{g['sfc']:.1f}}} & \\textbf{{{tps:.1f}}} \\\\")
    return "\n".join(out)


def tab_heavyhex():
    """tab:heavyhex (Table VI): own layout, own protocol, both compilers.
    The PORTER+R and PORTER-on-dSABRE-layout columns were removed on
    2026-08-31; the per-circuit rows and the fixed-layout control live in the
    appendix."""
    rows = load("heavyhex")
    out = []
    for topo in ("ring", "star"):
        rs = [r for r in rows if r["topology"] == topo]
        def col(k):
            vs = [epr(r, k) for r in rs]
            return None if any(v is None for v in vs) else gmean(vs)
        g = {k: col(k) for k in ("dSE", "porter")}
        f = lambda v: "---" if v is None else f"{v:.1f}"
        lo = min(v for v in g.values() if v is not None)
        c = lambda k: (f"\\textbf{{{f(g[k])}}}" if g[k] == lo else f"{f(g[k]):>5}")
        out.append(f"{topo} ({len(rs)})".ljust(17) + f" & {c('dSE')} & {c('porter')} \\\\")
    m = next(r for r in rows if r["topology"] == "star" and r["circuit"] == "multiplier")
    cells = [epr(m, k) for k in ("dSE", "porter")]
    lo = min(v for v in cells if v is not None)
    out.append("\\midrule")
    out.append("star Multiplier   & " + " & ".join(
        (f"\\textbf{{{v}}}" if v == lo else f"{('---' if v is None else v):>5}")
        for v in cells) + " \\\\")
    return "\n".join(out)


def app_heavyhex():
    r"""Per-circuit heavy-hex rows in the appendix.

    Columns: \dSABRE{}, \PORTER{} under its own layout, and \PORTER{} on
    \dSABRE{}'s own SabreLayout candidates -- the fixed-layout control the
    main table no longer carries.  No PORTER+R column: refinement is measured
    on the main suite only (tab:main)."""
    rows = load("heavyhex")
    order = ["ae", "ghz", "graphstate", "qft", "qnn", "random",
             "qpeexact", "qaoa", "multiplier"]
    keys = ("dSE", "porter", "porter_on_dse")
    out = []
    for ti, topo in enumerate(("ring", "star")):
        if ti:
            out.append("\\midrule")
        by = {r["circuit"]: r for r in rows if r["topology"] == topo}
        for c in order:
            r = by[c]
            f = lambda x: "$^{\\ast}$" if x is None else str(x)
            out.append(f"{topo:<5} & {c:<11} & " +
                       " & ".join(f"{f(epr(r, k)):>5}" for k in keys) + " \\\\")
        rs = [by[c] for c in order]
        def colg(k):
            vs = [epr(r, k) for r in rs]
            return None if any(v is None for v in vs) else gmean(vs)
        g = [colg(k) for k in keys]
        lo = min(v for v in g if v is not None)
        fg = lambda x: "---" if x is None else (
            f"\\textbf{{{x:.1f}}}" if x == lo else f"{x:.1f}")
        out.append(f"\\multicolumn{{2}}{{@{{}}l}}{{\\quad\\textbf{{gmean}} "
                   f"({len(rs)})}} & " + " & ".join(fg(x) for x in g) + " \\\\")
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


TABLES = {"tab:shared": tab_shared, "tab:ablation": tab_ablation,
          "tab:scaleup": tab_scaleup, "tab:heavyhex": tab_heavyhex}
# The per-circuit main comparison moved to the appendix as tab:maineprs;
# the main paper keeps only a hand-maintained suite-level summary.
APP_MAIN = {"tab:maineprs": tab_main}
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
              **APP_MAIN}


def splice(tex: str, label: str, block: str) -> str:
    """Replace the row body of `label` between the header \\midrule and
    \\bottomrule, leaving caption, header and column spec alone."""
    start = tex.index(f"\\label{{{label}}}")
    top = tex.index("\\midrule", start) + len("\\midrule")
    bot = tex.index("\\bottomrule", top)
    return tex[:top] + "\n" + block + "\n" + tex[bot:]


def _targets():
    """{path: [labels]} for every file holding a generated table.

    The main paper is a driver plus one file per section in sections/, so a
    table's home file changes when sections are reorganised; find each label
    rather than assuming a filename.  Scope matters: tab:shared and
    tab:heavyhex name *different* tables in the main paper and in the
    appendix, so the two sets are searched separately.  Every label must
    resolve to exactly one file within its own scope.
    """
    main = sorted((_HERE / "sections").glob("*.tex")) + [_HERE / "sfc.tex"]
    plan = {}
    for labels, files, scope in ((TABLES, main, "main paper"),
                                 (APP_TABLES, [_HERE / "sfc_appendix.tex"], "appendix")):
        for label, fn in labels.items():
            hits = [p for p in files if f"\\label{{{label}}}" in p.read_text()]
            if len(hits) != 1:
                sys.exit(f"{label}: found in {len(hits)} {scope} files "
                         f"({[p.name for p in hits]}), expected exactly 1")
            plan.setdefault(hits[0], []).append((label, fn))
    return plan


if __name__ == "__main__":
    plan = _targets()
    n = 0
    for path, labels in plan.items():
        tex = path.read_text()
        for label, fn in labels:
            block = fn()
            if "--write" in sys.argv:
                tex = splice(tex, label, block)
                n += 1
            else:
                print(f"\n%% ==== {path.name}:{label} ====\n{block}")
        if "--write" in sys.argv:
            path.write_text(tex)
    if "--write" in sys.argv:
        print(f"spliced {n} tables")
