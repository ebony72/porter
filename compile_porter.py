from __future__ import annotations

import argparse
import contextlib
import csv
import dataclasses
import json
import math
import random
import signal
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import porter


QASM_GATE_RE = r"^([a-zA-Z][a-zA-Z0-9_]*)\s*(?:\(([^)]*)\))?\s+(.*)$"
QASM_QUBIT_RE = r"^([a-zA-Z_][a-zA-Z0-9_]*)\[(\d+)\]$"


def _safe_float_expr(expr: str) -> float:
    return float(eval(expr, {"__builtins__": {}}, {"pi": math.pi}))


def _parse_qasm_qubit(token: str, qreg_offsets: Dict[str, int]) -> int:
    import re

    match = re.match(QASM_QUBIT_RE, token)
    if not match:
        raise ValueError(f"Unsupported qubit operand: {token}")
    qreg_name = match.group(1)
    index = int(match.group(2))
    if qreg_name not in qreg_offsets:
        raise ValueError(f"Unknown qreg {qreg_name!r}")
    return qreg_offsets[qreg_name] + index


def parse_qasm2(path: Path) -> Tuple[List[porter.Gate], int]:
    import re

    qreg_offsets: Dict[str, int] = {}
    total_qubits = 0
    gates: List[porter.Gate] = []

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line or not line.endswith(";"):
            continue
        stmt = line[:-1].strip()
        lowered = stmt.lower()
        if lowered.startswith(("openqasm", "include", "creg", "measure", "barrier")):
            continue

        qreg_match = re.match(r"qreg\s+([a-zA-Z_][a-zA-Z0-9_]*)\[(\d+)\]$", stmt)
        if qreg_match:
            qreg_offsets[qreg_match.group(1)] = total_qubits
            total_qubits += int(qreg_match.group(2))
            continue

        gate_match = re.match(QASM_GATE_RE, stmt)
        if not gate_match:
            raise ValueError(f"Unsupported QASM statement in {path.name}: {raw}")

        name = gate_match.group(1).lower()
        param_text = gate_match.group(2)
        operand_text = gate_match.group(3)
        operands = [part.strip() for part in operand_text.split(",")]
        logical_qubits = tuple(_parse_qasm_qubit(q, qreg_offsets) for q in operands)
        params = tuple(_safe_float_expr(part.strip()) for part in param_text.split(",")) if param_text else ()

        if name not in {"id", "rz", "sx", "x", "cx"}:
            raise ValueError(f"Unsupported gate {name!r} in {path.name}: {raw}")
        if name == "cx" and len(logical_qubits) != 2:
            raise ValueError(f"CX must have two operands in {path.name}: {raw}")
        if name != "cx" and len(logical_qubits) != 1:
            raise ValueError(f"{name} must have one operand in {path.name}: {raw}")

        gates.append(porter.Gate(name, logical_qubits, params))

    return gates, total_qubits


def _grid_hardware(
    grid_x: int,
    grid_y: int,
    core_x: int,
    core_y: int,
    inter_core_edges: List[Tuple[int, int]],
) -> porter.Hardware:
    core_size = grid_x * grid_y
    cores: Dict[int, porter.Core] = {}
    phys_to_core: Dict[int, int] = {}

    for cy in range(core_y):
        for cx in range(core_x):
            cid = cy * core_x + cx
            core_start = cid * core_size
            physical: List[int] = []
            coupling_edges: List[Tuple[int, int]] = []
            for y in range(grid_y):
                for x in range(grid_x):
                    p = core_start + y * grid_x + x
                    physical.append(p)
                    phys_to_core[p] = cid
                    if x < grid_x - 1:
                        coupling_edges.append((p, p + 1))
                    if y < grid_y - 1:
                        coupling_edges.append((p, p + grid_x))

            cores[cid] = porter.Core(
                cid=cid,
                physical_qubits=tuple(physical),
                coupling_edges=tuple(coupling_edges),
                ports={},
            )

    core_edges: List[Tuple[int, int]] = []
    for p0, p1 in inter_core_edges:
        c0 = phys_to_core[p0]
        c1 = phys_to_core[p1]
        cores[c0].ports[c1] = p0
        cores[c1].ports[c0] = p1
        core_edges.append((c0, c1))

    return porter.Hardware(cores=cores, core_edges=tuple(core_edges))


def hardware_from_device_json(path: Path) -> Tuple[str, porter.Hardware]:
    """Build a PORTER Hardware from a TeleSABRE device JSON.

    Makes no grid assumptions: cores are the connected components of the
    intra-core coupling graph, so any device file the baselines accept can be
    routed by PORTER on the identical physical qubit ids.  Used for the
    scale-up architectures (100/200/360 logical qubits), where hand-coding
    inter-core port lists would be error-prone.
    """
    device = json.loads(Path(path).read_text())["device"]
    intra = [tuple(e) for e in device["intra_core_edges"]]
    inter = [tuple(e) for e in device["inter_core_edges"]]
    n_phys = device["num_qubits"]

    adjacency: Dict[int, List[int]] = {q: [] for q in range(n_phys)}
    for a, b in intra:
        adjacency[a].append(b)
        adjacency[b].append(a)

    core_of: Dict[int, int] = {}
    components: List[List[int]] = []
    for q in range(n_phys):
        if q in core_of:
            continue
        cid = len(components)
        stack, members = [q], []
        core_of[q] = cid
        while stack:
            cur = stack.pop()
            members.append(cur)
            for nb in adjacency[cur]:
                if nb not in core_of:
                    core_of[nb] = cid
                    stack.append(nb)
        components.append(sorted(members))

    if len(components) != device["num_cores"]:
        raise ValueError(
            f"{Path(path).name}: intra-core graph has {len(components)} components "
            f"but the device declares {device['num_cores']} cores"
        )

    cores: Dict[int, porter.Core] = {}
    for cid, members in enumerate(components):
        member_set = set(members)
        edges = tuple((a, b) for a, b in intra
                      if a in member_set and b in member_set)
        cores[cid] = porter.Core(cid=cid, physical_qubits=tuple(members),
                                 coupling_edges=edges, ports={})

    core_edges: List[Tuple[int, int]] = []
    for p0, p1 in inter:
        c0, c1 = core_of[p0], core_of[p1]
        if c1 in cores[c0].ports or c0 in cores[c1].ports:
            raise ValueError(
                f"{Path(path).name}: more than one inter-core link between cores "
                f"{c0} and {c1}; PORTER's Core.ports holds one port per neighbour"
            )
        cores[c0].ports[c1] = p0
        cores[c1].ports[c0] = p1
        core_edges.append((c0, c1))

    return device["name"], porter.Hardware(cores=cores, core_edges=tuple(core_edges))


def hardware_for_name(name: str) -> Tuple[str, porter.Hardware]:
    normalized = name.upper()
    if normalized == "A":
        return "2x2C 3x3Q", _grid_hardware(
            3,
            3,
            2,
            2,
            [(5, 12), (16, 28), (7, 19), (23, 30)],
        )
    if normalized == "H":
        return "3x2C 4x4Q - H", _grid_hardware(
            4,
            4,
            3,
            2,
            [(13, 49), (7, 20), (23, 36), (59, 72), (30, 65), (75, 88), (46, 82)],
        )
    raise ValueError(f"Unsupported architecture {name!r}; expected A or H")


def telesabre_architecture_for_name(name: str):
    from architecture import Architecture

    normalized = name.upper()
    if normalized == "A":
        return Architecture.A()
    if normalized == "H":
        return Architecture.H()
    raise ValueError(f"Unsupported architecture {name!r}; expected A or H")


def convert_architecture(arch) -> porter.Hardware:
    cores: Dict[int, porter.Core] = {}
    for cid in range(arch.num_cores):
        physical = tuple(int(p) for p in arch.core_qubits[cid])
        physical_set = set(physical)
        coupling_edges = tuple(
            (int(edge.p1), int(edge.p2))
            for edge in arch.edges
            if edge.p1 in physical_set and edge.p2 in physical_set
        )
        cores[cid] = porter.Core(
            cid=cid,
            physical_qubits=physical,
            coupling_edges=coupling_edges,
            ports={},
        )

    core_edges: List[Tuple[int, int]] = []
    for edge in arch.inter_core_edges:
        c0 = int(arch.get_qubit_core(edge.p1))
        c1 = int(arch.get_qubit_core(edge.p2))
        cores[c0].ports[c1] = int(edge.p1)
        cores[c1].ports[c0] = int(edge.p2)
        core_edges.append((c0, c1))

    return porter.Hardware(cores=cores, core_edges=tuple(core_edges))


def convert_layout(layout, hw: porter.Hardware, num_logical: int) -> porter.Layout:
    phys_to_virt = [int(v) for v in layout.phys_to_virt.tolist()]
    return porter.Layout.from_telesabre_phys_to_virt(hw, phys_to_virt, num_logical)


def _first_cx_layer(gates: List[porter.Gate]) -> List[Tuple[int, int]]:
    busy: set[int] = set()
    layer: List[Tuple[int, int]] = []
    for gate in gates:
        if not gate.is_cx():
            continue
        q0, q1 = gate.qubits
        if q0 in busy or q1 in busy:
            continue
        layer.append((q0, q1))
        busy.add(q0)
        busy.add(q1)
    return layer


def build_initial_layout(
    gates: List[porter.Gate],
    hw: porter.Hardware,
    num_logical: int,
    *,
    min_free_per_core: int,
    gamma: float = 0.99,
) -> porter.Layout:
    """PORTER's initial layout: deterministic temporal locality-greedy.

    Single-shot and seed-free -- this is the one initial mapping PORTER
    uses (it replaced the balanced-first-layer / seeded-locality best-of-6
    search on 2026-07-12; see ``build_balanced_first_layer_layout`` below
    for the legacy heuristic kept for the paper's layout study).

    1. Every CX contributes ``gamma**layer`` to its qubit pair's weight,
       where ``layer`` is the gate's ASAP level in the CX-only DAG: early
       interactions weigh more (subsumes first-CX-layer co-location),
       accumulated multiplicity tracks chains (subsumes locality-greedy).
    2. Logical qubits are visited in order of first CX appearance and each
       is placed in the core of its heaviest already-placed neighbour when
       that core has headroom above ``min_free_per_core``, else in the core
       with the most remaining reserved capacity.  Every core keeps
       ``min_free_per_core`` free slots, so the router's teleport
       precondition holds by construction.
    3. Within each core, logicals are placed by descending total
       interaction weight onto physical slots by ascending intra-core
       centrality (sum of local distances).
    """
    from collections import defaultdict

    num_physical = len(hw.phys_to_core)
    if num_logical > num_physical:
        raise ValueError(
            f"Circuit has {num_logical} logical qubits but hardware has {num_physical} physical qubits"
        )

    level: Dict[int, int] = defaultdict(int)
    pair_weight: Dict[Tuple[int, int], float] = defaultdict(float)
    first_seen: Dict[int, int] = {}
    order_counter = 0
    for gate in gates:
        if not gate.is_cx():
            continue
        q0, q1 = gate.qubits
        lay = max(level[q0], level[q1])
        level[q0] = level[q1] = lay + 1
        pair_weight[(min(q0, q1), max(q0, q1))] += gamma ** lay
        for q in (q0, q1):
            if q not in first_seen:
                first_seen[q] = order_counter
                order_counter += 1

    nbr_weight: Dict[int, Dict[int, float]] = {q: {} for q in range(num_logical)}
    for (a, b), w in pair_weight.items():
        nbr_weight[a][b] = w
        nbr_weight[b][a] = w

    core_order = sorted(hw.cores)
    remaining = {
        cid: max(0, len(hw.cores[cid].physical_qubits) - min_free_per_core)
        for cid in core_order
    }
    if sum(remaining.values()) < num_logical:
        raise ValueError(
            "Initial layout cannot reserve "
            f"{min_free_per_core} free qubits per core for {num_logical} logical qubits"
        )

    visit = sorted(range(num_logical), key=lambda q: first_seen.get(q, 10 ** 9 + q))
    logical_to_core: Dict[int, int] = {}
    core_to_logicals: Dict[int, List[int]] = {cid: [] for cid in core_order}
    for q in visit:
        best_core, best_w = None, -1.0
        for nbr, w in nbr_weight[q].items():
            c = logical_to_core.get(nbr)
            if c is not None and remaining[c] > 0 and w > best_w:
                best_core, best_w = c, w
        if best_core is None:
            best_core = max(
                (c for c in core_order if remaining[c] > 0),
                key=lambda c: (remaining[c], -c),
            )
        logical_to_core[q] = best_core
        core_to_logicals[best_core].append(q)
        remaining[best_core] -= 1

    phys_to_virt = [-1] * num_physical
    dummy = num_logical
    for cid in core_order:
        physical = list(hw.cores[cid].physical_qubits)
        slots = sorted(
            physical,
            key=lambda p: (
                sum(hw.local_distance(cid, p, o) for o in physical if o != p),
                p,
            ),
        )
        logicals = sorted(
            core_to_logicals[cid],
            key=lambda q: (-sum(nbr_weight[q].values()), q),
        )
        for p, q in zip(slots, logicals):
            phys_to_virt[p] = q
        for p in slots[len(logicals):]:
            phys_to_virt[p] = dummy
            dummy += 1
    return porter.Layout.from_telesabre_phys_to_virt(hw, phys_to_virt, num_logical)


def build_balanced_first_layer_layout(
    gates: List[porter.Gate],
    hw: porter.Hardware,
    num_logical: int,
    seed: int,
    *,
    min_free_per_core: int,
) -> porter.Layout:
    """Legacy balanced-first-layer heuristic (pre-2026-07-12 default),
    kept only for the paper's initial-mapping study
    (``paper/porter_under_layouts.py``)."""
    num_physical = len(hw.phys_to_core)
    if num_logical > num_physical:
        raise ValueError(f"Circuit has {num_logical} logical qubits but hardware has {num_physical} physical qubits")

    core_order = sorted(hw.cores)
    remaining_capacity: Dict[int, int] = {
        cid: max(0, len(hw.cores[cid].physical_qubits) - min_free_per_core)
        for cid in core_order
    }
    if sum(remaining_capacity.values()) < num_logical:
        raise ValueError(
            "Initial layout cannot reserve "
            f"{min_free_per_core} free qubits per core for {num_logical} logical qubits"
        )

    logical_to_core: Dict[int, int] = {}
    core_to_logicals: Dict[int, List[int]] = {cid: [] for cid in core_order}

    def choose_core(required_slots: int) -> int:
        candidates = [cid for cid in core_order if remaining_capacity[cid] >= required_slots]
        if not candidates:
            raise ValueError(f"No core has {required_slots} reserved-capacity slots left")
        return min(candidates, key=lambda cid: (-remaining_capacity[cid], cid))

    def place(q: int, cid: int) -> None:
        if q in logical_to_core:
            return
        logical_to_core[q] = cid
        core_to_logicals[cid].append(q)
        remaining_capacity[cid] -= 1

    for q0, q1 in _first_cx_layer(gates):
        if q0 in logical_to_core and q1 in logical_to_core:
            continue
        if q0 in logical_to_core or q1 in logical_to_core:
            placed = q0 if q0 in logical_to_core else q1
            unplaced = q1 if placed == q0 else q0
            placed_core = logical_to_core[placed]
            if remaining_capacity[placed_core] > 0:
                place(unplaced, placed_core)
            else:
                place(unplaced, choose_core(1))
            continue

        cid = choose_core(2)
        place(q0, cid)
        place(q1, cid)

    for q in range(num_logical):
        if q not in logical_to_core:
            place(q, choose_core(1))

    rng = random.Random(seed)
    phys_to_virt = [-1] * num_physical
    dummy = num_logical
    for cid in core_order:
        physical = list(hw.cores[cid].physical_qubits)
        rng.shuffle(physical)
        logicals = list(core_to_logicals[cid])
        logicals.sort()
        if len(logicals) > len(physical):
            raise ValueError(f"Core {cid} has more assigned logical qubits than physical qubits")

        for p, q in zip(physical, logicals):
            phys_to_virt[p] = q
        for p in physical[len(logicals):]:
            phys_to_virt[p] = dummy
            dummy += 1

    if any(v < 0 for v in phys_to_virt):
        missing = [p for p, v in enumerate(phys_to_virt) if v < 0]
        raise ValueError(f"Initial layout did not assign physical qubits: {missing}")

    return porter.Layout.from_telesabre_phys_to_virt(hw, phys_to_virt, num_logical)


def build_telesabre_initial_layout(
    qasm_path: Path,
    arch,
    hw: porter.Hardware,
    circuit_gates: List[porter.Gate],
    num_logical: int,
    seed: int,
) -> porter.Layout:
    import numpy as np
    from circuit import Circuit, Gate as TelesabreGate
    from config import Config
    from qlimt import initial_layout

    if num_logical > arch.num_qubits:
        raise ValueError(
            f"{qasm_path.name} has {num_logical} qubits but {arch.name} has {arch.num_qubits}"
        )

    telesabre_gates = [TelesabreGate(list(g.qubits), g.name) for g in circuit_gates]
    circuit = Circuit(gates=telesabre_gates, num_qubits=num_logical, name=qasm_path.stem)
    config = Config()
    config.save_data = False
    np.random.seed(seed)
    telesabre_layout = initial_layout(config, circuit, arch)
    return convert_layout(telesabre_layout, hw, num_logical)


# ---------------------------------------------------------------------------
# Backward-refinement passes (opt-in)
# ---------------------------------------------------------------------------
#
# PORTER's default protocol is one forward pass from one deterministic layout.
# The shared-layout evaluation showed that a fixed layout is not the whole
# story: routing the SAME externally supplied layout, a forward--backward--
# forward schedule extracts more from it than a single forward pass does.
# This is SABRE's bidirectional layout-refinement trick, and it is the direct
# way to buy that back.
#
# The idea: routing the REVERSED circuit from pass 1's final layout ends on a
# layout that is good for the *start* of the forward circuit, because routing
# drifts interacting qubits together as it proceeds.  Pass 2's route is
# discarded -- only its final layout is kept -- and pass 3 re-routes forward
# from it.  We return the better of pass 1 and pass 3 by EPR, so refinement can
# never make the reported result worse than the single-pass one.
#
# Kept opt-in: PORTER's headline protocol remains a single deterministic run,
# and reporting both isolates what the extra passes are worth.


# Temporal-discount values swept by `run_layout_search`. `gamma` weights each
# CX by gamma**(its ASAP layer), so it sets how sharply the layout prefers
# EARLY interactions: 1.0 weights the whole circuit equally, 0.8 concentrates
# on the opening layers. No single value dominates -- measured over 24
# instances the per-circuit argmin is 0.8 nine times, 1.0 five, 0.95 four,
# 0.9 and 0.99 three each -- and 0.99 is uniquely best on QFT at 25q (74 vs 97)
# and 64q (262 vs 331), so this is a search, not a constant waiting to be
# retuned. gamma also affects ROUTABILITY, not only quality: 80q Random
# deadlocks at 0.9 and routes at the other four, which is why a best-of-N is
# the right shape and a single retuned value is not.
DEFAULT_LAYOUT_GAMMAS: Tuple[float, ...] = (0.8, 0.9, 0.95, 0.99, 1.0)


def run_layout_search(
    hw: porter.Hardware,
    cfg: porter.RouterConfig,
    circuit: List[porter.Gate],
    num_logical: int,
    *,
    gammas: Tuple[float, ...] = DEFAULT_LAYOUT_GAMMAS,
    passes: int = 1,
    refine_from: str = "both",
    horizons: Optional[Tuple[int, ...]] = None,
    selection: bool = True,
    pass_guard=None,
    pass_exceptions: Tuple[type, ...] = (RuntimeError, ValueError),
) -> Tuple[Optional[porter.RouterState], Dict[str, object]]:
    """Best-of-gamma initial-layout search, optionally with backward refinement.

    Phase 1 routes one forward pass from each gamma's layout at ``cfg``'s own
    horizon and keeps the best by EPR -- `len(gammas)` routing passes.
    Phase 2, when ``passes > 1``, runs `run_refinement_passes` from the
    winning gamma's layout and from the gamma=0.99 layout.

    Phase 2 selects a lookahead horizon (``selection=True`` since
    2026-08-31), which has a structural consequence worth knowing: the
    gamma=0.99 layout IS `build_initial_layout`'s default, so it is always
    among the seeds, and refining it under selection routes PORTER's own
    selected route as its pass 1.  PORTER+S therefore cannot report more EPR
    than PORTER -- and PORTER+SR, which takes the better of selection and
    this search, can no longer differ from it.

    Routes: ``len(gammas)`` for phase 1 plus, per seed, ``passes - 1``
    refinement passes and ``len(horizons) - 1`` extra selection probes.

    The two levers are independent and compose: gamma changes which layout the
    router starts from, refinement changes how much routing is spent improving
    it. On 64q QNN gamma=1.0 alone reaches 604 and refinement alone 537.

    Deterministic and seed-free, like the single-pass protocol it generalises:
    ``gammas=(0.99,), passes=1`` reproduces it byte-for-byte.

    Returns ``(best_state, info)``; ``best_state`` is None only if no gamma
    routes at all.
    """
    info: Dict[str, object] = {
        "gammas": list(gammas), "by_gamma": {}, "best_gamma": None,
        "passes": passes, "routes": 0, "refinement": None,
        "start_layout": None,
    }
    best_state = None
    best_layout = None

    for gm in gammas:
        try:
            layout = build_initial_layout(
                circuit, hw, num_logical,
                min_free_per_core=cfg.min_free_before_teleport, gamma=gm,
            )
        except ValueError:
            info["by_gamma"][str(gm)] = None
            continue
        router = porter.PorterRouter(hw, cfg)
        try:
            if pass_guard is None:
                state = router.compile(circuit, layout)
            else:
                with pass_guard():
                    state = router.compile(circuit, layout)
        except pass_exceptions:
            info["by_gamma"][str(gm)] = None
            info["routes"] += 1
            continue
        info["by_gamma"][str(gm)] = state.stats.epr
        info["routes"] += 1
        if best_state is None or state.stats.epr < best_state.stats.epr:
            best_state, best_layout = state, layout
            info["best_gamma"] = gm
            info["start_layout"] = layout

    if best_state is None or passes <= 1:
        return best_state, info

    # Which layout(s) to refine from.  Refining the winning gamma is NOT
    # reliably best: on 64q QNN gamma=1.0 wins phase 1 at 604 but refining it
    # reaches only 604, while refining the gamma=0.99 layout reaches 537.  The
    # two searches explore different neighbourhoods, so "both" runs the
    # schedule from each and is the shipped default.
    seeds = []
    if refine_from in ("best", "both") and info["best_gamma"] is not None:
        seeds.append((info["best_gamma"], best_layout))
    if refine_from in ("default", "both"):
        dg = 0.99 if 0.99 in gammas else gammas[len(gammas) // 2]
        if not seeds or seeds[0][0] != dg:
            try:
                seeds.append((dg, build_initial_layout(
                    circuit, hw, num_logical,
                    min_free_per_core=cfg.min_free_before_teleport, gamma=dg)))
            except ValueError:
                pass

    # Phase 1 ranks the gammas at cfg's own horizon rather than under
    # selection: making it select per gamma would cost len(gammas) x
    # len(horizons) routes for a ranking, and the horizon is a property of the
    # circuit rather than of the layout.  Selection is applied once per seed,
    # in phase 2, by run_refinement_passes.
    info["refinement"] = []
    for gm, seed_layout in seeds:
        refined, rinfo = run_refinement_passes(
            hw, cfg, circuit, seed_layout, passes=passes,
            horizons=horizons, selection=selection,
            pass_guard=pass_guard, pass_exceptions=pass_exceptions,
        )
        seed_start = rinfo.pop("start_layout", None)
        info["refinement"].append(dict(rinfo, seed_gamma=gm))
        # pass 1 is already counted; selection's extra probes are not
        info["routes"] += (max(0, rinfo["passes_run"] - 1)
                           + max(0, int(rinfo.get("horizon_routes", 1)) - 1))
        if refined is not None and refined.stats.epr < best_state.stats.epr:
            best_state = refined
            # The emitted stream belongs to that schedule's winning pass, so
            # the verifier must replay it against that pass's own layout.
            info["start_layout"] = seed_start
    return best_state, info


def reverse_circuit(circuit: List[porter.Gate]) -> List[porter.Gate]:
    """The same gates in reverse order.

    Gate ids are re-assigned by ``PorterRouter.compile`` via ``assign_gate_ids``,
    so they do not need fixing here.  Reversing the list reverses every
    per-qubit dependency edge, which is exactly the DAG pass 2 must route.
    """
    return list(reversed(circuit))


def run_refinement_passes(
    hw: porter.Hardware,
    cfg: porter.RouterConfig,
    circuit: List[porter.Gate],
    initial_layout: porter.Layout,
    *,
    passes: int = 3,
    horizons: Optional[Tuple[int, ...]] = None,
    selection: bool = True,
    pass_guard=None,
    pass_exceptions: Tuple[type, ...] = (RuntimeError, ValueError),
) -> Tuple[Optional[porter.RouterState], Dict[str, object]]:
    """Forward -> backward -> forward routing, returning the better forward pass.

    Refinement runs ON TOP of horizon selection (``selection=True`` since
    2026-08-31): the horizon is chosen once, on the first forward pass, and
    held fixed for the rest of the schedule, with ``info["horizon_routes"]``
    recording the extra routes so callers can report the complete protocol.
    That makes pass 1 exactly PORTER's own selected route, so -- since the
    best forward pass by EPR is returned -- PORTER+R can never report more
    EPR than PORTER.  At a fixed horizon it could and did: 80q AE 490 against
    PORTER's 299, 80q QPEexact 526 against 291.  Over the 24 main instances
    stacking moves the geometric mean from 171.4 to 163.0 (`bench_refine_
    on_selection.py`), 0 of 24 worse than PORTER and 9 strictly better.

    It costs wall-clock, not routes it can skip: the gmean per instance goes
    1.67 s -> 3.21 s, and a deep selected horizon can make a later pass
    oscillate until the caller's per-pass guard fires (900 s in
    `compare_routers`; 80q QPEexact runs four passes of five for that
    reason).  Pass ``selection=False`` to recover the fixed-horizon schedule
    -- which is what ``run_layout_search`` does, so PORTER+S stays the
    complementary lever (the layout at a fixed horizon) it is measured as.

    ``passes`` counts routing passes: 1 reproduces the default single-pass
    protocol exactly, 3 is one full refinement cycle, and odd values above 3
    repeat the cycle (each cycle is one backward pass plus one forward pass).
    Even values are rejected -- a backward pass alone yields no routable
    forward result.

    Returns ``(best_state, info)``.  ``best_state`` is ``None`` only when the
    very first forward pass fails; every later failure degrades to the best
    result already in hand, so refinement is never worse than not refining.

    ``info["start_layout"]`` is the layout the winning forward pass started
    from.  It is what an independent replay verifier must be given: the
    emitted stream belongs to that pass, not to pass 1, so replaying it
    against the original layout would (correctly) fail.
    """
    if passes < 1 or passes % 2 == 0:
        raise ValueError(
            f"passes must be a positive odd number (1, 3, 5, ...); got {passes}"
        )

    # PORTER's routing protocol picks a lookahead horizon per circuit; the
    # choice is made ONCE, on the first forward pass, and reused for the whole
    # schedule.  Re-selecting on every pass would multiply the pass count by
    # len(horizons) for no measured benefit -- the horizon is a property of the
    # circuit's interaction structure, which refinement does not change.
    if selection:
        first, sel_info = run_horizon_selection(
            hw, cfg, circuit, initial_layout, horizons=horizons,
            pass_guard=pass_guard, pass_exceptions=pass_exceptions)
        chosen = sel_info.get("chosen_horizon")
        if chosen is not None:
            cfg = dataclasses.replace(cfg, dag_extended_max_layers=int(chosen))
    else:
        first, sel_info = None, {"chosen_horizon": int(cfg.dag_extended_max_layers),
                                 "selection": False}

    router = porter.PorterRouter(hw, cfg)
    reversed_gates = reverse_circuit(circuit)
    info: Dict[str, object] = {"passes_run": 0, "passes_requested": passes,
                               "forward_eprs": [], "chosen_pass": None,
                               "failed_pass": None, "start_layout": None,
                               "chosen_horizon": sel_info.get("chosen_horizon"),
                               "horizon_eprs": sel_info.get("horizon_eprs", {}),
                               "horizon_routes": len(sel_info.get("horizon_eprs", {})),
                               "selection": bool(selection)}

    def _route(gates, layout):
        # A pass that deadlocks, is rejected by the layout precondition, or
        # exceeds `pass_guard`'s budget is a failed refinement ATTEMPT, not a
        # failed compile: the caller keeps the best forward result so far.
        # `pass_guard` is applied per pass rather than around the whole
        # schedule, so one slow backward pass cannot discard a good pass 1 --
        # which is exactly what a whole-schedule guard did on 360-qubit
        # QPEexact.  Anything outside `pass_exceptions` still propagates.
        try:
            if pass_guard is None:
                return router.compile(gates, layout)
            with pass_guard():
                return router.compile(gates, layout)
        except pass_exceptions:
            return None

    best = first if first is not None else _route(circuit, initial_layout)
    info["passes_run"] = 1
    if best is None:
        info["failed_pass"] = 1
        return None, info
    info["forward_eprs"].append(best.stats.epr)
    info["chosen_pass"] = 1
    info["start_layout"] = initial_layout

    layout = best.layout
    forward_pass_index = 1
    for cycle in range((passes - 1) // 2):
        back = _route(reversed_gates, layout)
        info["passes_run"] += 1
        if back is None:
            info["failed_pass"] = info["passes_run"]
            break
        fwd = _route(circuit, back.layout)
        info["passes_run"] += 1
        if fwd is None:
            info["failed_pass"] = info["passes_run"]
            break
        forward_pass_index += 2
        info["forward_eprs"].append(fwd.stats.epr)
        if fwd.stats.epr < best.stats.epr:
            best = fwd
            info["chosen_pass"] = forward_pass_index
            info["start_layout"] = back.layout
        # Keep refining from the newest forward layout even when it did not
        # win: the layout, not the route, is what the next cycle consumes.
        layout = fwd.layout

    return best, info


# PORTER's teleport-benefit lookahead peels `dag_extended_max_layers` DAG
# layers and, for each, credits the moving qubit's CXs exposed there.  The
# shipped 16 is well tuned for the 25q and 64q suites it was chosen on, but is
# far too short above ~64 logical qubits (100q/200q QFT and QPEexact all want
# >=128, saturating there) and too long for near-all-to-all interaction graphs
# (64q QNN wants 8, 80q QNN wants 4).  No single value serves both regimes and
# no single circuit statistic separates them -- interaction-graph density,
# `partners/(n-1)`, is the best predictor found (Spearman -0.765 on log2 of
# the best horizon) but cannot resolve the 0.42-0.53 band where most 64q
# circuits sit.  Selection does: over 24 instances, best-of-3 recovers 16.0%
# of the 17.2% oracle gain against the fixed default.
#
# Note `teleport_lookahead_cx_count` is NOT a second horizon: the lookahead
# collects only CXs of the one moving qubit, and a qubit has at most one
# zero-predecessor gate at a time, so the collected count can never exceed
# the layer budget and that knob is inert at any value >= this one.
PORTER_HORIZONS: Tuple[int, ...] = (8, 16, 128)

# How much wall clock a speculative (non-default) horizon may spend, as a
# multiple of what the default horizon took, and a floor for fast circuits.
# A deep peel makes each router iteration far more expensive AND can stop it
# converging: 64q QFT at L=128 takes ~24 ms per iteration against ~0.06 ms at
# L=16 and never terminates, so 20k iterations alone burn 471 s where the
# whole default route takes 1.2 s.  An iteration cap is therefore the wrong
# instrument; a relative time budget is the right one.  Every horizon that
# actually won in measurement finished in comparable or LESS time than the
# default (200q QPEexact 1.2 s at L=128 against 2.4 s at L=16), so a horizon
# that wants more than SPECULATIVE_TIME_FACTOR x the default's time is
# oscillating rather than converging and is safe to abandon.
SPECULATIVE_TIME_FACTOR: float = 4.0
SPECULATIVE_MIN_SECONDS: int = 5
# Deterministic replacement for the wall-clock share.  A speculative horizon may
# peel at most this multiple of the DAG layers the first route peeled -- a
# property of the route rather than of the machine, so the protocol's output no
# longer depends on load.  Calibrated on all 48 instances against that counter:
# every candidate that WINS its instance costs at most 6.47x the configured
# horizon's layers (64q Multiplier 6.05, 360q QPEexact 6.24, 80q Multiplier
# 6.47), while the cheapest candidate that wins nothing costs 7.95x, so 7 sits
# in a real gap -- it admits every winner and still rejects five deep routes
# that only cost time.  4x and 6x are both too tight and drop those three
# winners, 360q QPEexact by 91%.  The factor is fitted on this corpus; setting
# it too low costs EPR rather than correctness, since the configured horizon
# always runs unguarded and wins ties.  Set to 0 to fall back on the clock.
SPECULATIVE_WORK_FACTOR: float = 7.0

# Which horizons are worth trying depends on the circuit's interaction-graph
# density -- the mean fraction of the other logical qubits each qubit shares a
# CX with.  When that approaches 1 (near all-to-all: QNN, and Random at 80
# qubits) a long horizon reports the moving qubit as "needed" in every core at
# once, so the lookahead gain is noise; measured over 48 instances, NO circuit
# at density >= DENSE_INTERACTION_THRESHOLD ever selected the long horizon
# (25q ae/qft/qnn/random, 64q QNN, 80q QNN and 80q Random all chose 8 or 16),
# while the long horizon is exactly where those circuits burn their whole
# speculative time budget without converging.  Dropping it there costs no EPR
# and removes the single largest compile-time sink; the freed slot goes to a
# shorter horizon, which is what 80q QNN actually wants (1070 at L=4 against
# 1517 at the default).
PORTER_HORIZONS_DENSE: Tuple[int, ...] = (4, 8, 16)
DENSE_INTERACTION_THRESHOLD: float = 0.80


def circuit_interaction_density(circuit: List[porter.Gate], num_logical: int) -> float:
    """Mean fraction of the other logical qubits each qubit interacts with.

    1.0 is all-to-all; a linear chain of CXs tends to 2/(n-1).  Qubits that
    never take part in a CX are excluded -- they say nothing about how the
    interaction graph is shaped.
    """
    if num_logical < 2:
        return 0.0
    partners: Dict[int, set] = {}
    for gate in circuit:
        if not gate.is_cx():
            continue
        q0, q1 = gate.qubits
        partners.setdefault(q0, set()).add(q1)
        partners.setdefault(q1, set()).add(q0)
    if not partners:
        return 0.0
    return (sum(len(v) for v in partners.values())
            / len(partners) / (num_logical - 1))


def select_horizons(
    circuit: List[porter.Gate],
    num_logical: int,
    *,
    sparse: Tuple[int, ...] = PORTER_HORIZONS,
    dense: Tuple[int, ...] = PORTER_HORIZONS_DENSE,
    threshold: float = DENSE_INTERACTION_THRESHOLD,
) -> Tuple[Tuple[int, ...], float]:
    """Pick the horizon candidate set for a circuit.  Returns (horizons, density)."""
    density = circuit_interaction_density(circuit, num_logical)
    return (dense if density >= threshold else sparse), density


class HorizonTimeout(Exception):
    """A speculative horizon exceeded its wall-clock share."""


@contextlib.contextmanager
def _horizon_time_limit(seconds: Optional[int]):
    """SIGALRM wall-clock guard, or a no-op when it cannot be installed.

    Mirrors ``compare_routers._compiler_time_limit``: SIGALRM only interrupts
    at the next Python bytecode, which is fine for PORTER's pure-Python
    routing loop.  Signals can only be installed on the main thread of the
    main interpreter, so off-main-thread callers silently run unguarded
    rather than failing.
    """
    if (seconds is None or seconds <= 0
            or not hasattr(signal, "SIGALRM")
            or threading.current_thread() is not threading.main_thread()):
        yield
        return

    def _handler(signum, frame):
        raise HorizonTimeout(f"exceeded {seconds}s wall-clock share")

    previous = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(int(seconds))
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def run_horizon_selection(
    hw: porter.Hardware,
    cfg: porter.RouterConfig,
    circuit: List[porter.Gate],
    initial_layout: porter.Layout,
    *,
    horizons: Optional[Tuple[int, ...]] = None,
    time_factor: float = SPECULATIVE_TIME_FACTOR,
    min_seconds: int = SPECULATIVE_MIN_SECONDS,
    pass_guard=None,
    pass_exceptions: Tuple[type, ...] = (RuntimeError, ValueError),
) -> Tuple[Optional[porter.RouterState], Dict[str, object]]:
    """Route once per teleport-lookahead horizon and keep the best by EPR.

    ``horizons=None`` (the default) picks the candidate set from the circuit's
    interaction density via ``select_horizons``: near-all-to-all circuits get
    the short set, everything else the long one.  Pass an explicit tuple to
    override.

    ``cfg``'s own ``dag_extended_max_layers`` is routed FIRST, at the full
    iteration budget and with no time guard: it is the result the caller would
    have got anyway, and its wall time sets the budget for the rest.  Every
    other horizon is speculative and is abandoned once it exceeds
    ``time_factor`` times that baseline (floored at ``min_seconds``).

    Every attempt starts from the SAME ``initial_layout`` -- only the horizon
    differs -- so unlike ``run_refinement_passes`` the winning stream always
    replays against the layout that was passed in, and there is no
    ``start_layout`` to thread through a verifier.

    Selection is by EPR, ties broken in favour of ``cfg``'s own horizon and
    then by position in ``horizons``.  When ``cfg.dag_extended_max_layers`` is
    among ``horizons`` (as it is for the default tuple) the result is
    therefore never worse, and never slower by more than the speculative
    budget, than routing at ``cfg`` alone.

    A horizon that deadlocks, trips the iteration budget or runs out of its
    time share is a failed ATTEMPT, not a failed compile; ``best_state`` is
    ``None`` only when every horizon fails.
    """
    density: Optional[float] = None
    if horizons is None:
        horizons, density = select_horizons(circuit, initial_layout.num_logical)

    ordered: List[int] = []
    for raw in horizons:
        value = int(raw)
        if value < 1:
            raise ValueError(f"horizons must be positive; got {raw!r}")
        if value not in ordered:
            ordered.append(value)
    if not ordered:
        raise ValueError("horizons must not be empty")

    # The caller's own horizon goes first so it is never the one abandoned.
    default_horizon = int(cfg.dag_extended_max_layers)
    if default_horizon in ordered:
        ordered.remove(default_horizon)
        ordered.insert(0, default_horizon)

    info: Dict[str, object] = {
        "horizons_requested": list(ordered),
        "horizon_eprs": {},
        "horizon_seconds": {},
        "failed_horizons": {},
        "chosen_horizon": None,
        "default_horizon": default_horizon,
        "interaction_density": None if density is None else round(density, 4),
    }

    attempt_exceptions = tuple(pass_exceptions) + (HorizonTimeout,)

    def _route(router, gates, layout, budget):
        # The speculative budget must be installed INNERMOST.  Both guards use
        # SIGALRM, and signal.alarm() replaces any pending alarm rather than
        # queueing, so whichever is entered last is the one that fires.  With
        # the order reversed a caller-supplied pass_guard (900 s in
        # compare_routers) silently overwrote the speculative share and a
        # non-converging horizon ran for the full 900 s -- which is exactly
        # what it is meant to prevent.
        try:
            if pass_guard is None:
                with _horizon_time_limit(budget):
                    return router.compile(gates, layout)
            with pass_guard():
                with _horizon_time_limit(budget):
                    return router.compile(gates, layout)
        except attempt_exceptions as exc:
            return exc

    best: Optional[porter.RouterState] = None
    best_key: Optional[Tuple[int, int, int]] = None
    budget: Optional[int] = None
    work_budget: int = 0
    for position, horizon in enumerate(ordered):
        attempt_cfg = dataclasses.replace(
            cfg, dag_extended_max_layers=horizon,
            max_lookahead_layers=(0 if position == 0 or not SPECULATIVE_WORK_FACTOR
                                  else work_budget))
        started = time.perf_counter()
        # The first horizon establishes the time budget, so it runs unguarded.
        outcome = _route(porter.PorterRouter(hw, attempt_cfg), circuit,
                         initial_layout, None if position == 0 else budget)
        elapsed = time.perf_counter() - started
        info["horizon_seconds"][horizon] = round(elapsed, 3)
        if position == 0 and not isinstance(outcome, BaseException):
            work_budget = math.ceil(SPECULATIVE_WORK_FACTOR
                                    * outcome.stats.lookahead_layers_peeled)
            info["work_budget"] = work_budget
        if position == 0:
            budget = max(int(min_seconds), math.ceil(time_factor * elapsed))

        if isinstance(outcome, BaseException):
            info["failed_horizons"][horizon] = (
                f"{type(outcome).__name__}: {str(outcome)[:120]}")
            continue
        info["horizon_eprs"][horizon] = outcome.stats.epr
        key = (outcome.stats.epr, 0 if horizon == default_horizon else 1, position)
        if best_key is None or key < best_key:
            best, best_key = outcome, key
            info["chosen_horizon"] = horizon

    return best, info


def route(
    hw: porter.Hardware,
    cfg: porter.RouterConfig,
    circuit: List[porter.Gate],
    initial_layout: porter.Layout,
    *,
    horizons: Optional[Tuple[int, ...]] = None,
    selection: bool = True,
    pass_guard=None,
    pass_exceptions: Tuple[type, ...] = (RuntimeError, ValueError),
) -> Tuple[porter.RouterState, Dict[str, object]]:
    """PORTER's routing protocol: density-adaptive best-of-3 horizon selection.

    This is the single entry point every caller should use to route a layout,
    so that "what PORTER does" is defined in one place.  ``selection=False``
    falls back to one forward pass at ``cfg``'s own horizon, which is the
    pre-2026-08-29 protocol and is kept for ablations and for the paper's
    single-pass column.

    Raises the underlying router exception when no horizon completes, so the
    failure behaviour matches a plain ``PorterRouter.compile`` call.
    """
    if not selection:
        if pass_guard is None:
            state = porter.PorterRouter(hw, cfg).compile(circuit, initial_layout)
        else:
            with pass_guard():
                state = porter.PorterRouter(hw, cfg).compile(circuit, initial_layout)
        return state, {"chosen_horizon": int(cfg.dag_extended_max_layers),
                       "horizon_eprs": {int(cfg.dag_extended_max_layers): state.stats.epr},
                       "selection": False}

    state, info = run_horizon_selection(
        hw, cfg, circuit, initial_layout, horizons=horizons,
        pass_guard=pass_guard, pass_exceptions=pass_exceptions)
    if state is None:
        # Re-raise the default horizon's own failure so callers see the same
        # exception type they would have seen without selection.
        with _horizon_time_limit(None):
            if pass_guard is None:
                return porter.PorterRouter(hw, cfg).compile(circuit, initial_layout), info
            with pass_guard():
                return porter.PorterRouter(hw, cfg).compile(circuit, initial_layout), info
    info["selection"] = True
    return state, info


def run_selection_and_search(
    hw: porter.Hardware,
    cfg: porter.RouterConfig,
    circuit: List[porter.Gate],
    num_logical: int,
    *,
    horizons: Optional[Tuple[int, ...]] = None,
    passes: int = 5,
    gammas: Tuple[float, ...] = DEFAULT_LAYOUT_GAMMAS,
    pass_guard=None,
    pass_exceptions: Tuple[type, ...] = (RuntimeError, ValueError),
) -> Tuple[Optional[porter.RouterState], Dict[str, object]]:
    """PORTER+SR: the better of horizon selection and the gamma layout search.

    The two schedules search orthogonal things -- one varies the lookahead
    horizon on a fixed layout, the other varies the layout at a fixed horizon
    -- and measurement shows neither dominates: over the paper's 24 own-
    protocol instances selection wins four and the search wins fourteen, so
    taking the better of the two beats either alone.

    Route accounting is honest about the overlap: the search's first phase
    already routes the default gamma at ``cfg``'s own horizon, which is one of
    the horizon candidates, so ``info["routes"]`` counts that route once.

    ``info["start_layout"]`` is the winning schedule's own starting layout,
    which is what an independent replay verifier must be given.
    """
    sel_state, sel_info = run_horizon_selection(
        hw, cfg, circuit,
        build_initial_layout(circuit, hw, num_logical,
                             min_free_per_core=cfg.min_free_before_teleport),
        horizons=horizons, pass_guard=pass_guard,
        pass_exceptions=pass_exceptions)

    search_state, search_info = run_layout_search(
        hw, cfg, circuit, num_logical, gammas=gammas, passes=passes,
        pass_guard=pass_guard, pass_exceptions=pass_exceptions)

    sel_routes = len(sel_info.get("horizon_eprs", {})) + len(
        sel_info.get("failed_horizons", {}))
    info: Dict[str, object] = {
        "selection": {"epr": None if sel_state is None else sel_state.stats.epr,
                      "chosen_horizon": sel_info.get("chosen_horizon"),
                      "horizon_eprs": sel_info.get("horizon_eprs", {})},
        "search": {"epr": None if search_state is None else search_state.stats.epr,
                   "best_gamma": search_info.get("best_gamma"),
                   "routes": search_info.get("routes")},
        # The gamma=0.99 route at cfg's horizon is common to both schedules.
        "routes": sel_routes + int(search_info.get("routes") or 0) - 1,
        "chosen": None,
        "start_layout": None,
    }

    candidates = []
    if sel_state is not None:
        candidates.append(("selection", sel_state,
                           build_initial_layout(
                               circuit, hw, num_logical,
                               min_free_per_core=cfg.min_free_before_teleport)))
    if search_state is not None:
        candidates.append(("search", search_state, search_info["start_layout"]))
    if not candidates:
        return None, info

    # Ties go to selection: it is the cheaper schedule.
    name, state, start = min(candidates, key=lambda c: c[1].stats.epr)
    info["chosen"] = name
    info["start_layout"] = start
    return state, info


def serialize_compiled_op(index: int, op: porter.CompiledOp) -> Dict[str, object]:
    return {
        "index": index,
        "op_type": op.op_type,
        "gate_ids": [int(g.gid) for g in op.gates],
        "gate_names": [g.name for g in op.gates],
        "gate_qubits": [list(g.qubits) for g in op.gates],
        "logical_qubits": list(op.qubits),
        "physical_qubits": list(op.physical_qubits),
        "cores": list(op.cores),
        "path": list(op.path),
        "epr_cost": int(op.epr_cost),
        "metadata": dict(op.metadata),
    }


def write_outputs(
    out_dir: Path,
    qasm_path: Path,
    architecture_name: str,
    seed: int,
    summary: Dict[str, object],
    ops: List[Dict[str, object]],
) -> Dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"{qasm_path.stem}_{architecture_name.upper()}_seed{seed}"
    summary_path = out_dir / f"{prefix}_summary.json"
    ops_json_path = out_dir / f"{prefix}_compiled_ops.json"
    ops_csv_path = out_dir / f"{prefix}_compiled_ops.csv"

    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    ops_json_path.write_text(json.dumps(ops, ensure_ascii=False, indent=2), encoding="utf-8")

    fieldnames = [
        "index",
        "op_type",
        "gate_ids",
        "gate_names",
        "gate_qubits",
        "logical_qubits",
        "physical_qubits",
        "cores",
        "path",
        "epr_cost",
        "metadata",
    ]
    with ops_csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for op in ops:
            row = dict(op)
            for key in fieldnames:
                if key not in {"index", "op_type", "epr_cost"}:
                    row[key] = json.dumps(row[key], ensure_ascii=False)
            writer.writerow(row)

    return {
        "summary": summary_path,
        "compiled_ops_json": ops_json_path,
        "compiled_ops_csv": ops_csv_path,
    }


def compile_qasm(
    qasm_path: Path,
    architecture_name: str,
    seed: int,
    out_dir: Path,
    *,
    initial_layout_mode: str = "porter",
    max_iterations: Optional[int] = None,
    passes: int = 1,
    gamma_search: bool = False,
) -> Dict[str, object]:
    circuit_gates, num_logical = parse_qasm2(qasm_path)
    router_kwargs = {"random_seed": seed}
    if max_iterations is not None:
        router_kwargs["max_iterations"] = max_iterations
    router_config = porter.RouterConfig(**router_kwargs)

    if initial_layout_mode == "porter":
        hardware_name, hw = hardware_for_name(architecture_name)
        num_physical = len(hw.phys_to_core)
        if num_logical > num_physical:
            raise ValueError(
                f"{qasm_path.name} has {num_logical} qubits but {hardware_name} has {num_physical}"
            )
        initial_layout = build_initial_layout(
            circuit_gates,
            hw,
            num_logical,
            min_free_per_core=router_config.min_free_before_teleport,
        )
        initial_layout_label = "porter.temporal_locality"
    elif initial_layout_mode == "telesabre":
        arch = telesabre_architecture_for_name(architecture_name)
        hw = convert_architecture(arch)
        num_physical = arch.num_qubits
        hardware_name = arch.name
        initial_layout = build_telesabre_initial_layout(
            qasm_path,
            arch,
            hw,
            circuit_gates,
            num_logical,
            seed,
        )
        initial_layout_label = "qlimt.initial_layout"
    else:
        raise ValueError(f"Unsupported initial layout mode {initial_layout_mode!r}")

    start = time.perf_counter()
    if gamma_search:
        state, refine_info = run_layout_search(
            hw, router_config, circuit_gates, num_logical, passes=passes)
        if state is None:
            raise RuntimeError(f"no gamma routed ({refine_info})")
    elif passes == 1:
        router = porter.PorterRouter(hw, router_config)
        state = router.compile(circuit_gates, initial_layout)
        refine_info = None
    else:
        state, refine_info = run_refinement_passes(
            hw, router_config, circuit_gates, initial_layout, passes=passes
        )
        if state is None:
            raise RuntimeError(
                f"routing failed on the first forward pass ({refine_info})"
            )
    seconds = time.perf_counter() - start
    stats = state.stats

    initial_logical_per_core = [
        len(initial_layout.logicals_in_core(cid))
        for cid in sorted(hw.cores)
    ]
    initial_free_per_core = [
        initial_layout.free_count(hw, cid)
        for cid in sorted(hw.cores)
    ]
    ops = [serialize_compiled_op(index, op) for index, op in enumerate(state.emitted)]

    summary: Dict[str, object] = {
        "architecture": architecture_name.upper(),
        "hardware": hardware_name,
        "qasm": str(qasm_path),
        "seed": seed,
        "logical_qubits": num_logical,
        "physical_qubits": num_physical,
        "gate_count": len(circuit_gates),
        "initial_layout": initial_layout_label,
        "initial_logical_per_core": initial_logical_per_core,
        "initial_free_per_core": initial_free_per_core,
        "max_packet_size": router_config.max_packet_size,
        "min_free_before_teleport": router_config.min_free_before_teleport,
        "capacity_relief_assist_margin": router_config.capacity_relief_assist_margin,
        "status": "ok",
        "epr": int(stats.epr),
        "swaps": int(stats.local_swap_count),
        "depth": int(stats.depth),
        "intercore_depth": int(stats.intercore_depth),
        "teleports": int(stats.teleport_count),
        "teleports_normal": int(stats.teleport_normal_count),
        "teleports_blocked": int(stats.teleport_blocked_count),
        "teleports_capacity_relief": int(stats.teleport_capacity_relief_count),
        "telegates": int(stats.telegate_count),
        "telegate_packets": int(stats.telegate_packet_count),
        "local_cx": int(stats.local_cx_count),
        "single": int(stats.single_count),
        "emitted_ops": len(state.emitted),
        "remaining_gates": len(state.remaining),
        "passes": passes,
        "seconds": seconds,
    }
    if refine_info is not None:
        # `start_layout` is a Layout object -- useful to a caller (the replay
        # verifier needs it) but not JSON-serialisable, so keep it out of the
        # written summary.
        summary["refinement"] = {k: v for k, v in refine_info.items()
                                 if k != "start_layout"}

    paths = write_outputs(out_dir, qasm_path, architecture_name, seed, summary, ops)
    summary["outputs"] = {key: str(value) for key, value in paths.items()}
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile one QASM circuit with the PORTER router.")
    parser.add_argument("qasm", type=Path)
    parser.add_argument("--architecture", "-a", default="H", choices=("A", "H"))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out-dir", type=Path, default=Path("compile_outputs"))
    parser.add_argument(
        "--initial-layout",
        choices=("porter", "telesabre"),
        default="porter",
        help="porter uses the deterministic temporal locality-greedy mapper; telesabre reuses qlimt.initial_layout.",
    )
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument(
        "--gamma-search", action="store_true",
        help="best-of-gamma initial-layout search (see DEFAULT_LAYOUT_GAMMAS); "
             "combine with --passes for the strengthened protocol.",
    )
    parser.add_argument(
        "--passes", type=int, default=1,
        help="routing passes (odd). 1 = PORTER's default single forward pass; "
             "3 = one forward-backward-forward refinement cycle; 5 = two. "
             "The best forward pass by EPR is reported, so more passes can "
             "never report a worse result than fewer.",
    )
    args = parser.parse_args()

    summary = compile_qasm(
        args.qasm,
        args.architecture,
        args.seed,
        args.out_dir,
        initial_layout_mode=args.initial_layout,
        max_iterations=args.max_iterations,
        passes=args.passes,
        gamma_search=args.gamma_search,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
