"""Which relief tier receives an adjacent-blocked seed?  (Section V-C)

V-C claims the distance-reducing-only restriction on relief seeds is
unreachable while the TeleGate is available, and that it is what makes
strict TeleGate removal deadlock.  Two tiers can seed the relief BFS:

  opportunistic  -- runs when a normal plan EXISTS; receives ALL blocked
                    plans (router.py: _select_opportunistic_capacity_relief_plan,
                    whose own comment reads "Both blocked modes get the same
                    reservoir search")
  tail fallback  -- runs when NO normal plan exists; receives only the
                    distance-reducing ones unless
                    capacity_relief_from_adjacent_blocked is set

Measured over 13 circuits / 4,286 remote-stage calls under the shipped
configuration: every one of the 3,306 calls holding an adjacent-blocked plan
routed it to the opportunistic tier, and the tail fallback fired 30 times
with an adjacent-blocked seed available on NONE of them.  So the restriction
is a dead branch in the full protocol; removing the TeleGate is what makes it
live.  Run from the repo root or paper/.
"""
import sys, collections
REPO = "/Users/sanjiangli/Documents/pyzoo/SFC"
sys.path.insert(0, REPO)

import porter
from compile_porter import parse_qasm2, hardware_for_name, build_initial_layout
from ablation_mechanisms import TELESABRE_CIRCUITS, SUITES, FILES
from porter.router import PorterRouter

STAT = collections.Counter()
_stage = PorterRouter._execute_plan_first_remote_stage
_opp = PorterRouter._select_opportunistic_capacity_relief_plan


def stage(self, state, info):
    mf = self.cfg.min_free_before_teleport
    normal = self._filter_revisiting_teleports(
        self._generate_remote_plans(state, info, mf), state)
    blocked = self._generate_blocked_teleport_plans(state, info, mf)
    chosen, _ = self._select_ready_or_preparable_remote_plan(normal, state, info, mf)
    adj = [p for p in blocked if p.mode == "blocked_capacity_adjacent"]
    dr = [p for p in blocked if p.mode == "blocked_capacity_distance_reducing"]
    STAT["remote-stage calls"] += 1
    if adj:
        STAT["calls with an adjacent-blocked plan present"] += 1
    if chosen is None:
        STAT["TAIL tier fires (no normal plan)"] += 1
        if adj:
            STAT["  ** TAIL fires AND an adjacent-blocked seed exists (refused)"] += 1
        if dr:
            STAT["  TAIL has distance-reducing seeds"] += 1
    elif adj:
        STAT["OPP tier receives an adjacent-blocked plan"] += 1
    return _stage(self, state, info)


def opp(self, blocked_plans, *a, **k):
    if any(p.mode == "blocked_capacity_adjacent" for p in blocked_plans):
        STAT["OPP tier ranks adjacent-blocked among its seeds"] += 1
    out = _opp(self, blocked_plans, *a, **k)
    if out is not None:
        STAT["OPP relief plan committed"] += 1
    return out


PorterRouter._execute_plan_first_remote_stage = stage
PorterRouter._select_opportunistic_capacity_relief_plan = opp

CASES = [("25", "ae"), ("25", "random"), ("25", "qft"), ("25", "qnn"),
         ("64", "ae"), ("64", "qft"), ("64", "qaoa"), ("64", "qpeexact"),
         ("64", "graphstate"), ("64", "multiplier"),
         ("80", "qpeexact"), ("80", "ae"), ("80", "qft")]
SUB = {s: sub for s, _a, sub in SUITES}
ARCH = {s: a for s, a, _sub in SUITES}
for suite, circ in CASES:
    fname = FILES.get(suite, {}).get(circ) or \
        f"{circ}_nativegates_ibm_qiskit_opt3_{suite}.qasm"
    path = TELESABRE_CIRCUITS / SUB[suite] / fname
    if not path.exists():
        print(f"  missing {path}")
        continue
    _, hw = hardware_for_name(ARCH[suite])
    gates, nl = parse_qasm2(path)
    cfg = porter.RouterConfig(random_seed=0)
    layout = build_initial_layout(gates, hw, nl,
                                  min_free_per_core=cfg.min_free_before_teleport)
    porter.PorterRouter(hw, cfg).compile(gates, layout)
    print(f"  routed {suite}/{circ}")

print()
for k in sorted(STAT, key=lambda k: -STAT[k]):
    print(f"{STAT[k]:>9}  {k}")
