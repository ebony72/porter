"""Parse the LaTeX tables of the paper and check them against the results JSONs.

verify_paper_numbers.py encodes what the paper is *supposed* to say; this
reads the rows LaTeX will actually typeset, so a typo made while editing a
section file cannot sail past. Covers the five data tables of the main paper:
tab:main, tab:shared, tab:scaleup, tab:heavyhex, tab:ablation.
"""
import json
import math
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
# The main paper is a driver (sfc.tex) plus one file per section in sections/.
# Concatenate them so a table is found wherever its section currently lives.
_MAIN = [_HERE / "sfc.tex"] + sorted((_HERE / "sections").glob("*.tex"))
TEX = "\n".join(p.read_text() for p in _MAIN)
APP = (_HERE / "sfc_appendix.tex").read_text()
# The tex tracks the results files the tables were generated from.  During a
# protocol migration those are the `*_results_selection.json` variants; once
# they are promoted to the released names this falls back automatically.
_SEL = "_selection" if (_HERE / "compare_results_selection.json").exists() else ""


def _res(name):
    return _HERE / f"{name}_results{_SEL}.json"


CMP = json.load(open(_res("compare")))
BY = {(r["suite"], "qnn" if r["circuit"].startswith("qnn") else r["circuit"]): r
      for r in CMP}
HH = {(r["topology"], r["circuit"]): r
      for r in json.load(open(_res("heavyhex")))}
SU = {(r["suite"], r["circuit"]): r
      for r in json.load(open(_res("scaleup")))}
ABL = {(r["suite"], r["circuit"]): r
       for r in json.load(open(_HERE.parent / "ablation_results.json"))}
TD = {(r["suite"], r["circuit"]): r
      for r in json.load(open(_HERE / "teledata_ablation_basis.json"))}
fails = []


def chk(name, want, got):
    if want != got:
        fails.append(f"  {name}: tex={want!r} data={got!r}")


def gmean(v):
    # max(x,1) guards EPR counts, which can legitimately be 0.
    return math.exp(sum(math.log(max(x, 1)) for x in v) / len(v))


def gmean_raw(v):
    # Unclamped: compile times are routinely below 1 s, where the guard above
    # would silently inflate the mean.
    return math.exp(sum(math.log(x) for x in v) / len(v))


def cell(tok):
    tok = re.sub(r"\$\^\{\\(ast|dagger|ddagger)\}\$", "", tok)
    tok = tok.replace("{,}", "").replace("\\textbf{", "").replace("}", "")
    tok = tok.replace("$", "").strip()
    return None if tok in ("---", "") else int(tok)


def num(tok):
    tok = tok.replace("$", "").replace("\\mathbf{", "").replace("\\textbf{", "")
    tok = tok.replace("}", "").replace("{,}", "").strip()
    return None if tok in ("---", "") else float(tok)


def rows_of(label, pattern, src=None):
    src = TEX if src is None else src
    i = src.index(f"\\label{{{label}}}")
    seg = src[i:src.index(r"\end{tabular}", i)]
    seg = seg[seg.index(r"\midrule"):]
    out = []
    for line in seg.splitlines():
        line = line.strip()
        if line.endswith("\\\\") and re.match(pattern, line):
            out.append([c.strip() for c in line[:-2].split("&")])
    return seg, out


def gmean_rows(seg):
    return [[c.strip() for c in l.strip()[:-2].split("&")]
            for l in seg.splitlines() if r"\textbf{gmean}" in l]


# ---------------------------------------------------------------- tab:main
# The per-circuit rows moved to the appendix (tab:maineprs); the main paper
# now carries only a suite-level summary, whose gmeans are checked below.
seg, rows = rows_of("tab:maineprs", r"^\d\dq\s*&", APP)
chk("main row count", 24, len(rows))
for cols in rows:
    key = (cols[0].replace("q", ""), cols[1])
    r = BY[key]
    for j, leg in enumerate(("telesabre", "dSE", "sfc", "sfc_refined")):
        chk(f"main {key} {leg}", cell(cols[2 + j]), (r.get(leg) or {}).get("epr"))
    # Delta follows whichever PORTER protocol is stronger on the row:
    # horizon selection overtakes refinement on some circuits.
    ts = (r.get("telesabre") or {}).get("epr")
    best = min(r["sfc"]["epr"], r["sfc_refined"]["epr"])
    chk(f"main {key} dTS", num(cols[6]),
        round(100 * (best - ts) / ts, 1) if ts else None)
# tab:main in the main paper has two blocks: (a) suites over the circuits all
# four configurations complete, (b) suites and a pooled row over EVERY circuit
# with TeleSABRE dashed.  Both are checked, and the row counts are pinned so a
# reshaped table fails rather than passing on fewer rows.
# PORTER+S was dropped from the main paper on 2026-08-31 and now lives in
# appendix tab:layoutsearch (checked separately below).  Removing it does not
# move block (a)'s basis: every leg but TeleSABRE completes all 24, so the
# matched set is TeleSABRE-limited either way.
_MAIN_LEGS = ("telesabre", "dSE", "sfc", "sfc_refined")
seg_m, rows_m = rows_of("tab:main", r"^(\d\dq|all)\s*\(")
chk("tab:main summary row count", 7, len(rows_m))
for cols in rows_m:
    lab = cols[0].strip()
    n = int(re.search(r"\((\d+)\)", lab).group(1))
    suite = lab.split("q")[0] if lab.startswith(("25", "64", "80")) else None
    pool = [k for k in BY if suite is None or k[0] == suite]
    matched = [k for k in pool
               if all((BY[k].get(l) or {}).get("epr") for l in _MAIN_LEGS)]
    # A dashed TeleSABRE cell marks block (b), which averages the whole suite;
    # block (a) averages only the circuits all four configurations complete.
    # (At 25q the two sets coincide, so the dash is the only reliable marker.)
    in_b = num(cols[1]) is None
    basis = pool if in_b else matched
    chk(f"tab:main basis {lab}", n, len(basis))
    for j, leg in enumerate(_MAIN_LEGS):
        got = num(cols[1 + 2 * j])
        if leg == "telesabre" and in_b:
            continue
        chk(f"tab:main {lab} {leg}", got,
            round(gmean([BY[k][leg]["epr"] for k in basis]), 1))
        # The t column was UNCHECKED until 2026-09-04, and every PORTER cell
        # in it had gone stale at the three-horizon protocol while the two
        # baselines stayed current -- which is how "0.91x dSABRE's compile
        # time" survived into the abstract when the data says 1.18x.  Times
        # use gmean_raw: the clamped mean silently inflates sub-second cells.
        # TeleSABRE's time is over the circuits it completes, the rest over
        # the whole suite, matching the caption.
        t_basis = matched if leg == "telesabre" else pool
        chk(f"tab:main {lab} {leg} t", num(cols[2 + 2 * j]),
            round(gmean_raw([BY[k][leg]["seconds"] for k in t_basis]), 2))
    # The two portfolio columns: per-instance min of dSABRE and the named
    # PORTER configuration, on whatever basis the row uses.
    chk(f"tab:main {lab} column count", 11, len(cols))
    # The bold EPR cell must be the best single compiler, never the portfolio:
    # the portfolio is derived, and bolding it would read as a fifth column.
    _epr = [cols[i] for i in (1, 3, 5, 7)]
    _live = [(i, num(c)) for i, c in enumerate(_epr) if num(c) is not None]
    chk(f"tab:main {lab} bold is best compiler",
        [i for i, c in enumerate(_epr) if "textbf" in c],
        [i for i, v in _live if v == min(v for _, v in _live)])
    for _j in (9, 10):
        chk(f"tab:main {lab} portfolio col {_j} unbold", False,
            "textbf" in cols[_j])
    # Bold in the t column marks the fastest compiler in the row.
    _t = [cols[i] for i in (2, 4, 6, 8)]
    _tlive = [(i, num(c)) for i, c in enumerate(_t) if num(c) is not None]
    chk(f"tab:main {lab} bold t is fastest",
        [i for i, c in enumerate(_t) if "textbf" in c],
        [i for i, v in _tlive if v == min(v for _, v in _tlive)])
    for j, leg in enumerate(("sfc", "sfc_refined")):
        chk(f"tab:main {lab} portfolio {leg}", num(cols[9 + j]),
            round(gmean([min(BY[k]["dSE"]["epr"], BY[k][leg]["epr"])
                         for k in basis]), 1))

# --------------------------------------------------- tab:layoutsearch (APP)
# PORTER+S lives in the appendix only.  Its per-circuit EPR triples and the
# four gmean lines are checked here so the appendix cannot drift either.
_LS_ORDER = [(s, c) for s in ("25", "64", "80")
             for c in ("ae", "ghz", "graphstate", "qft", "qnn", "random",
                       "qpeexact", "qaoa", "multiplier")
             if not (s == "25" and c in ("qpeexact", "qaoa", "multiplier"))]
seg_ls, rows_ls = rows_of("tab:layoutsearch", r"^\d\dq\s*&", APP)
chk("layoutsearch row count", 24, len(rows_ls))
for key, cols in zip(_LS_ORDER, rows_ls):
    r = BY[key]
    for j, leg in enumerate(("sfc", "sfc_refined", "sfc_search")):
        chk(f"layoutsearch {key} {leg}", cell(cols[2 + j]), r[leg]["epr"])
    # gamma* and the two time columns
    chk(f"layoutsearch {key} gamma", float(cols[6]),
        round(r["sfc_search"]["best_gamma"], 2))
    for idx, leg in ((7, "sfc_refined"), (8, "sfc_search")):
        chk(f"layoutsearch {key} {leg} t", float(cols[idx]),
            round(r[leg]["seconds"], 1))
    # Delta is PORTER+S against PORTER+R, dashed where they coincide.
    d = num(cols[5])
    want = (None if r["sfc_search"]["epr"] == r["sfc_refined"]["epr"]
            else round(100 * (r["sfc_search"]["epr"] / r["sfc_refined"]["epr"] - 1), 1))
    chk(f"layoutsearch {key} delta", d, want)
_ls_gm = gmean_rows(seg_ls) + [
    [c.strip() for c in l.strip()[:-2].split("&")]
    for l in seg_ls.splitlines() if r"\textbf{gmean, all}" in l]
chk("layoutsearch gmean line count", 4, len(_ls_gm))
for cols, sub in zip(_ls_gm, [[k for k in _LS_ORDER if k[0] == s]
                              for s in ("25", "64", "80")] + [_LS_ORDER]):
    for j, leg in enumerate(("sfc", "sfc_refined", "sfc_search")):
        chk(f"layoutsearch gmean {leg} {len(sub)}", num(cols[1 + j]),
            round(gmean([BY[k][leg]["epr"] for k in sub]), 1))
    R = gmean([BY[k]["sfc_refined"]["epr"] for k in sub])
    S = gmean([BY[k]["sfc_search"]["epr"] for k in sub])
    chk(f"layoutsearch gmean delta {len(sub)}", num(cols[4]),
        round(100 * (S / R - 1), 1))
    for idx, leg in ((6, "sfc_refined"), (7, "sfc_search")):
        chk(f"layoutsearch gmean {leg} t {len(sub)}", num(cols[idx]),
            round(gmean_raw([BY[k][leg]["seconds"] for k in sub]), 2))

# tab:main's W/L/T row: the per-instance record against dSABRE over all 24.
_seg_wlt, _ = rows_of("tab:main", r"^$")
_m = re.search(r"^W/L/T\s*&(.+?)\\\\", _seg_wlt, re.M | re.S)
chk("tab:main has a W/L/T row", True, _m is not None)
if _m:
    _cells = re.findall(r"\{(\d+ / \d+ / \d+)\}", _m.group(1))
    chk("W/L/T cell count", 2, len(_cells))
    for _cell, _leg in zip(_cells, ("sfc", "sfc_refined")):
        w = sum(1 for r in CMP if r[_leg]["epr"] < r["dSE"]["epr"])
        l = sum(1 for r in CMP if r[_leg]["epr"] > r["dSE"]["epr"])
        chk(f"tab:main W/L/T {_leg}", _cell,
            f"{w} / {l} / {len(CMP) - w - l}")

# ----------------------------------------------------------- tab:protocols
# NOT parsed until 2026-09-04.  Its PORTER EPR and time cells had drifted from
# the data (174.9/1.25/0.91 against 175.0/1.63/1.18), and the compile-time
# ratio in it was quoted verbatim by the abstract, the intro and the
# conclusion.  Routes are checked against the live constants, not the tex.
_seg_pr, _rows_pr = rows_of("tab:protocols", r"^\\(dSABRE|PORTER)")
chk("tab:protocols row count", 3, len(_rows_pr))
_d_e = gmean([r["dSE"]["epr"] for r in CMP])
_d_t = gmean_raw([r["dSE"]["seconds"] for r in CMP])
import importlib
sys.path.insert(0, str(_HERE.parent))
_cdr_t = importlib.import_module("compile_porter")
_cr_t = importlib.import_module("compare_routers")
_H = len(_cdr_t.PORTER_HORIZONS)
for cols, (leg, routes) in zip(_rows_pr, (
        ("dSE", 9), ("sfc", _H), ("sfc_refined", _H + _cr_t.PORTER_REFINE_PASSES - 1))):
    e = gmean([r[leg]["epr"] for r in CMP])
    t = gmean_raw([r[leg]["seconds"] for r in CMP])
    chk(f"tab:protocols {leg} routes", cell(cols[1]), routes)
    chk(f"tab:protocols {leg} EPR", num(cols[2]), round(e, 1))
    chk(f"tab:protocols {leg} EPR ratio", num(cols[3]), round(e / _d_e, 2))
    chk(f"tab:protocols {leg} t", num(cols[4]), round(t, 2))
    chk(f"tab:protocols {leg} t ratio", num(cols[5]), round(t / _d_t, 2))

# -------------------------------------------------------------- tab:shared
# The layout-by-router grid: three layout sources x three routers, every cell
# a geometric mean over ALL 24 instances (no source excludes any circuit).
_ROWS = {
    r"\dSABRE{}'s":  ("dSE", "sfc_on_dse_layout", "sfc_on_dse_layout_refined"),
    r"\PORTER{}'s":  ("dSE_on_porter_layout", "sfc", "sfc_refined"),
    r"\texttt{pytket-dqc}'s": ("dSE_pytket", "sfc_pytket", "sfc_pytket_refined"),
}
# Two blocks: (a) all 24, (b) the 18 excluding GHZ/Graphstate.  The blocks
# disagree in every column -- pytket-dqc's partition is the best start in (a)
# and the worst in (b) -- so both are parsed and the split is pinned.
_TRIV = {"ghz", "graphstate"}
_ALL = CMP
_NT = [r for r in CMP if r["circuit"].replace("_OLD_DEEP", "") not in _TRIV]
seg, rows = rows_of("tab:shared", r"^(\\dSABRE|\\PORTER|\\texttt\{pytket)")
chk("layout-grid row count", 6, len(rows))
for blk, (basis, want_n) in enumerate(((_ALL, 24), (_NT, 18))):
    for cols, legs in zip(rows[3 * blk:3 * blk + 3], _ROWS.values()):
        for j_, leg in enumerate(legs):
            vals = [r[leg]["epr"] for r in basis]
            chk(f"layout grid ({'ab'[blk]}) {leg}", num(cols[1 + j_]),
                round(gmean(vals), 1))
            chk(f"layout grid ({'ab'[blk]}) {leg} n", want_n, len(vals))
# The reversal itself: pytket is the column minimum in (a) and the maximum
# in (b), for all three routers.  This is what V-B's argument rests on.
for j_ in range(3):
    a = [num(rows[i][1 + j_]) for i in range(3)]
    b = [num(rows[3 + i][1 + j_]) for i in range(3)]
    chk(f"grid col {j_} pytket best in (a)", a[2], min(a))
    chk(f"grid col {j_} pytket worst in (b)", b[2], max(b))

# ------------------------------------------------------------- tab:scaleup
SU_ORDER = [("100", "qft"), ("100", "qpeexact"), ("200", "qft"),
            ("200", "qpeexact"), ("360", "qft"), ("360", "qpeexact")]
seg, rows = rows_of("tab:scaleup", r"^(QFT|QPEexact)\s*&")
chk("scaleup row count", 6, len(rows))
for key, cols in zip(SU_ORDER, rows):
    r = SU[key]
    chk(f"scaleup {key} cx", cell(cols[1]), r["cx"])
    chk(f"scaleup {key} P", cell(cols[3]), r["physical"])
    chk(f"scaleup {key} K", cell(cols[4]), r["cores"])
    chk(f"scaleup {key} dSE", cell(cols[5]), r["dSE"]["epr"])
    # cols: 0 circ 1 cx 2 n 3 P 4 K 5 dSE-EPR 6 dSE-t 7 sfc-EPR 8 sfc-t.
    # The PORTER+R and PORTER-on-dSABRE-layout columns were removed on
    # 2026-08-31: refinement is measured on the main suite only.
    chk(f"scaleup {key} sfc", cell(cols[7]), r["sfc"]["epr"])
    chk(f"scaleup {key} column count", 9, len(cols))
    # the two time columns must be the COMPLETE protocol cost, not one route
    for idx, leg in ((6, "dSE"), (8, "sfc")):
        chk(f"scaleup {key} {leg} time", float(cols[idx]),
            round(r[leg]["seconds"], 1))

# ------------------------------------------------------------ tab:heavyhex
O9 = ["ae", "ghz", "graphstate", "qft", "qnn", "random", "qpeexact",
      "qaoa", "multiplier"]
seg, rows = rows_of("tab:heavyhex", r"^(ring|star)\s")
# Two summary rows since 2026-09-01: the star-Multiplier callout went with the
# livelock discussion, and PORTER-on-dSABRE's-layout became a third column --
# the fixed-layout control V-E's layout claim rests on.
chk("heavyhex summary row count", 2, len(rows))
HH_LEGS = ("dSE", "porter", "porter_on_dse")
for cols in rows:
    lab = cols[0].strip()
    topo = lab.split()[0]
    n = int(re.search(r"\((\d+)\)", lab).group(1))
    chk(f"heavyhex summary basis {lab}", n, len(O9))
    chk(f"heavyhex summary {lab} column count", 4, len(cols))
    for j, leg in enumerate(HH_LEGS):
        vals = [(HH[(topo, c)].get(leg) or {}).get("epr") for c in O9]
        got = round(gmean(vals), 1) if all(vals) else None
        chk(f"heavyhex summary {lab} {leg}", num(cols[1 + j]), got)
# V-E's claim: from dSABRE's own candidates PORTER is lowest on BOTH rows.
for cols in rows:
    chk(f"heavyhex {cols[0].strip()} control is lowest", num(cols[3]),
        min(num(cols[1]), num(cols[2]), num(cols[3])))

seg, rows = rows_of("tab:heavyhex", r"^(ring|star)\s*&", APP)
chk("heavyhex per-circuit row count", 18, len(rows))
APP_HH_LEGS = ("dSE", "porter", "porter_on_dse")
for cols in rows:
    key = (cols[0], cols[1])
    r = HH[key]
    chk(f"heavyhex {key} column count", 5, len(cols))
    for j, leg in enumerate(APP_HH_LEGS):
        chk(f"heavyhex {key} {leg}", cell(cols[2 + j]), (r.get(leg) or {}).get("epr"))

# ------------------------------------------------------------ tab:ablation
# 80q only since 2026-08-31, and the Suite column is gone with it, so rows now
# start with the circuit name.  The 25q/64q suites are still ablated and the
# cross-scale trend is pinned in verify_paper_numbers; it is just not tabulated.
_ABL80 = ["ae", "qft", "qnn", "random", "qpeexact", "qaoa", "multiplier"]
seg, rows = rows_of("tab:ablation", r"^(%s)\s*&" % "|".join(_ABL80))
chk("ablation row count", 7, len(rows))
chk("ablation rows are the 80q non-trivial set", _ABL80,
    [c[0].strip() for c in rows])
for cols in rows:
    key = ("80", cols[0].strip())
    a, t_ = ABL[key]["out"], TD[key]["out"]
    chk(f"ablation {key} column count", 7, len(cols))
    chk(f"ablation {key} full", cell(cols[1]), (a.get("full") or {}).get("epr"))
    chk(f"ablation {key} nopk", cell(cols[2]), (a.get("no_packets") or {}).get("epr"))
    chk(f"ablation {key} norel", cell(cols[3]), (a.get("no_relief") or {}).get("epr"))
    chk(f"ablation {key} teledata", cell(cols[4]),
        (t_.get("teledata_only_relief") or {}).get("epr"))
    # The double dagger must mark exactly the cells where strict removal failed.
    chk(f"ablation {key} relief-tier marker", "ddagger" in cols[4],
        (t_.get("teledata_only") or {}).get("epr") is None
        and (t_.get("teledata_only_relief") or {}).get("epr") is not None)
    chk(f"ablation {key} pk", cell(cols[5]), (t_.get("full") or {}).get("packets"))
    chk(f"ablation {key} tg", cell(cols[6]), (t_.get("full") or {}).get("telegates"))

# Summary lines: each carries one Full value plus whichever comparison columns
# share its basis, and $n$ states that basis.  All are over the 80q suite.
_ORD = ["ae", "ghz", "graphstate", "qft", "qnn", "random",
        "qpeexact", "qaoa", "multiplier"]
def _abl_cols(k):
    a_, t_ = ABL[k]["out"], TD[k]["out"]
    ep = lambda d, x: (d.get(x) or {}).get("epr")
    return (ep(a_, "full"), ep(a_, "no_packets"), ep(a_, "no_relief"),
            ep(t_, "teledata_only_relief"))
_, _sum_lines = rows_of("tab:ablation", r"^\\textbf\{gmean\}")
chk("ablation summary line count", 3, len(_sum_lines))
for cols in _sum_lines:
    m = re.search(r"\$n\{=\}(\d+)\$", cols[0])
    chk(f"ablation summary label parses: {cols[0][:40]}", True, m is not None)
    if not m:
        continue
    grp, n = "80", int(m.group(1))
    ks = [(grp, c) for c in _ORD if (grp, c) in ABL]
    for j in (1, 2, 3):
        got = num(cols[1 + j])
        if got is None:
            continue
        basis = [k for k in ks if _abl_cols(k)[j] is not None
                 and _abl_cols(k)[0] is not None]
        chk(f"ablation summary {grp} col{j} basis", n, len(basis))
        chk(f"ablation summary {grp} col{j}", got,
            round(gmean([_abl_cols(k)[j] for k in basis]), 1))
        chk(f"ablation summary {grp} col{j} full", num(cols[1]),
            round(gmean([_abl_cols(k)[0] for k in basis]), 1))

if fails:
    print(f"{len(fails)} TEX/DATA MISMATCHES:")
    print("\n".join(fails))
    sys.exit(1)
print("paper tables agree with the results files")
