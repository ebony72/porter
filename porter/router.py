"""The PORTER routing engine (see class docstring of PorterRouter)."""

from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from typing import Dict, List, Tuple, Optional, Set, Iterable, Any, Callable
import math
import random

from .hardware import CoreId, Edge, GateId, Hardware, LogicalQubit, PhysicalQubit, canonical_edge
from .layout import Layout
from .model import (
    Action,
    CompiledOp,
    FrontInfo,
    Gate,
    RemotePlan,
    RemotePlanScore,
    RouterConfig,
    RouterState,
    assign_gate_ids,
)


@dataclass
class DagSimState:
    """Copy-on-write view of the live DAG state.

    ``active`` and ``pred_base`` are shared read-only with the live router
    state; simulated predecessor-count decrements go to ``pred_overlay``.
    A snapshot therefore costs O(|frontier|) instead of O(|remaining gates|).
    The state must not outlive the current decision step: once the real DAG
    mutates, existing snapshots are stale.
    """

    active: Set[GateId]
    frontier: Set[GateId]
    removed: Set[GateId]
    pred_base: Dict[GateId, int]
    pred_overlay: Dict[GateId, int]

    def pred_count_of(self, gid: GateId) -> int:
        value = self.pred_overlay.get(gid)
        if value is None:
            value = self.pred_base.get(gid, 0)
        return value


class DagFrontierSimulator:
    """Small helper for virtual DAG-frontier advancement."""

    def __init__(self, successors: Dict[GateId, Set[GateId]]):
        self.successors = successors

    def snapshot(
        self,
        active: Iterable[GateId],
        pred_count: Dict[GateId, int],
        *,
        frontier: Optional[Iterable[GateId]] = None,
        removed: Optional[Iterable[GateId]] = None,
    ) -> DagSimState:
        removed_set = set(removed or ())
        if frontier is None:
            active_set = set(active)
            frontier_set = {
                gid for gid in active_set
                if gid not in removed_set and pred_count.get(gid, 0) == 0
            }
        else:
            active_set = active if isinstance(active, set) else set(active)
            frontier_set = set(frontier)
        return DagSimState(
            active=active_set,
            frontier=frontier_set,
            removed=removed_set,
            pred_base=pred_count,
            pred_overlay={},
        )

    @staticmethod
    def current_layer(state: DagSimState) -> List[GateId]:
        return sorted(
            gid for gid in state.frontier
            if gid in state.active and gid not in state.removed
        )

    def remove_gate_ids(self, state: DagSimState, gate_ids: Iterable[GateId]) -> None:
        # Batch removal is order-independent: the final overlay counts and
        # frontier do not depend on the processing order of ``gate_ids``.
        frontier = state.frontier
        active = state.active
        removed = state.removed
        overlay = state.pred_overlay
        base = state.pred_base
        successors = self.successors
        for gid in set(gate_ids):
            if gid not in active or gid in removed:
                continue
            removed.add(gid)
            frontier.discard(gid)
            for succ in successors.get(gid, ()):
                if succ not in active or succ in removed:
                    continue
                count = overlay.get(succ)
                if count is None:
                    count = base.get(succ, 0)
                count -= 1
                overlay[succ] = count
                if count == 0:
                    frontier.add(succ)


class CapacityReliefPlanner:
    """Generate capacity-relief teleport candidates."""

    def __init__(self, hw: Any):
        self.hw = hw

    def paths_to_nearest_reservoir(
        self,
        layout: Any,
        blocked_core: CoreId,
        min_free: int,
        max_path_hops: Optional[int],
    ) -> List[Tuple[CoreId, ...]]:
        if layout.free_count(self.hw, blocked_core) >= min_free:
            return []

        queue: deque[Tuple[CoreId, Tuple[CoreId, ...]]] = deque(
            [(blocked_core, (blocked_core,))]
        )
        visited: Set[CoreId] = {blocked_core}
        shortest_hops: Optional[int] = None
        paths: List[Tuple[CoreId, ...]] = []
        seen_tail_edges: Set[Tuple[CoreId, CoreId]] = set()

        while queue:
            current, path = queue.popleft()
            current_hops = len(path) - 1
            if shortest_hops is not None and current_hops >= shortest_hops:
                continue
            if max_path_hops is not None and current_hops >= max_path_hops:
                continue

            for nxt in self.hw.core_neighbors(current):
                next_hops = current_hops + 1
                if max_path_hops is not None and next_hops > max_path_hops:
                    continue
                if shortest_hops is not None and next_hops > shortest_hops:
                    continue

                if layout.free_count(self.hw, nxt) >= min_free:
                    if shortest_hops is None:
                        shortest_hops = next_hops
                    if next_hops == shortest_hops:
                        tail_edge = (current, nxt)
                        if tail_edge not in seen_tail_edges:
                            seen_tail_edges.add(tail_edge)
                            paths.append(path + (nxt,))
                    continue

                if shortest_hops is None and nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, path + (nxt,)))

        return paths

    def generate_plans(
        self,
        layout: Any,
        blocked_plans: List[Any],
        min_free: int,
        *,
        max_path_hops: Optional[int],
        mode: str,
        make_plan: Callable[..., Any],
    ) -> List[Any]:
        plans: List[Any] = []
        seen_actions: Set[Tuple[LogicalQubit, CoreId, CoreId]] = set()

        for blocked_plan in blocked_plans:
            if blocked_plan.kind != "teleport" or blocked_plan.dst_core is None:
                continue
            blocked_core = blocked_plan.dst_core
            if layout.free_count(self.hw, blocked_core) >= min_free:
                continue

            for path in self.paths_to_nearest_reservoir(
                layout, blocked_core, min_free, max_path_hops
            ):
                tail_src, reservoir = path[-2], path[-1]
                chain_hops = len(path) - 1
                for victim in layout.logicals_in_core(tail_src):
                    action_key = (victim, tail_src, reservoir)
                    if action_key in seen_actions:
                        continue
                    seen_actions.add(action_key)
                    plans.append(
                        make_plan(
                            kind="teleport",
                            gate=blocked_plan.gate,
                            moving_qubit=victim,
                            src_core=tail_src,
                            dst_core=reservoir,
                            mode=mode,
                            metadata={
                                "seed": blocked_plan.gate.gid,
                                "relief_for_seed": blocked_plan.gate.gid,
                                "blocked_core": blocked_core,
                                "blocked_move_src": blocked_plan.src_core,
                                "blocked_move_dst": blocked_plan.dst_core,
                                "blocked_move_qubit": blocked_plan.moving_qubit,
                                "blocked_plan_mode": blocked_plan.mode,
                                "relief_victim": victim,
                                "relief_destination": reservoir,
                                "chain_path": list(path),
                                "chain_hops": chain_hops,
                                "chain_tail_source": tail_src,
                                "chain_reservoir": reservoir,
                                "reason": "evacuate_bfs_tail_toward_nearest_capacity_reservoir",
                            },
                        )
                    )

        return plans


class PorterRouter:
    """PORTER: Plan-Oriented Router for Teleportation-Enabled aRchitectures.

    PORTER routes circuits on multi-core hardware with a strict two-stage,
    locality-first loop over the zero-predecessor DAG frontier:
      - executable single-qubit gates and local CX gates are emitted first;
      - local CX gates that need routing only generate local SWAP candidates;
      - only when the DAG front has no local work does the remote stage run.

    The remote stage is *plan-committed*: it first compares whole
    ``RemotePlan`` alternatives (teleport, single telegate, same-control
    telegate packet, capacity relief), commits to the best one, and only then
    generates preparation SWAPs — for that plan alone — until it is ready.

    The remote stage is physical:
      - telegate/teleport require the corresponding inter-core communication
        qubits to be free;
      - the moving logical qubit must be physically adjacent to its source-side
        communication qubit;
      - teleportation moves the logical qubit onto the target-side communication
        qubit;
      - when these conditions are not yet met, the remote-stage action set also
        includes local SWAPs that free communication qubits or move logical qubits
        toward them.
    """

    def __init__(self, hw: Hardware, cfg: Optional[RouterConfig] = None):
        self.hw = hw
        self.cfg = cfg or RouterConfig()
        self._rng = random.Random(self.cfg.random_seed)
        self._capacity_relief = CapacityReliefPlanner(hw)

    def compile(self, circuit: List[Gate], initial_layout: Layout) -> RouterState:
        """Route ``circuit`` from ``initial_layout`` and return the final state."""
        self._rng = random.Random(self.cfg.random_seed)
        state = RouterState(layout=initial_layout.clone(), remaining=assign_gate_ids(circuit))
        self._validate_tie_break_config()
        self._validate_circuit(state.remaining, initial_layout.num_logical)
        if self.cfg.repair_full_cores:
            self._repair_full_cores(state)
        self._initialize_dag(state)
        self._refresh_free_slot_queues(state)

        front: List[Gate] = []
        front_info: Optional[FrontInfo] = None
        front_dirty = True
        layout_dirty = True

        # Stall guard: `dag_active` only shrinks, so a run of iterations that
        # never shrinks it is a router doing work that retires no gate.
        stall_limit = int(getattr(self.cfg, "max_iterations_without_progress", 0) or 0)
        active_watermark = len(state.dag_active)
        stalled_iterations = 0

        for _ in range(self.cfg.max_iterations):
            if not state.dag_active:
                self._sync_remaining(state)
                self._finalize_depth_stats(state)
                return state

            if stall_limit:
                active_now = len(state.dag_active)
                if active_now < active_watermark:
                    active_watermark = active_now
                    stalled_iterations = 0
                else:
                    stalled_iterations += 1
                    if stalled_iterations > stall_limit:
                        self._sync_remaining(state)
                        raise RuntimeError(
                            f'Router retired no gate in {stall_limit} iterations; '
                            'abandoning as stalled')

            if front_dirty:
                front = self._current_dag_front(state)
                front_dirty = False
                layout_dirty = True
            if layout_dirty:
                front_info = self._classify_front(front, state.layout)
                layout_dirty = False
            assert front_info is not None

            if self._execute_direct_executable_from_front(state, front_info):
                front_dirty = True
                continue

            # Keep remote actions out of the decision set until all current
            # front-local CX gates have been made executable.
            if front_info.local_cx_need_swap:
                local_actions = self._generate_local_swap_actions(state, front_info)
                if local_actions:
                    self._apply_action(self._choose_best_action(local_actions, state, 'local_swap'), state)
                    layout_dirty = True
                    continue

            removed = self._execute_plan_first_remote_stage(state, front_info)
            if removed is None:
                self._sync_remaining(state)
                raise RuntimeError(self._deadlock_message(state, front_info))
            if removed:
                front_dirty = True
            else:
                layout_dirty = True

        self._sync_remaining(state)
        raise RuntimeError('Router exceeded max_iterations; possible oscillation or deadlock')

    @staticmethod
    def _validate_circuit(gates: List[Gate], num_logical: int) -> None:
        for g in gates:
            if not (g.is_cx() or g.is_single_qubit()):
                raise ValueError(
                    f"Unsupported gate for this router: {g} "
                    "(expected basis ['id', 'rz', 'sx', 'x', 'cx'])"
                )
            for q in g.qubits:
                if not (0 <= q < num_logical):
                    raise ValueError(
                        f"Gate {g} references q{q}, outside the layout's "
                        f"{num_logical} logical qubits"
                    )

    def _repair_full_cores(self, state: RouterState) -> None:
        """Legalize ``state.layout`` in place: no core may have zero free
        physical qubits (see RouterConfig.repair_full_cores). For each full
        core, evicts one logical qubit -- the lowest-indexed one, an
        arbitrary but deterministic choice; this is a legality fix, not a
        layout-quality heuristic -- into the core with the most free
        capacity elsewhere, repeating until no core is full. Raises
        ValueError if some full core has no core with spare capacity to
        receive an eviction (the circuit doesn't fit this hardware with any
        headroom at all)."""
        layout = state.layout
        core_ids = list(self.hw.cores)
        for _ in range(len(core_ids) + 1):
            full_cores = [cid for cid in core_ids if layout.free_count(self.hw, cid) == 0]
            if not full_cores:
                return
            for cid in full_cores:
                if layout.free_count(self.hw, cid) > 0:
                    continue
                dst_cid = max(
                    (c for c in core_ids if c != cid),
                    key=lambda c: (layout.free_count(self.hw, c), -c),
                )
                if layout.free_count(self.hw, dst_cid) == 0:
                    raise ValueError(
                        f"Initial layout leaves core {cid} at full capacity "
                        "and no other core has free capacity to relieve it "
                        "(circuit does not fit this hardware with any headroom)."
                    )
                q = layout.logicals_in_core(cid)[0]
                dst_phys = layout.free_physical_qubits(self.hw, dst_cid)[0]
                layout.move_logical_to_physical(q, dst_phys, dst_cid)
                state.stats.initial_layout_repairs += 1
        raise RuntimeError("_repair_full_cores did not converge; this indicates a bug")

    def _finalize_depth_stats(self, state: RouterState) -> None:
        """按 TeleSABRE 的物理比特时间线规则计算最终深度。"""
        qubit_depths: Dict[PhysicalQubit, int] = {p: 0 for p in self.hw.phys_to_core}
        intercore_depths: Dict[PhysicalQubit, int] = {p: 0 for p in self.hw.phys_to_core}
        covered_single_telegates: Set[GateId] = set()

        for index, op in enumerate(state.emitted):
            scheduled = self._depth_schedule_for_emitted_op(
                state.emitted, index, covered_single_telegates
            )
            if scheduled is None:
                continue
            physical_qubits, duration, is_intercore = scheduled
            touched = tuple(dict.fromkeys(physical_qubits))
            if not touched:
                raise RuntimeError(f"Depth scheduling operation has no physical qubits: {op.op_type}")
            unknown = [p for p in touched if p not in qubit_depths]
            if unknown:
                raise RuntimeError(f"Depth scheduling references unknown physical qubits: {unknown}")

            start = max(qubit_depths[p] for p in touched)
            finish = start + duration
            for p in touched:
                qubit_depths[p] = finish
                if is_intercore:
                    intercore_depths[p] = finish

        state.stats.depth = max(qubit_depths.values(), default=0)
        state.stats.depth_proxy = state.stats.depth
        state.stats.intercore_depth = max(intercore_depths.values(), default=0)

    def _depth_schedule_for_emitted_op(
        self,
        emitted: List[CompiledOp],
        index: int,
        covered_single_telegates: Set[GateId],
    ) -> Optional[Tuple[Tuple[PhysicalQubit, ...], int, bool]]:
        op = emitted[index]

        if op.op_type in {"single", "local_cx", "local_swap"}:
            return op.physical_qubits, 1, False
        if op.op_type == "teleport":
            return op.physical_qubits, 5, True

        if op.op_type == "cat_entangler":
            role = op.metadata.get("cat_role")
            if role == "single_telegate_start":
                gate_id = op.metadata.get("logical_gate")
                if not isinstance(gate_id, int):
                    raise RuntimeError("Single telegate depth scheduling is missing logical_gate")
                covered_single_telegates.add(gate_id)
                return self._single_telegate_depth_qubits(emitted, index, gate_id), 5, True
            if role == "packet_start":
                return op.physical_qubits, 5, True
            raise RuntimeError(f"Unknown cat_entangler role for depth scheduling: {role}")

        if op.op_type == "cat_cx":
            gate_id = op.metadata.get("logical_gate")
            if isinstance(gate_id, int) and gate_id in covered_single_telegates:
                return None
            return op.physical_qubits, 1, False

        if op.op_type == "cat_disentangler":
            role = op.metadata.get("cat_role")
            if role == "single_telegate_end":
                return None
            if role == "packet_end":
                return op.physical_qubits, 0, True
            raise RuntimeError(f"Unknown cat_disentangler role for depth scheduling: {role}")

        raise RuntimeError(f"Unknown emitted operation type for depth scheduling: {op.op_type}")

    def _single_telegate_depth_qubits(
        self, emitted: List[CompiledOp], start_index: int, gate_id: GateId
    ) -> Tuple[PhysicalQubit, ...]:
        start_op = emitted[start_index]
        for next_op in emitted[start_index + 1:]:
            if (
                next_op.op_type == "cat_cx"
                and next_op.metadata.get("logical_gate") == gate_id
            ):
                return start_op.physical_qubits + next_op.physical_qubits
            if (
                next_op.op_type == "cat_disentangler"
                and next_op.metadata.get("logical_gate") == gate_id
            ):
                break
        raise RuntimeError(f"Single telegate depth scheduling cannot find cat_cx for gate {gate_id}")

    # ---------------------------------------------------------------------
    # Ordinary per-qubit DAG construction
    # ---------------------------------------------------------------------

    def _initialize_dag(self, state: RouterState) -> None:
        gates = state.remaining
        state.gate_by_id = {g.gid: g for g in gates}
        state.dag_active = {g.gid for g in gates}
        state.active_cx_by_qubit = {}
        for g in gates:
            if g.is_cx():
                for q in g.qubits:
                    state.active_cx_by_qubit[q] = state.active_cx_by_qubit.get(q, 0) + 1
        state.dag_successors = {g.gid: set() for g in gates}
        state.dag_predecessors = {g.gid: set() for g in gates}
        state.dag_predecessor_count = {g.gid: 0 for g in gates}

        last_gate_on_qubit: Dict[LogicalQubit, GateId] = {}
        edge_count = 0
        for g in gates:
            preds: Set[GateId] = set()
            for q in g.qubits:
                pred = last_gate_on_qubit.get(q)
                if pred is not None:
                    preds.add(pred)
            for pred in preds:
                if g.gid not in state.dag_successors[pred]:
                    state.dag_successors[pred].add(g.gid)
                    state.dag_predecessors[g.gid].add(pred)
                    edge_count += 1
            for q in g.qubits:
                last_gate_on_qubit[q] = g.gid

        for gid, preds in state.dag_predecessors.items():
            state.dag_predecessor_count[gid] = len(preds)
        state.dag_edge_count = edge_count
        state.dag_frontier = {
            gid for gid, count in state.dag_predecessor_count.items() if count == 0
        }


    # ---------------------------------------------------------------------
    # DAG frontier construction and classification
    # ---------------------------------------------------------------------

    def _current_dag_front(self, state: RouterState) -> List[Gate]:
        # Gate ids are assigned in circuit order, so sorting by gid yields the
        # front in circuit order -- a canonical order independent of the set's
        # iteration order, which is what makes the emitted stream deterministic.
        front_ids = sorted(state.dag_frontier)
        return [state.gate_by_id[gid] for gid in front_ids]

    def _classify_front(self, front: List[Gate], layout: Layout) -> FrontInfo:
        singles: List[Gate] = []
        direct_local: List[Gate] = []
        local_need_swap: List[Gate] = []
        adj_remote: List[Gate] = []
        non_adj_remote: List[Gate] = []

        for g in front:
            if g.is_single_qubit():
                singles.append(g)
                continue
            if not g.is_cx():
                continue
            q0, q1 = g.qubits
            c0, c1 = layout.core_of(q0), layout.core_of(q1)
            if c0 == c1:
                p0, p1 = layout.phys_of(q0), layout.phys_of(q1)
                if self.hw.local_distance(c0, p0, p1) == 1:
                    direct_local.append(g)
                else:
                    local_need_swap.append(g)
            elif self.hw.core_distance(c0, c1) == 1:
                adj_remote.append(g)
            else:
                non_adj_remote.append(g)

        return FrontInfo(front, singles, direct_local, local_need_swap, adj_remote, non_adj_remote)


    def _execute_direct_executable_from_front(self, state: RouterState, info: FrontInfo) -> int:
        executable_ids = {g.gid for g in info.singles + info.direct_local_cx}
        executable = [g for g in info.front if g.gid in executable_ids]
        if not executable:
            return 0
        for g in executable:
            if g.is_single_qubit():
                q = g.qubits[0]
                p = state.layout.phys_of(q)
                c = state.layout.core_of(q)
                state.emitted.append(
                    CompiledOp(
                        op_type="single",
                        gates=(g,),
                        qubits=(q,),
                        physical_qubits=(p,),
                        cores=(c,),
                    )
                )
                state.stats.single_count += 1
            elif g.is_cx():
                q0, q1 = g.qubits
                p0, p1 = state.layout.phys_of(q0), state.layout.phys_of(q1)
                c = state.layout.core_of(q0)
                state.emitted.append(
                    CompiledOp(
                        op_type="local_cx",
                        gates=(g,),
                        qubits=(q0, q1),
                        physical_qubits=(p0, p1),
                        cores=(c,),
                    )
                )
                state.stats.local_cx_count += 1
            state.stats.emitted_gate_count += 1

        self._remove_gate_ids(state, executable_ids)
        return len(executable)

    # ---------------------------------------------------------------------
    # Action selection and score tracing
    # ---------------------------------------------------------------------

    def _choose_best_action(self, actions: List[Action], state: RouterState, stage: str) -> Action:
        scored = [
            (
                self._local_action_cost(action, state),
                self._action_secondary_score(action, stage),
                action,
            )
            for action in actions
        ]
        scored.sort(key=lambda item: (item[0], item[1], self._action_stable_key(item[2])))

        best_primary = scored[0][0]
        primary_tied = [item for item in scored if self._float_tied(item[0], best_primary)]
        best_secondary = primary_tied[0][1]
        tied = [item for item in primary_tied if self._float_tied(item[1], best_secondary)]
        if len(tied) == 1 or not self.cfg.seeded_tie_break_enabled:
            return tied[0][2]

        ordered = sorted(tied, key=lambda item: self._action_stable_key(item[2]))
        chosen_index = self._rng.randrange(len(ordered))
        self._record_seeded_tie_break(state, stage, len(ordered))
        return ordered[chosen_index][2]

    @staticmethod
    def _action_secondary_score(action: Action, stage: str) -> float:
        if stage == 'local_swap' and action.metadata.get('reason') == 'local_route':
            return float(action.metadata.get('after_front_local_distance', math.inf))
        return 0.0

    def _float_tied(self, a: float, b: float) -> bool:
        """Compare score values using the configured absolute tie tolerance."""
        if math.isinf(a) or math.isinf(b):
            return a == b
        return math.isclose(a, b, rel_tol=0.0, abs_tol=self.cfg.tie_score_epsilon)

    @staticmethod
    def _action_stable_key(action: Action) -> Tuple[Any, ...]:
        return (
            action.kind,
            action.gate.gid if action.gate is not None else -1,
            tuple(g.gid for g in action.gates),
            action.qubit if action.qubit is not None else -1,
            action.src_core if action.src_core is not None else -1,
            action.dst_core if action.dst_core is not None else -1,
            action.dst_phys if action.dst_phys is not None else -1,
            tuple(action.swap) if action.swap is not None else (-1, -1),
        )

    @staticmethod
    def _remote_plan_stable_key(plan: RemotePlan) -> Tuple[Any, ...]:
        return (
            plan.kind,
            plan.gate.gid,
            tuple(g.gid for g in plan.gates),
            plan.moving_qubit if plan.moving_qubit is not None else -1,
            plan.src_core if plan.src_core is not None else -1,
            plan.dst_core if plan.dst_core is not None else -1,
            plan.mode,
        )

    def _record_seeded_tie_break(self, state: RouterState, stage: str, candidate_count: int) -> None:
        state.stats.seeded_tie_break_count += 1
        state.stats.seeded_tie_candidate_total += candidate_count
        if stage == 'remote_plan':
            state.stats.seeded_remote_plan_tie_break_count += 1
        else:
            state.stats.seeded_local_swap_tie_break_count += 1


    # ---------------------------------------------------------------------
    # Action generation
    # ---------------------------------------------------------------------

    def _score_with_temp_swap(
        self,
        layout: Layout,
        p0: PhysicalQubit,
        p1: PhysicalQubit,
        score_fn: Callable[[Layout], Any],
    ) -> Any:
        """Apply a local SWAP, evaluate ``score_fn`` on the swapped layout, and
        restore the exact pre-swap mapping (including entries swap_physical may
        have minted for previously unmapped positions).  Equivalent to scoring
        a ``layout.clone()`` without the O(num_physical) copies."""
        p2l = layout.physical_to_logical
        had0, v0 = p0 in p2l, p2l.get(p0)
        had1, v1 = p1 in p2l, p2l.get(p1)
        layout.swap_physical(self.hw, p0, p1)
        try:
            return score_fn(layout)
        finally:
            if had0:
                p2l[p0] = v0
            else:
                p2l.pop(p0, None)
            if had1:
                p2l[p1] = v1
            else:
                p2l.pop(p1, None)
            n = layout.num_logical
            if v0 is not None and v0 < n:
                layout.logical_to_physical[v0] = p0
                layout.logical_to_core[v0] = self.hw.phys_to_core[p0]
            if v1 is not None and v1 < n:
                layout.logical_to_physical[v1] = p1
                layout.logical_to_core[v1] = self.hw.phys_to_core[p1]

    def _generate_local_swap_actions(self, state: RouterState, info: FrontInfo) -> List[Action]:
        actions: List[Action] = []
        front_gates = [g for g in info.local_cx_need_swap if g.is_cx()]
        if not front_gates:
            return []

        extended_gates = self._local_swap_extended_local_cx_gates(state, state.layout, set(g.gid for g in front_gates))
        front_phys: Set[PhysicalQubit] = set()
        for g in front_gates:
            for q in g.qubits:
                front_phys.add(state.layout.phys_of(q))

        candidate_edges: Set[Edge] = set()
        for p in front_phys:
            for n in self.hw.local_neighbors(p):
                if self.hw.phys_to_core[n] == self.hw.phys_to_core[p]:
                    candidate_edges.add(canonical_edge(p, n))

        for edge in sorted(candidate_edges):
            p0, p1 = edge
            if self.hw.phys_to_core[p0] != self.hw.phys_to_core[p1]:
                continue
            if state.layout.is_phys_free(p0) and state.layout.is_phys_free(p1):
                continue

            after_front, after_extended = self._score_with_temp_swap(
                state.layout,
                p0,
                p1,
                lambda sim: (
                    self._local_cx_distance_average(front_gates, sim),
                    self._local_cx_distance_average(extended_gates, sim),
                ),
            )
            local_sabre_score = after_front + self.cfg.local_swap_extended_weight * after_extended

            actions.append(
                Action(
                    kind="local_swap",
                    gate=front_gates[0],
                    swap=edge,
                    metadata={
                        "reason": "local_route",
                        "local_sabre_score": local_sabre_score,
                        # Used only as the lexicographic secondary criterion
                        # after local_sabre_score is tied.
                        "after_front_local_distance": after_front,
                    },
                )
            )
        return self._dedupe_actions(actions)

    def _local_swap_extended_local_cx_gates(
        self,
        state: RouterState,
        layout: Layout,
        exclude_gate_ids: Optional[Set[GateId]] = None,
    ) -> List[Gate]:
        exclude_gate_ids = exclude_gate_ids or set()
        max_cx = int(getattr(self.cfg, "local_swap_extended_cx_count", 20))
        max_layers = int(getattr(self.cfg, "local_swap_extended_max_layers", 8))
        if max_cx <= 0 or max_layers <= 0:
            return []

        sim = DagFrontierSimulator(state.dag_successors)
        dag = sim.snapshot(
            state.dag_active,
            state.dag_predecessor_count,
            frontier=state.dag_frontier,
        )
        out: List[Gate] = []
        seen: Set[GateId] = set()

        for layer in range(max_layers):
            current = sim.current_layer(dag)
            if not current or len(out) >= max_cx:
                break
            if layer > 0:
                for gid in current:
                    if gid in exclude_gate_ids or gid in seen:
                        continue
                    g = state.gate_by_id.get(gid)
                    if g is None or not g.is_cx():
                        continue
                    q0, q1 = g.qubits
                    if layout.core_of(q0) == layout.core_of(q1):
                        out.append(g)
                        seen.add(gid)
                        if len(out) >= max_cx:
                            break
            sim.remove_gate_ids(dag, current)
        return out

    def _local_cx_distance_average(self, gates: List[Gate], layout: Layout) -> float:
        total = 0.0
        count = 0
        for g in gates:
            if not g.is_cx():
                continue
            q0, q1 = g.qubits
            if layout.core_of(q0) != layout.core_of(q1):
                continue
            c = layout.core_of(q0)
            d = self.hw.local_distance(c, layout.phys_of(q0), layout.phys_of(q1))
            if math.isinf(d):
                d = 100.0
            total += float(d)
            count += 1
        return total / count if count else 0.0


    # ---------------------------------------------------------------------
    # Plan-first remote stage
    # ---------------------------------------------------------------------

    def _execute_plan_first_remote_stage(self, state: RouterState, info: FrontInfo) -> Optional[bool]:
        min_free = self.cfg.min_free_before_teleport
        normal_plans = self._generate_remote_plans(state, info, min_free)
        blocked_plans = self._generate_blocked_teleport_plans(state, info, min_free)

        normal_plan, normal_scores = self._select_ready_or_preparable_remote_plan(
            normal_plans, state, info, min_free
        )
        if normal_plan is not None:
            opportunistic_relief: Optional[RemotePlan] = None
            if self.cfg.capacity_relief_assist_enabled and blocked_plans:
                opportunistic_relief = self._select_opportunistic_capacity_relief_plan(
                    blocked_plans, normal_plan, normal_scores, state, info, min_free
                )

            if opportunistic_relief is not None:
                return self._commit_remote_plan(
                    opportunistic_relief,
                    state,
                    info,
                    min_free,
                    prep_stage='opportunistic_capacity_relief_prep',
                )

            return self._commit_remote_plan(
                normal_plan,
                state,
                info,
                min_free,
                prep_stage='remote_prep_committed',
            )

        blocked_distance_reducing = [
            plan for plan in blocked_plans
            if plan.mode == 'blocked_capacity_distance_reducing'
        ]
        max_path_hops: Optional[int] = None if self.cfg.capacity_relief_chain_enabled else 1
        recovery_plans = self._generate_bfs_capacity_relief_plans(
            state,
            blocked_distance_reducing,
            min_free,
            max_path_hops=max_path_hops,
            mode='capacity_relief_bfs',
        )
        if not recovery_plans and self.cfg.capacity_relief_from_adjacent_blocked:
            blocked_adjacent = [
                plan for plan in blocked_plans
                if plan.mode == 'blocked_capacity_adjacent'
            ]
            recovery_plans = self._generate_bfs_capacity_relief_plans(
                state,
                blocked_adjacent,
                min_free,
                max_path_hops=1,
                mode='capacity_relief_bfs',
            )
        recovery_plan = self._select_bfs_capacity_relief_plan(
            recovery_plans, state, info, min_free
        )
        if recovery_plan is None:
            return None

        return self._commit_remote_plan(
            recovery_plan,
            state,
            info,
            min_free,
            prep_stage='capacity_relief_bfs_prep',
        )

    def _commit_remote_plan(
        self,
        plan: RemotePlan,
        state: RouterState,
        info: FrontInfo,
        min_free: int,
        prep_stage: str,
    ) -> Optional[bool]:
        if self._remote_plan_ready(plan, state.layout, min_free):
            action = self._make_action_from_ready_plan(plan, state, min_free)
            return None if action is None else self._apply_action(action, state)

        made_progress = False
        seen_decision_states: Set[Tuple[Any, ...]] = set()

        for _ in range(self.cfg.max_prep_iterations_per_plan):
            layout_signature = tuple(sorted(state.layout.physical_to_logical.items()))
            decision_signature = (plan.plan_id(), layout_signature, self._rng.getstate())
            if decision_signature in seen_decision_states:
                raise RuntimeError(
                    'Committed remote preparation repeated its full decision state '
                    f'for plan {plan.plan_id()}; the greedy preparation trajectory cycles.'
                )
            seen_decision_states.add(decision_signature)

            prep_actions = self._select_preparation_swaps_for_plan(
                state, plan, prep_stage
            )
            if not prep_actions:
                return False if made_progress else None

            for prep in prep_actions:
                self._apply_action(prep, state)
                made_progress = True

            if self._remote_plan_ready(plan, state.layout, min_free):
                action = self._make_action_from_ready_plan(plan, state, min_free)
                if action is not None:
                    return self._apply_action(action, state)
                return False

            if not self.cfg.remote_plan_commitment:
                # Ablation: do not hold the choice open.  Returning here sends
                # control back to compile()'s loop, which re-classifies the
                # front and re-scores every plan from scratch before the next
                # move -- so preparation is spent one round at a time on
                # whatever currently scores best, rather than on one plan
                # until it is ready.
                return False

        raise RuntimeError(
            'Committed remote preparation exceeded max_prep_iterations_per_plan '
            f'for plan {plan.plan_id()}; the greedy preparation trajectory oscillates.'
        )

    def _select_ready_or_preparable_remote_plan(
        self,
        plans: List[RemotePlan],
        state: RouterState,
        info: FrontInfo,
        min_free: int,
    ) -> Tuple[Optional[RemotePlan], List[Tuple[float, RemotePlan, RemotePlanScore]]]:
        if not plans:
            return None, []
        _, scored = self._choose_best_remote_plan(plans, state, info, min_free)

        index = 0
        while index < len(scored):
            anchor = scored[index]
            group = [anchor]
            index += 1
            while index < len(scored) and self._remote_plan_semantically_tied(scored[index], anchor):
                group.append(scored[index])
                index += 1

            viable = []
            for item in group:
                _, candidate, _ = item
                if self._remote_plan_ready(candidate, state.layout, min_free) or self._has_preparation_swap_for_plan(state, candidate):
                    viable.append(item)
            if not viable:
                continue
            if len(viable) == 1 or not self.cfg.seeded_tie_break_enabled:
                return viable[0][1], scored

            ordered = sorted(viable, key=lambda item: self._remote_plan_stable_key(item[1]))
            chosen_index = self._rng.randrange(len(ordered))
            self._record_seeded_tie_break(state, 'remote_plan', len(ordered))
            return ordered[chosen_index][1], scored

        return None, scored

    def _score_for_plan_in_scored(
        self,
        plan: RemotePlan,
        scored: List[Tuple[float, RemotePlan, RemotePlanScore]],
    ) -> Optional[RemotePlanScore]:
        pid = plan.plan_id()
        for _total, p, score in scored:
            if p.plan_id() == pid:
                return score
        return None

    def _generate_blocked_teleport_plans(
        self, state: RouterState, info: FrontInfo, min_free: int
    ) -> List[RemotePlan]:
        plans: List[RemotePlan] = []
        layout = state.layout

        for g in info.adjacent_remote_cx:
            if not g.is_cx():
                continue
            q0, q1 = g.qubits
            c0, c1 = layout.core_of(q0), layout.core_of(q1)
            if not self.hw.are_adjacent_cores(c0, c1):
                continue
            if layout.free_count(self.hw, c1) < min_free:
                plans.append(
                    RemotePlan(
                        kind="teleport",
                        gate=g,
                        moving_qubit=q0,
                        src_core=c0,
                        dst_core=c1,
                        mode="blocked_capacity_adjacent",
                        metadata={
                            "seed": g.gid,
                            "direction": "control_to_target_core_blocked",
                            "other_core": c1,
                            "blocked_core": c1,
                            "blocked_move_src": c0,
                            "blocked_move_dst": c1,
                            "blocked_move_qubit": q0,
                            "reason": "destination_capacity_below_min_free",
                        },
                    )
                )
            if layout.free_count(self.hw, c0) < min_free:
                plans.append(
                    RemotePlan(
                        kind="teleport",
                        gate=g,
                        moving_qubit=q1,
                        src_core=c1,
                        dst_core=c0,
                        mode="blocked_capacity_adjacent",
                        metadata={
                            "seed": g.gid,
                            "direction": "target_to_control_core_blocked",
                            "other_core": c0,
                            "blocked_core": c0,
                            "blocked_move_src": c1,
                            "blocked_move_dst": c0,
                            "blocked_move_qubit": q1,
                            "reason": "destination_capacity_below_min_free",
                        },
                    )
                )

        for g in info.non_adjacent_remote_cx:
            if not g.is_cx():
                continue
            q0, q1 = g.qubits
            c0, c1 = layout.core_of(q0), layout.core_of(q1)
            d = self.hw.core_distance(c0, c1)
            if d <= 1:
                continue
            for q, src, other, direction in [
                (q0, c0, c1, "control_one_hop_toward_target_blocked"),
                (q1, c1, c0, "target_one_hop_toward_control_blocked"),
            ]:
                for dst in self.hw.core_neighbors(src):
                    if self.hw.core_distance(dst, other) >= d:
                        continue
                    if layout.free_count(self.hw, dst) >= min_free:
                        continue
                    plans.append(
                        RemotePlan(
                            kind="teleport",
                            gate=g,
                            moving_qubit=q,
                            src_core=src,
                            dst_core=dst,
                            mode="blocked_capacity_distance_reducing",
                            metadata={
                                "seed": g.gid,
                                "direction": direction,
                                "other_core": other,
                                "blocked_core": dst,
                                "blocked_move_src": src,
                                "blocked_move_dst": dst,
                                "blocked_move_qubit": q,
                                "reason": "destination_capacity_below_min_free",
                            },
                        )
                    )
        return self._dedupe_remote_plans(plans)

    def _select_opportunistic_capacity_relief_plan(
        self,
        blocked_plans: List[RemotePlan],
        normal_plan: RemotePlan,
        normal_scores: List[Tuple[float, RemotePlan, RemotePlanScore]],
        state: RouterState,
        info: FrontInfo,
        min_free: int,
    ) -> Optional[RemotePlan]:
        if not blocked_plans:
            return None

        normal_score = self._score_for_plan_in_scored(normal_plan, normal_scores)
        normal_gain = (
            normal_score.total
            if normal_score is not None
            else self._remote_plan_gain(normal_plan, state, info)
        )

        ranked_blocked = sorted(
            ((self._remote_plan_gain(plan, state, info), plan) for plan in blocked_plans),
            key=lambda item: (
                -item[0],
                item[1].gate.gid,
                item[1].moving_qubit if item[1].moving_qubit is not None else -1,
                item[1].src_core if item[1].src_core is not None else -1,
                item[1].dst_core if item[1].dst_core is not None else -1,
            ),
        )
        blocked_gain, best_blocked = ranked_blocked[0]
        margin = float(getattr(self.cfg, 'capacity_relief_assist_margin', 1.0))
        if blocked_gain - normal_gain <= margin:
            return None
        if best_blocked.mode == 'blocked_capacity_adjacent':
            max_path_hops: Optional[int] = 1
        else:
            max_path_hops = None if self.cfg.capacity_relief_chain_enabled else 1

        relief_plans = self._generate_bfs_capacity_relief_plans(
            state,
            [best_blocked],
            min_free,
            max_path_hops=max_path_hops,
            mode='opportunistic_capacity_relief_bfs',
        )
        return self._select_bfs_capacity_relief_plan(relief_plans, state, info, min_free)

    def _generate_remote_plans(self, state: RouterState, info: FrontInfo, min_free: int) -> List[RemotePlan]:
        plans: List[RemotePlan] = []
        layout = state.layout

        for g in info.adjacent_remote_cx:
            q0, q1 = g.qubits
            c0, c1 = layout.core_of(q0), layout.core_of(q1)

            if self.cfg.telegate_enabled:
                packet = self._find_telegate_packet(state, layout, g)
                packet_remote_cx_count = self._packet_remote_cx_count(packet, layout)
                if packet_remote_cx_count > 1:
                    plans.append(
                        RemotePlan(
                            kind="telegate_packet",
                            gate=g,
                            gates=tuple(packet),
                            metadata={
                                "seed": g.gid,
                                "packet_type": "same_control_ordered",
                                "packet_size": len(packet),
                                "remote_cx_count": packet_remote_cx_count,
                                "allows_target_side_single_gates": True,
                                "target_side_requires_ordered_local_swaps": True,
                            },
                        )
                    )

                plans.append(
                    RemotePlan(
                        kind="telegate",
                        gate=g,
                        gates=(g,),
                        metadata={"seed": g.gid, "packet_size": 1},
                    )
                )

            if layout.free_count(self.hw, c1) >= min_free:
                plans.append(
                    RemotePlan(
                        kind="teleport",
                        gate=g,
                        moving_qubit=q0,
                        src_core=c0,
                        dst_core=c1,
                        mode="localize_adjacent_control_to_target_core",
                        metadata={"seed": g.gid, "direction": "control_to_target_core"},
                    )
                )
            if layout.free_count(self.hw, c0) >= min_free:
                plans.append(
                    RemotePlan(
                        kind="teleport",
                        gate=g,
                        moving_qubit=q1,
                        src_core=c1,
                        dst_core=c0,
                        mode="localize_adjacent_target_to_control_core",
                        metadata={"seed": g.gid, "direction": "target_to_control_core"},
                    )
                )

        for g in info.non_adjacent_remote_cx:
            q0, q1 = g.qubits
            c0, c1 = layout.core_of(q0), layout.core_of(q1)
            d = self.hw.core_distance(c0, c1)
            if d <= 1:
                continue

            for q, src, other, direction in [
                (q0, c0, c1, "control_one_hop_toward_target"),
                (q1, c1, c0, "target_one_hop_toward_control"),
            ]:
                for dst in self.hw.core_neighbors(src):
                    if self.hw.core_distance(dst, other) >= d:
                        continue
                    if layout.free_count(self.hw, dst) < min_free:
                        continue
                    plans.append(
                        RemotePlan(
                            kind="teleport",
                            gate=g,
                            moving_qubit=q,
                            src_core=src,
                            dst_core=dst,
                            mode="distance_reducing",
                            metadata={"seed": g.gid, "direction": direction, "other_core": other},
                        )
                    )

        return self._dedupe_remote_plans(plans)

    def _generate_bfs_capacity_relief_plans(
        self,
        state: RouterState,
        blocked_plans: List[RemotePlan],
        min_free: int,
        *,
        max_path_hops: Optional[int],
        mode: str,
    ) -> List[RemotePlan]:

        plans = self._capacity_relief.generate_plans(
            state.layout,
            blocked_plans,
            min_free,
            max_path_hops=max_path_hops,
            mode=mode,
            make_plan=RemotePlan,
        )
        return self._dedupe_remote_plans(plans)

    def _select_bfs_capacity_relief_plan(
        self,
        plans: List[RemotePlan],
        state: RouterState,
        info: FrontInfo,
        min_free: int,
    ) -> Optional[RemotePlan]:

        if not plans:
            return None

        hop_tiers: Dict[int, List[RemotePlan]] = {}
        for plan in plans:
            hops = int(plan.metadata.get('chain_hops', 1))
            hop_tiers.setdefault(hops, []).append(plan)

        for hops in sorted(hop_tiers):
            chosen, _scored = self._select_ready_or_preparable_remote_plan(
                hop_tiers[hops], state, info, min_free
            )
            if chosen is not None:
                return chosen
        return None

    def _dedupe_remote_plans(self, plans: List[RemotePlan]) -> List[RemotePlan]:
        seen = set()
        out: List[RemotePlan] = []
        for p in plans:
            key = p.plan_id()
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
        return out

    def _remote_plan_semantically_tied(
        self,
        left: Tuple[float, RemotePlan, RemotePlanScore],
        right: Tuple[float, RemotePlan, RemotePlanScore],
    ) -> bool:
        """Equality relation induced by ``_remote_plan_selection_key``."""
        l_total, l_plan, l_score = left
        r_total, r_plan, r_score = right
        return (
            self._float_tied(l_total, r_total)
            and self._float_tied(l_score.prep, r_score.prep)
            and self._float_tied(l_score.capacity, r_score.capacity)
        )

    def _remote_plan_selection_key(
        self, item: Tuple[float, RemotePlan, RemotePlanScore]
    ) -> Tuple[Any, ...]:
        """Lexicographic plan order: estimated gain, then preparation cost,
        then destination headroom, then a stable identifier.

        Three earlier coordinates were removed on 2026-09-02 as provably
        unreachable or implied by the three that remain:

        * a readiness flag before ``prep``.  ``prep`` is defined as zero
          exactly when the plan is ready and positive otherwise, so the flag
          could never separate two plans that ``prep`` did not already order
          (measured: no unready plan with zero preparation cost in 259,125
          scored candidates).
        * a three-way plan-kind rank between ``prep`` and the capacity term.
          A ``telegate`` scores ``total = 1`` and a ``telegate_packet`` is only
          generated when it carries at least two remote CX gates, so ``-total``
          always separates those two and the rank's packet-before-telegate half
          was unreachable; its teleport-first half is now carried by the
          capacity term, which is negative for a ``teleport`` and zero for
          every other primitive.
        * a trailing ``-lookahead_gain``.  ``total`` is the sum of the realised
          and discounted gains, so that coordinate was reachable only when the
          two traded in exactly compensating amounts -- once in 24,494
          rankings -- and it then preferred the plan with the *smaller*
          realised gain, which is the wrong direction for a tie-break meant to
          favour surer progress.
        """
        total, plan, score = item
        return (
            -total,
            score.prep,
            score.capacity,
            self._remote_plan_stable_key(plan),
        )

    def _choose_best_remote_plan(
        self, plans: List[RemotePlan], state: RouterState, info: FrontInfo, min_free: int
    ) -> Tuple[RemotePlan, List[Tuple[float, RemotePlan, RemotePlanScore]]]:
        scored = []
        for plan in plans:
            score = self._score_remote_plan(plan, state, info, min_free)
            scored.append((score.total, plan, score))
        scored.sort(key=self._remote_plan_selection_key)
        return scored[0][1], scored

    def _score_remote_plan(
        self, plan: RemotePlan, state: RouterState, info: FrontInfo, min_free: int
    ) -> RemotePlanScore:
        ready = self._remote_plan_ready(plan, state.layout, min_free)
        prep = 0.0 if ready else self._remote_plan_readiness_cost(plan, state.layout, min_free)
        direct_gain, lookahead_gain = self._remote_plan_direct_lookahead_gain(plan, state, info)
        capacity = self._remote_plan_capacity_key(plan, state.layout)
        return RemotePlanScore(
            total=direct_gain + lookahead_gain,
            ready=ready,
            prep=prep,
            capacity=capacity,
            direct_gain=direct_gain,
            lookahead_gain=lookahead_gain,
        )

    def _remote_plan_ready(self, plan: RemotePlan, layout: Layout, min_free: int) -> bool:
        if plan.kind == "telegate":
            return self._telegate_ready(layout, plan.gate)
        if plan.kind == "telegate_packet":
            return self._same_control_packet_macro_ready(layout, list(plan.gates))
        if plan.kind == "teleport":
            return self._make_legal_teleport_action_for_layout(layout, plan, min_free) is not None
        return False

    def _remote_plan_readiness_cost(self, plan: RemotePlan, layout: Layout, min_free: int) -> float:
        if plan.kind == "teleport":
            assert plan.moving_qubit is not None and plan.src_core is not None and plan.dst_core is not None
            return self._remote_edge_readiness_cost(layout, plan.moving_qubit, plan.src_core, plan.dst_core, min_free)

        if plan.kind == "telegate":
            q0, q1 = plan.gate.qubits
            c0, c1 = layout.core_of(q0), layout.core_of(q1)
            if self.hw.core_distance(c0, c1) != 1:
                return 100.0
            p0, p1 = layout.phys_of(q0), layout.phys_of(q1)
            port0, port1 = self.hw.inter_core_ports(c0, c1)
            d0 = self.hw.local_distance(c0, p0, port0)
            d1 = self.hw.local_distance(c1, p1, port1)
            cost = abs(float(d0) - 1.0) + abs(float(d1) - 1.0)
            if not layout.is_phys_free(port0):
                cost += self._port_clearance_cost(layout, c0, c1)
            if not layout.is_phys_free(port1):
                cost += self._port_clearance_cost(layout, c1, c0)
            return cost

        if plan.kind == "telegate_packet":
            if not plan.gates:
                return 100.0
            control = plan.gates[0].qubits[0]
            target_core = layout.core_of(plan.gates[0].qubits[1])
            control_core = layout.core_of(control)
            if self.hw.core_distance(control_core, target_core) != 1:
                return 100.0
            control_port, target_port = self.hw.inter_core_ports(control_core, target_core)
            d_control = self.hw.local_distance(control_core, layout.phys_of(control), control_port)
            cost = abs(float(d_control) - 1.0)
            if not layout.is_phys_free(control_port):
                cost += self._port_clearance_cost(layout, control_core, target_core)
            if not layout.is_phys_free(target_port):
                cost += self._port_clearance_cost(layout, target_core, control_core)
            return cost

        return 100.0

    def _remote_plan_direct_lookahead_gain(
        self, plan: RemotePlan, state: RouterState, info: FrontInfo
    ) -> Tuple[float, float]:
        """Plan-local benefit used by the remote-plan scorer.
        The teleport direct set is treated as immediate pressure.  The
        lookahead set is only a prediction of later layout benefit and is
        therefore discounted.
        """
        if plan.kind == "telegate":
            return 1.0, 0.0

        if plan.kind == "telegate_packet":
            # A same-control packet is a current macro action: all remote CXs
            # collected in the ordered packet are executed under one cat-entangler
            # resource, even if some of them are not ordinary DAG-front nodes yet
            # because target-side single gates are packed between them.  Therefore
            # every remote CX in the legal packet contributes to current packet
            # gain; this is not speculative lookahead.
            return float(self._packet_remote_cx_count(plan.gates, state.layout)), 0.0

        if plan.kind == "teleport":
            return self._teleport_direct_lookahead_gain(plan, state, info)

        return 0.0, 0.0

    def _teleport_direct_lookahead_gain(
        self, plan: RemotePlan, state: RouterState, info: FrontInfo
    ) -> Tuple[float, float]:
        if plan.kind != "teleport" or plan.moving_qubit is None or plan.dst_core is None:
            return 0.0, 0.0

        direct, latent_direct, lookahead = self._collect_teleport_direct_latent_and_lookahead(
            state,
            info,
            plan.gate,
            plan.moving_qubit,
            plan.dst_core,
        )

        def delta(g: Gate) -> float:
            q0, q1 = g.qubits
            before = self.hw.core_distance(state.layout.core_of(q0), state.layout.core_of(q1))
            c0_after = plan.dst_core if q0 == plan.moving_qubit else state.layout.core_of(q0)
            c1_after = plan.dst_core if q1 == plan.moving_qubit else state.layout.core_of(q1)
            after = self.hw.core_distance(c0_after, c1_after)
            return float(before - after)

        front_direct_gain = sum(delta(g) for g in direct)
        latent_direct_gain = sum(delta(g) for g in latent_direct)
        latent_weight = float(self.cfg.teleport_latent_direct_weight)
        direct_gain = front_direct_gain + latent_weight * latent_direct_gain

        lookahead_gain = 0.0
        initial_weight = float(getattr(self.cfg, "teleport_lookahead_weight", 0.9))
        decay = float(getattr(self.cfg, "teleport_lookahead_decay", 0.9))
        weight_floor = float(getattr(self.cfg, "teleport_lookahead_weight_floor", 0.5))
        for g, layer in lookahead:
            decay_power = max(0, int(layer) - 1)
            layer_weight = max(weight_floor, initial_weight * (decay ** decay_power))
            lookahead_gain += layer_weight * delta(g)
        return direct_gain, lookahead_gain

    def _collect_teleport_direct_latent_and_lookahead(
        self,
        state: RouterState,
        info: FrontInfo,
        seed_gate: Gate,
        moving_qubit: LogicalQubit,
        dst_core: CoreId,
    ) -> Tuple[List[Gate], List[Gate], List[Tuple[Gate, int]]]:
        """Collect teleport influence sets from simulated DAG fronts.

        * direct: current DAG-front CXs involving the moving qubit.
        * latent_direct: q-related CXs exposed while repeatedly clearing, under
          the post-teleport core placement, only single-qubit gates and local CXs.
          These gates need not become local themselves; they are counted because
          the candidate teleport directly changes their core distance once they
          appear in the deterministic near-front closure.
        * lookahead: q-related CXs in later DAG generations after whole-front
          simulated deletion, excluding direct/latent-direct gates.
        """
        direct: List[Gate] = []
        seen: Set[GateId] = set()

        for g in info.front:
            if g.is_cx() and moving_qubit in g.qubits and g.gid not in seen:
                direct.append(g)
                seen.add(g.gid)

        # A teleport plan's seed should always contribute to immediate pressure.
        if seed_gate.is_cx() and moving_qubit in seed_gate.qubits and seed_gate.gid not in seen:
            direct.append(seed_gate)
            seen.add(seed_gate.gid)

        latent_direct, sim, stop_dag = self._collect_teleport_latent_direct_gates_with_stop_state(
            state=state,
            moving_qubit=moving_qubit,
            dst_core=dst_core,
            already_counted=set(seen),
        )
        for g in latent_direct:
            seen.add(g.gid)

        lookahead = self._collect_teleport_post_latent_lookahead_gates(
            state=state,
            moving_qubit=moving_qubit,
            exclude=set(seen),
            sim=sim,
            dag=stop_dag,
            max_cx=max(0, int(getattr(self.cfg, "teleport_lookahead_cx_count", 0))),
            max_layers=max(1, int(getattr(self.cfg, "dag_extended_max_layers", 16))),
        )
        return direct, latent_direct, lookahead

    def _collect_teleport_latent_direct_gates_with_stop_state(
        self,
        state: RouterState,
        moving_qubit: LogicalQubit,
        dst_core: CoreId,
        already_counted: Set[GateId],
    ) -> Tuple[List[Gate], DagFrontierSimulator, DagSimState]:
        """Return latent-direct gates plus the simulator state where local
        closure stops.  Post-latent lookahead continues from that state instead
        of re-snapshotting from the original current front.
        """

        def core_after(q: LogicalQubit) -> CoreId:
            return dst_core if q == moving_qubit else state.layout.core_of(q)

        sim = DagFrontierSimulator(state.dag_successors)
        dag = sim.snapshot(
            state.dag_active,
            state.dag_predecessor_count,
            frontier=state.dag_frontier,
        )
        seen = set(already_counted)
        out: List[Gate] = []

        while dag.frontier:
            current = sim.current_layer(dag)
            if not current:
                break

            # Count every q-related CX in the current simulated front as latent
            # direct influence.  Counting is independent of virtual removability.
            for gid in current:
                if gid in seen:
                    continue
                g = state.gate_by_id.get(gid)
                if g is not None and g.is_cx() and moving_qubit in g.qubits:
                    out.append(g)
                    seen.add(gid)

            removable: List[GateId] = []
            for gid in current:
                g = state.gate_by_id.get(gid)
                if g is None:
                    continue
                if g.is_single_qubit():
                    removable.append(gid)
                    continue
                if g.is_cx():
                    q0, q1 = g.qubits
                    if core_after(q0) == core_after(q1):
                        removable.append(gid)

            if not removable:
                # This is the remote-blocked / non-local stopping frontier used
                # by post-latent lookahead.
                break

            sim.remove_gate_ids(dag, removable)

        return out, sim, dag


    def _collect_teleport_post_latent_lookahead_gates(
        self,
        state: RouterState,
        moving_qubit: LogicalQubit,
        exclude: Set[GateId],
        sim: DagFrontierSimulator,
        dag: DagSimState,
        max_cx: int,
        max_layers: int,
    ) -> List[Tuple[Gate, int]]:
        # Only active CXs of the moving qubit are collectable, and there are
        # exactly `active_cx_by_qubit[moving_qubit]` of them, so the walk can
        # never return more.  Capping by it is output-preserving -- it stops
        # peeling layers that provably cannot yield another gate -- and it
        # returns immediately for a qubit whose line is already finished.
        cap = min(max_cx, state.active_cx_by_qubit.get(moving_qubit, 0))
        if cap <= 0 or max_layers <= 0:
            return []

        seen = set(exclude)
        out: List[Tuple[Gate, int]] = []

        for layer in range(1, max_layers + 1):
            if not dag.frontier or len(out) >= cap:
                break

            current = sim.current_layer(dag)
            if not current:
                break

            sim.remove_gate_ids(dag, current)
            # Two gates sharing a qubit are ordered by that qubit's own chain,
            # so at most one frontier gate can involve `moving_qubit`.  The
            # scan therefore has a unique answer and needs neither an ordering
            # nor a full pass: sorting the whole frontier once per peeled layer
            # was the single largest cost in this walk.
            for gid in dag.frontier:
                if gid in seen:
                    continue
                g = state.gate_by_id.get(gid)
                if g is not None and g.is_cx() and moving_qubit in g.qubits:
                    out.append((g, layer))
                    seen.add(gid)
                    break

        return out


    def _remote_plan_gain(
        self, plan: RemotePlan, state: RouterState, info: FrontInfo
    ) -> float:
        direct_gain, lookahead_gain = self._remote_plan_direct_lookahead_gain(plan, state, info)
        return direct_gain + lookahead_gain

    def _remote_plan_capacity_key(self, plan: RemotePlan, layout: Layout) -> float:
        """Destination headroom, negated so that more room sorts first.

        Only a ``teleport`` consumes a destination slot; every other primitive
        scores zero, which also makes this term carry the teleport-first
        preference that a separate plan-kind rank used to provide.  The earlier
        form ``1/max(1, f_dst - 1)`` is order-equivalent on the reachable
        domain -- a teleport is only admitted when ``f_dst >= min_free`` -- but
        collapses ``f_dst <= 2`` into one value if that floor is ever lowered.
        """
        if plan.kind != "teleport" or plan.dst_core is None:
            return 0.0
        return -float(layout.free_count(self.hw, plan.dst_core))


    def _make_action_from_ready_plan(
        self, plan: RemotePlan, state: RouterState, min_free: int
    ) -> Optional[Action]:
        if plan.kind == "telegate":
            md = dict(plan.metadata)
            md.update({"plan_kind": plan.kind, "plan_mode": plan.mode})
            return Action(kind="telegate", gate=plan.gate, gates=(plan.gate,), metadata=md)

        if plan.kind == "telegate_packet":
            md = dict(plan.metadata)
            md.update({"plan_kind": plan.kind, "plan_mode": plan.mode})
            return Action(kind="telegate_packet", gate=plan.gate, gates=tuple(plan.gates), metadata=md)

        if plan.kind == "teleport":
            action = self._make_legal_teleport_action_for_layout(state.layout, plan, min_free)
            if action is None:
                return None
            md = dict(action.metadata)
            md.update(dict(plan.metadata))
            md.update({"plan_kind": plan.kind, "plan_mode": plan.mode})
            return Action(
                kind="teleport",
                gate=plan.gate,
                qubit=action.qubit,
                src_core=action.src_core,
                dst_core=action.dst_core,
                dst_phys=action.dst_phys,
                metadata=md,
            )

        return None

    def _make_legal_teleport_action_for_layout(
        self, layout: Layout, plan: RemotePlan, min_free: int
    ) -> Optional[Action]:
        if plan.kind != "teleport":
            return None
        if plan.moving_qubit is None or plan.src_core is None or plan.dst_core is None:
            return None
        if not self.hw.are_adjacent_cores(plan.src_core, plan.dst_core):
            return None
        src_port, dst_port = self.hw.inter_core_ports(plan.src_core, plan.dst_core)
        if layout.free_count(self.hw, plan.dst_core) < min_free:
            return None
        if not layout.is_phys_free(src_port):
            return None
        if not layout.is_phys_free(dst_port):
            return None
        src_phys = layout.phys_of(plan.moving_qubit)
        if self.hw.local_distance(plan.src_core, src_phys, src_port) != 1:
            return None
        return Action(
            kind="teleport",
            gate=plan.gate,
            qubit=plan.moving_qubit,
            src_core=plan.src_core,
            dst_core=plan.dst_core,
            dst_phys=dst_port,
            metadata={
                "mode": plan.mode,
                "min_free": min_free,
                "src_port": src_port,
                "dst_port": dst_port,
                "physical_rule": "src endpoint adjacent to free src_port; dst_port free; teleport lands on dst_port",
            },
        )

    def _remote_preparation_requirements(
        self, plan: RemotePlan, layout: Layout
    ) -> List[Tuple[CoreId, CoreId, Optional[LogicalQubit]]]:
        """Return ``(core, neighbor, endpoint)`` requirements for ``plan``.

        ``endpoint`` is the logical qubit that must end beside that core's
        communication port.  ``None`` means that only the port must be freed.
        """
        if plan.kind == "teleport":
            if plan.moving_qubit is None or plan.src_core is None or plan.dst_core is None:
                return []
            if not self.hw.are_adjacent_cores(plan.src_core, plan.dst_core):
                return []
            return [
                (plan.src_core, plan.dst_core, plan.moving_qubit),
                (plan.dst_core, plan.src_core, None),
            ]

        if plan.kind == "telegate":
            q_control, q_target = plan.gate.qubits
            c_control = layout.core_of(q_control)
            c_target = layout.core_of(q_target)
            if not self.hw.are_adjacent_cores(c_control, c_target):
                return []
            return [
                (c_control, c_target, q_control),
                (c_target, c_control, q_target),
            ]

        if plan.kind == "telegate_packet" and plan.gates:
            control = plan.gates[0].qubits[0]
            control_core = layout.core_of(control)
            target_core = layout.core_of(plan.gates[0].qubits[1])
            if not self.hw.are_adjacent_cores(control_core, target_core):
                return []
            # Packet targets are routed later inside _apply_telegate_packet.
            return [
                (control_core, target_core, control),
                (target_core, control_core, None),
            ]

        return []

    def _remote_prep_side_score(
        self,
        layout: Layout,
        core: CoreId,
        neighbor: CoreId,
        endpoint: Optional[LogicalQubit],
    ) -> float:
        """Post-SWAP preparation score for one core of a fixed remote plan."""
        endpoint_cost = 0.0
        if endpoint is not None:
            if layout.core_of(endpoint) != core:
                return math.inf
            port = self.hw.cores[core].ports[neighbor]
            distance = self.hw.local_distance(core, layout.phys_of(endpoint), port)
            if math.isinf(distance):
                return math.inf
            # If the endpoint occupies the port, the port-clearance SWAP moves
            # it to a port neighbor; that work is already represented by the
            # nearest-free-slot term below.
            endpoint_cost = max(0.0, float(distance) - 1.0)

        free_cost = self._nearest_free_distance_to_port(layout, core, neighbor)
        return endpoint_cost + free_cost

    def _remote_prep_candidate_edges_for_side(
        self,
        state: RouterState,
        core: CoreId,
        neighbor: CoreId,
        endpoint: Optional[LogicalQubit],
    ) -> List[Edge]:
        """Return legal local-SWAP edges for one remote-preparation core side.

        A preparation SWAP must directly serve one of the two unresolved
        physical requirements of the selected remote plan:

        * move the logical endpoint toward its required communication-port
          neighbourhood; or
        * when that communication port is occupied, advance a nearest free slot
          toward the port so that it can be cleared.
        Candidate generation is shared by both plan viability probing and actual
        action selection.  The helper is intentionally pure with respect to the
        router RNG and layout: it only inspects the current state.
        """
        port = self.hw.cores[core].ports[neighbor]
        relevant: Set[PhysicalQubit] = set()

        if endpoint is not None:
            relevant.add(state.layout.phys_of(endpoint))

        # A free slot is relevant only while the communication port must still
        # be cleared.  When the port is already free, moving it would make the
        # plan less ready rather than advancing preparation.
        if not state.layout.is_phys_free(port):
            relevant.update(
                self._nearest_free_positions_to_port_from_state(
                    state, core, neighbor
                )
            )

        edges: Set[Edge] = set()
        for physical in relevant:
            if self.hw.phys_to_core.get(physical) != core:
                continue
            for local_neighbor in self.hw.local_neighbors(physical):
                if self.hw.phys_to_core[local_neighbor] == core:
                    edge = canonical_edge(physical, local_neighbor)
                    if not (
                        state.layout.is_phys_free(edge[0])
                        and state.layout.is_phys_free(edge[1])
                    ):
                        edges.add(edge)
        return sorted(edges)

    def _has_preparation_swap_for_plan(self, state: RouterState, plan: RemotePlan) -> bool:
        for core, neighbor, endpoint in self._remote_preparation_requirements(
            plan, state.layout
        ):
            baseline = self._remote_prep_side_score(
                state.layout, core, neighbor, endpoint
            )
            if math.isinf(baseline):
                # No sequence of local SWAPs can ever repair this side: a SWAP
                # cannot change the core's free-slot count nor reconnect an
                # unreachable port, so the plan as a whole is unpreparable
                # (e.g. teleporting out of a core with zero free slots, whose
                # occupied port can never be cleared).
                return False
            if self._float_tied(baseline, 0.0):
                continue
            if self._remote_prep_candidate_edges_for_side(
                state, core, neighbor, endpoint
            ):
                return True
        return False

    def _select_preparation_swaps_for_plan(
        self, state: RouterState, plan: RemotePlan, stage: str
    ) -> List[Action]:
        """Pick at most one improving local SWAP in each involved core.

        For each core, candidate SWAPs are the local coupling edges incident to
        the relevant logical endpoint (when present), or to any free physical
        position tied for nearest to an occupied communication port.
        """
        selected: List[Action] = []
        for core, neighbor, endpoint in self._remote_preparation_requirements(
            plan, state.layout
        ):
            port = self.hw.cores[core].ports[neighbor]
            baseline = self._remote_prep_side_score(
                state.layout, core, neighbor, endpoint
            )
            if math.isinf(baseline):
                # This side is unpreparable by local SWAPs (see
                # _has_preparation_swap_for_plan), so the plan can never become
                # ready; emitting SWAPs for any side would be pure churn.
                return []
            # This core is already ready for the selected plan; preparation on
            # the other core cannot invalidate it, so do not disturb it.
            if self._float_tied(baseline, 0.0):
                continue

            edges = self._remote_prep_candidate_edges_for_side(
                state, core, neighbor, endpoint
            )

            candidates: List[Tuple[float, Action]] = []
            for edge in edges:
                p0, p1 = edge
                post_score = self._score_with_temp_swap(
                    state.layout,
                    p0,
                    p1,
                    lambda sim: self._remote_prep_side_score(sim, core, neighbor, endpoint),
                )
                total_score = post_score
                candidates.append((
                    total_score,
                    Action(
                        kind="local_swap",
                        gate=plan.gate,
                        swap=edge,
                        metadata={
                            "reason": "remote_prep",
                            "prep_core": core,
                            "prep_neighbor": neighbor,
                            "prep_port": port,
                            "prep_endpoint": endpoint,
                            "post_prep_score": post_score,
                            "total_prep_score": total_score,
                            "plan_kind": plan.kind,
                            "plan_mode": plan.mode,
                        },
                    ),
                ))

            if not candidates:
                continue
            candidates.sort(key=lambda item: (item[0], self._action_stable_key(item[1])))
            best_score = candidates[0][0]
            tied = [item for item in candidates if self._float_tied(item[0], best_score)]
            if len(tied) == 1 or not self.cfg.seeded_tie_break_enabled:
                selected.append(tied[0][1])
            else:
                ordered = sorted(tied, key=lambda item: self._action_stable_key(item[1]))
                self._record_seeded_tie_break(state, stage, len(ordered))
                selected.append(ordered[self._rng.randrange(len(ordered))][1])

        return sorted(selected, key=lambda action: int(action.metadata["prep_core"]))

    def _telegate_ready(self, layout: Layout, gate: Gate) -> bool:
        if not gate.is_cx():
            return False
        q0, q1 = gate.qubits
        c0, c1 = layout.core_of(q0), layout.core_of(q1)
        if self.hw.core_distance(c0, c1) != 1:
            return False
        p0, p1 = layout.phys_of(q0), layout.phys_of(q1)
        port0, port1 = self.hw.inter_core_ports(c0, c1)
        return (
            layout.is_phys_free(port0)
            and layout.is_phys_free(port1)
            and self.hw.local_distance(c0, p0, port0) == 1
            and self.hw.local_distance(c1, p1, port1) == 1
        )

    def _find_telegate_packet(self, state: RouterState, layout: Layout, seed_gate: Gate) -> List[Gate]:
        """Collect a same-control telegate packet by DAG-frontier simulation.
        """
        if not seed_gate.is_cx():
            return [seed_gate]
        control, target = seed_gate.qubits
        if layout.core_of(control) == layout.core_of(target):
            return [seed_gate]
        return self._collect_same_control_packet(state, layout, seed_gate)

    def _same_control_packet_macro_ready(self, layout: Layout, packet: List[Gate]) -> bool:
        """Whether the shared-control side is ready to start a packet macro.

        The packet may include target-core single-qubit gates exposed by the DAG
        frontier simulation.  It must carry at least two same-control remote CX
        gates whose targets currently live in one target core.  Target-side CX
        adjacency is intentionally not checked here because the macro routes each
        target after the cat resource starts.
        """
        cx_gates = self._packet_cx_gates(packet)
        if len(cx_gates) <= 1:
            return False

        control = cx_gates[0].qubits[0]
        target_core = layout.core_of(cx_gates[0].qubits[1])
        if any(g.qubits[0] != control or layout.core_of(g.qubits[1]) != target_core for g in cx_gates):
            return False

        for g in packet:
            if g.is_cx():
                continue
            if not g.is_single_qubit():
                return False
            if layout.core_of(g.qubits[0]) != target_core:
                return False

        control_core = layout.core_of(control)
        if self.hw.core_distance(control_core, target_core) != 1:
            return False
        control_port, target_port = self.hw.inter_core_ports(control_core, target_core)
        control_phys = layout.phys_of(control)
        return (
            layout.is_phys_free(control_port)
            and layout.is_phys_free(target_port)
            and self.hw.local_distance(control_core, control_phys, control_port) == 1
        )

    def _collect_same_control_packet(self, state: RouterState, layout: Layout, seed_gate: Gate) -> List[Gate]:
        """DAG-frontier packet collection for an ordered same-control macro."""
        seed_control, seed_target = seed_gate.qubits
        control_core = layout.core_of(seed_control)
        target_core = layout.core_of(seed_target)
        if not self.hw.are_adjacent_cores(control_core, target_core):
            return [seed_gate]

        sim = DagFrontierSimulator(state.dag_successors)
        dag = sim.snapshot(
            state.dag_active,
            state.dag_predecessor_count,
            frontier=state.dag_frontier,
        )
        packet: List[Gate] = []
        packet_ids: Set[GateId] = set()
        cx_count = 0
        remote_seen = 0
        layer_count = 0

        while dag.frontier and layer_count < self.cfg.extended_packet_window:
            layer_count += 1
            current = sim.current_layer(dag)
            if not current:
                break

            removable: List[GateId] = []
            made_packet_progress = False

            for gid in current:
                if gid in packet_ids:
                    continue
                g = state.gate_by_id.get(gid)
                if g is None:
                    continue

                if g.is_cx() and layout.core_of(g.qubits[0]) != layout.core_of(g.qubits[1]):
                    remote_seen += 1
                    if remote_seen > self.cfg.remote_gate_limit:
                        continue

                if self._matches_same_control_packet(seed_control, control_core, target_core, g, layout):
                    if cx_count >= self.cfg.max_packet_size:
                        continue
                    packet.append(g)
                    packet_ids.add(gid)
                    removable.append(gid)
                    cx_count += 1
                    made_packet_progress = True
                    continue

                # Target-core single-qubit gates can be executed while the packet
                # cat resource is live.  They are admitted only when they are in
                # the simulated DAG front, so their original dependencies are safe.
                if g.is_single_qubit() and layout.core_of(g.qubits[0]) == target_core:
                    packet.append(g)
                    packet_ids.add(gid)
                    removable.append(gid)
                    made_packet_progress = True
                    continue

            if not removable:
                break

            sim.remove_gate_ids(dag, removable)

            if cx_count >= self.cfg.max_packet_size:
                break
            if not made_packet_progress:
                break

        # Ensure the seed appears first if it was part of the frontier; otherwise
        # fall back to a single-gate packet candidate that will not be selected as
        # telegate_packet because remote_cx_count == 1.
        if seed_gate.gid not in packet_ids:
            return [seed_gate]
        return packet

    def _matches_same_control_packet(
        self,
        seed_control: LogicalQubit,
        control_core: CoreId,
        target_core: CoreId,
        candidate: Gate,
        layout: Layout,
    ) -> bool:
        if not candidate.is_cx():
            return False
        c, t = candidate.qubits
        return c == seed_control and layout.core_of(c) == control_core and layout.core_of(t) == target_core


    @staticmethod
    def _packet_cx_gates(packet: Iterable[Gate]) -> List[Gate]:
        return [g for g in packet if g.is_cx()]

    def _packet_remote_cx_count(self, packet: Iterable[Gate], layout: Layout) -> int:
        count = 0
        for g in packet:
            if not g.is_cx():
                continue
            q0, q1 = g.qubits
            if layout.core_of(q0) != layout.core_of(q1):
                count += 1
        return count

    # ---------------------------------------------------------------------
    # Scoring
    # ---------------------------------------------------------------------

    def _local_action_cost(self, action: Action, state: RouterState) -> float:
        local_swap = self._local_swap_score_component(action)
        return  local_swap

    def _local_swap_score_component(self, action: Action) -> float:
        if action.kind != "local_swap":
            return 0.0
        reason = action.metadata.get("reason")
        if reason == "local_route":
            # Lower is better: SABRE-like front distance plus weighted extended-set distance.
            return float(action.metadata["local_sabre_score"])
        if reason == "remote_prep":
            return float(action.metadata.get("post_prep_score", math.inf))
        return 1.0

    # ---------------------------------------------------------------------
    # Cat/packet physical expansion helpers
    # ---------------------------------------------------------------------

    def _route_logical_to_port_neighbor_without_comm(
        self,
        layout: Layout,
        q: LogicalQubit,
        cid: CoreId,
        port: PhysicalQubit,
        forbidden_ports: Optional[Set[PhysicalQubit]] = None,
    ) -> List[Edge]:
        """Shortest local-SWAP route that moves q next to ``port``.

        The route is used only after a telegate packet has been selected.  It is
        not part of packet plan scoring.  SWAPs may pass through occupied data
        qubits because they simply permute the local layout.

        During a live cat/packet section, only the communication qubits used by
        that section are forbidden.  Other communication qubits in the same core
        are allowed to hold data and may participate in local SWAP routing.
        """
        active_forbidden = set(forbidden_ports or set())
        active_forbidden.add(port)

        start = layout.phys_of(q)
        if self.hw.phys_to_core[start] != cid:
            raise RuntimeError(f"q{q} is not in target core {cid}")
        if start in active_forbidden:
            raise RuntimeError(f"q{q} is on an active packet communication qubit {start}")

        goals = {
            p
            for p in self.hw.local_neighbors(port)
            if self.hw.phys_to_core[p] == cid and p not in active_forbidden
        }
        if not goals:
            raise RuntimeError(f"Communication port {port} in core {cid} has no usable neighbor")
        if start in goals:
            return []

        allowed = {
            p for p in self.hw.cores[cid].physical_qubits
            if p not in active_forbidden
        }
        q_frontier = deque([start])
        parent: Dict[PhysicalQubit, Optional[PhysicalQubit]] = {start: None}
        reached: Optional[PhysicalQubit] = None
        while q_frontier:
            u = q_frontier.popleft()
            if u in goals:
                reached = u
                break
            for v in self.hw.local_neighbors(u):
                if v not in allowed or v in parent:
                    continue
                parent[v] = u
                q_frontier.append(v)

        if reached is None:
            raise RuntimeError(f"No local route can move q{q} next to active packet port {port}")

        path = [reached]
        while parent[path[-1]] is not None:
            path.append(parent[path[-1]])
        path.reverse()
        return [canonical_edge(path[i], path[i + 1]) for i in range(len(path) - 1)]


    # ---------------------------------------------------------------------
    # Action application
    # ---------------------------------------------------------------------

    def _apply_action(self, action: Action, state: RouterState) -> bool:
        """Apply one physical action; return whether original DAG nodes were removed."""
        state.step += 1
        if action.kind == "local_swap":
            assert action.swap is not None
            p0, p1 = action.swap
            state.layout.swap_physical(self.hw, p0, p1)
            state.emitted.append(
                CompiledOp(
                    op_type="local_swap",
                    physical_qubits=(p0, p1),
                    cores=(self.hw.phys_to_core[p0],),
                    metadata=dict(action.metadata),
                )
            )
            state.stats.local_swap_count += 1
            self._after_layout_change(state, (self.hw.phys_to_core[p0],))
            return False

        if action.kind == "teleport":
            assert action.qubit is not None and action.src_core is not None and action.dst_core is not None
            assert action.dst_phys is not None
            q = action.qubit
            src_phys = state.layout.phys_of(q)
            src_port, dst_port = self.hw.inter_core_ports(action.src_core, action.dst_core)
            state.layout.move_logical_to_physical(q, action.dst_phys, action.dst_core)
            state.emitted.append(
                CompiledOp(
                    op_type="teleport",
                    qubits=(q,),
                    physical_qubits=(src_phys, src_port, action.dst_phys),
                    cores=(action.src_core, action.dst_core),
                    path=(action.src_core, action.dst_core),
                    epr_cost=1,
                    metadata=dict(action.metadata),
                )
            )
            state.stats.epr += 1
            state.stats.teleport_count += 1
            plan_mode = action.metadata.get("plan_mode", "")
            if plan_mode == "capacity_relief_bfs":
                # Tail relief: no normal plan existed at all, so a fresh BFS
                # search found the nearest reservoir core from scratch.
                state.stats.teleport_capacity_relief_count += 1
            elif plan_mode in (
                "blocked_capacity_adjacent",
                "blocked_capacity_distance_reducing",
                "opportunistic_capacity_relief_bfs",
            ):
                # Opportunistic relief: a normal plan existed, but a blocked
                # plan's gain was high enough to pre-empt it -- whether the
                # committed plan is that raw blocked candidate or a
                # BFS-refined variant of it generated for the comparison
                # (_select_opportunistic_capacity_relief_plan).
                state.stats.teleport_blocked_count += 1
            else:
                state.stats.teleport_normal_count += 1
            self._after_layout_change(state, (action.src_core, action.dst_core))
            return False

        if action.kind == "telegate":
            return self._apply_single_telegate(action, state)
        if action.kind == "telegate_packet":
            return self._apply_telegate_packet(action, state)
        raise ValueError(f"Unknown action kind: {action.kind}")

    def _apply_single_telegate(self, action: Action, state: RouterState) -> bool:
        assert action.gate is not None
        g = action.gate
        control, target = g.qubits
        control_core, target_core = state.layout.core_of(control), state.layout.core_of(target)
        control_port, target_port = self.hw.inter_core_ports(control_core, target_core)
        control_phys = state.layout.phys_of(control)
        target_phys = state.layout.phys_of(target)
        if not state.layout.is_phys_free(control_port) or not state.layout.is_phys_free(target_port):
            raise RuntimeError("Telegate ports are not free at execution time")
        if self.hw.local_distance(control_core, control_phys, control_port) != 1:
            raise RuntimeError("Telegate control is not adjacent to the source communication qubit")
        if self.hw.local_distance(target_core, target_phys, target_port) != 1:
            raise RuntimeError("Telegate target is not adjacent to the target communication qubit")

        common_md = {
            **dict(action.metadata),
            "logical_gate": g.gid,
            "logical_control": control,
            "logical_target": target,
            "control_port": control_port,
            "target_port": target_port,
        }
        state.emitted.append(CompiledOp(
            op_type="cat_entangler", gates=(g,), qubits=(control,),
            physical_qubits=(control_phys, control_port, target_port),
            cores=(control_core, target_core), path=(control_core, target_core), epr_cost=1,
            metadata={**common_md, "cat_role": "single_telegate_start"},
        ))
        state.stats.epr += 1
        state.emitted.append(CompiledOp(
            op_type="cat_cx", gates=(g,), qubits=(control, target),
            physical_qubits=(target_port, target_phys), cores=(target_core,),
            metadata={**common_md, "physical_control": target_port, "physical_target": target_phys,
                      "control_represented_by": "target_core_cat_communication_qubit"},
        ))
        state.stats.telegate_count += 1
        state.stats.emitted_gate_count += 1
        state.emitted.append(CompiledOp(
            op_type="cat_disentangler", gates=(g,), qubits=(control,),
            physical_qubits=(control_phys, control_port, target_port),
            cores=(control_core, target_core), path=(control_core, target_core),
            metadata={**common_md, "cat_role": "single_telegate_end"},
        ))
        self._remove_gate_ids(state, {g.gid})
        return True

    def _apply_telegate_packet(self, action: Action, state: RouterState) -> bool:
        packet_ops = tuple(action.gates)
        if not packet_ops:
            raise ValueError("Empty telegate packet")
        cx_gates = self._packet_cx_gates(packet_ops)
        if len(cx_gates) <= 1:
            raise ValueError("Telegate packet requires at least two CX gates")
        control = cx_gates[0].qubits[0]
        target_core = state.layout.core_of(cx_gates[0].qubits[1])
        control_core = state.layout.core_of(control)
        if any(g.qubits[0] != control or state.layout.core_of(g.qubits[1]) != target_core for g in cx_gates):
            raise RuntimeError("Invalid same-control telegate packet at execution time")
        packet_targets = {g.qubits[1] for g in cx_gates}
        for op in packet_ops:
            if op.is_cx():
                continue
            if not op.is_single_qubit() or state.layout.core_of(op.qubits[0]) != target_core:
                raise RuntimeError("Invalid target-core operation inside telegate packet")
        if not self.hw.are_adjacent_cores(control_core, target_core):
            raise RuntimeError("Telegate packet cores are not adjacent at execution time")
        control_port, target_port = self.hw.inter_core_ports(control_core, target_core)
        control_phys = state.layout.phys_of(control)
        if not state.layout.is_phys_free(control_port) or not state.layout.is_phys_free(target_port):
            raise RuntimeError("Telegate packet ports are not free at execution time")
        if self.hw.local_distance(control_core, control_phys, control_port) != 1:
            raise RuntimeError("Telegate packet control is not adjacent to the source communication qubit")

        gate_ids = [g.gid for g in packet_ops]
        cx_gate_ids = [g.gid for g in cx_gates]
        single_gate_ids = [g.gid for g in packet_ops if g.is_single_qubit()]
        common_md = {
            **dict(action.metadata), "packet_size": len(packet_ops), "remote_cx_count": len(cx_gates),
            "gate_ids": gate_ids, "cx_gate_ids": cx_gate_ids, "single_gate_ids": single_gate_ids,
            "logical_control": control, "logical_targets": sorted(packet_targets),
            "control_core": control_core, "target_core": target_core,
            "control_port": control_port, "target_port": target_port,
            "packet_execution": "ordered_with_target_side_single_gates",
        }
        state.emitted.append(CompiledOp(
            op_type="cat_entangler", gates=packet_ops, qubits=(control,),
            physical_qubits=(control_phys, control_port, target_port),
            cores=(control_core, target_core), path=(control_core, target_core), epr_cost=1,
            metadata={**common_md, "cat_role": "packet_start"},
        ))
        state.stats.epr += 1
        state.stats.telegate_packet_count += 1

        active_ports = {control_port, target_port}
        executed_order: List[GateId] = []
        executed_cx_order: List[GateId] = []
        executed_single_order: List[GateId] = []
        cx_index = 0
        for packet_index, op in enumerate(packet_ops):
            if op.is_cx():
                target = op.qubits[1]
                route = self._route_logical_to_port_neighbor_without_comm(
                    state.layout, target, target_core, target_port, forbidden_ports=active_ports
                )
                for swap_index, edge in enumerate(route):
                    p0, p1 = edge
                    if p0 in active_ports or p1 in active_ports:
                        raise RuntimeError("Packet target routing attempted to swap an active packet communication qubit")
                    state.layout.swap_physical(self.hw, p0, p1)
                    state.emitted.append(CompiledOp(
                        op_type="local_swap", physical_qubits=(p0, p1), cores=(target_core,),
                        metadata={"reason": "packet_target_route", "packet_seed": cx_gates[0].gid,
                                  "packet_gate": op.gid, "packet_index": packet_index,
                                  "packet_cx_index": cx_index, "swap_index": swap_index,
                                  "target": target, "target_port": target_port},
                    ))
                    state.stats.local_swap_count += 1
                    self._after_layout_change(state, (target_core,))
                target_phys = state.layout.phys_of(target)
                if not state.layout.is_phys_free(target_port):
                    raise RuntimeError("Target communication qubit became occupied during packet execution")
                if self.hw.local_distance(target_core, target_phys, target_port) != 1:
                    raise RuntimeError("Packet target is not adjacent to the target communication qubit")
                state.emitted.append(CompiledOp(
                    op_type="cat_cx", gates=(op,), qubits=(control, target),
                    physical_qubits=(target_port, target_phys), cores=(target_core,),
                    metadata={**common_md, "logical_gate": op.gid, "logical_target": target,
                              "packet_index": packet_index, "packet_cx_index": cx_index,
                              "execution_order": len(executed_order), "physical_control": target_port,
                              "physical_target": target_phys,
                              "control_represented_by": "target_core_cat_communication_qubit"},
                ))
                state.stats.emitted_gate_count += 1
                executed_order.append(op.gid); executed_cx_order.append(op.gid); cx_index += 1
                continue
            if op.is_single_qubit():
                q = op.qubits[0]; p = state.layout.phys_of(q); c = state.layout.core_of(q)
                if p in active_ports or c != target_core:
                    raise RuntimeError("Packet target-side single gate violates packet constraints")
                state.emitted.append(CompiledOp(
                    op_type="single", gates=(op,), qubits=(q,), physical_qubits=(p,), cores=(c,),
                    metadata={**common_md, "reason": "packet_target_single", "logical_gate": op.gid,
                              "packet_index": packet_index, "execution_order": len(executed_order)},
                ))
                state.stats.single_count += 1
                state.stats.emitted_gate_count += 1
                executed_order.append(op.gid); executed_single_order.append(op.gid)
                continue
            raise RuntimeError(f"Unsupported operation inside telegate packet: {op}")

        control_phys_end = state.layout.phys_of(control)
        state.emitted.append(CompiledOp(
            op_type="cat_disentangler", gates=packet_ops, qubits=(control,),
            physical_qubits=(control_phys_end, control_port, target_port),
            cores=(control_core, target_core), path=(control_core, target_core),
            metadata={**common_md, "cat_role": "packet_end", "executed_order": executed_order,
                      "executed_cx_order": executed_cx_order, "executed_single_order": executed_single_order},
        ))
        self._remove_gate_ids(state, {g.gid for g in packet_ops})
        return True

    def _after_layout_change(
        self, state: RouterState, cores: Optional[Iterable[CoreId]] = None
    ) -> None:
        self._refresh_free_slot_queues(state, only_cores=cores)

    def _remove_gate_ids(self, state: RouterState, gate_ids: Set[GateId]) -> None:
        """Remove executed gates from the DAG view and update the frontier.

        ``state.remaining`` is not pruned here; it is synchronized lazily via
        ``_sync_remaining`` (at exit points) to avoid an O(circuit) rebuild per
        executed batch.
        """
        for gid in sorted(gate_ids):
            if gid not in state.dag_active:
                continue
            state.dag_active.remove(gid)
            state.dag_frontier.discard(gid)
            gate = state.gate_by_id.get(gid)
            if gate is not None and gate.is_cx():
                for q in gate.qubits:
                    state.active_cx_by_qubit[q] = max(
                        0, state.active_cx_by_qubit.get(q, 0) - 1)
            for succ in state.dag_successors.get(gid, set()):
                if succ in state.dag_active:
                    count = max(0, state.dag_predecessor_count.get(succ, 0) - 1)
                    state.dag_predecessor_count[succ] = count
                    if count == 0:
                        state.dag_frontier.add(succ)

    @staticmethod
    def _sync_remaining(state: RouterState) -> None:
        state.remaining = [g for g in state.remaining if g.gid in state.dag_active]

    # ---------------------------------------------------------------------
    # Free-slot queues and physical-readiness helpers
    # ---------------------------------------------------------------------

    def _refresh_free_slot_queues(
        self, state: RouterState, only_cores: Optional[Iterable[CoreId]] = None
    ) -> None:
        """Rebuild free-slot queues, optionally only for the cores whose free
        sets could have changed (a local SWAP touches one core, a teleport
        touches two); other cores' queues are still valid."""
        if only_cores is None:
            queues: Dict[Tuple[CoreId, CoreId], List[Tuple[int, PhysicalQubit]]] = {}
            state.free_slot_queues = queues
            touched = self.hw.cores.items()
        else:
            queues = state.free_slot_queues
            touched = [(cid, self.hw.cores[cid]) for cid in dict.fromkeys(only_cores)]
        for cid, core in touched:
            free = state.layout.free_physical_qubits(self.hw, cid)
            for nbr, port in core.ports.items():
                queues[(cid, nbr)] = sorted((self.hw.local_distance(cid, port, p), p) for p in free)

    def _nearest_free_positions_to_port_from_state(
        self, state: RouterState, cid: CoreId, neighbor: CoreId
    ) -> List[PhysicalQubit]:
        """Return every currently-free slot tied for minimum distance to a port.

        The queue is refreshed after every real layout change.  Retaining all
        minimizers is important for preparation candidate generation: selecting
        only one minimizer by physical index would create an arbitrary routing
        preference before the simulator has scored the resulting SWAPs.
        """
        queue = state.free_slot_queues.get((cid, neighbor), [])
        nearest_distance: Optional[int] = None
        nearest: List[PhysicalQubit] = []
        for distance, p in queue:
            if not state.layout.is_phys_free(p):
                continue
            if nearest_distance is None:
                nearest_distance = distance
            if distance != nearest_distance:
                break
            nearest.append(p)
        return nearest

    def _nearest_free_to_port_from_layout(
        self, layout: Layout, cid: CoreId, neighbor: CoreId
    ) -> Optional[PhysicalQubit]:
        free = layout.free_physical_qubits(self.hw, cid)
        if not free:
            return None
        port = self.hw.cores[cid].ports[neighbor]
        return min(free, key=lambda p: self.hw.local_distance(cid, p, port))

    def _nearest_free_distance_to_port(self, layout: Layout, cid: CoreId, neighbor: CoreId) -> float:
        p = self._nearest_free_to_port_from_layout(layout, cid, neighbor)
        if p is None:
            return math.inf
        port = self.hw.cores[cid].ports[neighbor]
        return float(self.hw.local_distance(cid, p, port))

    def _port_clearance_cost(self, layout: Layout, cid: CoreId, neighbor: CoreId) -> float:
        """Estimated local-SWAP cost to clear the communication port for cid->neighbor.

        If the port is occupied, the nearest free physical qubit must be moved
        toward that port.  The local distance from the nearest free slot to the
        port is a closer proxy than a fixed occupancy penalty.
        """
        d = self._nearest_free_distance_to_port(layout, cid, neighbor)
        if math.isinf(d):
            return 100.0
        return float(d)

    def _remote_edge_readiness_cost(
        self, layout: Layout, q: LogicalQubit, src: CoreId, dst: CoreId, min_free: int
    ) -> float:
        """0 means a teleport q:src->dst is physically ready under our model."""
        src_port, dst_port = self.hw.inter_core_ports(src, dst)
        cost = 0.0
        src_phys = layout.phys_of(q)
        d_src = self.hw.local_distance(src, src_phys, src_port)
        if d_src == math.inf:
            cost += 20.0
        else:
            # Ideal: endpoint adjacent to a free communication qubit.
            cost += abs(float(d_src) - 1.0)
        if not layout.is_phys_free(src_port):
            cost += self._port_clearance_cost(layout, src, dst)
        if not layout.is_phys_free(dst_port):
            cost += self._port_clearance_cost(layout, dst, src)
        free_deficit = max(0, min_free - layout.free_count(self.hw, dst))#防御性代码，即使有容量不足的核心其评分会很高
        cost += 10.0 * free_deficit
        return cost


    def _dedupe_actions(self, actions: List[Action]) -> List[Action]:
        seen = set()
        out = []
        for a in actions:
            key = (
                a.kind,
                a.gate.gid if a.gate else None,
                tuple(g.gid for g in a.gates),
                a.qubit,
                a.src_core,
                a.dst_core,
                a.dst_phys,
                a.swap,
                a.metadata.get("reason"),
                a.metadata.get("prep_qubit"),
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(a)
        return out



    def _validate_tie_break_config(self) -> None:
        if self.cfg.tie_score_epsilon < 0.0:
            raise ValueError("tie_score_epsilon must be non-negative")


    def _deadlock_message(self, state: RouterState, info: FrontInfo) -> str:
        free = {cid: state.layout.free_count(self.hw, cid) for cid in self.hw.cores}
        lines = [
            'No legal action available.',
            f'Current DAG front: {[str(g) for g in info.front]}',
            f'Free slots by core: {free}',
            'Possible causes: no remote plan can be prepared, or capacity recovery cannot reach a reservoir core.',
        ]
        full_cores = sorted(cid for cid, n in free.items() if n == 0)
        if full_cores:
            lines.append(
                f'Cores {full_cores} have zero free slots: a full core can never '
                'clear its occupied communication ports with local SWAPs, so no '
                'teleport or telegate can touch it and its qubits are stranded. '
                'This is infeasible under the port-based action model; it usually '
                'means the (external) initial layout filled a core to capacity.'
            )
        return '\n'.join(lines)


# -------------------------------------------------------------------------
# Hardware, layout, and circuit helpers
# -------------------------------------------------------------------------


