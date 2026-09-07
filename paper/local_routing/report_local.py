"""Read the local-routing ablation and report per-arm gmeans and records."""
import sys, json, math, collections
from pathlib import Path as _P
_ROOT = _P(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "paper" / "horizon_sweep"))
import hz_common as H

PATH = "/private/tmp/claude-504/-Users-sanjiangli-Documents-pyzoo-SFC/198b52a7-cff4-4249-bd07-be4853d9b249/scratchpad/local_ablation.jsonl"
import os
ARMS = os.environ.get("ARMS", "porter,percore,decay,percore_decay,dsabre,dsabre_w025").split(",")
SEL = os.environ.get("SEL", "0") == "1"

rows = collections.defaultdict(dict)
for line in open(PATH):
    if line.strip():
        r = json.loads(line)
        if bool(r.get("selection")) == SEL:
            rows[r["key"]][r["arm"]] = r

def gmean(xs):
    xs = [max(float(x), 1.0) for x in xs]
    return math.exp(sum(map(math.log, xs))/len(xs)) if xs else float("nan")

GROUPS = ["main25", "main64", "main80", "scaleup", "heavyhexring", "heavyhexstar"]
def grp(k):
    a, b, _ = k.split("/")
    return a if a == "scaleup" else a + b

print(f"{'group':14s} {'n':>3s} " + " ".join(f"{a:>13s}" for a in ARMS))
for g in GROUPS + ["ALL"]:
    keys = [k for k in rows if (g == "ALL" or grp(k) == g)]
    # basis: instances where every arm completed
    basis = [k for k in keys if all(rows[k].get(a, {}).get("epr") is not None for a in ARMS)]
    if not basis:
        continue
    base = gmean([rows[k]["porter"]["epr"] for k in basis])
    cells = []
    for a in ARMS:
        v = gmean([rows[k][a]["epr"] for k in basis])
        cells.append(f"{v:7.1f}({100*(v/base-1):+5.1f}%)" if a != "porter" else f"{v:13.1f}")
    print(f"{g:14s} {len(basis):3d} " + " ".join(cells))

print()
print("completion (of 48):", {a: sum(1 for k in rows if rows[k].get(a,{}).get("epr") is not None)
                              for a in ARMS})
print("failures:")
for a in ARMS:
    bad = [(k, rows[k][a]["status"]) for k in rows
           if a in rows[k] and rows[k][a].get("epr") is None]
    if bad:
        print(f"  {a}: {bad}")

print()
print("W/L/T vs porter (all instances both complete):")
for a in ARMS[1:]:
    w = l = t = 0
    for k in rows:
        p, q = rows[k].get("porter",{}).get("epr"), rows[k].get(a,{}).get("epr")
        if p is None or q is None: continue
        if q < p: w += 1
        elif q > p: l += 1
        else: t += 1
    print(f"  {a:14s} {w:2d}W / {l:2d}L / {t:2d}T")

print()
tot = {a: sum(rows[k][a]["seconds"] for k in rows if rows[k].get(a,{}).get("epr") is not None)
       for a in ARMS}
print("wall time on completing routes:", {a: f"{v:.0f}s" for a, v in tot.items()})

print()
print("per-instance EPR (non-trivial only):")
print(f"{'instance':26s} " + " ".join(f"{a:>8s}" for a in ARMS))
for k in sorted(rows, key=lambda k: (grp(k), k)):
    if H.is_trivial(k): continue
    cells = []
    for a in ARMS:
        e = rows[k].get(a, {}).get("epr")
        cells.append(f"{e:8d}" if e is not None else f"{rows[k].get(a,{}).get('status','-')[:8]:>8s}")
    print(f"{k:26s} " + " ".join(cells))
