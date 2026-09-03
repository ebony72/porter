"""Data model: gates, emitted ops, router state/config, actions and remote plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Set, Any

from .hardware import CoreId, GateId, LogicalQubit, PhysicalQubit
from .layout import Layout


@dataclass(frozen=True)
class Gate:
    """A gate in the restricted basis ['id', 'rz', 'sx', 'x', 'cx']."""

    name: str
    qubits: Tuple[LogicalQubit, ...]
    params: Tuple[float, ...] = ()
    gid: GateId = -1

    def __post_init__(self):
        object.__setattr__(self, "name", self.name.lower())
        object.__setattr__(self, "qubits", tuple(self.qubits))
        object.__setattr__(self, "params", tuple(self.params))
        object.__setattr__(self, "_is_cx", self.name == "cx" and len(self.qubits) == 2)
        object.__setattr__(
            self,
            "_is_single",
            self.name in {"id", "rz", "sx", "x"} and len(self.qubits) == 1,
        )

    def is_cx(self) -> bool:
        return self._is_cx

    def is_single_qubit(self) -> bool:
        return self._is_single

    def __str__(self) -> str:
        qs = ",".join(f"q{q}" for q in self.qubits)
        if self.params:
            ps = ",".join(str(p) for p in self.params)
            return f"{self.gid}:{self.name}({ps}) {qs}"
        return f"{self.gid}:{self.name} {qs}"


@dataclass
class CompiledOp:
    """An operation emitted by the router."""

    op_type: str
    gates: Tuple[Gate, ...] = ()
    qubits: Tuple[LogicalQubit, ...] = ()
    physical_qubits: Tuple[PhysicalQubit, ...] = ()
    cores: Tuple[CoreId, ...] = ()
    path: Tuple[CoreId, ...] = ()
    epr_cost: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RouterStats:
    epr: int = 0
    teleport_count: int = 0
    telegate_count: int = 0
    telegate_packet_count: int = 0

    # Breakdown of teleport_count by the committed plan's provenance (see
    # PorterRouter._execute_plan_first_remote_stage): every committed
    # teleport falls into exactly one of these three, and they sum to
    # teleport_count.
    #   normal           : an unblocked candidate from the normal plan set.
    #   blocked           : a capacity-blocked ("blockedteledata") candidate,
    #                       committed via the opportunistic pre-emptive
    #                       relief comparator because it promised much
    #                       higher gain than the best normal plan.
    #   capacity_relief   : a multi-hop BFS tail-relief teleport toward the
    #                       nearest reservoir core, generated only when no
    #                       normal plan exists at all.
    teleport_normal_count: int = 0
    teleport_blocked_count: int = 0
    teleport_capacity_relief_count: int = 0

    local_swap_count: int = 0
    # DAG layers peeled by the teleport lookahead walk; the deterministic work
    # counter `run_horizon_selection` budgets a speculative horizon against.
    lookahead_layers_peeled: int = 0
    local_cx_count: int = 0
    single_count: int = 0
    emitted_gate_count: int = 0
    depth: int = 0
    depth_proxy: int = 0
    intercore_depth: int = 0

    # Reproducible randomized tie-break diagnostics.  These counters increase
    # only when two or more candidates are still indistinguishable after all
    # semantic comparison criteria for their decision stage have been applied.
    seeded_tie_break_count: int = 0
    seeded_tie_candidate_total: int = 0
    seeded_local_swap_tie_break_count: int = 0
    seeded_remote_plan_tie_break_count: int = 0

    # Number of logical qubits evicted from a full core at the start of
    # compile() to make an externally supplied initial layout legal; see
    # RouterConfig.repair_full_cores. 0 for any layout that already respects
    # the no-full-core invariant (PORTER's own initial layouts always do).
    initial_layout_repairs: int = 0


@dataclass
class RouterState:
    layout: Layout
    remaining: List[Gate]
    emitted: List[CompiledOp] = field(default_factory=list)
    stats: RouterStats = field(default_factory=RouterStats)
    step: int = 0
    # Ordinary per-qubit DAG state.
    dag_successors: Dict[GateId, Set[GateId]] = field(default_factory=dict)
    dag_predecessor_count: Dict[GateId, int] = field(default_factory=dict)
    dag_predecessors: Dict[GateId, Set[GateId]] = field(default_factory=dict)
    dag_active: Set[GateId] = field(default_factory=set)
    # Zero-predecessor active gates, maintained incrementally so the DAG front
    # never has to be recomputed by scanning every remaining gate.
    dag_frontier: Set[GateId] = field(default_factory=set)
    # Active CX count per logical qubit, maintained alongside `dag_active`.
    # Bounds how many of a qubit's gates a lookahead walk can still find, so
    # the walk can stop instead of peeling layers that cannot yield anything.
    active_cx_by_qubit: Dict[LogicalQubit, int] = field(default_factory=dict)
    gate_by_id: Dict[GateId, Gate] = field(default_factory=dict)
    dag_edge_count: int = 0

    # Physical-routing state.
    free_slot_queues: Dict[Tuple[CoreId, CoreId], List[Tuple[int, PhysicalQubit]]] = field(default_factory=dict)


@dataclass
class RouterConfig:
    # DAG and local-SWAP lookahead.
    local_swap_extended_weight: float = 0.8
    local_swap_extended_max_layers: int = 12
    local_swap_extended_cx_count: int = 20

    # Packet construction.
    extended_packet_window: int = 120
    remote_gate_limit: int = 20
    max_packet_size: int = 8

    # Action-vocabulary ablation.  With telegate_enabled=False the remote
    # plan generator emits no TeleGate and no TeleGatePacket alternatives, so
    # the only inter-core primitive left is TeleData (state teleportation) --
    # dSABRE's action vocabulary inside PORTER's plan-committed framework.
    # Default True; setting it False changes the emitted op stream.
    telegate_enabled: bool = True
    # When no normal remote plan exists at all, the tail-relief BFS is fed
    # only the *distance-reducing* (non-adjacent) capacity-blocked plans; an
    # all-adjacent blocked front therefore has no recovery.  With the
    # TeleGate available that never bites, because a TeleGate needs no free
    # slot and so is always a normal plan for an adjacent remote CX.  Under
    # telegate_enabled=False it does bite, so this flag additionally routes
    # adjacent-blocked plans (single relief hop) into the same BFS.
    # Default False: the shipped protocol's op stream is unaffected.
    capacity_relief_from_adjacent_blocked: bool = False

    # Unit-of-commitment ablation.  PORTER's remote stage commits to a whole
    # RemotePlan and will not reopen the choice until that plan is ready
    # (_commit_remote_plan).  dSABRE's unit is one teleport hop, re-scored
    # against the whole front every iteration.  With
    # remote_plan_commitment=False the committed loop hands control back
    # after ONE round of preparation SWAPs, so the front is re-classified and
    # every plan re-generated and re-scored before the next move -- dSABRE's
    # discipline inside PORTER's plan machinery.  Default True; setting it
    # False changes the emitted op stream.
    remote_plan_commitment: bool = True
   

    # Teleport benefit lookahead.
    dag_extended_max_layers: int = 16
    teleport_lookahead_cx_count: int = 50
    teleport_lookahead_weight: float = 0.9
    teleport_latent_direct_weight: float = 1.0
    teleport_lookahead_decay: float = 0.9
    teleport_lookahead_weight_floor: float = 0.5

    # Capacity constraints and recovery.
    #
    # A core with zero free physical qubits is a hard deadlock under this
    # router's port-based action model: no local SWAP can change a core's
    # occupancy, so a fully-packed core can never clear its own communication
    # ports, and any gate touching its qubits is stranded forever (see the
    # qnn-25 pytket-dqc case documented in CLAUDE.md's failure-model
    # section). PORTER's own initial-layout builders always reserve
    # min_free_before_teleport free slots per core, so this only arises from
    # an externally supplied layout (e.g. a shared TeleSABRE/pytket-dqc
    # mapping) that doesn't know about the constraint. With
    # repair_full_cores enabled, compile() legalizes such a layout before
    # routing starts by evicting one logical qubit from each full core into
    # the core with the most free capacity, repeating until no core is full
    # (or raising ValueError if the circuit doesn't fit this hardware with
    # any headroom at all). Disable only to test how a given input layout
    # behaves as-is.
    repair_full_cores: bool = True
    min_free_before_teleport: int = 2
    capacity_relief_assist_enabled: bool = True
    capacity_relief_assist_margin: float = 5.0
    # Permit capacity-relief BFS to expand beyond an immediately adjacent reservoir.
    # When disabled, the same BFS generator is restricted to depth one.
    capacity_relief_chain_enabled: bool = True

    # Local action scoring.
    w_port: float = 1.0
    w_local_swap: float = 2.0

    # Tie handling.  Once selected, remote preparation is unbounded: it
    # continues until the plan is ready, no relevant preparation SWAP exists,
    # or the complete deterministic decision state repeats.
    random_seed: int = 0
    seeded_tie_break_enabled: bool = True
    tie_score_epsilon: float = 1e-9
    max_iterations: int = 200_000
    # Abandon a route that has stopped retiring gates.  Measured over 96 routes
    # (48 instances x L in {16,128}): every route that completes has a longest
    # no-retirement run of at most 17 iterations, and every route that does not
    # complete exceeds 5,084 -- a 299x separation with nothing in between.  So a
    # limit of 1,000 sits 59x above healthy behaviour and 5x below every observed
    # stall.  Being an iteration count rather than a wall-clock share, it
    # abandons a stalled route reproducibly.  0 disables the guard.
    max_iterations_without_progress: int = 1_000
    # Work budget for a speculative horizon, counted in DAG layers peeled by the
    # lookahead walk -- the dominant cost inside the collector, and one that
    # rises with the horizon as the run time does.  `run_horizon_selection` sets
    # it from the first route's own count so a candidate cannot cost
    # unboundedly more than the route the caller would have got anyway.  Unlike
    # a wall-clock share this is a property of the route, not of the machine.
    # 0 disables the budget.
    max_lookahead_layers: int = 0
    # Hard bound on preparation SWAPs applied while committing one remote
    # plan.  The decision-state cycle check includes the RNG state, so an
    # oscillating trajectory that consumes randomness on every round would
    # otherwise never repeat its signature and spin forever.
    max_prep_iterations_per_plan: int = 10_000


@dataclass(frozen=True)
class Action:
    kind: str
    gate: Optional[Gate] = None
    gates: Tuple[Gate, ...] = ()
    qubit: Optional[LogicalQubit] = None
    src_core: Optional[CoreId] = None
    dst_core: Optional[CoreId] = None
    dst_phys: Optional[PhysicalQubit] = None
    swap: Optional[Tuple[PhysicalQubit, PhysicalQubit]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FrontInfo:
    front: List[Gate]
    singles: List[Gate]
    direct_local_cx: List[Gate]
    local_cx_need_swap: List[Gate]
    adjacent_remote_cx: List[Gate]
    non_adjacent_remote_cx: List[Gate]


@dataclass(frozen=True)
class RemotePlan:
    """A high-level plan for handling one remote-gate opportunity.

    The remote stage first compares these plans.  Only after a plan is selected
    do we generate local preparation SWAPs for that specific plan.  This avoids
    mixing every possible remote-prep SWAP from every remote gate into one flat
    action pool.
    """

    kind: str
    gate: Gate
    gates: Tuple[Gate, ...] = ()
    moving_qubit: Optional[LogicalQubit] = None
    src_core: Optional[CoreId] = None
    dst_core: Optional[CoreId] = None
    mode: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def plan_id(self) -> Tuple[Any, ...]:
        return (
            self.kind,
            self.gate.gid,
            tuple(g.gid for g in self.gates),
            self.moving_qubit,
            self.src_core,
            self.dst_core,
            self.mode,
        )


@dataclass
class RemotePlanScore:
    total: float
    ready: bool
    prep: float
    capacity: float
    direct_gain: float = 0.0
    lookahead_gain: float = 0.0



def assign_gate_ids(circuit: List[Gate]) -> List[Gate]:
    return [Gate(g.name, g.qubits, g.params, gid=i) for i, g in enumerate(circuit)]

