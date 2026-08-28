"""Parse the LaTeX tables in sfc.tex and check them against the results JSONs.

verify_paper_numbers.py encodes what the paper is *supposed* to say; this
reads the rows LaTeX will actually typeset, so a typo made while editing the
.tex cannot sail past. Covers the five data tables of the main paper:
tab:main, tab:shared, tab:scaleup, tab:heavyhex, tab:ablation.
"""
import json
import math
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
TEX = (_HERE / "sfc.tex").read_text()
APP = (_HERE / "sfc_appendix.tex").read_text()
CMP = json.load(open(_HERE / "compare_results.json"))
BY = {(r["suite"], "qnn" if r["circuit"].startswith("qnn") else r["circuit"]): r
      for r in CMP}
HH = {(r["topology"], r["circuit"]): r
      for r in json.load(open(_HERE / "heavyhex_results.json"))}
SU = {(r["suite"], r["circuit"]): r
      for r in json.load(open(_HERE / "scaleup_results.json"))}
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
    return math.exp(sum(math.log(max(x, 1)) for x in v) / len(v))


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
seg, rows = rows_of("tab:main", r"^\d\dq\s*&")
chk("main row count", 24, len(rows))
for cols in rows:
    key = (cols[0].replace("q", ""), cols[1])
    r = BY[key]
    for j, leg in enumerate(("telesabre", "dSE", "sfc", "sfc_refined")):
        chk(f"main {key} {leg}", cell(cols[2 + j]), (r.get(leg) or {}).get("epr"))
    ts, rf = (r.get("telesabre") or {}).get("epr"), r["sfc_refined"]["epr"]
    chk(f"main {key} dTS", num(cols[6]),
        round(100 * (rf - ts) / ts, 1) if ts else None)
for cols in gmean_rows(seg):
    n = int(re.search(r"\((\d+)\)", cols[0]).group(1))
    suite = {6: "25", 8: "64", 3: "80"}[n]
    conv = [k for k in BY if k[0] == suite and (BY[k].get("telesabre") or {}).get("epr")]
    chk(f"main gmean n {suite}", n, len(conv))
    for j, leg in enumerate(("telesabre", "dSE", "sfc", "sfc_refined")):
        chk(f"main gmean {suite} {leg}", num(cols[1 + j]),
            round(gmean([BY[k][leg]["epr"] for k in conv]), 1))

# -------------------------------------------------------------- tab:shared
# The main paper carries per-suite gmeans; the per-circuit rows live in the
# appendix, and both are checked.
seg, rows = rows_of("tab:shared", r"^(\d\dq|\\textbf\{all\})\s*\(")
chk("shared summary row count", 4, len(rows))
ts_all = [r for r in CMP if (r.get("telesabre") or {}).get("epr")]
for cols in rows:
    lab = cols[0]
    n = int(re.search(r"\((\d+)\)", lab).group(1))
    suite = None if "all" in lab else lab.split("q")[0]
    sub = [r for r in ts_all if suite is None or r["suite"] == suite]
    chk(f"shared summary n {lab}", n, len(sub))
    G = lambda leg: round(gmean([r[leg]["epr"] for r in sub]), 1)
    chk(f"shared summary {lab} TS", num(cols[1]), G("telesabre"))
    chk(f"shared summary {lab} dSE", num(cols[2]), G("dSE_shared"))
    chk(f"shared summary {lab} P+R", num(cols[4]), G("sfc_shared_refined"))

seg, rows = rows_of("tab:shared-full", r"^\d\dq\s*&", APP) if "tab:shared-full" in APP \
    else rows_of("tab:shared", r"^\d\dq\s*&", APP)
chk("shared per-circuit row count", 17, len(rows))
for cols in rows:
    key = (cols[0].replace("q", ""), cols[1])
    r = BY[key]
    chk(f"shared {key} TS", cell(cols[2]), r["telesabre"]["epr"])
    chk(f"shared {key} dSE", cell(cols[4]), r["dSE_shared"]["epr"])
    chk(f"shared {key} P", cell(cols[7]), r["sfc_shared"]["epr"])
    chk(f"shared {key} P+R", cell(cols[8]), r["sfc_shared_refined"]["epr"])

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
    for j, leg in enumerate(("sfc", "sfc_refined", "sfc_on_dse_layout",
                             "sfc_on_dse_layout_refined")):
        chk(f"scaleup {key} {leg}", cell(cols[7 + j]), r[leg]["epr"])

# ------------------------------------------------------------ tab:heavyhex
O9 = ["ae", "ghz", "graphstate", "qft", "qnn", "random", "qpeexact",
      "qaoa", "multiplier"]
seg, rows = rows_of("tab:heavyhex", r"^(ring|star)\s")
chk("heavyhex summary row count", 4, len(rows))
HH_LEGS = ("dSE", "porter", "porter_refined", "porter_on_dse",
           "porter_on_dse_refined")
for cols in rows:
    lab = cols[0].strip()
    if "Multiplier" in lab:
        r = HH[("star", "multiplier")]
        chk("heavyhex star mult dSE", cell(cols[1]), r["dSE"]["epr"])
        chk("heavyhex star mult P/dS", cell(cols[4]), r["porter_on_dse"]["epr"])
        chk("heavyhex star mult P+R/dS", cell(cols[5]),
            r["porter_on_dse_refined"]["epr"])
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
for cols in rows:
    key = (cols[0], cols[1])
    r = HH[key]
    for j, leg in enumerate(HH_LEGS):
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
print("sfc.tex tables agree with the results files")
