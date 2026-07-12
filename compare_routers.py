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
     A second shared-layout leg uses pytket-dqc's own HypergraphPartitioning
     mapping, with the same four chip-wide corner (min-degree) physical
     qubits withheld from every core's capacity that dSE's own-protocol
     SabreLayout already reserves (see `_locked_boundary_corner_nodes`) --
     the pytket-dqc analogue of `sabre_locked_boundary_layout`, so neither
     shared-layout leg is handicapped by a partitioner that's still allowed
     to fill communication-reserved corner slots.

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
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional, Set

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

# Every compiler invocation (TeleSABRE's subprocess, one dSE run_sabre_passes
# call, one PORTER router.compile() call) is capped at this many seconds so
# a single slow/hung run can't stall the whole suite.
COMPILER_TIMEOUT_SECONDS = 900


class CompilerTimeout(Exception):
    """Raised when a single dSE/PORTER compiler call exceeds
    COMPILER_TIMEOUT_SECONDS. TeleSABRE is a real subprocess and is bounded
    directly via subprocess.run(..., timeout=...) instead -- see
    run_telesabre."""


@contextmanager
def _compiler_time_limit(seconds: int = COMPILER_TIMEOUT_SECONDS):
    """Wall-clock guard for one synchronous compiler call. Uses SIGALRM, so
    it only interrupts at the next bytecode the interpreter executes -- fine
    for dSE's and PORTER's pure-Python routing loops, but note it cannot
    preempt a call that never returns control to the interpreter (e.g. a
    tight native loop with no Python-level callback)."""
    def _handler(signum, frame):
        raise CompilerTimeout(f"exceeded {seconds}s wall-clock limit")
    previous = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)

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
    # qubits per circuit. AE at this size cannot be produced by stock
    # mqt.bench: its phase-estimation construction computes
    # Operator(Q).power(2**j), whose accumulated non-unitarity trips
    # qiskit's unitarity check ("Input matrix is not unitary") for j beyond
    # ~27 eval qubits. We instead reconstruct the identical indep circuit
    # supplying Q^(2^j)=RY(2**(j+1)*theta_p) analytically (RY period 4pi),
    # then run mqt.bench's own get_benchmark_native_gates pipeline. The
    # resulting CNOT sub-sequence is byte-identical to real mqt.bench at
    # N=10/20/25/28 (validated in bench/MQTBench/ae_extract_80.py); only the
    # non-essential single-qubit angles carry float error at high bit
    # indices. See paper for the note.
    "80": dict(
        label="80-qubit suite (architecture H, 2x3 cores of 4x4, 96 physical qubits)",
        arch_name="H",
        circuit_dir=TELESABRE_DIR / "circuits" / "qasm_80",
        device_json=TELESABRE_DIR / "devices" / "H_grid_2_3_4_4.json",
        files=[
            "ae_nativegates_ibm_qiskit_opt3_80.qasm",
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
                    capture_output=True, text=True, timeout=COMPILER_TIMEOUT_SECONDS,
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
        try:
            with _compiler_time_limit():
                m = run_sabre_passes(router, dag, rev_dag, layout)
        except CompilerTimeout:
            continue
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
    try:
        with _compiler_time_limit():
            m = run_sabre_passes(router, dag, rev_dag, layout)
    except CompilerTimeout:
        return None
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
        with _compiler_time_limit():
            state = router.compile(circuit, layout)
    except (RuntimeError, ValueError, CompilerTimeout):
        # ValueError: RouterConfig.repair_full_cores found the whole chip at
        # capacity (see run_sfc, above).
        return None
    elapsed = time.perf_counter() - t0
    return dict(
        epr=state.stats.epr, swaps=state.stats.local_swap_count,
        depth=state.stats.depth, intercore_depth=state.stats.intercore_depth,
        teleports=state.stats.teleport_count,
        teleports_normal=state.stats.teleport_normal_count,
        teleports_blocked=state.stats.teleport_blocked_count,
        teleports_capacity_relief=state.stats.teleport_capacity_relief_count,
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
#
# Locked boundary: pytket-dqc's HypergraphPartitioning only ever decides
# which *core* each logical qubit goes to -- capacity is the length of each
# server's qubit list in the NISQNetwork it's given, it never sees individual
# physical qubits. So the pytket-dqc analogue of dSABRE's
# `sabre_locked_boundary_layout` (SabreLayout run on the architecture graph
# with the four lowest-degree/corner physical qubits removed) is withholding
# those same four corner qubits from each core's *capacity* here, so the
# partitioner can never over-pack a core into its reserved communication
# slots. The corner qubits also have to be excluded from the later
# physical-placement-within-core step (`placement_to_layout_locked` below);
# `_pytket_nisq_network`'s capacity reduction alone doesn't do that, since
# `bench_pytket_large.placement_to_layout` would otherwise still place
# qubits directly onto them.

def _locked_boundary_corner_nodes(arch: DistributedArchitecture) -> Set[int]:
    """Chip-wide corner (min-degree) physical qubits in ``arch.Gr``, using
    the exact same selection dSABRE's `sabre_locked_boundary_layout` makes,
    so both own-protocol (dSE/SabreLayout) and shared-layout (pytket-dqc)
    legs reserve the identical four physical qubits."""
    degrees = dict(arch.Gr.degree())
    min_degree = min(degrees.values())
    return set(sorted(n for n, d in degrees.items() if d == min_degree)[:4])


def _pytket_nisq_network(arch: DistributedArchitecture, corner_nodes: Set[int]) -> NISQNetwork:
    server_qubits, next_id = {}, 0
    for c in range(arch.num_cores):
        reserved = sum(1 for p in arch.core_qubits(c) if p in corner_nodes)
        n = len(arch.core_qubits(c)) - reserved
        server_qubits[c] = list(range(next_id, next_id + n))
        next_id += n
    return NISQNetwork([[u, v] for u, v in arch.core_graph.edges()], server_qubits)


def pytket_hypergraph_partition(
    qc: QuantumCircuit, arch: DistributedArchitecture, corner_nodes: Set[int],
    num_seeds: int = PYTKET_NUM_SEEDS,
):
    """Best-of-``num_seeds`` pytket-dqc HypergraphPartitioning placement,
    with ``corner_nodes`` withheld from every core's capacity (locked
    boundary; see module comment above).
    Returns (e_bit_cost, {logical_qubit_index: core_id}) or (None, None)."""
    tk_circ = circuit_from_qasm_str(_qasm2.dumps(qc), maxwidth=qc.num_qubits + 10)
    DecomposeBoxes().apply(tk_circ)
    DQCPass().apply(tk_circ)
    network = _pytket_nisq_network(arch, corner_nodes)
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


def _topo_assign_locked(lq_list, ig, arch, core_id: int, corner_nodes: Set[int]) -> dict:
    """``bench_pytket_large._topo_assign``, reimplemented locally (rather
    than modifying dSABRE's file) so corner physical qubits can be withheld
    from the candidate pool. Falls back to including a corner qubit only if
    a core's non-corner capacity is insufficient for its assigned logical
    qubits -- shouldn't happen once `_pytket_nisq_network` already accounts
    for the reservation, but this keeps that a soft constraint rather than a
    crash if pytket-dqc's own capacity bookkeeping ever disagrees."""
    if not lq_list:
        return {}
    dist = arch.intra_dist[core_id]
    non_corner = [p for p in arch.core_qubits(core_id) if p not in corner_nodes]
    all_phys = non_corner if len(non_corner) >= len(lq_list) else arch.core_qubits(core_id)
    phys_by_centrality = sorted(all_phys,
        key=lambda p: sum(dist[p][q] for q in all_phys))
    lq_by_importance = sorted(lq_list,
        key=lambda q: ig.degree(q, weight="weight") if q in ig else 0,
        reverse=True)
    mapping = dict(zip(lq_by_importance, phys_by_centrality[:len(lq_by_importance)]))

    sub = set(lq_list)
    adj = {lq: [] for lq in lq_list}
    for u, v, d in ig.edges(data=True):
        if u in sub and v in sub:
            w = d.get("weight", 1)
            adj[u].append((v, w)); adj[v].append((u, w))

    def delta(a, b):
        pa, pb = mapping[a], mapping[b]; d = 0.0
        for nbr, w in adj[a]:
            if nbr != b: d += w * (dist[pb][mapping[nbr]] - dist[pa][mapping[nbr]])
        for nbr, w in adj[b]:
            if nbr != a: d += w * (dist[pa][mapping[nbr]] - dist[pb][mapping[nbr]])
        return d

    for _ in range(20):
        improved = False
        lqs = list(mapping)
        for i in range(len(lqs)):
            for j in range(i + 1, len(lqs)):
                if delta(lqs[i], lqs[j]) < 0:
                    mapping[lqs[i]], mapping[lqs[j]] = mapping[lqs[j]], mapping[lqs[i]]
                    improved = True
        if not improved:
            break
    return mapping


def placement_to_layout_locked(placement_dict, dag, arch: DistributedArchitecture, corner_nodes: Set[int]) -> dict:
    """``bench_pytket_large.placement_to_layout`` with corner qubits withheld
    (see `_topo_assign_locked`); leftover unassigned logical qubits also
    prefer non-corner free physical qubits before falling back to corners."""
    qubits = dag.qubits
    ig = _bpl._interaction_graph(dag)
    core_to_lq: Dict[int, list] = {}
    for qubit_idx, server_id in placement_dict.items():
        core_to_lq.setdefault(server_id, []).append(qubits[qubit_idx])
    layout = {}
    for core_id, lq_list in core_to_lq.items():
        layout.update(_topo_assign_locked(lq_list, ig, arch, core_id, corner_nodes))
    assigned = set(layout.values())
    free = [p for p in arch.data_qubits if p not in assigned and p not in corner_nodes]
    free += [p for p in arch.data_qubits if p not in assigned and p in corner_nodes]
    fi = iter(free)
    for lq in dag.qubits:
        if lq not in layout:
            layout[lq] = next(fi)
    return layout


def run_dsabre_pytket_layout(
    arch: DistributedArchitecture, hw_cfg: HardwareConfig,
    dag, rev_dag, placement: Dict[int, int], corner_nodes: Set[int],
) -> Optional[dict]:
    layout = placement_to_layout_locked(placement, dag, arch, corner_nodes)
    router = dSABRE_BurstExt(arch, hw_cfg)
    t0 = time.perf_counter()
    try:
        with _compiler_time_limit():
            m = run_sabre_passes(router, dag, rev_dag, layout)
    except CompilerTimeout:
        return None
    elapsed = time.perf_counter() - t0
    if not m or m.get("aborted"):
        return None
    return dict(epr=m["eprs"], swaps=m["ls"], seconds=round(elapsed, 3))


def run_sfc_pytket_layout(
    circuit: List[dr.Gate], hw: dr.Hardware, num_logical: int,
    dag, arch: DistributedArchitecture, placement: Dict[int, int], corner_nodes: Set[int],
) -> Optional[dict]:
    """Route PORTER from the same topology-aware physical placement used for
    dSE above (`placement_to_layout_locked`, which places within each
    pytket-assigned core using the dSABRE arch's own intra-core distance
    table -- identical physical qubit ids to PORTER's hardware -- withholding
    the same locked-boundary corner qubits dSE's own-protocol SabreLayout
    already reserves).

    Even with the boundary locked, pytket-dqc may still fill a core to 100%
    of its (reduced) capacity -- under PORTER's port-based action model a
    full core can never clear its occupied communication ports with local
    SWAPs, so it would otherwise be a hard deadlock. router.compile() now
    legalizes this automatically (RouterConfig.repair_full_cores, default
    on): it evicts one logical qubit from each full core into the core with
    the most free capacity before routing starts, raising ValueError only if
    the *whole chip* is at capacity (no core has room to receive an
    eviction) -- caught below and folded into the same None result as an
    ordinary routing deadlock."""
    layout_dict = placement_to_layout_locked(placement, dag, arch, corner_nodes)
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
        with _compiler_time_limit():
            state = router.compile(circuit, layout)
    except (RuntimeError, ValueError, CompilerTimeout):
        return None
    elapsed = time.perf_counter() - t0
    return dict(
        epr=state.stats.epr, swaps=state.stats.local_swap_count,
        depth=state.stats.depth, intercore_depth=state.stats.intercore_depth,
        teleports=state.stats.teleport_count,
        teleports_normal=state.stats.teleport_normal_count,
        teleports_blocked=state.stats.teleport_blocked_count,
        teleports_capacity_relief=state.stats.teleport_capacity_relief_count,
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
    ``min_free_per_core``), else in the least-loaded core.  Unlike the
    balanced-first-layer heuristic's fully deterministic core assignment,
    this gives every seed a genuinely different core partition -- needed for
    circuits hostile to that heuristic, such as long qubit chains (GHZ),
    where it only ever co-locates the first CX pair and scatters the rest at
    random.
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
    the balanced-first-layer heuristic (seeds 0..NUM_SEEDS-1) and a
    seeded locality-greedy partition (seeds 0..NUM_SEEDS-1), mirroring the
    "own layout heuristic, best-of-N-seed" protocol used for TeleSABRE and
    dSABRE below."""
    best = None
    builders = [
        ("balanced", cdr.build_initial_layout),
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
                with _compiler_time_limit():
                    state = router.compile(circuit, layout)
            except (RuntimeError, ValueError, CompilerTimeout):
                # ValueError can only come from RouterConfig.repair_full_cores
                # finding the whole chip at capacity (no core has room to
                # receive an eviction); PORTER's own layout builders always
                # reserve free slots per core, so this should not fire here.
                continue
            elapsed = time.perf_counter() - t0
            epr = state.stats.epr
            if best is None or epr < best["epr"]:
                best = dict(
                    epr=epr, swaps=state.stats.local_swap_count,
                    depth=state.stats.depth, intercore_depth=state.stats.intercore_depth,
                    teleports=state.stats.teleport_count,
                    teleports_normal=state.stats.teleport_normal_count,
                    teleports_blocked=state.stats.teleport_blocked_count,
                    teleports_capacity_relief=state.stats.teleport_capacity_relief_count,
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
    corner_nodes = _locked_boundary_corner_nodes(arch)
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

        # -- shared-layout comparison (pytket-dqc's own initial mapping,
        #    locked boundary -- see _locked_boundary_corner_nodes) --
        pytket_cost, pytket_placement = pytket_hypergraph_partition(
            qc, arch, corner_nodes, num_seeds=pytket_seeds
        )
        print(f"  pytket-dqc (e-bits): {pytket_cost}", flush=True)
        dse_pytket = sfc_pytket = None
        if pytket_placement is not None:
            dse_pytket = run_dsabre_pytket_layout(arch, hw_cfg, dag, rev_dag, pytket_placement, corner_nodes)
            print(f"  dSE  (pytket layout): {dse_pytket}", flush=True)
            try:
                sfc_pytket = run_sfc_pytket_layout(circuit, hw, num_logical, dag, arch, pytket_placement, corner_nodes)
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
