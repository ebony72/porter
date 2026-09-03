"""Report: normalised vs summed lookahead, over the horizon grid."""
import json, math, sys, collections
from pathlib import Path
HERE=Path(__file__).resolve().parent
G=[json.loads(l) for l in (HERE/'horizon_grid.jsonl').read_text().splitlines() if l.strip()]
S=[json.loads(l) for l in (HERE/'scale_cells.jsonl').read_text().splitlines() if l.strip()]
SUM={(r['key'],r['L']):r for r in G if r['arm']=='base'}
ARMS=collections.defaultdict(dict)
for r in S: ARMS[r['arm']][(r['key'],r['L'])]=r
Ls=[4,8,16,32,64,128,256]
TRIV=('ghz','graphstate')
keys=sorted({k for k,_ in SUM})
nont=[k for k in keys if k.split('/')[2] not in TRIV]
def gm(v): return math.exp(sum(math.log(max(x,1)) for x in v)/len(v))
def suite(k):
    a,b,_=k.split('/'); return a if a=='scaleup' else a+b

for arm in sorted(ARMS):
    A=ARMS[arm]
    cells=[(k,L) for (k,L) in A if L in Ls]
    print(f"\n{'='*78}\narm {arm}  ({len(cells)} cells)\n{'='*78}")
    fs=sum(1 for c in cells if A[c]['status']!='completed')
    fb=sum(1 for c in cells if c in SUM and SUM[c]['status']!='completed')
    print(f"non-completions on the same cells:   sum {fb:3d}   {arm} {fs:3d}")
    bad=[(k,L) for (k,L) in cells if A[(k,L)]['status']!='completed']
    if bad: print("  still failing:", ", ".join(f"{k}@{L}" for k,L in sorted(bad)))
    ver=collections.Counter(str(A[c].get('verified')) for c in cells if A[c]['status']=='completed')
    print("  replay verification:",dict(ver))

    print(f"\n  per-horizon completion and gmean EPR (non-trivial instances, n={len(nont)})")
    print(f"  {'L':>5} | {'sum done':>9}{'gmean':>9} | {arm+' done':>10}{'gmean':>9}")
    for L in Ls:
        a=[SUM[(k,L)]['epr'] for k in nont if (k,L) in SUM and SUM[(k,L)]['status']=='completed']
        b=[A[(k,L)]['epr'] for k in nont if (k,L) in A and A[(k,L)]['status']=='completed']
        if not b: continue
        print(f"  {L:5d} | {len(a):9d}{gm(a):9.1f} | {len(b):10d}{gm(b):9.1f}")

    # protocol level: best-of-4 {4,8,16,128} within each arm, and the cross portfolio
    def best(src,k,hz):
        v=[src[(k,L)]['epr'] for L in hz if (k,L) in src and src[(k,L)]['status']=='completed']
        return min(v) if v else None
    HZ=[4,8,16,128]
    rows=[]
    for k in nont:
        a=best(SUM,k,HZ); b=best(A,k,HZ)
        rows.append((k,a,b))
    ok=[r for r in rows if r[1] and r[2]]
    print(f"\n  shipped protocol basis: best of {HZ}   (n={len(ok)} where both complete)")
    print(f"    sum   gmean {gm([r[1] for r in ok]):8.1f}")
    print(f"    {arm:5s} gmean {gm([r[2] for r in ok]):8.1f}   "
          f"({100*(gm([r[2] for r in ok])/gm([r[1] for r in ok])-1):+.1f}%)")
    w=sum(1 for r in ok if r[2]<r[1]); l=sum(1 for r in ok if r[2]>r[1])
    print(f"    per instance: {w} better / {l} worse / {len(ok)-w-l} tied")
    bys=collections.defaultdict(list)
    for r in ok: bys[suite(r[0])].append(r)
    print(f"    {'suite':12s}{'n':>4}{'sum':>9}{'  '+arm:>9}{'delta':>9}")
    for s in sorted(bys):
        rr=bys[s]; ga=gm([x[1] for x in rr]); gb=gm([x[2] for x in rr])
        print(f"    {s:12s}{len(rr):4d}{ga:9.1f}{gb:9.1f}{100*(gb/ga-1):+8.1f}%")
    # how many routes does each arm need?
    print(f"\n  how flat is the arm?  gmean of best-of-N, N candidates from {Ls}")
    for hz in ([16],[16,128],[4,16,128],[4,8,16,128],Ls):
        v=[best(A,k,hz) for k in nont]
        if all(v): print(f"    {str(hz):28s} {gm(v):8.1f}")
        else:
            miss=[k for k,x in zip(nont,v) if not x]
            print(f"    {str(hz):28s}   incomplete on {miss}")
