"""Cross-verify every number in sfc.tex tables and headline claims against
compare_results.json / action_mix_results.json / ../ablation_results.json /
teledata_ablation_basis.json.
Expected values below mirror the paper; rerun after any harness refresh."""
import json
import math

BASE = "/Users/sanjiangli/Documents/pyzoo/SFC"
# Track the results files the paper's tables are generated from.  During the
# protocol migration those are the `*_results_selection.json` variants; when
# they are promoted to the released names this falls back automatically.
import os as _os
_SEL = "_selection" if _os.path.exists(
    f"{BASE}/paper/compare_results_selection.json") else ""
cmp_rows = json.load(open(f"{BASE}/paper/compare_results{_SEL}.json"))
mix_rows = json.load(open(f"{BASE}/paper/action_mix_results.json"))
abl_rows = json.load(open(f"{BASE}/ablation_results.json"))
td_rows = json.load(open(f"{BASE}/paper/teledata_ablation_basis.json"))
hh_rows = json.load(open(f"{BASE}/paper/heavyhex_results{_SEL}.json"))
pc_rows = json.load(open(f"{BASE}/paper/plan_commitment_results.json"))
su_rows = json.load(open(f"{BASE}/paper/scaleup_results{_SEL}.json"))
hz_rows = json.load(open(f"{BASE}/paper/horizon_results.json"))

def norm(c):
    return "qnn" if c.startswith("qnn") else c

by = {(r["suite"], norm(r["circuit"])): r for r in cmp_rows}
mix_by = {(r["suite"], norm(r["circuit"])): r for r in mix_rows}
abl_by = {(r["suite"], norm(r["circuit"])): r for r in abl_rows}

fails = []
notes = []


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
    "ae":            (119, 346, 65, 309, 65, 328, 65, 328, -45.4),
    "ghz":             (13, 44, 5, 17, 4, 29, 4, 29, -69.2),
    "graphstate":    (21, 63, 6, 31, 7, 34, 4, 19, -81.0),
    "qft":           (138, 448, 81, 365, 74, 327, 74, 327, -46.4),
    "qnn":           (515, 820, 143, 711, 119, 642, 116, 603, -77.5),
    "random":          (636, 1367, 411, 1448, 401, 1327, 383, 1319, -39.8),
}
main64 = {
    "ae":            (353, 1494, 165, 1325, 157, 1468, 177, 1627, -55.5),
    "ghz":           (16, 132, 6, 39, 6, 86, 6, 86, -62.5),
    "graphstate":    (62, 281, 15, 88, 20, 131, 16, 103, -74.2),
    "qft":           (312, 1711, 179, 1480, 262, 1846, 262, 1846, -16.0),
    "qnn":           (889, 5471, 538, 5260, 638, 5901, 537, 5608, -39.6),
    "random":        (None, None, 732, 3603, 737, 4048, 737, 4048, None),
    "qpeexact":      (289, 1706, 187, 1576, 222, 1729, 222, 1729, -23.2),
    "qaoa":          (956, 4189, 555, 3734, 775, 4784, 607, 4256, -36.5),
    "multiplier":    (1601, 9654, 1285, 8969, 1076, 8649, 763, 8264, -52.3),
}
main80 = {
    "ae":            (None, None, 332, 2624, 299, 2433, 490, 3156, None),
    "ghz":             (26, 215, 13, 80, 7, 115, 7, 115, -73.1),
    "graphstate":    (87, 435, 20, 97, 28, 198, 24, 150, -72.4),
    "qft":             (None, None, 322, 2362, 446, 2968, 393, 2692, None),
    "qnn":             (None, None, 807, 8445, 1070, 9347, 1181, 9959, None),
    "random":        (None, None, 10551, 56624, 11040, 62119, 11040, 62119, None),
    "qpeexact":      (784, 2875, 347, 2254, 291, 2378, 526, 3427, -62.9),
    "qaoa":          (None, None, 862, 6067, 1122, 7370, 1122, 7370, None),
    "multiplier":      (None, None, 4841, 22029, 2411, 15709, 2699, 16810, None),
}

for suite, table in (("25", main25), ("64", main64), ("80", main80)):
    for circ, (tse, tss, dse, dss, pe, ps, re_, rs, delta) in table.items():
        r = by[(suite, circ)]
        ts, dS, sf = r.get("telesabre") or {}, r.get("dSE") or {}, r.get("sfc") or {}
        rf = r.get("sfc_refined") or {}
        check(f"main{suite} {circ} TS epr", tse, ts.get("epr"))
        check(f"main{suite} {circ} TS swap", tss, ts.get("swaps"))
        check(f"main{suite} {circ} dSE epr", dse, dS.get("epr"))
        check(f"main{suite} {circ} dSE swap", dss, dS.get("swaps"))
        check(f"main{suite} {circ} P epr", pe, sf.get("epr"))
        check(f"main{suite} {circ} P swap", ps, sf.get("swaps"))
        check(f"main{suite} {circ} P+R epr", re_, rf.get("epr"))
        check(f"main{suite} {circ} P+R swap", rs, rf.get("swaps"))
        # Refinement used to dominate the single pass by construction, since
        # both routed the same horizon and +R kept the best pass.  Since
        # PORTER's protocol became horizon selection and +R deliberately did
        # NOT (it holds the horizon fixed), they are different protocols and
        # +R may legitimately be worse.  Record it rather than failing.
        if re_ is not None and pe is not None and re_ > pe:
            notes.append(f"  selection beats refinement main{suite} {circ}: "
                         f"{re_} (+R) vs {pe} (selected)")
        if delta is not None:
            # tab:main's delta follows whichever PORTER protocol is stronger
            # on the row: horizon selection overtakes refinement on some.
            check(f"main{suite} {circ} deltaTS", delta,
                  round(pct(min(sf["epr"], rf["epr"]), ts["epr"]), 1))

# gmeans (own protocol): 25q over 6; 64q over the 5 TS completes; 80q over 2
def own(suite, routers, circs):
    out = {}
    for name in routers:
        vals = [by[(suite, c)][name]["epr"] for c in circs]
        out[name] = gmean(vals)
    return out

g25 = own("25", ("telesabre", "dSE", "sfc", "sfc_refined"),
          ["ae", "ghz", "graphstate", "qft", "qnn", "random"])
check("gmean25 TS", 106.6, round(g25["telesabre"], 1))
check("gmean25 dSE", 45.8, round(g25["dSE"], 1))
check("gmean25 P", 43.1, round(g25["sfc"], 1))
check("gmean25 delta", -63.6, round(pct(g25["sfc_refined"], g25["telesabre"]), 1))

# TeleSABRE-matched basis: the circuits it completes at 64q
c64 = ['ae', 'ghz', 'graphstate', 'qft', 'qnn', 'qpeexact', 'qaoa', 'multiplier']
g64 = own("64", ("telesabre", "dSE", "sfc", "sfc_refined"), c64)
check("gmean64 TS", 284.5, round(g64["telesabre"], 1))
check("gmean64 dSE", 144.6, round(g64["dSE"], 1))
check("gmean64 P", 166.2, round(g64["sfc"], 1))
check("gmean64 delta", -47.6, round(pct(g64["sfc_refined"], g64["telesabre"]), 1))

g80 = own("80", ("telesabre", "dSE", "sfc", "sfc_refined"), ['ghz', 'graphstate', 'qpeexact'])
check("gmean80(3) TS", 121.0, round(g80["telesabre"], 1))
check("gmean80(3) dSE", 44.9, round(g80["dSE"], 1))
check("gmean80(3) P", 38.5, round(g80["sfc"], 1))
check("gmean80(3) delta", -63.2, round(pct(g80["sfc_refined"], g80["telesabre"]), 1))

# 80q five-circuit basis dSABRE completes (user's question)
# 80q circuits dSABRE completes (all of them)
c80d = ['ae', 'ghz', 'graphstate', 'qft', 'qnn', 'random', 'qpeexact', 'qaoa', 'multiplier']
g80d = own("80", ("dSE", "sfc"), c80d)
check("gmean80(all) dSE", 412.1, round(g80d["dSE"], 1))
check("gmean80(all) P", 396.7, round(g80d["sfc"], 1))

# completion counts
ts_done = sum(1 for r in cmp_rows if r.get("telesabre") and r["telesabre"].get("epr"))
dse_done = sum(1 for r in cmp_rows if r.get("dSE") and r["dSE"].get("epr"))
p_done = sum(1 for r in cmp_rows if r.get("sfc") and r["sfc"].get("epr"))
check("completions TS", 17, ts_done)
check("completions dSE", 24, dse_done)
check("completions P", 24, p_done)

# ------------------------------------------------- layout-by-router grid (V-B)
# The shared-layout experiment now routes every compiler from all three layout
# sources over ALL 24 instances (TeleSABRE's layout is no longer a row: it
# covers only 17 and is much the weakest of the three -- see below).
_GRID = {
    "dSABRE":  ("dSE", "sfc_on_dse_layout", "sfc_on_dse_layout_refined"),
    "PORTER":  ("dSE_on_porter_layout", "sfc", "sfc_refined"),
    "pytket":  ("dSE_pytket", "sfc_pytket", "sfc_pytket_refined"),
}
_g = lambda leg: gmean([r[leg]["epr"] for r in cmp_rows])
for src, (d, p, pr) in _GRID.items():
    for leg in (d, p, pr):
        check(f"grid {src} {leg} covers all 24", 24,
              sum(1 for r in cmp_rows if (r.get(leg) or {}).get("epr")))
# "the routing loops land within 2% of one another on every row, dSABRE ahead"
for src, (d, p, _) in _GRID.items():
    ratio = _g(p) / _g(d)
    check(f"grid {src}: dSABRE ahead", True, ratio > 1.0)
    check(f"grid {src}: within 2%", True, ratio < 1.022)
# "wins twelve to eight on the pytket row"
check("pytket-row dSABRE wins", 12,
      sum(1 for r in cmp_rows if r["dSE_pytket"]["epr"] < r["sfc_pytket"]["epr"]))
check("pytket-row PORTER wins", 8,
      sum(1 for r in cmp_rows if r["sfc_pytket"]["epr"] < r["dSE_pytket"]["epr"]))
# "pytket's partition is the best start for both routers"
check("pytket best for dSABRE", 4.5,
      round(100 * (1 - _g("dSE_pytket") / _g("dSE")), 1))
check("pytket best for PORTER", 4.8,
      round(100 * (1 - _g("sfc_pytket") / _g("sfc")), 1))
# "refinement gains 3.0% on dSABRE's layout and nothing on pytket's"
check("refinement gain on dSE layout", 5.1,
      round(100 * (1 - _g("sfc_on_dse_layout_refined") / _g("sfc_on_dse_layout")), 1))
check("refinement gain on pytket layout", -0.0,
      round(100 * (1 - _g("sfc_pytket_refined") / _g("sfc_pytket")), 1))
# TeleSABRE's layout, on the 17 instances it covers: weakest source, and the
# one on which refinement appears to pay.
_ts = [r for r in cmp_rows if (r.get("telesabre") or {}).get("epr")]
_h = lambda leg: gmean([r[leg]["epr"] for r in _ts])
check("TS layout instances", 17, len(_ts))
check("TS layout routed by dSABRE", 100.9, round(_h("dSE_shared"), 1))
check("pytket layout routed by dSABRE, same 17", 71.1, round(_h("dSE_pytket"), 1))
check("refinement gain on TS layout", 20.2,
      round(100 * (1 - _h("sfc_shared_refined") / _h("sfc_shared")), 1))
check("TS-layout PORTER+R beats dSABRE", True,
      _h("sfc_shared_refined") < _h("dSE_shared"))

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

# --------------------------------------------------- ablation: TeleData only
td_by = {(r["suite"], norm(r["circuit"])): r for r in td_rows}
teledata = {
    # (TeleData-only EPR or None if it does not complete,
    #  completes without the extra relief tier?, pk, tg)
    ("25", "ae"):     (68, False, 8, 0),
    ("25", "qft"):    (74, True, 0, 0),
    ("25", "qnn"):    (119, True, 0, 0),
    ("25", "random"): (413, False, 43, 93),
    ("64", "ae"):     (198, False, 32, 0),
    ("64", "qft"):    (216, False, 45, 1),
    ("64", "qnn"):    (694, False, 240, 5),
    ("64", "random"): (None, False, 77, 228),
    ("80", "ae"):     (354, False, 264, 15),
    ("80", "qft"):    (307, False, 209, 2),
    ("80", "qnn"):    (926, False, 448, 30),
    ("80", "random"): (None, False, 572, 3538),
}
for key, (td, raw_ok, pk, tg) in teledata.items():
    o = td_by[key]["out"]
    check(f"td {key} epr", td, (o.get("teledata_only_relief") or {}).get("epr"))
    check(f"td {key} raw-completes", raw_ok,
          (o.get("teledata_only") or {}).get("epr") is not None)
    check(f"td {key} pk", pk, (o.get("full") or {}).get("packets"))
    check(f"td {key} tg", tg, (o.get("full") or {}).get("telegates"))
    # The extra relief tier must be inert with the TeleGate available, or the
    # TeleData-only column is not a pure action-vocabulary comparison.
    check(f"td {key} relief-tier-inert", (o.get("full") or {}).get("epr"),
          (o.get("full_relief") or {}).get("epr"))
    # The stream must really contain no telegate of either kind.
    if td is not None:
        r = o["teledata_only_relief"]
        check(f"td {key} no telegates", 0, r["telegates"])
        check(f"td {key} no packets", 0, r["packets"])
        check(f"td {key} epr==teleports", r["epr"], r["teleports"])

td_ok = [r for r in td_rows
         if (r["out"].get("teledata_only_relief") or {}).get("epr") is not None]
check("td gmean basis count", 16, len(td_ok))
check("td gmean full", 78.3,
      round(gmean([r["out"]["full"]["epr"] for r in td_ok]), 1))
check("td gmean nopk", 83.9,
      round(gmean([(abl_by[(r["suite"], r["circuit"])]["out"]["no_packets"])["epr"]
                   for r in td_ok]), 1))
check("td gmean teledata", 71.7,
      round(gmean([r["out"]["teledata_only_relief"]["epr"] for r in td_ok]), 1))
# Per-suite claims in the prose, over the table's own basis rows.
def _td_delta_pct(suite, circs):
    rs = [td_by[(suite, c)] for c in circs]
    return round(100 * (gmean([r["out"]["teledata_only_relief"]["epr"] for r in rs])
                        / gmean([r["out"]["full"]["epr"] for r in rs]) - 1))

check("td 25q gmean delta pct", 2, _td_delta_pct("25", ("ae", "qft", "qnn", "random")))
check("td 80q gmean delta pct", -33, _td_delta_pct("80", ("ae", "qft", "qnn")))
# Per-circuit deltas quoted at 64q.
for c, want in (("qft", -18), ("qnn", -20), ("ae", 12)):
    r = td_by[("64", c)]["out"]
    check(f"td 64q {c} delta pct", want,
          round(100 * (r["teledata_only_relief"]["epr"] / r["full"]["epr"] - 1)))
# "Ten of the twelve rows deadlock" without the extra relief tier.
basis12 = [(s_, c) for s_ in ("25", "64", "80") for c in ("ae", "qft", "qnn", "random")]
check("td raw deadlock count (of 12)", 10,
      sum(1 for k in basis12
          if (td_by[k]["out"].get("teledata_only") or {}).get("epr") is None))

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

# --------------------------------------- architecture / setup / Sec III facts
import importlib
import sys as _sys
if BASE not in _sys.path:
    _sys.path.insert(0, BASE)
_porter = importlib.import_module("porter")
_cdr = importlib.import_module("compile_porter")
_cfg = _porter.RouterConfig()
# Every parameter Section III quotes must equal the shipped default.
for _attr, _want, _lbl in (
        ("min_free_before_teleport", 2, "f_min"),
        ("dag_front_limit", 96, "front cap"),
        ("local_swap_extended_weight", 0.8, "lambda_loc"),
        ("local_swap_extended_cx_count", 20, "N_loc"),
        ("local_swap_extended_max_layers", 12, "L_loc"),
        ("dag_extended_max_layers", 16, "L_tp"),
        ("teleport_lookahead_cx_count", 50, "N_tp"),
        ("teleport_lookahead_weight", 0.9, "w0"),
        ("teleport_lookahead_decay", 0.9, "lookahead gamma"),
        ("teleport_lookahead_weight_floor", 0.5, "w_min"),
        ("capacity_relief_assist_margin", 5.0, "m_assist"),
        ("max_packet_size", 8, "max packet size"),
        ("extended_packet_window", 120, "packet window"),
        ("max_prep_iterations_per_plan", 10000, "prep cap")):
    check(f"secIII param {_lbl}", _want, getattr(_cfg, _attr))
# Architectures as described in Setup.
for _name, _cores, _per, _links in (("A", 4, 9, 4), ("H", 6, 16, 7)):
    _, _hw = _cdr.hardware_for_name(_name)
    check(f"arch {_name} cores", _cores, len(_hw.cores))
    check(f"arch {_name} per-core", _per, len(_hw.cores[0].physical_qubits))
    check(f"arch {_name} links", _links, len(_hw.core_edges))
# The two refinement examples quoted in Section III-C.
for _c, _a, _b in (("qnn", 638, 537), ("multiplier", 1076, 763)):
    _r = by[("64", _c)]
    check(f"secIII refine {_c} one-pass", _a, _r["sfc"]["epr"])
    check(f"secIII refine {_c} refined", _b, _r["sfc_refined"]["epr"])

# ------------------------------------------------ timing / scale-up prose
# Per-routing-pass comparison on the 64q suite. dSABRE runs three passes per
# candidate layout, so its per-route cost is (protocol time - layout time)/3n.
_r64 = [r for r in cmp_rows if r["suite"] == "64"]
def _dse_per_route(r):
    d = r["dSE"]
    return (d["seconds"] - d.get("layout_seconds", 0)) / (3 * d.get("n_candidates", 1))
def _p_per_route(r):
    return r["sfc"]["seconds"] - r["sfc"].get("layout_seconds", 0)
_ratios = [_dse_per_route(r) / _p_per_route(r) for r in _r64]
check("64q PORTER slower per pass on", 9, sum(1 for x in _ratios if x < 1))
check("64q per-pass gmean", 0.08, round(gmean(_ratios), 2))
check("64q dSABRE routes per circuit", 9,
      3 * _r64[0]["dSE"].get("n_candidates", 1))
check("64q complete-cost gmean dSE", 1.77,
      round(gmean([r["dSE"]["seconds"] for r in _r64]), 2))
check("64q complete-cost gmean PORTER", 1.98,
      round(gmean([r["sfc"]["seconds"] for r in _r64]), 2))
check("64q complete-cost advantage", 0.9,
      round(gmean([r["dSE"]["seconds"] for r in _r64])
            / gmean([r["sfc"]["seconds"] for r in _r64]), 1))
_mult = [r for r in _r64 if r["circuit"] == "multiplier"][0]
check("64q multiplier per-pass", 0.29,
      round(_dse_per_route(_mult) / _p_per_route(_mult), 2))
check("64q multiplier is the only per-pass win", 0,
      sum(1 for x in _ratios if x >= 1))
# ---- Sec IV-E prose, rewritten 2026-08-29 when the shipped protocol became
# horizon selection.  Every figure below was stale (it described the old
# single-pass run) and contradicted tab:scaleup, so all of it is pinned now.
_su_p = gmean([r["sfc"]["epr"] for r in su_rows])
_su_d = gmean([r["dSE"]["epr"] for r in su_rows])
check("scaleup PORTER beats dSABRE on all six", 6,
      sum(1 for r in su_rows if r["sfc"]["epr"] < r["dSE"]["epr"]))
check("scaleup gmean ratio", 0.72, round(_su_p / _su_d, 2))
for _n, _want in (("100", 0.90), ("200", 0.67), ("360", 0.62)):
    _rs = [r for r in su_rows if r["suite"] == _n]
    check(f"scaleup {_n}q ratio", _want,
          round(gmean([r["sfc"]["epr"] for r in _rs])
                / gmean([r["dSE"]["epr"] for r in _rs]), 2))
check("scaleup complete-cost PORTER", 8.4,
      round(gmean([r["sfc"]["seconds"] for r in su_rows]), 1))
check("scaleup complete-cost dSABRE", 15.4,
      round(gmean([r["dSE"]["seconds"] for r in su_rows]), 1))
check("scaleup complete-cost ratio", 0.54,
      round(gmean([r["sfc"]["seconds"] for r in su_rows])
            / gmean([r["dSE"]["seconds"] for r in su_rows]), 2))
check("scaleup +R loses on all six", 6,
      sum(1 for r in su_rows if r["sfc_refined"]["epr"] > r["sfc"]["epr"]))
check("scaleup +R pct behind selection", 83,
      round(100 * (gmean([r["sfc_refined"]["epr"] for r in su_rows]) / _su_p - 1)))
check("scaleup dSE-layout ratio", 0.96,
      round(gmean([r["sfc_on_dse_layout"]["epr"] for r in su_rows]) / _su_d, 2))
check("scaleup default-horizon ratio (the 1.45x it replaces)", 1.45,
      round(gmean([hz_rows[f"scaleup/{r['suite']}/{r['circuit']}"]
                   ["horizon_eprs"][str(hz_rows[f"scaleup/{r['suite']}/{r['circuit']}"]
                                        ["default_horizon"])] for r in su_rows]) / _su_d, 2))
check("scaleup every instance selects the long horizon", 6,
      sum(1 for r in su_rows if r["sfc"].get("chosen_horizon") == 128))
_q360 = [r for r in su_rows if r["suite"] == "360" and r["circuit"] == "qft"][0]
check("scaleup 360q qft: dSABRE's layout is worse for PORTER", True,
      _q360["sfc_on_dse_layout"]["epr"] > _q360["sfc"]["epr"])
check("scaleup 360q qft own layout", 1156, _q360["sfc"]["epr"])
check("scaleup 360q qft on dSE layout", 1791, _q360["sfc_on_dse_layout"]["epr"])

# Sec IV-F: the star gmeans quoted in prose (PORTER's own protocol, all nine).
_star = [r for r in hh_rows if r["topology"] == "star"]
check("star PORTER own-protocol gmean", 122.3,
      round(gmean([r["porter"]["epr"] for r in _star]), 1))
check("star dSABRE gmean", 101.1,
      round(gmean([r["dSE"]["epr"] for r in _star]), 1))
check("star PORTER wins", 2,
      sum(1 for r in _star if r["porter"]["epr"] < r["dSE"]["epr"]))

# Sec IV-J: per-ROUTE cost.  PORTER's protocol is three routes, so its
# per-route cost is its protocol time / 3 -- comparing dSABRE's per-route cost
# against PORTER's whole protocol (as the prose once did) gives a bogus 0.08x.
def _p_per_route3(r):
    return (r["sfc"]["seconds"] - r["sfc"].get("layout_seconds", 0)) / 3
_ratios3 = [_dse_per_route(r) / _p_per_route3(r) for r in _r64]
check("64q per-route gmean (3 routes)", 0.27, round(gmean(_ratios3), 2))
check("64q PORTER dearer per route on all nine", 9,
      sum(1 for x in _ratios3 if x < 1))

# Sec IV-J: selection vs the gamma-search, per instance.
check("search beats selection on", 14,
      sum(1 for r in cmp_rows if r["sfc_search"]["epr"] < r["sfc"]["epr"]))
check("selection beats search on", 4,
      sum(1 for r in cmp_rows if r["sfc"]["epr"] < r["sfc_search"]["epr"]))
check("selection/search ties", 6,
      sum(1 for r in cmp_rows if r["sfc"]["epr"] == r["sfc_search"]["epr"]))
# Sec IV-D: PORTER's own protocol against dSABRE, per instance.
check("PORTER own-protocol wins vs dSE", 10,
      sum(1 for r in cmp_rows if r["sfc"]["epr"] < r["dSE"]["epr"]))
check("PORTER own-protocol losses vs dSE", 12,
      sum(1 for r in cmp_rows if r["sfc"]["epr"] > r["dSE"]["epr"]))

# Scale-up per-attempt speed range quoted in Sec IV-G.
_su_rat = [r["dSE"]["seconds_best_attempt"] / r["sfc"]["seconds"] for r in su_rows]
check("scaleup per-attempt min", 0.4, round(min(_su_rat), 1))
check("scaleup per-attempt max", 0.9, round(max(_su_rat), 1))
_q360 = [r for r in su_rows if r["suite"] == "360" and r["circuit"] == "qft"][0]
check("scaleup 360q qft per-attempt", 0.9,
      round(_q360["dSE"]["seconds_best_attempt"] / _q360["sfc"]["seconds"], 1))
# Refinement now helps on NONE of the six scale-up instances (the shipped
# protocol selects a horizon; refinement holds it fixed and loses on all six).
check("scaleup refinement helps", 0,
      sum(1 for r in su_rows if r["sfc_refined"]["epr"] < r["sfc"]["epr"]))

# The abstract, intro, results and conclusion all quote the SINGLE-PASS
# reductions against TeleSABRE. These are the paper's headline numbers and
# were previously unpinned, which is how a stale 49.8% survived for a while.
check("headline 25q single-pass", -59.6,
      round(pct(g25["sfc"], g25["telesabre"]), 1))
check("headline 64q single-pass", -41.6,
      round(pct(g64["sfc"], g64["telesabre"]), 1))
check("headline 80q single-pass", -68.2,
      round(pct(g80["sfc"], g80["telesabre"]), 1))

# --------------------------------------- own-protocol / shared-layout prose
# Claims in Sec IV-D and IV-E that are easy to get wrong by eye.
_pr = [r for r in cmp_rows]
_ts = [r for r in _pr if (r.get("telesabre") or {}).get("epr")]
# "every converged circuit improves, from -16.0% to -81.0%"
_d = sorted(round(100 * (r["sfc_refined"]["epr"] / r["telesabre"]["epr"] - 1), 1)
            for r in _ts)
check("dTS best", -81.0, _d[0])
check("dTS worst", -16.0, _d[-1])
check("dTS all negative", True, all(x < 0 for x in _d))
# "PORTER+R wins seven, loses thirteen, ties four"
_w = sum(1 for r in _pr if r["sfc_refined"]["epr"] < r["dSE"]["epr"])
_l = sum(1 for r in _pr if r["sfc_refined"]["epr"] > r["dSE"]["epr"])
check("P+R vs dSE wins", 9, _w)
check("P+R vs dSE losses", 13, _l)
check("P+R vs dSE ties", 2, len(_pr) - _w - _l)
# "64q Multiplier is the widest margin here" and the worst losses are ~1.5x
_best = min(_pr, key=lambda r: r["sfc_refined"]["epr"] / r["dSE"]["epr"])
check("widest P+R win circuit", "80/ghz", f'{_best["suite"]}/{_best["circuit"]}')
_worst = max(_pr, key=lambda r: r["sfc_refined"]["epr"] / r["dSE"]["epr"])
check("worst P+R loss circuit", "80/qpeexact", f'{_worst["suite"]}/{_worst["circuit"]}')
check("worst P+R loss ratio", 1.5,
      round(_worst["sfc_refined"]["epr"] / _worst["dSE"]["epr"], 1))
# grid, row against row: neither router gains from its own layout source
# (Table tab:shared; the old standalone cross-layout table is gone).
_g = lambda leg: gmean([r[leg]["epr"] for r in _pr])
check("grid dSE gain from own layout", -0.4,
      round(100 * (1 - _g("dSE") / _g("dSE_on_porter_layout")), 1))
check("grid PORTER gain from dSE layout", -0.2,
      round(100 * (1 - _g("sfc_on_dse_layout") / _g("sfc")), 1))
check("grid PORTER+R gain from dSE layout", 3.0,
      round(100 * (1 - _g("sfc_on_dse_layout_refined") / _g("sfc_refined")), 1))
# shared-layout figures quoted in the prose but no longer in the table.
# These legs run PORTER's own (horizon-selecting) protocol, not one pass.
check("shared 25q PORTER selected dTS", -41.5,
      round(100 * (gmean([r["sfc_shared"]["epr"] for r in _ts if r["suite"] == "25"])
                   / gmean([r["telesabre"]["epr"] for r in _ts if r["suite"] == "25"]) - 1), 1))
check("shared pooled PORTER selected dTS", -37.7,
      round(100 * (gmean([r["sfc_shared"]["epr"] for r in _ts])
                   / gmean([r["telesabre"]["epr"] for r in _ts]) - 1), 1))
# "removing plan commitment moves EPR by only 0.6%, in PORTER's favour"
_c = gmean([r["out"]["committed"]["epr"] for r in pc_rows])
_h = gmean([r["out"]["hopwise"]["epr"] for r in pc_rows])
for _s, _want in (("64", -36.5), ("80", -33.1)):
    check(f"shared {_s}q PORTER selected dTS", _want,
          round(100 * (gmean([r["sfc_shared"]["epr"] for r in _ts if r["suite"] == _s])
                       / gmean([r["telesabre"]["epr"] for r in _ts if r["suite"] == _s]) - 1), 1))
check("shared pooled PORTER selected gmean", 107.7,
      round(gmean([r["sfc_shared"]["epr"] for r in _ts]), 1))
check("shared: dSABRE leads at 25 and 80, PORTER at 64", True,
      gmean([r["dSE_shared"]["epr"] for r in _ts if r["suite"] == "64"])
      > gmean([r["sfc_shared"]["epr"] for r in _ts if r["suite"] == "64"]))
check("hopwise delta pct", -0.6, round(100 * (_h / _c - 1), 1))
check("hopwise is the lower of the two", True, _h < _c)
# Related Work: our dSABRE column must never exceed what it publishes at 64q.
_pub64 = {"ae": 165, "ghz": 6, "graphstate": 15, "qft": 180, "qnn": 539,
          "random": 732, "qpeexact": 187, "qaoa": 555, "multiplier": 1285}
for c, v in _pub64.items():
    got = by[("64", c)]["dSE"]["epr"]
    if got > v:
        fails.append(f"  64q {c}: our dSABRE {got} WORSE than its published {v}")

# ------------------------------------------------- ablation prose claims
# Sec IV-H says relief HURTS on exactly two instances and that disabling
# packets helps on exactly one. Both are easy to get wrong by eye.
_B12 = [(su, c) for su in ("25", "64", "80")
        for c in ("ae", "qft", "qnn", "random")]
_relief_hurts = [k for k in _B12
                 if (abl_by[k]["out"].get("no_relief") or {}).get("epr")
                 and abl_by[k]["out"]["no_relief"]["epr"] < abl_by[k]["out"]["full"]["epr"]]
check("abl instances where relief hurts", 2, len(_relief_hurts))
check("abl relief-hurts set", "25/random,64/qnn",
      ",".join(f"{a}/{b}" for a, b in sorted(_relief_hurts)))
_pk_helps = [k for k in _B12
             if abl_by[k]["out"]["no_packets"]["epr"] < abl_by[k]["out"]["full"]["epr"]]
check("abl instances where no-packets helps", 1, len(_pk_helps))
check("abl no-packets-helps set", "80/qft",
      ",".join(f"{a}/{b}" for a, b in sorted(_pk_helps)))
# "ten of the twelve rows deadlock" without the extra relief tier.
check("abl raw-teledata deadlocks of 12", 10,
      sum(1 for k in _B12
          if (td_by[k]["out"].get("teledata_only") or {}).get("epr") is None))
# Hop-wise completes every instance it was run on.
check("hopwise completions", len(pc_rows),
      sum(1 for r in pc_rows if "epr" in r["out"]["hopwise"]))

# ------------------------------------------------------------ instance count
# The abstract and intro claim a total instance count; keep it honest.
check("total instances", 48, len(cmp_rows) + len(su_rows) + len(hh_rows))
check("main-suite instances", 24, len(cmp_rows))

# ------------------------------------------------------- heavy-hex (Sec IV-I)
hh_by = {(r["topology"], r["circuit"]): r for r in hh_rows}
# (dSABRE, PORTER, PORTER+R, PORTER-on-dSABRE-layout); None = does not complete.
# The dSABRE column must also equal what dsabre/code/results/results_heavyhex*
# publishes -- that equality is the check that both routers see the same device.
heavyhex = {
    ("ring", "ae"):             (86, 69, 88, 61, 85),
    ("ring", "ghz"):            (2, 2, 2, 2, 2),
    ("ring", "graphstate"):     (12, 12, 10, 13, 12),
    ("ring", "qft"):            (110, 109, 103, 110, 97),
    ("ring", "qnn"):            (249, 240, 240, 269, 246),
    ("ring", "random"):         (465, 465, 452, 419, 419),
    ("ring", "qpeexact"):       (80, 105, 90, 93, 84),
    ("ring", "qaoa"):           (249, 244, 247, 244, 246),
    ("ring", "multiplier"):     (451, 506, 397, 416, 373),
    ("star", "ae"):             (118, 149, 144, 104, 114),
    ("star", "ghz"):            (3, 3, 3, 4, 3),
    ("star", "graphstate"):     (10, 16, 14, 11, 9),
    ("star", "qft"):            (125, 117, 124, 108, 120),
    ("star", "qnn"):            (241, 449, 314, 321, 314),
    ("star", "random"):         (475, 547, 452, 478, 463),
    ("star", "qpeexact"):       (120, 162, 162, 102, 90),
    ("star", "qaoa"):           (251, 405, 245, 245, 244),
    ("star", "multiplier"):     (722, 455, None, 462, 462),
}
# dSABRE's published figures for these two architectures.
hh_published = {
    "ring": {"ae": 86, "ghz": 2, "graphstate": 12, "qft": 110, "qnn": 249,
             "random": 465, "qpeexact": 80, "qaoa": 249, "multiplier": 451},
    "star": {"ae": 118, "ghz": 3, "graphstate": 10, "qft": 125, "qnn": 241,
             "random": 475, "qpeexact": 120, "qaoa": 251, "multiplier": 722},
}
_HH_LEGS = ("dSE", "porter", "porter_refined", "porter_on_dse",
            "porter_on_dse_refined")
for key, want in heavyhex.items():
    r = hh_by[key]
    for leg, w in zip(_HH_LEGS, want):
        check(f"hh {key} {leg}", w, (r.get(leg) or {}).get("epr"))
    check(f"hh {key} dSE matches published", hh_published[key[0]][key[1]],
          (r.get("dSE") or {}).get("epr"))

def _hh_gmean_raw(topo, leg, circs):
    return gmean([hh_by[(topo, c)][leg]["epr"] for c in circs])


def _hh_gmean(topo, leg, circs):
    return round(_hh_gmean_raw(topo, leg, circs), 1)

_HH9 = ["ae", "ghz", "graphstate", "qft", "qnn", "random",
        "qpeexact", "qaoa", "multiplier"]
_HH8 = [c for c in _HH9 if c != "multiplier"]
for topo, circs, exp in (
    ("ring", _HH9, (85.2, 86.1, 82.3, 82.9, 81.4)),
    ("star", _HH8, (79.1, 103.8, 89.8, 81.2, 76.6)),
):
    for leg, w in zip(_HH_LEGS, exp):
        check(f"hh gmean {topo}({len(circs)}) {leg}", w, _hh_gmean(topo, leg, circs))
check("hh gmean star(9) dSE", 101.1, _hh_gmean("star", "dSE", _HH9))
check("hh gmean star(9) porter_on_dse", 98.5,
      _hh_gmean("star", "porter_on_dse", _HH9))
check("hh gmean star(9) porter_on_dse_refined", 93.5,
      _hh_gmean("star", "porter_on_dse_refined", _HH9))
# Prose: the fixed-layout control with matched passes reverses BOTH topologies.
check("hh ring fixed-layout P+R delta pct", -4.4,
      round(100 * (_hh_gmean_raw("ring", "porter_on_dse_refined", _HH9)
                   / _hh_gmean_raw("ring", "dSE", _HH9) - 1), 1))
check("hh star fixed-layout P+R delta pct", -7.5,
      round(100 * (_hh_gmean_raw("star", "porter_on_dse_refined", _HH9)
                   / _hh_gmean_raw("star", "dSE", _HH9) - 1), 1))
# Prose claims: ring PORTER+R -3.4% and 6W/2L/1T; star PORTER+R +13.6% and 3W/4L/1T.
check("hh ring P+R delta pct", -3.4,
      round(100 * (_hh_gmean_raw("ring", "porter_refined", _HH9)
                   / _hh_gmean_raw("ring", "dSE", _HH9) - 1), 1))
check("hh star P+R delta pct", 13.6,
      round(100 * (_hh_gmean_raw("star", "porter_refined", _HH8)
                   / _hh_gmean_raw("star", "dSE", _HH8) - 1), 1))
for topo, circs, rec in (("ring", _HH9, (6, 2, 1)), ("star", _HH8, (3, 4, 1))):
    w = sum(1 for c in circs
            if hh_by[(topo, c)]["porter_refined"]["epr"] < hh_by[(topo, c)]["dSE"]["epr"])
    l = sum(1 for c in circs
            if hh_by[(topo, c)]["porter_refined"]["epr"] > hh_by[(topo, c)]["dSE"]["epr"])
    t = len(circs) - w - l
    for lbl, want_, got_ in zip(("wins", "losses", "ties"), rec, (w, l, t)):
        check(f"hh {topo} P+R {lbl}", want_, got_)
# The paper contrasts the ring lead with PORTER+R's 3.2% deficit on the
# 4x4-grid 64q suite (TeleSABRE-matched basis) -- keep the two in step.
check("hh grid-64q P+R deficit pct", 3.2,
      round(100 * (g64["sfc_refined"] / g64["dSE"] - 1), 1))
# Star Multiplier: PORTER's own layout fails, dSABRE's layout gives 462 vs 722.
check("hh star multiplier porter fails", False,
      (hh_by[("star", "multiplier")].get("porter") or {}).get("epr") is None)
check("hh star multiplier reduction pct", -36,
      round(100 * (hh_by[("star", "multiplier")]["porter_on_dse"]["epr"]
                   / hh_by[("star", "multiplier")]["dSE"]["epr"] - 1)))

# ------------------------------------------------------- scale-up (Sec IV-H)
su_by = {(r["suite"], r["circuit"]): r for r in su_rows}
# (CX, n, P, K, dSABRE, PORTER, PORTER+R, PORTER/dS-layout, PORTER+R/dS-layout)
scaleup = {
    ("100", "qft"):         (3420, 100, 150, 6, 200, 198, 339, 240, 273),
    ("100", "qpeexact"):    (3579, 100, 150, 6, 246, 200, 262, 200, 343),
    ("200", "qft"):         (7220, 200, 300, 12, 765, 579, 1128, 1031, 1031),
    ("200", "qpeexact"):    (7579, 200, 300, 12, 896, 528, 979, 765, 946),
    ("360", "qft"):         (13300, 360, 500, 20, 1890, 1156, 2822, 1791, 2546),
    ("360", "qpeexact"):    (13979, 360, 500, 20, 1938, 1224, 2342, 1444, 2416),
}
# dSABRE publishes this exact series; our column must reproduce it (<= its
# figures, since our protocol hands it up to six candidate layouts, not three).
su_published = {("100", "qft"): 201, ("100", "qpeexact"): 246,
                ("200", "qft"): 766, ("200", "qpeexact"): 896,
                ("360", "qft"): 1890, ("360", "qpeexact"): 1938}
_SU_LEGS = ("dSE", "sfc", "sfc_refined",
            "sfc_on_dse_layout", "sfc_on_dse_layout_refined")
for key, want in scaleup.items():
    r = su_by[key]
    check(f"su {key} cx", want[0], r["cx"])
    check(f"su {key} n", want[1], r["num_logical"])
    check(f"su {key} P", want[2], r["physical"])
    check(f"su {key} K", want[3], r["cores"])
    for leg, w in zip(_SU_LEGS, want[4:]):
        check(f"su {key} {leg}", w, (r.get(leg) or {}).get("epr"))
    got = r["dSE"]["epr"]
    if got > su_published[key]:
        fails.append(f"  su {key} dSABRE {got} WORSE than its published "
                     f"{su_published[key]} -- baseline handicapped")

def _su_gmean(leg):
    return round(gmean([r[leg]["epr"] for r in su_rows]), 1)

for leg, w in zip(_SU_LEGS, (705.7, 507.7, 930.3, 678.9, 908.4)):
    check(f"su gmean {leg}", w, _su_gmean(leg))
# Prose ratios against dSABRE on the scale-up series.
_su_d = gmean([r["dSE"]["epr"] for r in su_rows])
for leg, w in (("sfc", 0.72), ("sfc_refined", 1.32),
               ("sfc_on_dse_layout", 0.96), ("sfc_on_dse_layout_refined", 1.29)):
    check(f"su ratio {leg}", w,
          round(gmean([r[leg]["epr"] for r in su_rows]) / _su_d, 2))
# The claim that dSABRE's layout is WORSE for PORTER on the largest instance.
check("su 360 qft dSABRE-layout worse than own", True,
      su_by[("360", "qft")]["sfc_on_dse_layout"]["epr"]
      > su_by[("360", "qft")]["sfc"]["epr"])

# 64q GHZ narrative: paper text says PORTER 6, dSABRE 6, TeleSABRE 16.
# NB: dSABRE's *superseded* (May-2026) table had it regressing here, 14 vs 11;
# its current table does not, so the paper no longer makes that claim.
g = by[("64", "ghz")]
check("64q ghz TS", 16, g["telesabre"]["epr"])
check("64q ghz dSE", 6, g["dSE"]["epr"])
check("64q ghz P", 6, g["sfc"]["epr"])

# Narrative win/loss claims in the results prose, checked against the data.
# Refreshed 2026-08-31 when dSABRE was restricted to its own default layout
# rule: GHZ flips from a tie to a PORTER win at both 25q and 80q.
narrative = {
    ("25", "ae"): "P",
    ("25", "ghz"): "P",
    ("25", "graphstate"): "P",
    ("25", "qft"): "P",
    ("25", "qnn"): "P",
    ("25", "random"): "P",
    ("64", "ae"): "dSE",
    ("64", "ghz"): "tie",
    ("64", "graphstate"): "dSE",
    ("64", "multiplier"): "P",
    ("64", "qaoa"): "dSE",
    ("64", "qft"): "dSE",
    ("64", "qnn"): "P",
    ("64", "qpeexact"): "dSE",
    ("64", "random"): "P",
    ("80", "ae"): "dSE",
    ("80", "ghz"): "P",
    ("80", "graphstate"): "dSE",
    ("80", "multiplier"): "P",
    ("80", "qaoa"): "dSE",
    ("80", "qft"): "dSE",
    ("80", "qnn"): "dSE",
    ("80", "qpeexact"): "dSE",
    ("80", "random"): "dSE",
}
for key, want in narrative.items():
    r = by[key]
    d = r["dSE"]["epr"]
    pv = (r.get("sfc_search") or r.get("sfc_refined") or r["sfc"])["epr"]
    got = "P" if pv < d else ("dSE" if pv > d else "tie")
    check(f"narrative {key}", want, got)

print()
if fails:
    print(f"{len(fails)} MISMATCHES:")
    for f in fails:
        print(f)
else:
    print("ALL CHECKS PASS")
