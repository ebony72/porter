"""PORTER — Plan-Oriented Router for Teleportation-Enabled aRchitectures.

A router for multi-core (distributed) quantum hardware.  It routes over the
zero-predecessor DAG frontier with a locality-first priority (local work
always precedes inter-core work) and a plan-committed remote stage that
chooses among teleport (TeleData), single telegate, same-control telegate
packets, and capacity-relief moves, then prepares exactly the chosen plan.

Public API::

    from porter import PorterRouter, RouterConfig, Hardware, Layout, Gate
    state = PorterRouter(hw, RouterConfig(random_seed=0)).compile(circuit, layout)
"""

from .hardware import (
    Core,
    CoreId,
    Edge,
    GateId,
    Hardware,
    LogicalQubit,
    PhysicalQubit,
    bfs_distances,
    canonical_edge,
)
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
    RouterStats,
    assign_gate_ids,
)
from .router import CapacityReliefPlanner, DagFrontierSimulator, DagSimState, PorterRouter

# Backwards-compatible alias (pre-rename name).
DistributedRouter = PorterRouter

__all__ = [
    "Action",
    "CapacityReliefPlanner",
    "CompiledOp",
    "Core",
    "CoreId",
    "DagFrontierSimulator",
    "DagSimState",
    "DistributedRouter",
    "Edge",
    "FrontInfo",
    "Gate",
    "GateId",
    "Hardware",
    "Layout",
    "LogicalQubit",
    "PhysicalQubit",
    "PorterRouter",
    "RemotePlan",
    "RemotePlanScore",
    "RouterConfig",
    "RouterState",
    "RouterStats",
    "assign_gate_ids",
    "bfs_distances",
    "canonical_edge",
]
