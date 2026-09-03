"""Report: what the revisit block rescues, and what it does to healthy routes."""
import json, math, collections
from pathlib import Path
HERE = Path(__file__).resolve().parent
G = [json.loads(l) for l in (HERE/'horizon_grid.jsonl').read_text().splitlines() if l.strip()]
SUM = {(r['key'], r['L']): r for r in G if r['arm'] == 'base'}
R = [json.loads(l) for l in (HERE/'revisit_cells.jsonl').read_text().splitlines() if l.strip()]
FM = {}
fmp = HERE/'freeze_modes.jsonl'
if fmp.exists():
    FM = {(r['key'], r['L']): r['mode'] for r in
          (json.loads(l) for l in fmp.read_text().splitlines() if l.strip())}

def gm(v): return math.exp(sum(math.log(max(x, 1)) for x in v)/len(v))

print(f"=== revisit block on the {len(R)} cells the shipped scorer fails ===\n")
resc = [r for r in R if r['block']['status'] == 'completed']
notr = [r for r in R if r['block']['status'] != 'completed']
print(f"rescued: {len(resc)}   still failing: {len(notr)}   of {len(R)}\n")
by = collections.Counter()
for r in R:
    key = (r['key'], r['block']['L'])
    by[(FM.get(key, '?'), r['block']['status'] == 'completed')] += 1
print("by the failure mode hz_freeze.py assigned:")
for mode in sorted({m for m, _ in by}):
    ok, no = by[(mode, True)], by[(mode, False)]
    print(f"  {mode:18s} rescued {ok:2d} / {ok+no:2d}")
print("\nnot rescued:")
for r in notr:
    print(f"  {r['key']:28s} L={r['block']['L']:4d}  mode={FM.get((r['key'],r['block']['L']),'?')}")
print("\nrescued cells (EPR of the newly available route vs the instance's shipped-protocol best):")
def shipped_best(k):
    v = [SUM[(k, L)]['epr'] for L in (4, 8, 16, 128)
         if (k, L) in SUM and SUM[(k, L)]['status'] == 'completed']
    return min(v) if v else None
better = 0
for r in sorted(resc, key=lambda r: r['key']):
    b = shipped_best(r['key']); e = r['block']['epr']
    mark = ''
    if b is not None and e < b:
        mark = f'   <- beats the shipped best ({b})'; better += 1
    print(f"  {r['key']:28s} L={r['block']['L']:4d}  epr={e:6d}  shipped best={b}{mark}")
print(f"\n{better} rescued routes beat their instance's shipped-protocol result.")

hp = HERE/'revisit_healthy16.jsonl'
if hp.exists():
    H = [json.loads(l) for l in hp.read_text().splitlines() if l.strip()]
    same = sum(1 for r in H if r['block'].get('sha') and r['block']['sha'] == r['plain'].get('sha'))
    eprsame = sum(1 for r in H if r['block'].get('epr') == r['plain'].get('epr'))
    bad = [r for r in H if r['block']['status'] != 'completed' and r['plain']['status'] == 'completed']
    print(f"\n=== effect on healthy routes (every instance at the configured L=16, n={len(H)}) ===")
    print(f"  byte-identical op stream: {same}/{len(H)}")
    print(f"  identical EPR:            {eprsame}/{len(H)}")
    print(f"  broken by the flag:       {len(bad)}")
    diff = [r for r in H if r['block'].get('epr') != r['plain'].get('epr')]
    for r in diff:
        print(f"    {r['key']:28s} plain={r['plain'].get('epr')} block={r['block'].get('epr')}")
    if H:
        a = [r['plain']['epr'] for r in H if r['plain']['status'] == 'completed'
             and r['block']['status'] == 'completed']
        b = [r['block']['epr'] for r in H if r['plain']['status'] == 'completed'
             and r['block']['status'] == 'completed']
        print(f"  gmean EPR at L=16: plain {gm(a):.1f}  block {gm(b):.1f}")
