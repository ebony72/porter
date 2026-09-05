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
    loop (columns), geometric-mean EPR, in two blocks.

    Block (a) is over all 24 instances; every leg must cover the whole suite
    -- the table's claim is that no instance is excluded -- so a missing
    value is an error, not a dash.  Block (b) repeats it without GHZ and
    Graphstate, whose EPR counts are one to two orders of magnitude below
    the rest of the suite and therefore dominate an unweighted geometric
    mean.  The two blocks disagree in every column, which is V-B's subject,
    so both are generated rather than one being derived by hand.
    """
    rows = load("compare")
    triv = lambda r: r["circuit"].replace("_OLD_DEEP", "") in ("ghz", "graphstate")
    blocks = [("\\emph{(a)} all twenty-four instances", rows, 24),
              ("\\emph{(b)} the eighteen excluding GHZ and Graphstate",
               [r for r in rows if not triv(r)], 18)]
    out = []
    for bi, (header, basis, want_n) in enumerate(blocks):
        cells = []
        for label, legs in _GRID:
            vals = []
            for leg in legs:
                xs = [epr(r, leg) for r in basis]
                if len(xs) != want_n or not all(xs):
                    sys.exit(f"tab:shared: leg {leg} covers "
                             f"{sum(1 for x in xs if x)} of {len(xs)}, "
                             f"expected {want_n}")
                vals.append(gmean(xs))
            cells.append((label, vals))
        best = [min(c[1][j] for c in cells) for j in range(3)]
        if bi:
            out.append("\\midrule")
        out.append(f"\\multicolumn{{4}}{{@{{}}l}}{{{header}}} \\\\")
        for label, vals in cells:
            f = lambda j: (f"\\textbf{{{vals[j]:.1f}}}"
                           if abs(vals[j] - best[j]) < 5e-2 else f"{vals[j]:.1f}")
            out.append(f"{label:<36} & {f(0)} & {f(1)} & {f(2)} \\\\")
    return "\n".join(out)


def tab_ablation():
    r"""tab:ablation (Table IV): one mechanism disabled at a time, 80q only.

    The ablation still RUNS on all three suites -- the cross-scale trend is
    quoted in V-C and pinned in verify_paper_numbers -- but only the 80-qubit
    rows are shown, the scale at which every mechanism bites hardest.  Since
    2026-09-04 ALL nine circuits appear: GHZ and Graphstate used to be
    dropped as rows on which every configuration coincides, but they were
    always inside the summary lines, so showing them makes the table's own
    arithmetic checkable and states plainly where a mechanism does nothing.
    The Suite column is gone, every row being 80q.

    A summary line carries one Full value, so columns share a line only when
    they complete on the same circuits; where they do not, the comparison
    gets its own line and $n$ states the basis.
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
    def all_of(suite):
        return [(suite, c) for c in order if (suite, c) in A]

    def shown(suite):
        return all_of(suite)
    def cols_of(k):
        return (ep(A[k], "full"), ep(A[k], "no_packets"), ep(A[k], "no_relief"),
                ep(T[k], "teledata_only_relief"))
    def basis(ks, i):
        return tuple(k for k in ks if cols_of(k)[i] is not None
                     and cols_of(k)[0] is not None)

    def summary(ks, n_all):
        groups = {}
        for i in (1, 2, 3):
            groups.setdefault(basis(ks, i), []).append(i)
        lines = []
        for b, idx in groups.items():
            v = {0: gmean([cols_of(k)[0] for k in b])}
            v.update({i: gmean([cols_of(k)[i] for k in b]) for i in idx})
            lo = min(v.values())
            cells = ["" if i not in v else
                     (f"\\textbf{{{v[i]:.1f}}}" if abs(v[i] - lo) < 5e-2 else f"{v[i]:.1f}")
                     for i in range(4)]
            tag = "" if len(b) == n_all else f" of {n_all}"
            lines.append(f"\\textbf{{gmean}}, $n{{=}}{len(b)}${tag} & "
                         + " & ".join(cells) + " & & \\\\")
        return lines

    out = []
    for k in shown("80"):
        a, t = A[k], T[k]
        td = ep(t, "teledata_only_relief")
        mark = "" if ep(t, "teledata_only") is not None else "$^{\\ddagger}$"
        g = lambda v: "$^{\\dagger}$" if v is None else str(v)
        tdc = ("$^{\\dagger}$" if td is None else
               (f"\\textbf{{{td}}}{mark}" if td < ep(a, "full") else f"{td}{mark}"))
        out.append(f"{k[1]:<11} & {ep(a,'full'):>5} & {g(ep(a,'no_packets')):>5} & "
                   f"{g(ep(a,'no_relief')):>5} & {tdc} & {cnt(k,'packets'):>4} & "
                   f"{cnt(k,'telegates'):>4} \\\\")
    out.append("\\midrule")
    ks80 = all_of("80")
    out += summary(ks80, len(ks80))
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
        # 360q QPEexact used to carry a machine-dependence dagger: its L=128
        # route sat just inside the speculative WALL-CLOCK share, so a slower
        # run fell back to 2342.  SPECULATIVE_WORK_FACTOR replaced that share
        # with a budget in DAG layers peeled, and the value is now
        # deterministic (verified 3/3 at 1224, and 200q QFT 3/3 at 579, on a
        # machine 1.7x slower than the session that produced the table).
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
    """tab:heavyhex (Table VI): own layout, own protocol, plus the
    fixed-layout control -- PORTER routing dSABRE's own SabreLayout
    candidates -- which is what shows the star gap is PORTER's layout
    rather than its routing loop.  The star-Multiplier callout row was
    removed on 2026-09-01 with the livelock discussion it supported."""
    rows = load("heavyhex")
    out = []
    for topo in ("ring", "star"):
        rs = [r for r in rows if r["topology"] == topo]
        def col(k):
            vs = [epr(r, k) for r in rs]
            return None if any(v is None for v in vs) else gmean(vs)
        g = {k: col(k) for k in ("dSE", "porter", "porter_on_dse")}
        f = lambda v: "---" if v is None else f"{v:.1f}"
        lo = min(v for v in g.values() if v is not None)
        c = lambda k: (f"\\textbf{{{f(g[k])}}}" if g[k] == lo else f"{f(g[k]):>5}")
        out.append(f"{topo} ({len(rs)})".ljust(17)
                   + f" & {c('dSE')} & {c('porter')} & {c('porter_on_dse')} \\\\")
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



def _gmean_raw(xs):
    """Unclamped geometric mean, for TIMES: gmean() drops falsy values and the
    clamped form used for EPR silently inflates sub-second cells."""
    return math.exp(sum(math.log(x) for x in xs) / len(xs))


def _main_by():
    rows = load("compare")
    return {(r["suite"], r["circuit"].replace("_OLD_DEEP", "")): r for r in rows}


def tab_mainsummary():
    """tab:main -- the suite-level summary in the main paper.

    Hand-maintained until now, and stale twice: the 2026-09-04 audit found its
    whole t column a protocol behind while both baselines were current, which
    is how "0.91x dSABRE's compile time" reached the abstract.  Column order
    mirrors verify_tex_tables.py.  Bold marks the lowest EPR of the four
    compilers; times and portfolio cells are never bold.
    """
    by = _main_by()
    legs = ("telesabre", "dSE", "sfc", "sfc_refined")
    keys = list(by)

    def row(label, pool, block_b):
        matched = [k for k in pool if all(epr(by[k], l) for l in legs)]
        basis = pool if block_b else matched
        eprs, cells = [], []
        for leg in legs:
            if leg == "telesabre" and block_b:
                eprs.append(None); cells.append(("---", "---")); continue
            e = round(gmean([by[k][leg]["epr"] for k in basis]), 1)
            tb = matched if leg == "telesabre" else pool
            t = round(_gmean_raw([by[k][leg]["seconds"] for k in tb]), 2)
            eprs.append(e); cells.append((f"{e:.1f}", f"{t:.2f}"))
        best = min(e for e in eprs if e is not None)
        out = [f"{label} ({len(basis)})"]
        for e, (ec, tc) in zip(eprs, cells):
            out += ["\\textbf{%s}" % ec if e == best else ec, tc]
        for leg in ("sfc", "sfc_refined"):
            v = gmean([min(by[k]["dSE"]["epr"], by[k][leg]["epr"]) for k in basis])
            out.append(f"{round(v, 1):.1f}")
        return " & ".join(out) + " \\\\"

    L = ["\\multicolumn{11}{@{}l}{\\emph{(a)} over the circuits \\emph{all four} complete} \\\\"]
    for su in ("25", "64", "80"):
        L.append(row(f"{su}q", [k for k in keys if k[0] == su], False))
    L.append("\\midrule")
    L.append("\\multicolumn{11}{@{}l}{\\emph{(b)} over \\emph{every} circuit in the suite; \\TeleSABRE{} omitted} \\\\")
    for su in ("25", "64", "80"):
        L.append(row(f"{su}q", [k for k in keys if k[0] == su], True))
    L.append(row("all", keys, True))
    L.append("\\midrule")
    ts_done = sum(1 for k in keys if epr(by[k], "telesabre"))
    L.append("done    & " + " & ".join("\\multicolumn{2}{c}{%s}" % v for v in (
        f"{ts_done} / 24", "24 / 24", "24 / 24", "24 / 24", "---")) + " \\\\")
    wlt = []
    for leg in ("sfc", "sfc_refined"):
        w = sum(1 for k in keys if by[k][leg]["epr"] < by[k]["dSE"]["epr"])
        l = sum(1 for k in keys if by[k][leg]["epr"] > by[k]["dSE"]["epr"])
        wlt.append(f"{w} / {l} / {len(keys)-w-l}")
    L.append("W/L/T   & \\multicolumn{2}{c}{---} & \\multicolumn{2}{c}{---}"
             f" & \\multicolumn{{2}}{{c}}{{{wlt[0]}}}"
             f" & \\multicolumn{{2}}{{c}}{{{wlt[1]}}}"
             " & \\multicolumn{2}{c}{---} \\\\")
    return "\n".join(L)


def tab_protocols():
    """tab:protocols -- routes, EPR and complete time per protocol, each as a
    ratio to dSABRE.  Route counts are read from the live constants."""
    sys.path.insert(0, str(_HERE.parent))
    import compile_porter as _cp
    import compare_routers as _cr
    by = _main_by()
    keys = list(by)
    d_e = gmean([by[k]["dSE"]["epr"] for k in keys])
    d_t = _gmean_raw([by[k]["dSE"]["seconds"] for k in keys])
    H, P = len(_cp.PORTER_HORIZONS), _cr.PORTER_REFINE_PASSES
    out = []
    for name, routes, leg in (("\\dSABRE{}", 9, "dSE"),
                              ("\\PORTER{}", H, "sfc"),
                              ("\\PORTER{}$+$R", H + P - 1, "sfc_refined")):
        e = gmean([by[k][leg]["epr"] for k in keys])
        t = _gmean_raw([by[k][leg]["seconds"] for k in keys])
        out.append(f"{name} & {routes} & {e:.1f} & {e/d_e:.2f} & {t:.2f} & {t/d_t:.2f} \\\\")
    return "\n".join(out)


def app_layoutsearch():
    """tab:layoutsearch (Appendix J) -- PORTER / +R / +S per circuit, the +S
    delta against +R, the winning gamma, and both wall clocks.  Hand-maintained
    until now; column order mirrors verify_tex_tables.py."""
    by = _main_by()
    order = [(s, c) for s in ("25", "64", "80")
             for c in ("ae", "ghz", "graphstate", "qft", "qnn", "random",
                       "qpeexact", "qaoa", "multiplier")
             if (s, c) in by]
    L = []
    for si, suite in enumerate(("25", "64", "80")):
        if si:
            L.append("\\midrule")
        for k in [k for k in order if k[0] == suite]:
            r = by[k]
            e = [r[l]["epr"] for l in ("sfc", "sfc_refined", "sfc_search")]
            d = ("---" if e[2] == e[1]
                 else "$%+.1f$" % (100 * (e[2] / e[1] - 1)))
            L.append("%sq & %-11s & %5d & %5d & %5d & %9s & %.2f & %8.1f & %7.1f \\\\"
                     % (suite, k[1], e[0], e[1], e[2], d,
                        round(r["sfc_search"]["best_gamma"], 2),
                        round(r["sfc_refined"]["seconds"], 1),
                        round(r["sfc_search"]["seconds"], 1)))
        L.append(_ls_gmean_line(by, [k for k in order if k[0] == suite], suite))
    L.append("\\midrule")
    L.append(_ls_gmean_line(by, order, None))
    return "\n".join(L)


def _ls_gmean_line(by, sub, suite):
    g = [gmean([by[k][l]["epr"] for k in sub])
         for l in ("sfc", "sfc_refined", "sfc_search")]
    lab = ("\\multicolumn{2}{@{}l}{\\textbf{gmean, all} (%d)}" % len(sub)
           if suite is None
           else "\\multicolumn{2}{@{}l}{\\quad\\textbf{gmean} (%d)}" % len(sub))
    return ("%s & %.1f & %.1f & \\textbf{%.1f} & $\\mathbf{%+.1f}$ & & %.2f & %.2f \\\\"
            % (lab, g[0], g[1], g[2], 100 * (g[2] / g[1] - 1),
               _gmean_raw([by[k]["sfc_refined"]["seconds"] for k in sub]),
               _gmean_raw([by[k]["sfc_search"]["seconds"] for k in sub])))


def _ls_unused(by, order):
    for suite in ("25", "64", "80", None):
        sub = order if suite is None else [k for k in order if k[0] == suite]
        g = [gmean([by[k][l]["epr"] for k in sub])
             for l in ("sfc", "sfc_refined", "sfc_search")]
        d = 100 * (g[2] / g[1] - 1)
        lab = ("\\multicolumn{2}{@{}l}{\\textbf{gmean, all} (%d)}" % len(sub)
               if suite is None
               else "\\multicolumn{2}{@{}l}{\\quad\\textbf{gmean} (%d)}" % len(sub))
        if suite is None:
            L.append("\\midrule")
        L.append("%s & %.1f & %.1f & \\textbf{%.1f} & $\\mathbf{%+.1f}$ & & %.2f & %.2f \\\\"
                 % (lab, g[0], g[1], g[2], d,
                    _gmean_raw([by[k]["sfc_refined"]["seconds"] for k in sub]),
                    _gmean_raw([by[k]["sfc_search"]["seconds"] for k in sub])))
    return "\n".join(L)


def app_actionset():
    """tab:actionset (Appendix) -- the 64q action mix.

    Columns 1-3 are TeleSABRE's TeleData/TeleGate and dSABRE's TeleData; they
    come from neither results file this generator reads and neither compiler
    changed, so they are carried over from the existing row verbatim.  Columns
    4-7 are PORTER's, regenerated from action_mix_results.json.  PORTER's
    column is a SINGLE forward pass at the configured horizon (action_mix.py
    calls compile() directly), which the caption states.
    """
    mix = {r["circuit"].replace("_OLD_DEEP", ""): r
           for r in json.loads((_HERE / "action_mix_results.json").read_text())
           if r["suite"] == "64"}
    tex = (_HERE / "sfc_appendix.tex").read_text()
    seg = tex[tex.index("\\label{tab:actionset}"):]
    seg = seg[:seg.index("\\end{tabular}")]
    # NB the header row also matches ^[A-Z]\w+\s*& ("Circuit & \TeleData &
    # ..."); taking it as data shifts every row by one.  Data rows are the ones
    # after \midrule whose second cell is a number or ---.
    # The table has three \midrule-separated parts: header, the nine data
    # rows, and a bold Total row.  The header also matches ^[A-Z]\w+\s*&
    # ("Circuit & \TeleData & ..."), so taking part[-1] or matching the whole
    # segment shifts or drops rows -- both happened while writing this.
    parts = seg.split("\\midrule")
    rows = [l for l in parts[1].splitlines()
            if re.match(r"^[A-Z]\w+\s*&", l.strip())]
    order = ["ae", "ghz", "graphstate", "qft", "qnn", "random",
             "qpeexact", "qaoa", "multiplier"]
    if len(rows) != len(order):
        raise SystemExit(f"tab:actionset: parsed {len(rows)} data rows, want {len(order)}")
    out, tot = [], [0, 0, 0, 0]
    for line, c in zip(rows, order):
        cols = [x.strip() for x in line.strip().rstrip("\\\\").split("&")]
        m = mix[c]
        td = (m["teleports_normal"] + m["teleports_blocked"]
              + m["teleports_capacity_relief"])
        vals = [td, m["telegates"], m["telegate_packets"], m["packet_cx_total"]]
        for j, v in enumerate(vals):
            tot[j] += v
        cols[4:8] = [str(v) for v in vals]
        out.append("%-10s & %5s & %4s & %5s & %5s & %4s & %4s & %5s \\\\"
                   % tuple(cols[:8]))
    # Regenerate the Total row's PORTER half from the same data.
    trow = next(l for l in parts[2].splitlines() if "textbf{Total}" in l)
    tcols = [x.strip() for x in trow.strip().rstrip("\\\\").split("&")]
    tcols[4:8] = ["\\textbf{%d}" % v for v in tot]
    out.append("\\midrule")
    out.append(" & ".join(tcols[:8]) + " \\\\")
    return "\n".join(out)


TABLES = {"tab:main": tab_mainsummary, "tab:protocols": tab_protocols,
          "tab:shared": tab_shared, "tab:ablation": tab_ablation,
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


# `tab:pytket` IS regenerated since 2026-09-03.  It used to be excluded on the
# grounds that its basis was unclear, and that was right: its \PORTER{} EPR
# column reproduced PORTER's OWN-layout leg on 7 of its 12 rows, not the
# pytket-layout leg it was captioned as, and its dSABRE column was stale at
# 64q.  With `sfc_pytket` and `dSE_pytket` now current on all 24 instances the
# basis is settled, so the table is generated from them over all three suites.
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


def app_mainswaps():
    """tab:mainswaps: local SWAP counts, own protocol, same row order and
    non-convergence marker as tab:maineprs.  Was hand-maintained and had
    drifted on 26 of its 96 cells (2026-09-04), including dSABRE columns
    predating the 2026-08-31 layout-family change."""
    rows = load("compare")
    out = []
    for si, suite in enumerate(("25", "64", "80")):
        if si:
            out.append("\\midrule")
        for r in (x for x in rows if x["suite"] == suite):
            c = r["circuit"].replace("_OLD_DEEP", "")
            cells = []
            for leg in ("telesabre", "dSE", "sfc", "sfc_refined"):
                v = (r.get(leg) or {}).get("swaps")
                cells.append("$^{\\ast}$" if v is None else str(v))
            out.append(f"{suite}q & {c:<11} & " +
                       " & ".join(f"{x:>10}" for x in cells) + " \\\\")
    return "\n".join(out)


APP_TABLES = {"tab:actionset": app_actionset,
              "tab:layoutsearch": app_layoutsearch,
              "tab:heavyhex": app_heavyhex, "tab:shared": app_shared,
              "tab:pytket": app_pytket,
              "tab:mainswaps": app_mainswaps, **APP_MAIN}


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
