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
    local_swap_count: int = 0
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
    gate_by_id: Dict[GateId, Gate] = field(default_factory=dict)
    dag_edge_count: int = 0

    # Physical-routing state.
    free_slot_queues: Dict[Tuple[CoreId, CoreId], List[Tuple[int, PhysicalQubit]]] = field(default_factory=dict)


@dataclass
class RouterConfig:
    # DAG and local-SWAP lookahead.
    dag_front_limit: int = 96
    local_swap_extended_weight: float = 0.8
    local_swap_extended_max_layers: int = 12
    local_swap_extended_cx_count: int = 20

    # Packet construction.
    extended_packet_window: int = 120
    remote_gate_limit: int = 20
    max_packet_size: int = 8
   

    # Teleport benefit lookahead.
    dag_extended_max_layers: int = 16
    teleport_lookahead_cx_count: int = 50
    teleport_lookahead_weight: float = 0.9
    teleport_latent_direct_weight: float = 1.0
    teleport_lookahead_decay: float = 0.9
    teleport_lookahead_weight_floor: float = 0.5

    # Capacity constraints and recovery.
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

