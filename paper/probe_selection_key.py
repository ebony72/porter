"""What the last two components of the remote-plan selection key actually do.

Section III-E orders scored plans by ``(-total, prep, -f_dst)`` with a stable
identifier resolving anything still tied.  This probe measures the two trailing
components over the paper's main suites, under PORTER's own protocol, and
writes ``paper/selection_key_probe.json``.  ``verify_paper_numbers.py`` pins
every figure III-E quotes from it.

Definitions, which matter because several near-miss ones give other numbers:

* A *ranking* is one scored candidate set at the head of a remote stage --- the
  normal-plan selection, not the sets re-scored inside capacity relief.  The
  observer wraps ``_select_ready_or_preparable_remote_plan`` and reads the set
  it already built, so it draws no extra randomness and the routes it observes
  are the shipped ones.
* The *winner* is the plan the key sorts first, ``min(scored, key=...)``.
* A ranking is *tie-decided* when some rival of a different primitive carries
  the identical ``total``, so ``-total`` did not choose the action.  Which of
  the two trailing components separated the winner from the best such rival is
  recorded, along with the winner's destination headroom when ``-f_dst`` did.
* ``crosskind``/``within`` count the rankings where the winner and a rival are
  tied on ``total`` *and* ``prep`` and are separated by ``-f_dst``, split by
  whether that rival is of another primitive or another TeleData.

Also audits the single-link invariant of Section III-D: every plan generated,
of every primitive and every generating mode, has ``c_dst`` adjacent to
``c_src``.

Run: python3 paper/probe_selection_key.py   (~12 min)
"""
import collections
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, _REPO)

import porter
import compile_porter as cp
from compare_routers import SUITES

R = porter.router.PorterRouter
_SEL = R._select_ready_or_preparable_remote_plan
_STAGE = R._execute_plan_first_remote_stage
_GEN = R._generate_remote_plans
_BLOCKED = R._generate_blocked_teleport_plans
_RELIEF = R._generate_bfs_capacity_relief_plans
_PREP = R._select_preparation_swaps_for_plan
_COMMIT = R._commit_remote_plan
_OPP = R._select_opportunistic_capacity_relief_plan

GATEY = ("telegate", "telegate_packet")
C = collections.Counter()
TIE_TOTALS = collections.Counter()
FDST_AT_TIE = collections.Counter()
CORE_DIST = collections.Counter()
PREP_ROUNDS = collections.Counter()
_first = {"pending": False}
_rounds = {"n": 0}


def _cores(router, plan, layout):
    """(c_src, c_dst) under the unified plan tuple of Section III-D."""
    if plan.kind == "teleport":
        return plan.src_core, plan.dst_core
    if plan.kind == "telegate":
        q0, q1 = plan.gate.qubits
        return layout.core_of(q0), layout.core_of(q1)
    if plan.kind == "telegate_packet" and plan.gates:
        control, target = plan.gates[0].qubits
        return layout.core_of(control), layout.core_of(target)
    return None, None


def _audit(router, plans, layout):
    for plan in plans:
        c_src, c_dst = _cores(router, plan, layout)
        key = (plan.kind, plan.mode)
        if c_src is None or c_dst is None:
            CORE_DIST[key + ("no-cores",)] += 1
        else:
            CORE_DIST[key + (router.hw.core_distance(c_src, c_dst),)] += 1
    return plans


def gen_obs(self, state, info, min_free):
    return _audit(self, _GEN(self, state, info, min_free), state.layout)


def blocked_obs(self, state, info, min_free):
    return _audit(self, _BLOCKED(self, state, info, min_free), state.layout)


def relief_obs(self, state, blocked, min_free, **kw):
    return _audit(self, _RELIEF(self, state, blocked, min_free, **kw), state.layout)


def stage_obs(self, state, info):
    _first["pending"] = True
    return _STAGE(self, state, info)


def sel_obs(self, plans, state, info, min_free):
    plan, scored = _SEL(self, plans, state, info, min_free)
    if not _first["pending"] or not scored:
        return plan, scored
    _first["pending"] = False
    C["rankings"] += 1
    kinds = {p.kind for _, p, _ in scored}
    if len(kinds) > 1:
        C["mixed_kind"] += 1

    # Every group of equal total that spans primitives, wherever it sits.
    groups = collections.defaultdict(set)
    for total, p, _score in scored:
        groups[total].add(p.kind)
    for total, ks in groups.items():
        if len(ks) > 1:
            C["contains_crosskind_tie"] += 1
            if abs(total - round(total)) > 1e-9:
                C["tie_at_noninteger_total"] += 1
            if total <= 0:
                C["tie_at_nonpositive_total"] += 1
            if ks == {"telegate", "telegate_packet"}:
                C["tie_telegate_vs_packet"] += 1

    w_total, w_plan, w_score = min(scored, key=self._remote_plan_selection_key)
    rivals = [
        (t, p, s) for (t, p, s) in scored
        if p is not w_plan and p.kind != w_plan.kind and t == w_total
    ]
    if rivals:
        C["tie_decided"] += 1
        TIE_TOTALS[w_total] += 1
        C["tie_won_by_teledata" if w_plan.kind == "teleport" else "tie_won_by_gate_family"] += 1
        _, _r_plan, r_score = min(rivals, key=lambda item: self._remote_plan_selection_key(item))
        if not self._float_tied(w_score.prep, r_score.prep):
            C["tie_broken_by_prep"] += 1
        elif not self._float_tied(w_score.capacity, r_score.capacity):
            C["tie_broken_by_capacity"] += 1
            if w_plan.kind == "teleport":
                FDST_AT_TIE[int(round(-w_score.capacity))] += 1
        else:
            C["tie_broken_by_stable_id"] += 1
        # Does the winner realise its whole total now, or is part predicted?
        if w_plan.kind == "teleport":
            d = w_score.direct_gain
            C["tie_teledata_lookahead_zero" if abs(d - w_total) < 1e-9
              else "tie_teledata_lookahead_nonzero"] += 1

    # What separates plans that agree on total AND prep, i.e. the rankings the
    # capacity component itself resolves.
    same = [(t, p, s) for (t, p, s) in scored
            if p is not w_plan and t == w_total
            and self._float_tied(s.prep, w_score.prep)
            and not self._float_tied(s.capacity, w_score.capacity)]
    if same:
        if any(p.kind != w_plan.kind for _, p, _ in same):
            C["capacity_separates_crosskind"] += 1
        if any(p.kind == w_plan.kind == "teleport" for _, p, _ in same):
            C["capacity_separates_within_teledata"] += 1
    return plan, scored


def prep_obs(self, state, plan, stage):
    """Count preparation rounds and empty candidate sets.  Section III-F's
    completion argument says the empty case cannot arise: no core is ever
    full, so a side carrying an endpoint always admits a SWAP (the endpoint
    itself is occupied) and the destination side is unsatisfied only when its
    port is occupied, where the nearest free position necessarily has an
    occupied neighbour on a shortest path to the port."""
    out = _PREP(self, state, plan, stage)
    C["prep_calls"] += 1
    _rounds["n"] += 1
    if not out:
        C["prep_empty_candidate_set"] += 1
    return out


def commit_obs(self, plan, state, info, min_free, prep_stage=None):
    _rounds["n"] = 0
    try:
        out = _COMMIT(self, plan, state, info, min_free, prep_stage=prep_stage)
    except RuntimeError as exc:
        msg = str(exc)
        if "cycles" in msg:
            C["prep_abort_repeated_decision_state"] += 1
        elif "oscillates" in msg:
            C["prep_abort_iteration_budget"] += 1
        raise
    PREP_ROUNDS[_rounds["n"]] += 1
    return out


def opp_obs(self, blocked, normal_plan, normal_scores, state, info, min_free):
    """Count the stages where the assist margin is met but the one-hop relief
    search returns nothing -- the blocked plan is adjacent-mode, so the search
    is capped at a single hop and every neighbour is itself below f_min."""
    out = _OPP(self, blocked, normal_plan, normal_scores, state, info, min_free)
    if out is None and blocked:
        score = self._score_for_plan_in_scored(normal_plan, normal_scores)
        gain, best = max(((self._remote_plan_gain(b, state, info), b) for b in blocked),
                         key=lambda item: item[0])
        if score is not None and gain - score.total > float(self.cfg.capacity_relief_assist_margin):
            C["assist_margin_met_but_no_relief_plan"] += 1
            if best.mode == "blocked_capacity_adjacent":
                C["assist_unreachable_adjacent_mode"] += 1
            free = {c: state.layout.free_count(self.hw, c) for c in self.hw.cores}
            floor = self.cfg.min_free_before_teleport
            if all(free[n] < floor for n in self.hw.core_neighbors(best.dst_core)):
                C["assist_unreachable_all_neighbours_below_floor"] += 1
            if any(f >= floor for c, f in free.items() if c != best.dst_core):
                C["assist_unreachable_though_reservoir_exists"] += 1
    return out


def main():
    R._select_preparation_swaps_for_plan = prep_obs
    R._commit_remote_plan = commit_obs
    R._select_opportunistic_capacity_relief_plan = opp_obs
    R._execute_plan_first_remote_stage = stage_obs
    R._select_ready_or_preparable_remote_plan = sel_obs
    R._generate_remote_plans = gen_obs
    R._generate_blocked_teleport_plans = blocked_obs
    R._generate_bfs_capacity_relief_plans = relief_obs
    instances = []
    try:
        for suite in ("25", "64"):
            spec = SUITES[suite]
            for fname in spec["files"]:
                circuit = fname.split("_")[0]
                gates, n = cp.parse_qasm2(spec["circuit_dir"] / fname)
                _label, hw = cp.hardware_for_name(spec["arch_name"])
                cfg = porter.RouterConfig()
                layout = cp.build_initial_layout(
                    gates, hw, n, min_free_per_core=cfg.min_free_before_teleport)
                try:
                    st, _ = cp.route(hw, cfg, gates, layout, selection=True)
                    stats = st.stats
                    epr = (stats.teleport_count + stats.telegate_count
                           + stats.telegate_packet_count)
                    ok = True
                except Exception:
                    epr, ok = None, False
                instances.append({"suite": suite, "circuit": circuit,
                                  "completed": ok, "epr": epr})
                print(f"  {suite}/{circuit} {'ok' if ok else 'FAILED'}", flush=True)
    finally:
        R._execute_plan_first_remote_stage = _STAGE
        R._select_ready_or_preparable_remote_plan = _SEL
        R._generate_remote_plans = _GEN
        R._generate_blocked_teleport_plans = _BLOCKED
        R._generate_bfs_capacity_relief_plans = _RELIEF
        R._select_preparation_swaps_for_plan = _PREP
        R._commit_remote_plan = _COMMIT
        R._select_opportunistic_capacity_relief_plan = _OPP

    out = {
        "instances": instances,
        "counts": dict(C),
        "tie_totals": {str(k): v for k, v in sorted(TIE_TOTALS.items())},
        "fdst_when_capacity_decided": {str(k): v for k, v in sorted(FDST_AT_TIE.items())},
        "plan_core_distance": {f"{k[0]}|{k[1]}|{k[2]}": v for k, v in sorted(
            CORE_DIST.items(), key=lambda kv: tuple(str(x) for x in kv[0]))},
        "prep_rounds_per_committed_plan": {str(k): v for k, v in sorted(PREP_ROUNDS.items())},
        "max_prep_rounds": max(PREP_ROUNDS) if PREP_ROUNDS else 0,
        "max_prep_iterations_per_plan": porter.RouterConfig().max_prep_iterations_per_plan,
        "plans_generated": sum(CORE_DIST.values()),
        "distances_observed": sorted({k[2] for k in CORE_DIST}, key=str),
    }
    path = os.path.join(_HERE, "selection_key_probe.json")
    with open(path, "w") as fh:
        json.dump(out, fh, indent=1)
    print("\n" + json.dumps({k: v for k, v in out.items() if k != "plan_core_distance"}, indent=1))
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
