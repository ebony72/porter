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

# -------------------------------------------------------------- tab:shared
# The layout-by-router grid: three layout sources x three routers, every cell
# a geometric mean over ALL 24 instances (no source excludes any circuit).
_ROWS = {
    r"\dSABRE{}'s":  ("dSE", "sfc_on_dse_layout", "sfc_on_dse_layout_refined"),
    r"\PORTER{}'s":  ("dSE_on_porter_layout", "sfc", "sfc_refined"),
    r"\texttt{pytket-dqc}'s": ("dSE_pytket", "sfc_pytket", "sfc_pytket_refined"),
}
seg, rows = rows_of("tab:shared", r"^(\\dSABRE|\\PORTER|\\texttt\{pytket)")
chk("layout-grid row count", 3, len(rows))
for cols, legs in zip(rows, _ROWS.values()):
    for j_, leg in enumerate(legs):
        vals = [r[leg]["epr"] for r in CMP]
        chk(f"layout grid {leg}", num(cols[1 + j_]), round(gmean(vals), 1))
        chk(f"layout grid {leg} n", 24, len(vals))

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
# The "star (8)" row exists only while PORTER fails star/Multiplier under its
# own layout; horizon selection routes it, so the expected count follows the
# data rather than being hardcoded.
_star_incomplete = any(
    (r.get("porter") or {}).get("epr") is None
    for r in json.load(open(_res("heavyhex"))) if r["topology"] == "star")
# The regex also matches the "star Multiplier" callout row, hence the +1.
chk("heavyhex summary row count", 4 if _star_incomplete else 3, len(rows))
# Own layout, own protocol only since 2026-08-31; the fixed-layout control
# and the per-circuit rows are in the appendix, and no PORTER+R column
# appears in either -- refinement is measured on the main suite alone.
HH_LEGS = ("dSE", "porter")
for cols in rows:
    lab = cols[0].strip()
    if "Multiplier" in lab:
        r = HH[("star", "multiplier")]
        chk("heavyhex star mult dSE", cell(cols[1]), r["dSE"]["epr"])
        chk("heavyhex star mult porter", cell(cols[2]), r["porter"]["epr"])
        chk("heavyhex star mult column count", 3, len(cols))
        continue
    topo = lab.split()[0]
    n = int(re.search(r"\((\d+)\)", lab).group(1))
    circs = O9 if n == 9 else [c for c in O9 if c != "multiplier"]
    chk(f"heavyhex summary basis {lab}", n, len(circs))
    for j, leg in enumerate(HH_LEGS):
        vals = [(HH[(topo, c)].get(leg) or {}).get("epr") for c in circs]
        got = round(gmean(vals), 1) if all(vals) else None
        chk(f"heavyhex summary {lab} {leg}", num(cols[1 + j]), got)

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
# Per-circuit rows are 80q only; 25q and 64q appear as one summary line each,
# and those lines are checked separately below.
seg, rows = rows_of("tab:ablation", r"^\d\dq\s*&")
chk("ablation row count", 7, len(rows))
chk("ablation rows are 80q only", {"80q"}, {c[0].strip() for c in rows})
for cols in rows:
    key = (cols[0].replace("q", ""), cols[1])
    a, t = ABL[key]["out"], TD[key]["out"]
    # The Hop-wise (plan-commitment) column was removed on 2026-08-31.
    chk(f"ablation {key} column count", 8, len(cols))
    chk(f"ablation {key} full", cell(cols[2]), (a.get("full") or {}).get("epr"))
    chk(f"ablation {key} nopk", cell(cols[3]), (a.get("no_packets") or {}).get("epr"))
    chk(f"ablation {key} norel", cell(cols[4]), (a.get("no_relief") or {}).get("epr"))
    chk(f"ablation {key} teledata", cell(cols[5]),
        (t.get("teledata_only_relief") or {}).get("epr"))
    # The double dagger must mark exactly the cells where strict removal failed.
    chk(f"ablation {key} relief-tier marker", "ddagger" in cols[5],
        (t.get("teledata_only") or {}).get("epr") is None
        and (t.get("teledata_only_relief") or {}).get("epr") is not None)

    chk(f"ablation {key} pk", cell(cols[6]), (t.get("full") or {}).get("packets"))
    chk(f"ablation {key} tg", cell(cols[7]), (t.get("full") or {}).get("telegates"))


# Summary lines of tab:ablation.  Each carries one Full value plus whichever
# comparison columns share its basis, and $n$ states that basis; a line is
# checked against a gmean over EVERY circuit of the group that the compared
# columns complete.  The line count is pinned so a relabelled table fails
# rather than matching nothing.
_ORD = ["ae", "ghz", "graphstate", "qft", "qnn", "random",
        "qpeexact", "qaoa", "multiplier"]
def _abl_cols(k):
    a_, t_ = ABL[k]["out"], TD[k]["out"]
    ep = lambda d, x: (d.get(x) or {}).get("epr")
    return (ep(a_, "full"), ep(a_, "no_packets"), ep(a_, "no_relief"),
            ep(t_, "teledata_only_relief"))
_, _sum_lines = rows_of("tab:ablation", r"^\\multicolumn\{2\}")
chk("ablation summary line count", 9, len(_sum_lines))
for cols in _sum_lines:
    lab = cols[0]
    m = re.search(r"\{(?:\\textbf\{)?(all|\d\d)q?\}?, \$n\{=\}(\d+)\$", lab)
    chk(f"ablation summary label parses: {lab[:40]}", True, m is not None)
    if not m:
        continue
    grp, n = m.group(1), int(m.group(2))
    ks = [(s_, c) for s_ in (("25", "64", "80") if grp == "all" else (grp,))
          for c in _ORD if (s_, c) in ABL]
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
