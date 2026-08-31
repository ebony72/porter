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
PC = {(r["suite"], r["circuit"]): r
      for r in json.load(open(_HERE / "plan_commitment_results.json"))}

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
for cols in gmean_rows(seg):
    n = int(re.search(r"\((\d+)\)", cols[0]).group(1))
    suite = {6: "25", 8: "64", 3: "80"}[n]
    conv = [k for k in BY if k[0] == suite and (BY[k].get("telesabre") or {}).get("epr")]
    chk(f"main gmean n {suite}", n, len(conv))
    for j, leg in enumerate(("telesabre", "dSE", "sfc", "sfc_refined")):
        chk(f"main gmean {suite} {leg}", num(cols[1 + j]),
            round(gmean([BY[k][leg]["epr"] for k in conv]), 1))

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
seg, rows = rows_of("tab:ablation", r"^\d\dq\s*&")
chk("ablation row count", 12, len(rows))
for cols in rows:
    key = (cols[0].replace("q", ""), cols[1])
    a, t, c = ABL[key]["out"], TD[key]["out"], PC[key]["out"]
    chk(f"ablation {key} full", cell(cols[2]), (a.get("full") or {}).get("epr"))
    chk(f"ablation {key} nopk", cell(cols[3]), (a.get("no_packets") or {}).get("epr"))
    chk(f"ablation {key} norel", cell(cols[4]), (a.get("no_relief") or {}).get("epr"))
    chk(f"ablation {key} hopwise", cell(cols[5]), (c.get("hopwise") or {}).get("epr"))
    chk(f"ablation {key} teledata", cell(cols[6]),
        (t.get("teledata_only_relief") or {}).get("epr"))
    chk(f"ablation {key} pk", cell(cols[7]), (t.get("full") or {}).get("packets"))
    chk(f"ablation {key} tg", cell(cols[8]), (t.get("full") or {}).get("telegates"))

if fails:
    print(f"{len(fails)} TEX/DATA MISMATCHES:")
    print("\n".join(fails))
    sys.exit(1)
print("paper tables agree with the results files")
