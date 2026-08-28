"""Head-to-head comparison of PORTER against TeleSABRE
(compiled C binary) and dSABRE_BurstExt ("dSE", the project's default/
production router, from ../dsabre/code) on the same circuits and the same
physical topology.

Two comparison protocols are run per circuit:

  1. Own-protocol (each router's established best practice, best-of-3 seeds):
       * TeleSABRE : built-in hungarian initial layout, config seeds 0-2,
                     via the compiled `telesabre` binary.
       * dSE       : SabreLayout on the architecture graph with 2 corners
                     removed per core (`sabre_two_corner_layout`, seeds 0-2)
                     + SABRE-style fwd->bwd->fwd routing passes.
       * PORTER    : single deterministic temporal locality-greedy layout.

  2. Shared-layout (isolates routing quality from layout quality): dSE and
     PORTER are both routed from TeleSABRE's *own* initial layout -- extracted
     from the winning seed's report.json, iteration 0, i.e. the layout
     TeleSABRE itself settled on (after its internal forward/backward/
     forward layout refinement) before its accepted forward routing pass.
     A second shared-layout leg uses pytket-dqc's own HypergraphPartitioning
     mapping, with the four chip-wide corner (min-degree) physical qubits of
     dSABRE's stock `sabre_locked_boundary_layout` withheld from every
     core's capacity (see `_locked_boundary_corner_nodes`) -- the pytket-dqc
     analogue of that corner removal, so the partitioner is never allowed to
     fill communication-reserved corner slots. (dSE's *own-protocol* leg now
     reserves 2 corners per core instead -- see `sabre_two_corner_layout`.)

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
# `bench_pytket_large` (whose placement_to_layout/_topo_assign we reuse verbatim)
# was moved into code/investigations/ by dSABRE's 2026-08 reorganisation.
DSABRE_INVEST_DIR = DSABRE_CODE_DIR / "investigations"

sys.path.insert(0, str(PORTER_DIR))
sys.path.insert(0, str(DSABRE_INVEST_DIR))
sys.path.insert(0, str(DSABRE_CODE_DIR))

import porter as dr
import compile_porter as cdr

import networkx as nx
from qiskit import QuantumCircuit
from qiskit.converters import circuit_to_dag
from qiskit.transpiler.passes import RemoveBarriers
from qiskit.transpiler import PassManager

from architecture import DistributedArchitecture, build_h_grid_architecture
from config import HardwareConfig
from dsabre_ext import dSABRE_BurstExt
from layout import run_sabre_passes, sabre_locked_boundary_layout

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
            # The remaining three of dSABRE's own nine-circuit 64q suite,
            # added 2026-08-23 so the two papers' 64q bases match exactly.
            "qpeexact_nativegates_ibm_qiskit_opt3_64.qasm",
            "qaoa_nativegates_ibm_qiskit_opt3_64.qasm",
            "multiplier_nativegates_ibm_qiskit_opt3_64.qasm",
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
            # Deep QNN (ZZFeatureMap full + RealAmplitudes), reconstructed to
            # match the deep 64q qnn_OLD_DEEP file. The stock
            # qnn_nativegates_..._80.qasm from mqt.bench 2.2.2 is a shallow
            # 79-CX chain whose interaction graph is identical to GHZ, so it is
            # not a usable distinct benchmark. See bench/MQTBench/qnn_extract_80.py.
            # (The _DEEP suffix follows the basis token so cname resolves to "qnn".)
            "qnn_nativegates_ibm_qiskit_opt3_80_DEEP.qasm",
            "random_nativegates_ibm_qiskit_opt3_80.qasm",
            # The same three families that complete dSABRE's nine-circuit 64q
            # basis, at 80q. Like the rest of the 80q suite these are v2.2.2
            # generations in the v1 nativegates_ibm_qiskit_opt3 format, not
            # v1.1.0 downloads -- the 80q suite has no v1.1.0 source.
            "qpeexact_nativegates_ibm_qiskit_opt3_80.qasm",
            "qaoa_nativegates_ibm_qiskit_opt3_80.qasm",
            "multiplier_nativegates_ibm_qiskit_opt3_80.qasm",
        ],
    ),
}

NUM_SEEDS = 3

# Opt-in: add the external pytket-dqc partition as an extra candidate in
# PORTER's own-protocol best-of (run_sfc / run_suite). Off by default so
# PORTER stays self-contained; enable with `--porter-include-pytket`.
PORTER_INCLUDE_PYTKET = False


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

    converted = DistributedArchitecture(intra_graphs, inter_links)
    # Prefer dSABRE's OWN builder when it reproduces this topology exactly.
    # Both SabreLayout and dSABRE's routing tie-breaks depend on the insertion
    # order of the coupling graph, not only on the topology, and the converted
    # object's order costs dSABRE real EPR: on the 64q suite it lands at a
    # geometric mean of 195.0 against the 173.3 it publishes, a 12.6% handicap
    # that is an artefact of graph construction rather than a protocol choice.
    # Routing on its native object reproduces its published numbers to +0.6%.
    # Returns the converted object when no native builder matches (architecture
    # A, whose 3x3 cores the H-grid builder cannot express and on which dSABRE
    # publishes nothing).
    native = _dsabre_native_architecture(converted)
    return native if native is not None else converted


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
        "init_layout_hun_min_free_gate": 5, "init_layout_hun_min_free_qubit": 4,
        # NB: the key is `init_layout_hun_min_free_qubit`. TeleSABRE's
        # config_set_parameter (src/config.c) returns silently on an
        # unknown key, so a misspelling here is not an error -- it
        # silently falls back to the binary's default of 3 and changes
        # every TeleSABRE number. This spelling matches dSABRE's
        # code/benchmark.py, and reproduces its published table exactly.
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
    t_protocol = time.perf_counter()
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
                                depth=depth, seed=seed,
                                seconds_best_attempt=round(elapsed, 3),
                                initial_phys_to_virt=initial_p2v)
    finally:
        if tmp_qasm is not None:
            tmp_qasm.unlink(missing_ok=True)
    if best is not None:
        # `seconds` is the COMPLETE protocol: every seed attempted, not just
        # the winning one -- the cost a user actually pays to obtain this
        # result. `seconds_best_attempt` keeps the single winning run.
        best["seconds"] = round(time.perf_counter() - t_protocol, 3)
        best["n_attempts"] = NUM_SEEDS
    return best


# ---------------------------------------------------------------------------
# dSE own-protocol initial mapping: SabreLayout with 2 corners per core removed
# ---------------------------------------------------------------------------
#
# dSABRE's stock `sabre_locked_boundary_layout` removes the four lowest-id
# minimum-degree vertices of the whole-chip graph, which under core-major
# qubit numbering are always the four corners of core 0: the other cores get
# no reserved communication slots at all and regularly come out fully packed.
# We instead reserve TWO corners in EVERY core -- the two least useful ones,
# i.e. the corner positions farthest (total shortest-path distance in the
# chip graph) from all other physical qubits, so the reservation costs the
# mapper the least. On architecture A this leaves 4x(9-2)=28 usable slots
# (>= 25 logical qubits); the stock per-chip removal generalised to per-core
# would leave only 4x(9-4)=20.

def _per_core_reserved_corner_nodes(arch: DistributedArchitecture, per_core: int = 2) -> Set[int]:
    """The ``per_core`` least-useful corner physical qubits of each core:
    among the core's minimum-degree (corner) vertices in ``arch.Gr``, the
    ones with the largest total shortest-path distance to all other physical
    qubits. Deterministic (distance ties broken by ascending node id)."""
    dist = dict(nx.all_pairs_shortest_path_length(arch.Gr))
    reserved: Set[int] = set()
    for c in range(arch.num_cores):
        nodes = arch.core_qubits(c)
        degs = {n: arch.Gr.degree(n) for n in nodes}
        min_deg = min(degs.values())
        cands = [n for n in nodes if degs[n] == min_deg]
        if len(cands) < per_core:
            cands = sorted(nodes, key=lambda n: (degs[n], n))[:per_core]
        remoteness = {n: sum(dist[n].values()) for n in cands}
        chosen = sorted(cands, key=lambda n: (-remoteness[n], n))[:per_core]
        reserved.update(chosen)
    return reserved


def sabre_two_corner_layout(qc, dag, arch: DistributedArchitecture, seed: int = 0):
    """dSABRE's `sabre_locked_boundary_layout` (layout.py) with the corner
    selection replaced by `_per_core_reserved_corner_nodes`: SabreLayout on
    the architecture graph with 2 corners removed from every core, seeds
    [seed, seed+1, seed+2]. Body otherwise mirrors the original."""
    from qiskit.transpiler import PassManager as _PM, CouplingMap
    from qiskit.transpiler.passes import SabreLayout
    import random as _random

    corner_nodes = _per_core_reserved_corner_nodes(arch)

    reduced_nodes = [n for n in arch.Gr.nodes() if n not in corner_nodes]
    node_to_idx = {n: i for i, n in enumerate(reduced_nodes)}
    reduced_edges = [
        (node_to_idx[u], node_to_idx[v])
        for u, v in arch.Gr.edges()
        if u not in corner_nodes and v not in corner_nodes
    ]
    directed = reduced_edges + [(v, u) for u, v in reduced_edges]
    cm = CouplingMap(couplinglist=directed, description="dsabre_2corners_per_core_removed")

    layouts = []
    for sd in [seed, seed + 1, seed + 2]:
        try:
            pm = _PM([SabreLayout(cm, max_iterations=3, seed=sd, swap_trials=5)])
            transpiled = pm.run(qc)
            if transpiled.layout is None:
                continue
            tl = transpiled.layout
            virt_layout = (tl.initial_virtual_layout(filter_ancillas=True)
                           if hasattr(tl, "initial_virtual_layout") else tl.initial_layout)
            result = {}
            for virt_qubit, reduced_idx in virt_layout.get_virtual_bits().items():
                try:
                    bit_index = qc.find_bit(virt_qubit).index
                except Exception:
                    continue
                result[dag.qubits[bit_index]] = reduced_nodes[reduced_idx]
            assigned = set(result.values())
            free = [p for p in arch.data_qubits if p not in assigned]
            _random.Random(sd).shuffle(free)
            fp = iter(free)
            for lq in dag.qubits:
                if lq not in result:
                    result[lq] = next(fp)
            layouts.append(result)
        except Exception:
            continue
    return layouts


def _dsabre_native_architecture(arch: DistributedArchitecture):
    """dSABRE's OWN `build_h_grid_architecture` for this topology, or None.

    Why this matters: SabreLayout's output depends on the *insertion order* of
    the coupling graph's nodes and edges, not only on the topology.  Building
    the architecture by converting a PORTER Hardware yields a different
    insertion order from dSABRE's own builder, and therefore different (worse,
    on our suites) SabreLayout candidates -- 64q AE lands at 191 EPR instead of
    the 165 dSABRE publishes, a 12.6% suite-wide handicap that is an artefact
    of graph construction rather than a protocol choice.  Generating dSABRE's
    layouts on its own architecture object removes it.

    Routing is essentially insensitive to the same ordering (191 vs 190 on
    identical layouts), so only layout generation needs the native object.
    Returns None when no native builder reproduces the topology -- architecture
    A, whose 3x3 cores dSABRE's H-grid builder cannot express and on which it
    publishes no results; there the converted architecture is used for both.
    """
    n_cores = arch.num_cores
    m2 = len(arch.core_qubits(0))
    m = int(round(m2 ** 0.5))
    if m * m != m2:
        return None
    for r in range(1, n_cores + 1):
        if n_cores % r:
            continue
        sdim = n_cores // r
        try:
            cand = build_h_grid_architecture(r=r, s=sdim, m=m)
        except Exception:
            continue
        if cand.num_cores != n_cores or set(cand.data_qubits) != set(arch.data_qubits):
            continue
        if {frozenset(l) for l in cand.inter_core_links} != {frozenset(l) for l in arch.inter_core_links}:
            continue
        ea = {frozenset(e) for c in range(n_cores) for e in arch.intra[c].edges()}
        eb = {frozenset(e) for c in range(n_cores) for e in cand.intra[c].edges()}
        if ea != eb:
            continue
        if any(set(cand.core_qubits(c)) != set(arch.core_qubits(c)) for c in range(n_cores)):
            continue
        return cand
    return None


def dsabre_layout_candidates(qc, dag, arch: DistributedArchitecture, seed: int = 0) -> List[Dict]:
    """dSABRE's own-protocol initial-layout candidates.

    Two families, both generated on dSABRE's own architecture object where one
    exists (see `_dsabre_native_architecture`):

    * `sabre_locked_boundary_layout` -- its current rule, reserving per core the
      `adaptive_corner_count` least-useful minimum-degree vertices (k=4 at
      100/200q, k=2 at 64q, k=1 at 25/80q on our architectures);
    * the fixed-two-per-core variant, which is the same rule with k pinned to 2.

    Neither dominates: the adaptive rule wins 80q Graphstate (20 vs 22 EPR) and
    100q QPEexact (200 vs 262), the fixed-two rule wins 80q AE (306 vs 340),
    80q QFT (322 vs 340), 100q QFT (234 vs 252) and 25q Random (404 vs 411).
    Rather than pick, dSABRE is handed both and takes its best -- six candidate
    layouts, hence eighteen routing passes per circuit against PORTER's one (or
    five with refinement).  This can only strengthen the baseline relative to
    its own published protocol, and it reproduces dSABRE's published 64q
    numbers.
    """
    gen_arch = _dsabre_native_architecture(arch) or arch
    cands = []
    for fn in (sabre_locked_boundary_layout, sabre_two_corner_layout):
        try:
            cands += list(fn(qc, dag, gen_arch, seed=seed))
        except Exception:
            continue  # a rule can fail to place on a tight chip; keep the rest
    seen, out = set(), []
    for lay in cands:
        key = tuple(sorted((qc.find_bit(q).index, ph) for q, ph in lay.items()))
        if key in seen:
            continue
        seen.add(key)
        out.append(lay)
    return out


# ---------------------------------------------------------------------------
# dSABRE runner
# ---------------------------------------------------------------------------

class dSE(dSABRE_BurstExt):
    """dSABRE's production router, with pre-routing layout repair accounted
    separately.

    In safe mode (dSABRE's shipped default) `route()` calls
    `_make_layout_safe` in its precondition block -- before the routing clock
    starts and before any gate is considered -- to bring an externally
    supplied layout up to `core_reserve` free slots per core.  Those relay
    teleports land in `metrics["eprs"]` even though they are a property of
    the starting layout, not of routing: they happen before routing begins,
    exactly as PORTER's `_repair_full_cores` does.  PORTER performs that
    repair as a free permutation of the initial layout, so charging dSABRE
    EPR pairs for the same adjustment would not be a like-for-like routing
    comparison.

    We therefore record the first `_make_layout_safe` call of each `route()`
    -- the entry one; any later call comes from `_safe_route_gate` mid-route
    and is genuine routing cost -- and expose it as
    `metrics["entry_repair_eprs"]` so `run_dsabre` can net it out.
    dSABRE's own files are not modified.
    """

    def route(self, dag, initial_layout):
        self._entry_repair_seen = False
        self._entry_repair_eprs = 0
        metrics, final = super().route(dag, initial_layout)
        metrics["entry_repair_eprs"] = self._entry_repair_eprs
        return metrics, final

    def _make_layout_safe(self, l2p, p2l, metrics, protect=()):
        before = metrics["eprs"]
        ok = super()._make_layout_safe(l2p, p2l, metrics, protect=protect)
        if not getattr(self, "_entry_repair_seen", True):
            self._entry_repair_eprs = metrics["eprs"] - before
            self._entry_repair_seen = True
        return ok


def run_dsabre(router_ctor, arch: DistributedArchitecture, hw_cfg: HardwareConfig,
                dag, rev_dag, layouts: List[Dict],
                layout_seconds: float = 0.0) -> Optional[dict]:
    """Best EPR over every candidate layout, with COMPLETE protocol timing.

    `seconds` follows dSABRE's own reporting convention -- "layout generation
    and all nine routes" -- generalised to however many candidates it is given:
    initial-layout generation plus three routing passes over *every* candidate,
    not just the winning one. `seconds_best_attempt` keeps the single winning
    candidate's three passes for reference.
    """
    t_protocol = time.perf_counter()
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
            repair = m.get("entry_repair_eprs", 0)
            epr = m["eprs"] - repair
            if best is None or epr < best["epr"]:
                best = dict(epr=epr, swaps=m["ls"],
                            seconds_best_attempt=round(elapsed, 3),
                            entry_repair_eprs=repair)
    if best is not None:
        best["seconds"] = round(layout_seconds + (time.perf_counter() - t_protocol), 3)
        best["layout_seconds"] = round(layout_seconds, 3)
        best["n_candidates"] = len(layouts)
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
    router = dSE(arch, hw_cfg)
    t0 = time.perf_counter()
    try:
        with _compiler_time_limit():
            m = run_sabre_passes(router, dag, rev_dag, layout)
    except CompilerTimeout:
        return None
    elapsed = time.perf_counter() - t0
    if not m or m.get("aborted"):
        return None
    repair = m.get("entry_repair_eprs", 0)
    return dict(epr=m["eprs"] - repair, swaps=m["ls"], seconds=round(elapsed, 3),
                entry_repair_eprs=repair)


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
    """Chip-wide corner (min-degree) physical qubits in ``arch.Gr``, the
    exact same selection dSABRE's stock `sabre_locked_boundary_layout`
    makes. Kept for the pytket-dqc legs (historical convention from
    dSABRE's own pytket benchmark); dSE's own-protocol leg uses the
    per-core reservation in `sabre_two_corner_layout` instead."""
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
    router = dSE(arch, hw_cfg)
    t0 = time.perf_counter()
    try:
        with _compiler_time_limit():
            m = run_sabre_passes(router, dag, rev_dag, layout)
    except CompilerTimeout:
        return None
    elapsed = time.perf_counter() - t0
    if not m or m.get("aborted"):
        return None
    repair = m.get("entry_repair_eprs", 0)
    return dict(epr=m["eprs"] - repair, swaps=m["ls"], seconds=round(elapsed, 3),
                entry_repair_eprs=repair)


def porter_layout_from_pytket_placement(
    hw: dr.Hardware, num_logical: int, dag, arch: DistributedArchitecture,
    placement: Dict[int, int], corner_nodes: Set[int],
) -> dr.Layout:
    """PORTER Layout for the same physical placement dSE is given.

    Shared by the single-pass and refined pytket legs so both start from a
    byte-identical layout. Raises ValueError if the placement does not cover
    exactly the circuit's logical qubits.
    """
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
    return dr.Layout(
        logical_to_physical=logical_to_physical, logical_to_core=logical_to_core,
        physical_to_logical=physical_to_logical, num_logical=num_logical,
    )


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
    layout = porter_layout_from_pytket_placement(
        hw, num_logical, dag, arch, placement, corner_nodes)
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


def run_sfc_sabre_layout(
    circuit: List[dr.Gate], hw: dr.Hardware, num_logical: int,
    dag, sabre_layouts: List[Dict],
) -> Optional[dict]:
    """Route PORTER from dSABRE's own initial layouts -- SabreLayout on the
    corners-removed architecture graph (`sabre_locked_boundary_layout`, the
    exact candidates dSE uses under its own protocol). Best EPR over the (up
    to three) candidate layouts, mirroring how dSE selects among them.

    Each candidate is a {qiskit Qubit: physical int} dict; we convert it to a
    PORTER Layout the same way as the pytket leg. SabreLayout keeps the four
    locked corner qubits free but places nothing else with PORTER's
    f_min-per-core reservation in mind, so a core may come in full;
    router.compile() legalizes that via RouterConfig.repair_full_cores, or
    folds a whole-chip-full ValueError into the same None as a deadlock."""
    qubit_index = {q: i for i, q in enumerate(dag.qubits)}
    t_protocol = time.perf_counter()
    best = None
    for layout_dict in sabre_layouts:
        logical_to_physical = {qubit_index[q]: p for q, p in layout_dict.items()}
        if set(logical_to_physical) != set(range(num_logical)):
            continue
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
            continue
        elapsed = time.perf_counter() - t0
        if best is None or state.stats.epr < best["epr"]:
            best = dict(
                epr=state.stats.epr, swaps=state.stats.local_swap_count,
                depth=state.stats.depth, intercore_depth=state.stats.intercore_depth,
                teleports=state.stats.teleport_count,
                teleports_normal=state.stats.teleport_normal_count,
                teleports_blocked=state.stats.teleport_blocked_count,
                teleports_capacity_relief=state.stats.teleport_capacity_relief_count,
                telegates=state.stats.telegate_count,
                telegate_packets=state.stats.telegate_packet_count,
                seconds_best_attempt=round(elapsed, 3),
            )
    if best is not None:
        # COMPLETE: PORTER routes every candidate dSABRE is given and keeps the
        # best, so its cost here is the sum over candidates, not one route.
        best["seconds"] = round(time.perf_counter() - t_protocol, 3)
        best["n_candidates"] = len(sabre_layouts)
    return best


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


def run_sfc(circuit: List[dr.Gate], hw: dr.Hardware, num_logical: int,
            *, pytket_candidate: Optional[tuple] = None) -> Optional[dict]:
    """PORTER with its own initial layout: ONE deterministic temporal
    locality-greedy layout (``cdr.build_initial_layout``, seed-free) routed
    in a single pass at router seed 0.  No layout search -- this replaced
    the former balanced-first-layer / seeded-locality best-of-6 protocol
    (2026-07-12), which it beats on 14 of the 16 comparable paper
    instances (gmean EPR 55.4 vs 92.0) and on 14/15 held-out circuits.
    The legacy builders remain below / in compile_porter only for the
    paper's initial-mapping study (``paper/porter_under_layouts.py``).

    ``pytket_candidate`` is an opt-in hook (off by default, keeping PORTER
    self-contained): pass ``(dag, arch, placement, corner_nodes)`` to route
    the external pytket-dqc partition as one extra candidate and fold it into
    the best-of. PORTER routes several times faster than pytket-dqc partitions
    (own-layout build is ~microseconds vs seconds-to-minutes for the
    partition), so the marginal cost is the partition itself, not the routing;
    it lowers EPR on structured circuits but not on the dense/Random ones that
    PORTER's own layout already wins."""
    best = None
    cfg = dr.RouterConfig(random_seed=0)
    t_protocol = time.perf_counter()
    try:
        layout = cdr.build_initial_layout(
            circuit, hw, num_logical,
            min_free_per_core=cfg.min_free_before_teleport,
        )
    except ValueError:
        layout = None
    layout_seconds = time.perf_counter() - t_protocol
    if layout is not None:
        router = dr.PorterRouter(hw, cfg)
        t0 = time.perf_counter()
        try:
            with _compiler_time_limit():
                state = router.compile(circuit, layout)
        except (RuntimeError, ValueError, CompilerTimeout):
            # ValueError can only come from RouterConfig.repair_full_cores
            # finding the whole chip at capacity (no core has room to
            # receive an eviction); PORTER's own layout builder always
            # reserves free slots per core, so this should not fire here.
            state = None
        if state is not None:
            elapsed = time.perf_counter() - t0
            best = dict(
                epr=state.stats.epr, swaps=state.stats.local_swap_count,
                depth=state.stats.depth, intercore_depth=state.stats.intercore_depth,
                teleports=state.stats.teleport_count,
                teleports_normal=state.stats.teleport_normal_count,
                teleports_blocked=state.stats.teleport_blocked_count,
                teleports_capacity_relief=state.stats.teleport_capacity_relief_count,
                telegates=state.stats.telegate_count,
                telegate_packets=state.stats.telegate_packet_count,
                layout="temporal_locality", seed=0,
                # COMPLETE protocol: layout construction plus the single
                # routing pass. PORTER builds one layout and routes once, so
                # this is its entire compile cost.
                seconds=round(layout_seconds + elapsed, 3),
                seconds_best_attempt=round(elapsed, 3),
                layout_seconds=round(layout_seconds, 3), n_candidates=1,
            )

    if pytket_candidate is not None:
        dag, arch, placement, corner_nodes = pytket_candidate
        if placement is not None:
            try:
                res = run_sfc_pytket_layout(circuit, hw, num_logical, dag, arch, placement, corner_nodes)
            except ValueError:
                res = None
            if res is not None and (best is None or res["epr"] < best["epr"]):
                best = dict(res, layout="pytket", seed=0)
    return best


# ---------------------------------------------------------------------------
# Cross-layout legs: each router on the other's initial layout
# ---------------------------------------------------------------------------
#
# The shared-layout protocol feeds both routers a THIRD party's layout
# (TeleSABRE's, pytket-dqc's). These two legs close the 2x2 instead: PORTER on
# dSABRE's SabreLayout candidates (run_sfc_sabre_layout, below) and dSABRE on
# PORTER's temporal locality-greedy layout. Together with the two own-protocol
# columns they separate "whose layout" from "whose router" on the routers'
# own layouts rather than on a neutral one.


def porter_layout_to_dsabre(layout: dr.Layout, dag, num_logical: int) -> Dict:
    """PORTER Layout -> dSABRE-style {qiskit Qubit: physical int}.

    PORTER's Layout carries dummy logical ids for the empty physical slots;
    only the real logical qubits (< num_logical) are placed.
    """
    logical_to_phys = {q: layout.phys_of(q) for q in range(num_logical)}
    if set(logical_to_phys) != set(range(num_logical)):
        raise ValueError("PORTER layout does not cover exactly the circuit's logical qubits")
    return {dag.qubits[q]: p for q, p in logical_to_phys.items()}


def run_dsabre_porter_layout(
    arch: DistributedArchitecture, hw_cfg: HardwareConfig, dag, rev_dag,
    circuit: List[dr.Gate], hw: dr.Hardware, num_logical: int,
) -> Optional[dict]:
    """dSABRE routed from PORTER's own deterministic temporal locality-greedy
    layout -- the mirror of run_sfc_sabre_layout."""
    cfg = dr.RouterConfig(random_seed=0)
    try:
        porter_layout = cdr.build_initial_layout(
            circuit, hw, num_logical,
            min_free_per_core=cfg.min_free_before_teleport,
        )
        layout = porter_layout_to_dsabre(porter_layout, dag, num_logical)
    except ValueError:
        return None
    router = dSE(arch, hw_cfg)
    t0 = time.perf_counter()
    try:
        with _compiler_time_limit():
            m = run_sabre_passes(router, dag, rev_dag, layout)
    except CompilerTimeout:
        return None
    elapsed = time.perf_counter() - t0
    if not m or m.get("aborted"):
        return None
    repair = m.get("entry_repair_eprs", 0)
    return dict(epr=m["eprs"] - repair, swaps=m["ls"], seconds=round(elapsed, 3),
                entry_repair_eprs=repair)


def run_sfc_sabre_layout_refined(
    circuit: List[dr.Gate], hw: dr.Hardware, num_logical: int, dag,
    sabre_layouts: List[Dict],
) -> Optional[dict]:
    """PORTER+R on dSABRE's SabreLayout candidates; best over the candidates,
    mirroring how dSE selects among them."""
    qubit_index = {q: i for i, q in enumerate(dag.qubits)}
    t_protocol = time.perf_counter()
    best = None
    for layout_dict in sabre_layouts:
        logical_to_physical = {qubit_index[q]: p for q, p in layout_dict.items()}
        if set(logical_to_physical) != set(range(num_logical)):
            continue
        physical_to_logical = {p: q for q, p in logical_to_physical.items()}
        logical_to_core = {q: hw.phys_to_core[p] for q, p in logical_to_physical.items()}
        dummy = num_logical
        for ph in hw.phys_to_core:
            if ph not in physical_to_logical:
                physical_to_logical[ph] = dummy
                dummy += 1
        layout = dr.Layout(
            logical_to_physical=logical_to_physical, logical_to_core=logical_to_core,
            physical_to_logical=physical_to_logical, num_logical=num_logical,
        )
        rec = _run_porter_refined(circuit, hw, num_logical, layout)
        if rec is not None and (best is None or rec["epr"] < best["epr"]):
            best = rec
    if best is not None:
        best = dict(best, seconds=round(time.perf_counter() - t_protocol, 3),
                    seconds_best_attempt=best["seconds"],
                    n_candidates=len(sabre_layouts))
    return best


# ---------------------------------------------------------------------------
# PORTER with backward refinement (opt-in extra leg)
# ---------------------------------------------------------------------------
#
# PORTER's headline protocol stays a single forward pass from a single
# deterministic layout.  These legs add SABRE-style forward--backward--forward
# refinement (cdr.run_refinement_passes) so the two can be reported side by
# side and the extra passes' contribution isolated.  Still seed-free and
# deterministic; the only cost is routing passes.

PORTER_REFINE_PASSES = 5


def _porter_state_record(state, elapsed, **extra):
    return dict(
        epr=state.stats.epr, swaps=state.stats.local_swap_count,
        depth=state.stats.depth, intercore_depth=state.stats.intercore_depth,
        teleports=state.stats.teleport_count,
        teleports_normal=state.stats.teleport_normal_count,
        teleports_blocked=state.stats.teleport_blocked_count,
        teleports_capacity_relief=state.stats.teleport_capacity_relief_count,
        telegates=state.stats.telegate_count,
        telegate_packets=state.stats.telegate_packet_count,
        seconds=round(elapsed, 3), **extra,
    )


def _run_porter_refined(circuit, hw, num_logical, layout, passes=None):
    """Route `layout` with refinement; None if even the first pass fails."""
    passes = PORTER_REFINE_PASSES if passes is None else passes
    cfg = dr.RouterConfig(random_seed=0)
    t0 = time.perf_counter()
    try:
        # The wall-clock guard is applied PER PASS (pass_guard), so a slow
        # later pass degrades to the best forward pass already in hand instead
        # of discarding the whole schedule.
        state, info = cdr.run_refinement_passes(
            hw, cfg, circuit, layout, passes=passes,
            pass_guard=_compiler_time_limit,
            pass_exceptions=(RuntimeError, ValueError, CompilerTimeout),
        )
    except (RuntimeError, ValueError, CompilerTimeout):
        return None
    if state is None:
        return None
    return _porter_state_record(
        state, time.perf_counter() - t0,
        passes=passes, passes_run=info["passes_run"],
        chosen_pass=info["chosen_pass"], forward_eprs=info["forward_eprs"],
    )


def run_sfc_search(circuit: List[dr.Gate], hw: dr.Hardware,
                   num_logical: int) -> Optional[dict]:
    """PORTER's strengthened own protocol: best-of-gamma layout search plus
    backward refinement (`cdr.run_layout_search`).

    Two independent levers -- which layout the router starts from (gamma) and
    how much routing is spent improving it (refinement) -- searched together.
    Costs 9-13 routing passes against dSABRE's 18, and is still deterministic
    and seed-free.
    """
    cfg = dr.RouterConfig(random_seed=0)
    t0 = time.perf_counter()
    try:
        state, info = cdr.run_layout_search(
            hw, cfg, circuit, num_logical, passes=PORTER_REFINE_PASSES,
            pass_guard=_compiler_time_limit,
            pass_exceptions=(RuntimeError, ValueError, CompilerTimeout),
        )
    except (RuntimeError, ValueError, CompilerTimeout):
        return None
    if state is None:
        return None
    return _porter_state_record(
        state, time.perf_counter() - t0,
        layout="temporal_locality_search", seed=0,
        best_gamma=info["best_gamma"], by_gamma=info["by_gamma"],
        routes=info["routes"], n_candidates=len(info["gammas"]),
    )


def run_sfc_refined(circuit: List[dr.Gate], hw: dr.Hardware,
                    num_logical: int) -> Optional[dict]:
    """PORTER's own layout, routed with backward refinement."""
    cfg = dr.RouterConfig(random_seed=0)
    t0 = time.perf_counter()
    try:
        layout = cdr.build_initial_layout(
            circuit, hw, num_logical,
            min_free_per_core=cfg.min_free_before_teleport,
        )
    except ValueError:
        return None
    layout_seconds = time.perf_counter() - t0
    rec = _run_porter_refined(circuit, hw, num_logical, layout)
    if not rec:
        return None
    # COMPLETE protocol: layout construction plus every pass actually run.
    return dict(rec, layout="temporal_locality", seed=0,
                seconds=round(rec["seconds"] + layout_seconds, 3),
                layout_seconds=round(layout_seconds, 3))


def run_sfc_shared_layout_refined(circuit, hw, num_logical,
                                  phys_to_virt) -> Optional[dict]:
    layout = dr.Layout.from_telesabre_phys_to_virt(hw, phys_to_virt, num_logical)
    return _run_porter_refined(circuit, hw, num_logical, layout)


def run_sfc_pytket_layout_refined(circuit, hw, num_logical, dag, arch,
                                  placement, corner_nodes) -> Optional[dict]:
    try:
        layout = porter_layout_from_pytket_placement(
            hw, num_logical, dag, arch, placement, corner_nodes)
    except ValueError:
        return None
    return _run_porter_refined(circuit, hw, num_logical, layout)


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
    # dSABRE's own protocol: `None` on all three budgets means "derive from the
    # architecture" -- `deadlock_limit_for(arch) = 4*max(1,diam(core graph))*(
    # diam(core)+1)`, the only per-suite constant its current router has -- and
    # is what every one of its own benchmark drivers passes.  The hand-tuned
    # 100/100/20000 this harness used previously came from the pre-safe-mode
    # router's scaling guidance: under safe mode `max_backup_attempts` is
    # overridden to the unrouted-gate count regardless (so 100 was inert), and a
    # binding `max_iterations` cuts the heuristic search short and hands the
    # remainder to `_safe_drain`, which completes the route at a worse EPR
    # count.  Deriving is both the baseline's own convention and the fairer one.
    hw_cfg = HardwareConfig(
        deadlock_limit=None, max_backup_attempts=None, max_iterations=None
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
        _t_lay = time.perf_counter()
        sabre_layouts = dsabre_layout_candidates(qc, dag, arch, seed=0)
        sabre_layout_seconds = time.perf_counter() - _t_lay

        dse = run_dsabre(dSE, arch, hw_cfg, dag, rev_dag, sabre_layouts,
                         layout_seconds=sabre_layout_seconds)
        print(f"  dSE  (SabreLayout) : {dse}", flush=True)

        # pytket-dqc partition computed once here and reused twice: as PORTER's
        # opt-in own-protocol candidate (when --porter-include-pytket) and for
        # the shared-layout leg below. The partition is the expensive step
        # (seconds to minutes), so never run it twice.
        pytket_cost, pytket_placement = pytket_hypergraph_partition(
            qc, arch, corner_nodes, num_seeds=pytket_seeds
        )
        sfc = run_sfc(
            circuit, hw, num_logical,
            pytket_candidate=(dag, arch, pytket_placement, corner_nodes)
            if PORTER_INCLUDE_PYTKET else None,
        )
        print(f"  PORTER  (own layouts{'+pytket' if PORTER_INCLUDE_PYTKET else ''}) : {sfc}", flush=True)
        sfc_refined = run_sfc_refined(circuit, hw, num_logical)
        print(f"  PORTER+R (own, {PORTER_REFINE_PASSES}p) : {sfc_refined}", flush=True)
        sfc_search = run_sfc_search(circuit, hw, num_logical)
        print(f"  PORTER+S (gamma search + refine) : {sfc_search}", flush=True)

        # -- cross-layout: each router on the other's own initial layout ----
        sfc_on_dse = run_sfc_sabre_layout(circuit, hw, num_logical, dag, sabre_layouts)
        print(f"  PORTER  (dSE layout)  : {sfc_on_dse}", flush=True)
        sfc_on_dse_refined = run_sfc_sabre_layout_refined(
            circuit, hw, num_logical, dag, sabre_layouts)
        print(f"  PORTER+R (dSE layout) : {sfc_on_dse_refined}", flush=True)
        dse_on_porter = run_dsabre_porter_layout(
            arch, hw_cfg, dag, rev_dag, circuit, hw, num_logical)
        print(f"  dSE  (PORTER layout)  : {dse_on_porter}", flush=True)

        # -- shared-layout comparison (TeleSABRE's own initial layout) ----
        dse_shared = sfc_shared = sfc_shared_refined = None
        if ts_p2v is not None:
            try:
                dse_shared = run_dsabre_shared_layout(arch, hw_cfg, dag, rev_dag, ts_p2v, num_logical)
            except ValueError as exc:
                print(f"  dSE  (TS layout)   : skipped ({exc})", flush=True)
            else:
                print(f"  dSE  (TS layout)   : {dse_shared}", flush=True)
            sfc_shared = run_sfc_shared_layout(circuit, hw, num_logical, ts_p2v)
            print(f"  PORTER  (TS layout)   : {sfc_shared}", flush=True)
            sfc_shared_refined = run_sfc_shared_layout_refined(circuit, hw, num_logical, ts_p2v)
            print(f"  PORTER+R (TS layout)  : {sfc_shared_refined}", flush=True)
        else:
            print("  (no TeleSABRE initial layout available; skipping shared-layout comparison)", flush=True)

        # -- shared-layout comparison (pytket-dqc's own initial mapping,
        #    locked boundary -- reuses the partition computed above) --
        print(f"  pytket-dqc (e-bits): {pytket_cost}", flush=True)
        dse_pytket = sfc_pytket = sfc_pytket_refined = None
        if pytket_placement is not None:
            dse_pytket = run_dsabre_pytket_layout(arch, hw_cfg, dag, rev_dag, pytket_placement, corner_nodes)
            print(f"  dSE  (pytket layout): {dse_pytket}", flush=True)
            try:
                sfc_pytket = run_sfc_pytket_layout(circuit, hw, num_logical, dag, arch, pytket_placement, corner_nodes)
            except ValueError as exc:
                print(f"  PORTER  (pytket layout): skipped ({exc})", flush=True)
            else:
                print(f"  PORTER  (pytket layout): {sfc_pytket}", flush=True)
            sfc_pytket_refined = run_sfc_pytket_layout_refined(
                circuit, hw, num_logical, dag, arch, pytket_placement, corner_nodes)
            print(f"  PORTER+R (pytket layout): {sfc_pytket_refined}", flush=True)
        else:
            print("  (pytket-dqc partitioning failed on all seeds; skipping)", flush=True)

        records.append(dict(
            suite=suite_key, circuit=cname, num_logical=num_logical, cx=n_cx,
            telesabre=ts, dSE=dse, sfc=sfc,
            sfc_refined=sfc_refined, sfc_search=sfc_search,
            sfc_on_dse_layout=sfc_on_dse,
            sfc_on_dse_layout_refined=sfc_on_dse_refined,
            dSE_on_porter_layout=dse_on_porter,
            dSE_shared=dse_shared, sfc_shared=sfc_shared,
            sfc_shared_refined=sfc_shared_refined,
            pytket_ebits=pytket_cost, dSE_pytket=dse_pytket, sfc_pytket=sfc_pytket,
            sfc_pytket_refined=sfc_pytket_refined,
        ))
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", action="append", choices=list(SUITES), default=None)
    parser.add_argument("--out", type=Path, default=Path("compare_results.json"))
    parser.add_argument(
        "--porter-include-pytket", action="store_true",
        help="opt-in: add the external pytket-dqc partition as an extra "
             "candidate in PORTER's own-protocol best-of (default off, "
             "keeping PORTER self-contained).",
    )
    args = parser.parse_args()
    global PORTER_INCLUDE_PYTKET
    PORTER_INCLUDE_PYTKET = args.porter_include_pytket
    suites = args.suite or list(SUITES)

    all_records = []
    for s in suites:
        all_records.extend(run_suite(s))

    args.out.write_text(json.dumps(all_records, indent=2))
    print(f"\nWrote {len(all_records)} records to {args.out}", flush=True)


if __name__ == "__main__":
    main()
