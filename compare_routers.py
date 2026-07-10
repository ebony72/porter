"""Head-to-head comparison of PORTER against TeleSABRE
(compiled C binary) and dSABRE_BurstExt ("dSE", the project's default/
production router, from ../dsabre/code) on the same circuits and the same
physical topology.

Two comparison protocols are run per circuit:

  1. Own-protocol (each router's established best practice, best-of-3 seeds):
       * TeleSABRE : built-in hungarian initial layout, config seeds 0-2,
                     via the compiled `telesabre` binary.
       * dSE       : SabreLayout on the corners-removed architecture graph
                     (seeds 0-2) + SABRE-style fwd->bwd->fwd routing passes.
       * PORTER    : balanced-first-layer / seeded-locality initial layouts, seeds 0-2 each.

  2. Shared-layout (isolates routing quality from layout quality): dSE and
     PORTER are both routed from TeleSABRE's *own* initial layout -- extracted
     from the winning seed's report.json, iteration 0, i.e. the layout
     TeleSABRE itself settled on (after its internal forward/backward/
     forward layout refinement) before its accepted forward routing pass.

All routers see an *identical* physical topology (same physical qubit ids,
same inter-core ports) for a given architecture, verified at import time.

Usage:
  python compare_routers.py --suite 25          # architecture A, qasm_25/
  python compare_routers.py --suite 64          # architecture H, qasm_64/
  python compare_routers.py --suite 25 --suite 64
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional

PORTER_DIR = Path(__file__).resolve().parent
TELESABRE_DIR = PORTER_DIR.parent / "other" / "telesabre"
DSABRE_CODE_DIR = PORTER_DIR.parent / "dsabre" / "code"

sys.path.insert(0, str(PORTER_DIR))
sys.path.insert(0, str(DSABRE_CODE_DIR))

import porter as dr
import compile_porter as cdr

import networkx as nx
from qiskit import QuantumCircuit
from qiskit.converters import circuit_to_dag
from qiskit.transpiler.passes import RemoveBarriers
from qiskit.transpiler import PassManager

from architecture import DistributedArchitecture
from config import HardwareConfig
from dsabre_ext import dSABRE_BurstExt
from layout import sabre_locked_boundary_layout, run_sabre_passes

from pytket.qasm import circuit_from_qasm_str
from pytket.passes import DecomposeBoxes
from pytket_dqc import NISQNetwork
from pytket_dqc.allocators import HypergraphPartitioning
from pytket_dqc.utils import DQCPass
import qiskit.qasm2 as _qasm2

# placement_to_layout / _topo_assign / _interaction_graph implement a
# topology-aware intra-core placement given a pytket-dqc KaHyPar core
# assignment; reused verbatim from dSABRE's own 100q/200q/360q pytket
# benchmark rather than reimplemented.
import bench_pytket_large as _bpl

PYTKET_NUM_SEEDS = 3

# The stock ../other/telesabre/telesabre binary segfaults on architecture A:
# initial_layout_hungarian() in src/layout.c leaves virt_to_core[q] == -1 when
# no core has more than init_layout_hun_min_free_qubit slots free (which
# happens on 3x3, 9-slot cores at min_free_qubit=4), and that -1 is then used
# as a negative array index.  patched_telesabre/ holds a locally patched
# binary (adds a fallback-to-least-full-core branch); see its README.md and
# rebuild with patched_telesabre/build.sh.  ../other/telesabre is never
# modified in place.
_TELESABRE_PATCHED_BIN = PORTER_DIR / "patched_telesabre" / "telesabre"
if not _TELESABRE_PATCHED_BIN.exists():
    raise SystemExit(
        f"Patched TeleSABRE binary missing: {_TELESABRE_PATCHED_BIN}\n"
        "Build it with patched_telesabre/build.sh (the stock binary "
        "segfaults on architecture A; see patched_telesabre/README.md)."
    )
TELESABRE_BIN = _TELESABRE_PATCHED_BIN

SUITES = {
    "25": dict(
        label="25-qubit suite (architecture A, 2x2 cores of 3x3, 36 physical qubits)",
        arch_name="A",
        circuit_dir=TELESABRE_DIR / "circuits" / "qasm_25",
        device_json=TELESABRE_DIR / "devices" / "A_grid_2_2_3_3.json",
        files=[
            "ae_nativegates_ibm_qiskit_opt3_25.qasm",
            "ghz_nativegates_ibm_qiskit_opt3_25.qasm",
            "graphstate_nativegates_ibm_qiskit_opt3_25.qasm",
            "qft_nativegates_ibm_qiskit_opt3_25.qasm",
            "qnn_nativegates_ibm_qiskit_opt3_25.qasm",
            "random_nativegates_ibm_qiskit_opt3_25.qasm",
        ],
    ),
    "64": dict(
        label="64-qubit suite (architecture H, 2x3 cores of 4x4, 96 physical qubits)",
        arch_name="H",
        circuit_dir=TELESABRE_DIR / "circuits" / "qasm_64",
        device_json=TELESABRE_DIR / "devices" / "H_grid_2_3_4_4.json",
        files=[
            "ae_nativegates_ibm_qiskit_opt3_64.qasm",
            "ghz_nativegates_ibm_qiskit_opt3_64.qasm",
            "graphstate_nativegates_ibm_qiskit_opt3_64.qasm",
            "qft_nativegates_ibm_qiskit_opt3_64.qasm",
            "qnn_OLD_DEEP_nativegates_ibm_qiskit_opt3_64.qasm.bak",
            "random_nativegates_ibm_qiskit_opt3_64.qasm",
        ],
    ),
    # Same architecture H (96 physical qubits) as "64", just more logical
    # qubits per circuit. AE is excluded: its phase-estimation construction
    # hits a numerical-precision failure ("Input matrix is not unitary") at
    # this size in the installed mqt.bench/qiskit combination, independent
    # of our code path (reproduces via both get_benchmark_native_gates and
    # get_benchmark_indep). A reduced circuit-family set at larger qubit
    # counts is already precedented by dSABRE's own 100q/200q/360q suites.
    "80": dict(
        label="80-qubit suite (architecture H, 2x3 cores of 4x4, 96 physical qubits)",
        arch_name="H",
        circuit_dir=TELESABRE_DIR / "circuits" / "qasm_80",
        device_json=TELESABRE_DIR / "devices" / "H_grid_2_3_4_4.json",
        files=[
            "ghz_nativegates_ibm_qiskit_opt3_80.qasm",
            "graphstate_nativegates_ibm_qiskit_opt3_80.qasm",
            "qft_nativegates_ibm_qiskit_opt3_80.qasm",
            "qnn_nativegates_ibm_qiskit_opt3_80.qasm",
            "random_nativegates_ibm_qiskit_opt3_80.qasm",
        ],
    ),
}

NUM_SEEDS = 3


# ---------------------------------------------------------------------------
# Topology converter: PORTER Hardware -> dSABRE DistributedArchitecture
# ---------------------------------------------------------------------------

def sfc_hardware_to_dsabre_architecture(hw: dr.Hardware) -> DistributedArchitecture:
    """Build a dSABRE DistributedArchitecture with the *same* physical qubit
    ids, intra-core edges, and inter-core ports as an PORTER Hardware instance,
    so EPR/SWAP counts are comparable across routers."""
    intra_graphs: Dict[int, nx.Graph] = {}
    for cid, core in hw.cores.items():
        g = nx.Graph()
        g.add_nodes_from(core.physical_qubits)
        g.add_edges_from(core.coupling_edges, weight=1)
        intra_graphs[cid] = g

    inter_links: List[tuple] = []
    for a, b in hw.core_edges:
        pa, pb = hw.inter_core_ports(a, b)
        inter_links.append((pa, pb))

    return DistributedArchitecture(intra_graphs, inter_links)


def verify_topology_match(hw: dr.Hardware, arch: DistributedArchitecture) -> None:
    sfc_qubits = set(hw.phys_to_core)
    if sfc_qubits != set(arch.data_qubits):
        raise AssertionError("physical qubit id mismatch between PORTER hardware and dSABRE architecture")
    for cid, core in hw.cores.items():
        if set(core.physical_qubits) != set(arch.core_qubits(cid)):
            raise AssertionError(f"core {cid} qubit set mismatch")
    sfc_inter = {frozenset(hw.inter_core_ports(a, b)) for a, b in hw.core_edges}
    dsabre_inter = {frozenset(link) for link in arch.inter_core_links}
    if sfc_inter != dsabre_inter:
        raise AssertionError("inter-core port mismatch between PORTER hardware and dSABRE architecture")


# ---------------------------------------------------------------------------
# TeleSABRE runner
# ---------------------------------------------------------------------------

def _telesabre_config(seed: int, report_path: str, save_report: bool) -> str:
    cfg = {"config": {
        "name": "cmp", "seed": seed,
        "energy_type": "extended-set",
        "usage_penalties_reset_interval": 5,
        "optimize_initial": True,
        "initial_layout_type": "hungarian",
        "teleport_bonus": 100, "telegate_bonus": 100,
        "safety_valve_iters": 100,
        "extended_set_size": 20, "extended_set_factor": 0.05,
        "inter_core_edge_weight": 2, "full_core_penalty": 10,
        "max_solving_deadlock_iterations": 1000,
        "gate_usage_penalty": 0.0, "swap_usage_penalty": 0.002,
        "teledata_usage_penaly": 0.005, "telegate_usage_penalty": 0.005,
        "init_layout_hun_min_free_gate": 5, "init_layout_hun_free_qubit": 4,
        "enable_passing_core_emptying_teleport_possibility": False,
        "max_iterations": 200000,
        "save_report": save_report, "report_filename": report_path,
        "required_successes": 1, "max_attempts": 10,
    }}
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(cfg, f)
    f.close()
    return f.name


def run_telesabre(qasm_path: Path, device_json: Path) -> Optional[dict]:
    """Best-of-3-seed TeleSABRE run. Also captures, for the winning seed,
    its own initial layout (``initial_phys_to_virt``) as reported in
    iteration 0 of its report.json -- the layout it settled on internally
    after forward/backward/forward refinement, before its accepted forward
    routing pass -- for use as the shared-layout protocol below."""
    # main.c infers file type from the *last* dot in the filename, so a
    # circuit named e.g. "*.qasm.bak" is rejected outright ("does not have
    # a .json or .qasm extension") rather than routed. Always hand the
    # binary a clean *.qasm-suffixed temp copy to avoid this.
    clean_qasm_path = qasm_path
    tmp_qasm = None
    if qasm_path.suffix != ".qasm":
        tmp_qasm = Path(tempfile.mktemp(suffix=".qasm"))
        tmp_qasm.write_text(qasm_path.read_text())
        clean_qasm_path = tmp_qasm

    best = None
    try:
        for seed in range(NUM_SEEDS):
            rpt = tempfile.mktemp(suffix=".json")
            cfg_path = _telesabre_config(seed, rpt, save_report=True)
            t0 = time.perf_counter()
            try:
                proc = subprocess.run(
                    [str(TELESABRE_BIN), cfg_path, str(device_json), str(clean_qasm_path)],
                    capture_output=True, text=True, timeout=300,
                )
            except subprocess.TimeoutExpired:
                Path(cfg_path).unlink(missing_ok=True)
                Path(rpt).unlink(missing_ok=True)
                continue
            elapsed = time.perf_counter() - t0
            Path(cfg_path).unlink(missing_ok=True)

            out = proc.stdout + proc.stderr
            depth = td = tg = ls_ts = 0
            ok = False
            for line in out.splitlines():
                s = line.strip()
                if "Depth:" in s:
                    depth = int(s.split(":")[1])
                elif "Teledata:" in s:
                    td = int(s.split(":")[1])
                elif "Telegate:" in s:
                    tg = int(s.split(":")[1])
                elif "Swaps:" in s:
                    ls_ts = int(s.split(":")[1])
                elif "Success: true" in s:
                    ok = True

            initial_p2v = None
            if ok and Path(rpt).exists():
                try:
                    report = json.loads(Path(rpt).read_text())
                    initial_p2v = report["iterations"][0]["phys_to_virt"]
                except (json.JSONDecodeError, KeyError, IndexError):
                    initial_p2v = None
            Path(rpt).unlink(missing_ok=True)

            if ok:
                eprs = td + tg
                if best is None or eprs < best["epr"]:
                    best = dict(epr=eprs, teledata=td, telegate=tg, swaps=ls_ts,
                                depth=depth, seed=seed, seconds=round(elapsed, 3),
                                initial_phys_to_virt=initial_p2v)
    finally:
        if tmp_qasm is not None:
            tmp_qasm.unlink(missing_ok=True)
    return best


# ---------------------------------------------------------------------------
# dSABRE runner
# ---------------------------------------------------------------------------

def run_dsabre(router_ctor, arch: DistributedArchitecture, hw_cfg: HardwareConfig,
                dag, rev_dag, layouts: List[Dict]) -> Optional[dict]:
    router = router_ctor(arch, hw_cfg)
    best = None
    for layout in layouts:
        t0 = time.perf_counter()
        m = run_sabre_passes(router, dag, rev_dag, layout)
        elapsed = time.perf_counter() - t0
        if m and not m.get("aborted"):
            if best is None or m["eprs"] < best["epr"]:
                best = dict(epr=m["eprs"], swaps=m["ls"], seconds=round(elapsed, 3))
    return best


# ---------------------------------------------------------------------------
# Shared-layout protocol: TeleSABRE's own initial layout fed to dSE and PORTER
# ---------------------------------------------------------------------------

def telesabre_phys_to_virt_to_dsabre_layout(
    phys_to_virt: List[int], dag, num_logical: int
) -> Dict:
    """Convert TeleSABRE's phys_to_virt array into a dSABRE-style
    {qiskit Qubit: physical int} layout dict."""
    logical_to_phys: Dict[int, int] = {}
    for p, v in enumerate(phys_to_virt):
        if v < num_logical:
            logical_to_phys[v] = p
    if set(logical_to_phys) != set(range(num_logical)):
        raise ValueError("phys_to_virt does not cover exactly the circuit's logical qubits")
    return {dag.qubits[q]: p for q, p in logical_to_phys.items()}


def run_dsabre_shared_layout(
    arch: DistributedArchitecture, hw_cfg: HardwareConfig,
    dag, rev_dag, phys_to_virt: List[int], num_logical: int,
) -> Optional[dict]:
    layout = telesabre_phys_to_virt_to_dsabre_layout(phys_to_virt, dag, num_logical)
    router = dSABRE_BurstExt(arch, hw_cfg)
    t0 = time.perf_counter()
    m = run_sabre_passes(router, dag, rev_dag, layout)
    elapsed = time.perf_counter() - t0
    if not m or m.get("aborted"):
        return None
    return dict(epr=m["eprs"], swaps=m["ls"], seconds=round(elapsed, 3))


def run_sfc_shared_layout(
    circuit: List[dr.Gate], hw: dr.Hardware, num_logical: int, phys_to_virt: List[int],
) -> Optional[dict]:
    layout = dr.Layout.from_telesabre_phys_to_virt(hw, phys_to_virt, num_logical)
    cfg = dr.RouterConfig(random_seed=0)
    router = dr.PorterRouter(hw, cfg)
    t0 = time.perf_counter()
    try:
        state = router.compile(circuit, layout)
    except RuntimeError:
        return None
    elapsed = time.perf_counter() - t0
    return dict(
        epr=state.stats.epr, swaps=state.stats.local_swap_count,
        depth=state.stats.depth, intercore_depth=state.stats.intercore_depth,
        teleports=state.stats.teleport_count,
        telegates=state.stats.telegate_count,
        telegate_packets=state.stats.telegate_packet_count,
        seconds=round(elapsed, 3),
    )


# ---------------------------------------------------------------------------
# Shared-layout protocol: pytket-dqc's own initial mapping fed to dSE and PORTER
# ---------------------------------------------------------------------------
#
# TeleSABRE's CLI only supports its own built-in hungarian/round-robin/random
# initial-layout heuristics (src/config.h: enum initial_layout_type has no
# "custom" option), so it cannot be routed from an externally supplied
# layout without modifying its source; it is therefore excluded from this
# protocol, matching dSABRE's own bench_pytket_large.py precedent (which
# also only feeds the pytket layout to dSE, not to TeleSABRE).

def _pytket_nisq_network(arch: DistributedArchitecture) -> NISQNetwork:
    server_qubits, next_id = {}, 0
    for c in range(arch.num_cores):
        n = len(arch.core_qubits(c))
        server_qubits[c] = list(range(next_id, next_id + n))
        next_id += n
    return NISQNetwork([[u, v] for u, v in arch.core_graph.edges()], server_qubits)


def pytket_hypergraph_partition(
    qc: QuantumCircuit, arch: DistributedArchitecture, num_seeds: int = PYTKET_NUM_SEEDS
):
    """Best-of-``num_seeds`` pytket-dqc HypergraphPartitioning placement.
    Returns (e_bit_cost, {logical_qubit_index: core_id}) or (None, None)."""
    tk_circ = circuit_from_qasm_str(_qasm2.dumps(qc), maxwidth=qc.num_qubits + 10)
    DecomposeBoxes().apply(tk_circ)
    DQCPass().apply(tk_circ)
    network = _pytket_nisq_network(arch)
    alloc = HypergraphPartitioning()

    best_cost, best_placement = None, None
    for seed in range(num_seeds):
        try:
            dist = alloc.allocate(tk_circ, network, seed=seed)
            cost = dist.cost()
        except Exception:
            continue
        if best_cost is None or cost < best_cost:
            best_cost = cost
            best_placement = {
                k: v for k, v in dist.placement.placement.items()
                if isinstance(k, int) and k < qc.num_qubits
            }
    return best_cost, best_placement


def run_dsabre_pytket_layout(
    arch: DistributedArchitecture, hw_cfg: HardwareConfig,
    dag, rev_dag, placement: Dict[int, int],
) -> Optional[dict]:
    layout = _bpl.placement_to_layout(placement, dag, arch)
    router = dSABRE_BurstExt(arch, hw_cfg)
    t0 = time.perf_counter()
    m = run_sabre_passes(router, dag, rev_dag, layout)
    elapsed = time.perf_counter() - t0
    if not m or m.get("aborted"):
        return None
    return dict(epr=m["eprs"], swaps=m["ls"], seconds=round(elapsed, 3))


def run_sfc_pytket_layout(
    circuit: List[dr.Gate], hw: dr.Hardware, num_logical: int,
    dag, arch: DistributedArchitecture, placement: Dict[int, int],
) -> Optional[dict]:
    """Route PORTER from the same topology-aware physical placement used for
    dSE above (``bench_pytket_large.placement_to_layout``, which places
    within each pytket-assigned core using the dSABRE arch's own intra-core
    distance table -- identical physical qubit ids to PORTER's hardware)."""
    layout_dict = _bpl.placement_to_layout(placement, dag, arch)
    qubit_index = {q: i for i, q in enumerate(dag.qubits)}
    logical_to_physical = {qubit_index[q]: p for q, p in layout_dict.items()}
    if set(logical_to_physical) != set(range(num_logical)):
        raise ValueError("pytket layout does not cover exactly the circuit's logical qubits")
    physical_to_logical = {p: q for q, p in logical_to_physical.items()}
    logical_to_core = {q: hw.phys_to_core[p] for q, p in logical_to_physical.items()}
    dummy = num_logical
    for p in hw.phys_to_core:
        if p not in physical_to_logical:
            physical_to_logical[p] = dummy
            dummy += 1
    layout = dr.Layout(
        logical_to_physical=logical_to_physical, logical_to_core=logical_to_core,
        physical_to_logical=physical_to_logical, num_logical=num_logical,
    )
    cfg = dr.RouterConfig(random_seed=0)
    router = dr.PorterRouter(hw, cfg)
    t0 = time.perf_counter()
    try:
        state = router.compile(circuit, layout)
    except RuntimeError:
        return None
    elapsed = time.perf_counter() - t0
    return dict(
        epr=state.stats.epr, swaps=state.stats.local_swap_count,
        depth=state.stats.depth, intercore_depth=state.stats.intercore_depth,
        teleports=state.stats.teleport_count,
        telegates=state.stats.telegate_count,
        telegate_packets=state.stats.telegate_packet_count,
        seconds=round(elapsed, 3),
    )


# ---------------------------------------------------------------------------
# PORTER runner
# ---------------------------------------------------------------------------

def build_seeded_locality_layout(
    circuit: List[dr.Gate], hw: dr.Hardware, num_logical: int, seed: int, min_free_per_core: int
) -> dr.Layout:
    """Randomized interaction-graph-greedy initial layout: process logical
    qubits in a seeded random order, placing each one in the core holding its
    heaviest already-placed CX neighbour (if that core has headroom above
    ``min_free_per_core``), else in the least-loaded core.  Unlike try15's
    fully deterministic core assignment, this gives every seed a genuinely
    different core partition -- needed for try15-hostile circuits such as
    long qubit chains (GHZ), where try15 only ever co-locates the first CX
    pair and scatters the rest at random.
    """
    import random as _random

    weight: Dict[int, Dict[int, int]] = {q: {} for q in range(num_logical)}
    for g in circuit:
        if g.is_cx():
            q0, q1 = g.qubits
            weight[q0][q1] = weight[q0].get(q1, 0) + 1
            weight[q1][q0] = weight[q1].get(q0, 0) + 1

    core_order = sorted(hw.cores)
    capacity = {cid: len(hw.cores[cid].physical_qubits) for cid in core_order}
    remaining = {cid: max(0, capacity[cid] - min_free_per_core) for cid in core_order}
    if sum(remaining.values()) < num_logical:
        raise ValueError("insufficient reserved-capacity slots for seeded locality layout")

    rng = _random.Random(seed)
    order = list(range(num_logical))
    rng.shuffle(order)

    logical_to_core: Dict[int, int] = {}
    core_to_logicals: Dict[int, List[int]] = {cid: [] for cid in core_order}

    def place(q: int, cid: int) -> None:
        logical_to_core[q] = cid
        core_to_logicals[cid].append(q)
        remaining[cid] -= 1

    for q in order:
        best_core = None
        best_weight = -1
        for nbr, w in weight[q].items():
            c = logical_to_core.get(nbr)
            if c is not None and remaining[c] > 0 and w > best_weight:
                best_core = c
                best_weight = w
        if best_core is None:
            candidates = [c for c in core_order if remaining[c] > 0]
            best_core = max(candidates, key=lambda c: (remaining[c], -c))
        place(q, best_core)

    num_physical = len(hw.phys_to_core)
    phys_to_virt = [-1] * num_physical
    dummy = num_logical
    for cid in core_order:
        physical = list(hw.cores[cid].physical_qubits)
        rng.shuffle(physical)
        logicals = sorted(core_to_logicals[cid])
        for p, q in zip(physical, logicals):
            phys_to_virt[p] = q
        for p in physical[len(logicals):]:
            phys_to_virt[p] = dummy
            dummy += 1

    return dr.Layout.from_telesabre_phys_to_virt(hw, phys_to_virt, num_logical)


def run_sfc(circuit: List[dr.Gate], hw: dr.Hardware, num_logical: int) -> Optional[dict]:
    """PORTER with its own initial-layout candidates, best of ``2 * NUM_SEEDS``:
    the try15 balanced-first-layer heuristic (seeds 0..NUM_SEEDS-1) and a
    seeded locality-greedy partition (seeds 0..NUM_SEEDS-1), mirroring the
    "own layout heuristic, best-of-N-seed" protocol used for TeleSABRE and
    dSABRE below."""
    best = None
    builders = [
        ("try15", cdr.build_initial_layout),
        ("locality", build_seeded_locality_layout),
    ]
    for layout_name, builder in builders:
        for seed in range(NUM_SEEDS):
            cfg = dr.RouterConfig(random_seed=seed)
            try:
                layout = builder(
                    circuit, hw, num_logical, seed=seed,
                    min_free_per_core=cfg.min_free_before_teleport,
                )
            except ValueError:
                continue
            router = dr.PorterRouter(hw, cfg)
            t0 = time.perf_counter()
            try:
                state = router.compile(circuit, layout)
            except RuntimeError:
                continue
            elapsed = time.perf_counter() - t0
            epr = state.stats.epr
            if best is None or epr < best["epr"]:
                best = dict(
                    epr=epr, swaps=state.stats.local_swap_count,
                    depth=state.stats.depth, intercore_depth=state.stats.intercore_depth,
                    teleports=state.stats.teleport_count,
                    telegates=state.stats.telegate_count,
                    telegate_packets=state.stats.telegate_packet_count,
                    layout=layout_name, seed=seed, seconds=round(elapsed, 3),
                )
    return best


# Note: we do not reuse dSE's SabreLayout-corners-removed candidates for PORTER
# in the own-protocol comparison above. That layout only guarantees a global
# capacity margin (4 physical qubits removed chip-wide), not a *per-core*
# margin; on this suite it regularly leaves individual cores with zero free
# physical qubits (e.g. a 9-slot core holding all 9 assigned logical
# qubits). PORTER's teleport mechanism requires `min_free_before_teleport` free
# slots in a core before it can ever be used as a teleport destination, so a
# fully-packed core is not a valid starting state for it -- not a
# routing-quality gap, but an incompatible precondition. TeleSABRE's own
# initial layout (used in the shared-layout protocol below) does not have
# this problem, since TeleSABRE's own hungarian heuristic reserves headroom
# per core exactly for its own teleport threshold.


# ---------------------------------------------------------------------------
# Suite driver
# ---------------------------------------------------------------------------

def load_qasm(path: Path):
    qc = QuantumCircuit.from_qasm_file(str(path))
    qc = qc.remove_final_measurements(inplace=False)
    qc = PassManager([RemoveBarriers()]).run(qc)
    return qc, circuit_to_dag(qc)


def run_suite(suite_key: str) -> List[dict]:
    spec = SUITES[suite_key]
    _, hw = cdr.hardware_for_name(spec["arch_name"])
    arch = sfc_hardware_to_dsabre_architecture(hw)
    verify_topology_match(hw, arch)
    hw_cfg = HardwareConfig() if suite_key == "25" else HardwareConfig(
        deadlock_limit=100, max_backup_attempts=100, max_iterations=20000
    )
    pytket_seeds = PYTKET_NUM_SEEDS if suite_key != "80" else 1

    records = []
    for fname in spec["files"]:
        qasm_path = spec["circuit_dir"] / fname
        cname = fname.split("_nativegates")[0].replace(".qasm.bak", "").replace(".qasm", "")
        print(f"[{suite_key}q] {cname} ...", flush=True)

        circuit, num_logical = cdr.parse_qasm2(qasm_path)
        n_cx = sum(1 for g in circuit if g.is_cx())

        qc, dag = load_qasm(qasm_path)
        rev_dag = circuit_to_dag(qc.reverse_ops())

        ts = run_telesabre(qasm_path, spec["device_json"])
        ts_p2v = ts.pop("initial_phys_to_virt", None) if ts else None
        print(f"  TeleSABRE          : {ts}", flush=True)

        # -- own-protocol comparison --------------------------------------
        sabre_layouts = sabre_locked_boundary_layout(qc, dag, arch, seed=0)

        dse = run_dsabre(dSABRE_BurstExt, arch, hw_cfg, dag, rev_dag, sabre_layouts)
        print(f"  dSE  (SabreLayout) : {dse}", flush=True)

        sfc = run_sfc(circuit, hw, num_logical)
        print(f"  PORTER  (own layouts) : {sfc}", flush=True)

        # -- shared-layout comparison (TeleSABRE's own initial layout) ----
        dse_shared = sfc_shared = None
        if ts_p2v is not None:
            try:
                dse_shared = run_dsabre_shared_layout(arch, hw_cfg, dag, rev_dag, ts_p2v, num_logical)
            except ValueError as exc:
                print(f"  dSE  (TS layout)   : skipped ({exc})", flush=True)
            else:
                print(f"  dSE  (TS layout)   : {dse_shared}", flush=True)
            sfc_shared = run_sfc_shared_layout(circuit, hw, num_logical, ts_p2v)
            print(f"  PORTER  (TS layout)   : {sfc_shared}", flush=True)
        else:
            print("  (no TeleSABRE initial layout available; skipping shared-layout comparison)", flush=True)

        # -- shared-layout comparison (pytket-dqc's own initial mapping) --
        pytket_cost, pytket_placement = pytket_hypergraph_partition(qc, arch, num_seeds=pytket_seeds)
        print(f"  pytket-dqc (e-bits): {pytket_cost}", flush=True)
        dse_pytket = sfc_pytket = None
        if pytket_placement is not None:
            dse_pytket = run_dsabre_pytket_layout(arch, hw_cfg, dag, rev_dag, pytket_placement)
            print(f"  dSE  (pytket layout): {dse_pytket}", flush=True)
            try:
                sfc_pytket = run_sfc_pytket_layout(circuit, hw, num_logical, dag, arch, pytket_placement)
            except ValueError as exc:
                print(f"  PORTER  (pytket layout): skipped ({exc})", flush=True)
            else:
                print(f"  PORTER  (pytket layout): {sfc_pytket}", flush=True)
        else:
            print("  (pytket-dqc partitioning failed on all seeds; skipping)", flush=True)

        records.append(dict(
            suite=suite_key, circuit=cname, num_logical=num_logical, cx=n_cx,
            telesabre=ts, dSE=dse, sfc=sfc,
            dSE_shared=dse_shared, sfc_shared=sfc_shared,
            pytket_ebits=pytket_cost, dSE_pytket=dse_pytket, sfc_pytket=sfc_pytket,
        ))
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", action="append", choices=list(SUITES), default=None)
    parser.add_argument("--out", type=Path, default=Path("compare_results.json"))
    args = parser.parse_args()
    suites = args.suite or list(SUITES)

    all_records = []
    for s in suites:
        all_records.extend(run_suite(s))

    args.out.write_text(json.dumps(all_records, indent=2))
    print(f"\nWrote {len(all_records)} records to {args.out}", flush=True)


if __name__ == "__main__":
    main()
