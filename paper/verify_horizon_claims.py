"""Check Section IV-E's justification for the fixed four-value horizon set.

The rest of the paper's numbers come from the released ``*_results*.json``
legs and are checked by ``verify_paper_numbers.py`` / ``verify_tex_tables.py``.
IV-E is different: the case for dropping the density branch rests on
``paper/horizon_sweep/``, an offline grid that no verifier read.  That is the
same unpinned class that let "2,132" and "122.3" survive a re-run, so the
claims are pinned here.

Two facts about the data are load-bearing and worth stating up front.

*   **The retired rule cannot be re-derived from the code.**
    ``hz_four.py --stage pick`` obtains the branch by calling
    ``compile_porter.select_horizons``, which since ``abb845b`` returns the
    fixed set for every circuit -- so re-running it today compares the fixed
    set with itself and reports parity for the wrong reason.  We reconstruct
    the branch from the cached ``rho`` in ``depth_features.json`` and the
    retired threshold instead (dense ``>= 0.80`` took ``(4,8,16)``, everything
    else ``(8,16,128)``).
*   **Scoring must match the harness.**  We import ``hz_four``'s own
    ``load_cells``/``score``/``gm`` rather than reimplementing them, so a
    candidate is budgeted exactly as the protocol budgets it
    (``max(5, 4x`` the configured horizon's own time)) and an instance whose
    ``L=16`` route does not complete is skipped by both arms alike.

Run from ``paper/``:  ``python3 verify_horizon_claims.py``
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SWEEP = os.path.join(HERE, "horizon_sweep")
sys.path.insert(0, SWEEP)
import hz_four as F                                              # noqa: E402

DENSE_THRESHOLD = 0.80          # retired DENSE_INTERACTION_THRESHOLD
DENSE, SPARSE = (4, 8, 16), (8, 16, 128)        # retired PORTER_HORIZONS*
FIXED = (4, 8, 16, 128)         # live compile_porter.PORTER_HORIZONS

fails = []


def check(label, expected, actual, tol=0.005001):
    ok = (str(actual) == expected if isinstance(expected, str)
          else abs(float(actual) - float(expected)) <= tol)
    if not ok:
        fails.append(f"  MISMATCH {label}: paper={expected} data={actual}")


cells = F.load_cells()
feat = json.load(open(os.path.join(SWEEP, "depth_features.json")))
all48 = sorted(feat)
main24 = [k for k in all48 if k.startswith("main/")]
branch_of = lambda k: (DENSE if feat[k]["circuit"]["rho"] >= DENSE_THRESHOLD
                       else SPARSE)


def portfolio(keys, horizons):
    """(EPR of each completed instance, total wall clock) for one portfolio."""
    eprs, secs = [], 0.0
    for k in keys:
        sub = horizons(k) if callable(horizons) else horizons
        e, s = F.score(cells, [k], sub)
        eprs += e
        secs += s
    return eprs, secs


# ---------------------------------------------------------------- the set
check("horizons are the live constant", str(list(FIXED)),
      str(list(F.H.cp.PORTER_HORIZONS)))
# "the union of the two sets the retired rule chose between"
check("fixed set is the union of the retired pair", str(sorted(FIXED)),
      str(sorted(set(DENSE) | set(SPARSE))))
# "the configured horizon ... which the set contains"
check("configured horizon is a candidate", True, 16 in FIXED)

# ------------------------------------------- fixed set against the branch
b24, tb24 = portfolio(main24, branch_of)
f24, tf24 = portfolio(main24, FIXED)
b48, _ = portfolio(all48, branch_of)
f48, _ = portfolio(all48, FIXED)
check("branch and fixed set cover the same main instances",
      str(len(b24)), str(len(f24)))
# "matches a tuned two-set rule on the main suite"
check("fixed set matches the branch on main 24", 0.0,
      round(100 * (F.gm(f24) / F.gm(b24) - 1), 1))
check("branch main-24 gmean", 175.0, round(F.gm(b24), 1), tol=0.05001)
check("fixed main-24 gmean", 175.0, round(F.gm(f24), 1), tol=0.05001)
# "and is 0.2% better pooled" -- over all forty-eight
check("fixed set pooled gain over the branch", -0.2,
      round(100 * (F.gm(f48) / F.gm(b48) - 1), 1))
# "1.6 times the compile time for one pass"
check("fixed set single-pass time ratio", 1.6, round(tf24 / tb24, 1))

# ------------------------------------------------- "three values are not enough"
best3 = min((F.gm(portfolio(main24, s)[0]), s)
            for s in __import__("itertools").combinations(F.HORIZONS, 3)
            if 16 in s and len(portfolio(main24, s)[0]) == len(b24))
check("best three-value set", "(4, 16, 128)", str(best3[1]))
check("best three-value set vs branch, main 24", 0.5,
      round(100 * (best3[0] / F.gm(b24) - 1), 1))
check("best three-value set vs branch, pooled", 0.2,
      round(100 * (F.gm(portfolio(all48, best3[1])[0]) / F.gm(b48) - 1), 1))

# ------------------------------------- "nor is this particular quartet distinguished"
NEAR = ((4, 16, 32, 128), (4, 16, 48, 128), (4, 16, 64, 128))
pooled = {s: F.gm(portfolio(all48, s)[0]) for s in (FIXED,) + NEAR}
for s in NEAR:
    check(f"{s} within a percent of the adopted set pooled", True,
          abs(100 * (pooled[s] / pooled[FIXED] - 1)) < 1.0)
# "and the last is slightly better pooled"
check("best of the four quartets pooled", str(NEAR[-1]),
      str(min(pooled, key=pooled.get)))

# ------------------------------------------------------- backward refinement
ref = {r["key"]: r for r in
       (json.loads(l) for l in open(os.path.join(SWEEP,
                                                 "four_horizon_refined.jsonl")))
       if tuple(r["horizons"]) == FIXED}
rel = json.load(open(os.path.join(HERE, "compare_results_selection.json")))
rel = rel if isinstance(rel, list) else rel["rows"]
ALIAS = {"qnn": ("qnn_DEEP", "qnn_OLD_DEEP")}


def sweep_key(row):
    for cand in (row["circuit"],) + ALIAS.get(row["circuit"], ()):
        k = f"main/{row['suite']}/{cand}"
        if k in ref:
            return k
    raise KeyError(row["circuit"])


check("+R covers the twenty-four main instances", str(len(rel)), str(len(ref)))
# "under backward refinement it is identical on every one of the twenty-four"
check("+R over the fixed set differs from the released leg on", 0,
      sum(1 for r in rel if ref[sweep_key(r)]["epr"] != r["sfc_refined"]["epr"]),
      tol=0)
# "1.3 with refinement".  Only the fixed-set half is in a released file: the
# branch's 386 s is reported in horizon_sweep/report_four_horizon.md and HEAD
# can no longer reproduce it, the branch having been removed from the code.
BRANCH_REFINED_SECONDS = 386.0
_tf = sum(ref[sweep_key(r)]["seconds"] for r in rel)
check("+R fixed-set total seconds", 499, round(_tf), tol=1.0)
check("fixed set refinement time ratio", 1.3,
      round(_tf / BRANCH_REFINED_SECONDS, 1))

if fails:
    print(f"\n{len(fails)} MISMATCHES:")
    print("\n".join(fails))
    sys.exit(1)
print("Section IV-E's horizon claims agree with paper/horizon_sweep/")
