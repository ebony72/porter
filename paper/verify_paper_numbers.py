"""Cross-verify every number in sfc.tex tables and headline claims against
compare_results.json / action_mix_results.json / ../ablation_results.json.
Expected values below mirror the paper; rerun after any harness refresh."""
import json
import math

BASE = "/Users/sanjiangli/Documents/pyzoo/SFC"
cmp_rows = json.load(open(f"{BASE}/paper/compare_results.json"))
mix_rows = json.load(open(f"{BASE}/paper/action_mix_results.json"))
abl_rows = json.load(open(f"{BASE}/ablation_results.json"))

def norm(c):
    return "qnn" if c.startswith("qnn") else c

by = {(r["suite"], norm(r["circuit"])): r for r in cmp_rows}
mix_by = {(r["suite"], norm(r["circuit"])): r for r in mix_rows}
abl_by = {(r["suite"], norm(r["circuit"])): r for r in abl_rows}

fails = []


def check(label, expected, actual, tol=0.05001):
    if expected is None and actual is None:
        return
    ok = (
        expected is not None
        and actual is not None
        and (
            (isinstance(expected, str) and str(actual) == expected)
            or (
                not isinstance(expected, str)
                and abs(float(actual) - float(expected)) <= tol
            )
        )
    )
    if not ok:
        fails.append(f"  MISMATCH {label}: paper={expected} data={actual}")


def gmean(vals):
    return math.exp(sum(math.log(v) for v in vals) / len(vals))


def pct(new, old):
    return 100.0 * (new - old) / old


# ------------------------------------------------------------------ main25/64/80
# paper: circuit -> (TS_epr, TS_swap, dSE_epr, dSE_swap, P_epr, P_swap, delta)
main25 = {
    "ae":         (118, 370, 68, 395, 65, 328, -44.9),
    "ghz":        (11, 30, 4, 17, 4, 29, -63.6),
    "graphstate": (17, 43, 7, 24, 7, 34, -58.8),
    "qft":        (141, 371, 89, 427, 74, 327, -47.5),
    "qnn":        (357, 770, 153, 761, 119, 642, -66.7),
    "random":     (632, 1512, 417, 1438, 401, 1327, -36.6),
}
main64 = {
    "ae":         (323, 1508, 262, 2016, 177, 1627, -45.2),
    "ghz":        (11, 111, 9, 73, 6, 86, -45.5),
    "graphstate": (76, 379, 18, 103, 20, 131, -73.7),
    "qft":        (410, 1872, 258, 2295, 262, 1846, -36.1),
    "qnn":        (1365, 6292, 509, 8610, 864, 6595, -36.7),
    "random":     (None, None, 770, 4077, 737, 4048, None),
}
main80 = {
    "ae":         (None, None, 513, 3441, 490, 3156, None),
    "ghz":        (19, 172, 10, 93, 7, 115, -63.2),
    "graphstate": (88, 521, 25, 144, 28, 198, -68.2),
    "qft":        (None, None, 349, 2630, 446, 2968, None),
    "qnn":        (None, None, 869, 13500, 1517, 10920, None),
    "random":     (None, None, None, None, 11040, 62119, None),
}

for suite, table in (("25", main25), ("64", main64), ("80", main80)):
    for circ, (tse, tss, dse, dss, pe, ps, delta) in table.items():
        r = by[(suite, circ)]
        ts, dS, sf = r.get("telesabre") or {}, r.get("dSE") or {}, r.get("sfc") or {}
        check(f"main{suite} {circ} TS epr", tse, ts.get("epr"))
        check(f"main{suite} {circ} TS swap", tss, ts.get("swaps"))
        check(f"main{suite} {circ} dSE epr", dse, dS.get("epr"))
        check(f"main{suite} {circ} dSE swap", dss, dS.get("swaps"))
        check(f"main{suite} {circ} P epr", pe, sf.get("epr"))
        check(f"main{suite} {circ} P swap", ps, sf.get("swaps"))
        if delta is not None:
            check(f"main{suite} {circ} deltaTS", delta,
                  round(pct(sf["epr"], ts["epr"]), 1))

# gmeans (own protocol): 25q over 6; 64q over the 5 TS completes; 80q over 2
def own(suite, routers, circs):
    out = {}
    for name in routers:
        vals = [by[(suite, c)][name]["epr"] for c in circs]
        out[name] = gmean(vals)
    return out

g25 = own("25", ("telesabre", "dSE", "sfc"),
          ["ae", "ghz", "graphstate", "qft", "qnn", "random"])
check("gmean25 TS", 94.3, round(g25["telesabre"], 1))
check("gmean25 dSE", 47.0, round(g25["dSE"], 1))
check("gmean25 P", 43.1, round(g25["sfc"], 1))
check("gmean25 delta", -54.3, round(pct(g25["sfc"], g25["telesabre"]), 1))

c64 = ["ae", "ghz", "graphstate", "qft", "qnn"]
g64 = own("64", ("telesabre", "dSE", "sfc"), c64)
check("gmean64 TS", 172.1, round(g64["telesabre"], 1))
check("gmean64 dSE", 89.0, round(g64["dSE"], 1))
check("gmean64 P", 86.4, round(g64["sfc"], 1))
check("gmean64 delta", -49.8, round(pct(g64["sfc"], g64["telesabre"]), 1))

g80 = own("80", ("telesabre", "dSE", "sfc"), ["ghz", "graphstate"])
check("gmean80(2) TS", 40.9, round(g80["telesabre"], 1))
check("gmean80(2) dSE", 15.8, round(g80["dSE"], 1))
check("gmean80(2) P", 14.0, round(g80["sfc"], 1))
check("gmean80(2) delta", -65.8, round(pct(g80["sfc"], g80["telesabre"]), 1))

# 80q five-circuit basis dSABRE completes (user's question)
c80d = ["ae", "ghz", "graphstate", "qft", "qnn"]
g80d = own("80", ("dSE", "sfc"), c80d)
check("gmean80(5) dSE", 131.2, round(g80d["dSE"], 1))
check("gmean80(5) P", 145.4, round(g80d["sfc"], 1))

# completion counts
ts_done = sum(1 for r in cmp_rows if r.get("telesabre") and r["telesabre"].get("epr"))
dse_done = sum(1 for r in cmp_rows if r.get("dSE") and r["dSE"].get("epr"))
p_done = sum(1 for r in cmp_rows if r.get("sfc") and r["sfc"].get("epr"))
check("completions TS", 13, ts_done)
check("completions dSE", 17, dse_done)
check("completions P", 18, p_done)

# ------------------------------------------------------------------ shared table
shared = {
    ("25", "ae"):         (77, 393, -34.7, 62, 267, -47.5),
    ("25", "ghz"):        (8, 33, -27.3, 6, 26, -45.5),
    ("25", "graphstate"): (10, 37, -41.2, 14, 57, -17.6),
    ("25", "qft"):        (89, 410, -36.9, 96, 343, -31.9),
    ("25", "qnn"):        (177, 818, -50.4, 158, 707, -55.7),
    ("25", "random"):     (439, 1529, -30.5, 412, 1392, -34.8),
    ("64", "ae"):         (183, 1963, -43.3, 233, 1753, -27.9),
    ("64", "ghz"):        (8, 124, -27.3, 8, 104, -27.3),
    ("64", "graphstate"): (32, 167, -57.9, 49, 289, -35.5),
    ("64", "qft"):        (228, 2104, -44.4, 227, 1668, -44.6),
    ("64", "qnn"):        (544, 8250, -60.1, 679, 5963, -50.3),
    ("80", "ghz"):        (15, 173, -21.1, 11, 156, -42.1),
    ("80", "graphstate"): (55, 306, -37.5, 71, 402, -19.3),
}
for (suite, circ), (de, ds, dd, pe, ps, pd) in shared.items():
    r = by[(suite, circ)]
    ts = r["telesabre"]["epr"]
    dS, sf = r["dSE_shared"], r["sfc_shared"]
    check(f"shared {suite} {circ} dSE epr", de, dS["epr"])
    check(f"shared {suite} {circ} dSE swap", ds, dS["swaps"])
    check(f"shared {suite} {circ} dSE dTS", dd, round(pct(dS["epr"], ts), 1))
    check(f"shared {suite} {circ} P epr", pe, sf["epr"])
    check(f"shared {suite} {circ} P swap", ps, sf["swaps"])
    check(f"shared {suite} {circ} P dTS", pd, round(pct(sf["epr"], ts), 1))

def shared_gmeans(keys):
    ts = gmean([by[k]["telesabre"]["epr"] for k in keys])
    dS = gmean([by[k]["dSE_shared"]["epr"] for k in keys])
    sf = gmean([by[k]["sfc_shared"]["epr"] for k in keys])
    return ts, dS, sf

k25 = [("25", c) for c in ["ae", "ghz", "graphstate", "qft", "qnn", "random"]]
k64 = [("64", c) for c in ["ae", "ghz", "graphstate", "qft", "qnn"]]
k80 = [("80", c) for c in ["ghz", "graphstate"]]
for label, keys, exp in (
    ("sh25", k25, (94.3, 59.1, -37.3, 56.5, -40.1)),
    ("sh64", k64, (172.1, 89.7, -47.9, 107.1, -37.8)),
    ("sh80", k80, (40.9, 28.7, -29.8, 27.9, -31.7)),
    ("shALL", k25 + k64 + k80, (104.5, 62.1, -40.6, 64.8, -38.0)),
):
    ts, dS, sf = shared_gmeans(keys)
    check(f"{label} TS gmean", exp[0], round(ts, 1))
    check(f"{label} dSE gmean", exp[1], round(dS, 1))
    check(f"{label} dSE delta", exp[2], round(pct(dS, ts), 1))
    check(f"{label} P gmean", exp[3], round(sf, 1))
    check(f"{label} P delta", exp[4], round(pct(sf, ts), 1))

# pooled fixed-layout claim: 30 instances, P wins 15, dSE 12, ties 3,
# pooled gmean 73.8 vs 76.7
pool = []
for r in cmp_rows:
    if r.get("dSE_shared") and r.get("sfc_shared"):
        pool.append((r["dSE_shared"]["epr"], r["sfc_shared"]["epr"]))
    if r.get("dSE_pytket") and r.get("sfc_pytket"):
        pool.append((r["dSE_pytket"]["epr"], r["sfc_pytket"]["epr"]))
p_w = sum(1 for d, p in pool if p < d)
d_w = sum(1 for d, p in pool if d < p)
tie = sum(1 for d, p in pool if d == p)
check("pooled instances", 30, len(pool))
check("pooled P wins", 15, p_w)
check("pooled dSE wins", 12, d_w)
check("pooled ties", 3, tie)
check("pooled gmean P", 73.8, round(gmean([p for _, p in pool]), 1))
check("pooled gmean dSE", 76.7, round(gmean([d for d, _ in pool]), 1))

# ------------------------------------------------------------------ action mix
actionmix = {
    ("25", "ae"):         (43, 14, 0, 0, 8, 50, 6.2, 8, 65),
    ("25", "ghz"):        (4, 0, 0, 0, 0, 0, None, None, 4),
    ("25", "graphstate"): (7, 0, 0, 0, 0, 0, None, None, 7),
    ("25", "qft"):        (58, 16, 0, 0, 0, 0, None, None, 74),
    ("25", "qnn"):        (89, 30, 0, 0, 0, 0, None, None, 119),
    ("25", "random"):     (261, 4, 0, 93, 43, 90, 2.1, 3, 401),
    ("64", "ae"):         (100, 43, 2, 0, 32, 101, 3.2, 8, 177),
    ("64", "ghz"):        (6, 0, 0, 0, 0, 0, None, None, 6),
    ("64", "graphstate"): (20, 0, 0, 0, 0, 0, None, None, 20),
    ("64", "qft"):        (179, 37, 0, 1, 45, 105, 2.3, 6, 262),
    ("64", "qnn"):        (464, 150, 5, 5, 240, 630, 2.6, 8, 864),
    ("64", "random"):     (405, 16, 11, 228, 77, 157, 2.0, 3, 737),
    ("80", "ae"):         (147, 57, 7, 15, 264, 834, 3.2, 8, 490),
    ("80", "ghz"):        (7, 0, 0, 0, 0, 0, None, None, 7),
    ("80", "graphstate"): (28, 0, 0, 0, 0, 0, None, None, 28),
    ("80", "qft"):        (166, 62, 7, 2, 209, 553, 2.6, 8, 446),
    ("80", "qnn"):        (778, 254, 7, 30, 448, 1182, 2.6, 8, 1517),
    ("80", "random"):     (6559, 257, 114, 3538, 572, 1209, 2.1, 4, 11040),
}
for key, (nm, bl, tl, tg, pk, pcx, pmean, pmax, epr) in actionmix.items():
    m = mix_by[key]
    check(f"mix {key} norm", nm, m["teleports_normal"])
    check(f"mix {key} blk", bl, m["teleports_blocked"])
    check(f"mix {key} tail", tl, m["teleports_capacity_relief"])
    check(f"mix {key} telegate", tg, m["telegates"])
    check(f"mix {key} packets", pk, m["telegate_packets"])
    check(f"mix {key} packetCX", pcx, m["packet_cx_total"])
    if pmean is not None:
        check(f"mix {key} mean", pmean, round(m["packet_cx_mean"], 1))
        check(f"mix {key} max", pmax, m["packet_cx_max"])
    check(f"mix {key} epr", epr, m["epr"])
    tot = (m["teleports_normal"] + m["teleports_blocked"]
           + m["teleports_capacity_relief"] + m["telegates"]
           + m["telegate_packets"])
    check(f"mix {key} columns-sum-to-EPR", m["epr"], tot)

# ------------------------------------------------------------------ ablation
ablation = {
    ("25", "ae"):     (65, 71, 80, 8),
    ("25", "qft"):    (74, 74, 140, 0),
    ("25", "qnn"):    (119, 122, 212, 0),
    ("25", "random"): (401, 412, 395, 43),
    ("64", "ae"):     (177, 211, 327, 32),
    ("64", "qft"):    (262, 372, 382, 45),
    ("64", "qnn"):    (864, 931, 600, 240),
    ("64", "random"): (737, 843, 789, 77),
    ("80", "ae"):     (490, 688, None, 264),
    ("80", "qft"):    (446, 435, None, 209),
    ("80", "qnn"):    (1517, 1571, None, 448),
    ("80", "random"): (11040, 11628, None, 572),
}
for key, (full, nopk, norel, pk) in ablation.items():
    a = abl_by[key]["out"]
    check(f"abl {key} full", full, (a.get("full") or {}).get("epr"))
    check(f"abl {key} nopk", nopk, (a.get("no_packets") or {}).get("epr"))
    nr = (a.get("no_relief") or {}).get("epr")
    check(f"abl {key} norelief", norel, nr)
    check(f"abl {key} pk", pk, (a.get("full") or {}).get("packets"))

full_v, nopk_v, norel_v = [], [], []
for r in abl_rows:
    o = r["out"]
    e = [(o.get(k) or {}).get("epr") for k in ("full", "no_packets", "no_relief")]
    if all(v is not None for v in e):
        full_v.append(e[0]); nopk_v.append(e[1]); norel_v.append(e[2])
check("abl basis count", 14, len(full_v))
check("abl gmean full", 57.6, round(gmean(full_v), 1))
check("abl gmean nopk", 61.4, round(gmean(nopk_v), 1))
check("abl gmean norelief", 67.0, round(gmean(norel_v), 1))

# ------------------------------------------------------------------ timing
timing = {
    ("25", "ae"):     (558, 0.15, 0.79, 0.07),
    ("25", "random"): (1124, 1.24, 5.39, 0.40),
    ("64", "ae"):     (1962, 0.97, 10.54, 0.27),
    ("64", "qft"):    (1966, 1.78, 8.41, 0.41),
    ("64", "qnn"):    (8126, 17.52, 133.33, 2.24),
    ("80", "random"): (23381, None, None, 38.17),
}
for key, (cx, tst, dst, pt) in timing.items():
    r = by[key]
    check(f"time {key} cx", cx, r["cx"])
    check(f"time {key} TS", tst, (r.get("telesabre") or {}).get("seconds"), tol=0.005001)
    check(f"time {key} dSE", dst, (r.get("dSE") or {}).get("seconds"), tol=0.005001)
    check(f"time {key} P", pt, (r.get("sfc") or {}).get("seconds"), tol=0.005001)

# speedup claims: up to 59x per attempt; 39x on ae64; 59x/178x on qnn64
qnn = by[("64", "qnn")]
ae = by[("64", "ae")]
check("speedup qnn64 (59x)", 59, round(qnn["dSE"]["seconds"] / qnn["sfc"]["seconds"]), tol=0.5)
check("speedup qnn64 best-of-3 (178x)", 178,
      round(3 * qnn["dSE"]["seconds"] / qnn["sfc"]["seconds"]), tol=1.0)
check("speedup ae64 (39x)", 39, round(ae["dSE"]["seconds"] / ae["sfc"]["seconds"]), tol=0.5)
ratios = [(r["dSE"]["seconds"] / r["sfc"]["seconds"], r["suite"], r["circuit"])
          for r in cmp_rows if r.get("dSE") and r["dSE"].get("seconds")
          and r.get("sfc") and r["sfc"].get("seconds")]
print(f"dSE/P per-attempt speedup range across data: "
      f"{min(ratios)[0]:.1f}x ({min(ratios)[2]}-{min(ratios)[1]}) to "
      f"{max(ratios)[0]:.1f}x ({max(ratios)[2]}-{max(ratios)[1]})")

# 64q GHZ narrative: paper text says PORTER 6 vs TS 11 and dSE 14
g = by[("64", "ghz")]
print(f"64q GHZ: TS={g['telesabre']['epr']} dSE={g['dSE']['epr']} P={g['sfc']['epr']}"
      f"  (text: PORTER win 6 vs. 11 (TS) and 9 (two-corner dSE); 14 vs. 11 is dSE's published table)")

# 25q text: wins AE,QFT,QNN,Random; ties GHZ(4), Graphstate(7)
# 80q text: P wins AE(490 vs 513), GHZ(7 vs 10); loses graphstate(28 vs 25),
#           qft(446 vs 349), qnn(1517 vs 869)

print()
if fails:
    print(f"{len(fails)} MISMATCHES:")
    for f in fails:
        print(f)
else:
    print("ALL CHECKS PASS")
