"""PORTER vs dSABRE on the two heavy-hex architectures of the dSABRE paper.

Four IBM 27-qubit heavy-hex cores (108 physical qubits) wired as a ring
(4 links, every core degree 2) or a star (3 links, core 0 a hub every
inter-core route must cross), running the same nine-circuit 64q suite as
the main tables.  A heavy-hex tile is irregular -- degrees over {1,2,3},
six degree-1 leaves, diameter 12 against a 4x4 grid's 6 -- so this tests
how much of either router's behaviour depends on grid-shaped cores wired
in a grid.

Architecture handling follows the rule the main harness learned the hard
way (see CLAUDE.md): dSABRE routes on the object its OWN builder produces,
because SabreLayout and dSABRE's tie-breaks depend on graph insertion order
and a converted object costs it real EPR.  PORTER's Hardware is derived
FROM that same object, and `verify_topology_match` asserts the two describe
the identical device before anything is routed.

Legs
  dSE               dSABRE own protocol: sabre_locked_boundary_layout
                    candidates x (fwd, bwd, fwd), best by EPR -- exactly
                    what dsabre/code/bench_heavyhex.py runs, so the numbers
                    are checked against its published results files.
  porter            PORTER own protocol: temporal locality-greedy layout,
                    one forward pass.
  porter_refined    the same layout with the 5-pass backward refinement.
  porter_on_dse     PORTER routing dSABRE's own layout candidates (shared
                    layout: isolates routing from initial mapping), and
  porter_on_dse_refined  the same with the 5-pass backward refinement, which
                    matches dSABRE's own pass count.

Output: paper/heavyhex_results.json
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import networkx as nx
from qiskit.converters import circuit_to_dag

import compare_routers as cr
import compile_porter as cdr
import porter as dr

from architecture import build_heavy_hex_architecture
from config import HardwareConfig
from dsabre_ext import dSABRE_BFSExt
from layout import sabre_locked_boundary_layout, run_sabre_passes

CIRCUIT_DIR = cr.TELESABRE_DIR / "circuits" / "qasm_64"
SUFFIX = "_nativegates_ibm_qiskit_opt3_64.qasm"
CIRCUITS = ["ae", "ghz", "graphstate", "qft", "qnn", "random",
            "qpeexact", "qaoa", "multiplier"]
QNN_FILE = "qnn_OLD_DEEP_nativegates_ibm_qiskit_opt3_64.qasm.bak"
EXPECTED_CX = {"ae": 1962, "ghz": 63, "graphstate": 64, "qft": 1966,
               "qnn": 8126, "random": 1627, "qpeexact": 2139,
               "qaoa": 3920, "multiplier": 13040}
NUM_CORES = 4
HW = HardwareConfig(deadlock_limit=None, max_backup_attempts=None,
                    max_iterations=None)
PORTER_REFINE_PASSES = 5

# dSABRE's published dSE numbers for these two architectures, used as a
# preflight that our dSABRE leg reproduces its own benchmark.
PUBLISHED_DSE = {
    "ring": {"ae": 86, "ghz": 2, "graphstate": 12, "qft": 110, "qnn": 249,
             "random": 465, "qpeexact": 80, "qaoa": 249, "multiplier": 451},
    "star": {"ae": 118, "ghz": 3, "graphstate": 10, "qft": 125, "qnn": 241,
             "random": 475, "qpeexact": 120, "qaoa": 251, "multiplier": 722},
}


def dsabre_architecture_to_porter_hardware(arch) -> dr.Hardware:
    """PORTER Hardware describing the SAME device as a dSABRE architecture.

    Physical qubit ids, intra-core coupling edges and inter-core port
    endpoints are all carried over unchanged, so EPR and SWAP counts mean
    the same thing on both sides.  PORTER models one communication port per
    (core, neighbouring core) pair, which is exactly dSABRE's inter-core
    link structure here; a second link between the same pair of cores would
    need a richer port model and is rejected rather than silently collapsed.
    """
    ports: dict[int, dict[int, int]] = {cid: {} for cid in arch.intra}
    for u, v in arch.inter_core_links:
        cu, cv = arch.core_of(u), arch.core_of(v)
        if cu == cv:
            raise ValueError(f"intra-core link {(u, v)} in inter_core_links")
        for a, b, ca, cb in ((u, v, cu, cv), (v, u, cv, cu)):
            if ports[ca].get(cb, a) != a:
                raise ValueError(
                    f"core {ca} has two distinct ports toward core {cb} "
                    f"({ports[ca][cb]} and {a}); PORTER models one port per "
                    "core pair")
            ports[ca][cb] = a

    cores = {}
    for cid, g in arch.intra.items():
        cores[cid] = dr.Core(
            cid=cid,
            physical_qubits=tuple(sorted(g.nodes())),
            coupling_edges=tuple(dr.canonical_edge(a, b) for a, b in g.edges()),
            ports=dict(ports[cid]),
        )
    core_edges = tuple(dr.canonical_edge(a, b) for a, b in arch.core_graph.edges())
    return dr.Hardware(cores=cores, core_edges=core_edges)


def gmean(v):
    v = [x for x in v if x]
    return math.exp(sum(math.log(x) for x in v) / len(v)) if v else float("nan")


def run_topology(topo: str, circuits: list[str] | None = None) -> list[dict]:
    arch = build_heavy_hex_architecture(NUM_CORES, topo)
    hw = dsabre_architecture_to_porter_hardware(arch)
    cr.verify_topology_match(hw, arch)
    caps = {cid: len(c.physical_qubits) for cid, c in hw.cores.items()}
    print(f"[{topo}] cores={arch.num_cores} physical={len(arch.data_qubits)} "
          f"links={len(arch.inter_core_links)} "
          f"core_graph={sorted(arch.core_graph.edges())} capacities={caps}",
          flush=True)

    router = dSABRE_BFSExt(arch, HW)
    records = []
    for cname in (circuits or CIRCUITS):
        qf = CIRCUIT_DIR / (QNN_FILE if cname == "qnn" else cname + SUFFIX)
        qc, dag = cr.load_qasm(qf)
        rev_dag = circuit_to_dag(qc.reverse_ops())
        n_cx = sum(1 for _ in dag.two_qubit_ops())
        if EXPECTED_CX[cname] != n_cx:
            raise SystemExit(f"{cname}: {n_cx} CX, expected {EXPECTED_CX[cname]}")
        circuit, num_logical = cdr.parse_qasm2(qf)
        print(f"[{topo}] {cname} (cx={n_cx}) ...", flush=True)
        rec = {"topology": topo, "circuit": cname, "cx": n_cx,
               "qubits": num_logical}

        # -- dSABRE own protocol (exactly bench_heavyhex.py) -------------
        t0 = time.perf_counter()
        layouts = sabre_locked_boundary_layout(qc, dag, arch, seed=0)
        layout_s = time.perf_counter() - t0
        best = None
        for lay in layouts:
            m = run_sabre_passes(router, dag, rev_dag, lay)
            if m and not m.get("aborted") and (best is None or m["eprs"] < best["eprs"]):
                best = m
        rec["dSE"] = (dict(epr=best["eprs"], swaps=best["ls"],
                           seconds=round(layout_s + time.perf_counter() - t0, 3),
                           n_candidates=len(layouts))
                      if best else None)
        pub = PUBLISHED_DSE[topo].get(cname)
        if best and pub is not None and best["eprs"] != pub:
            rec["dSE"]["DEVIATES_from_published"] = pub

        # -- PORTER own protocol ----------------------------------------
        for leg, passes in (("porter", 1), ("porter_refined", PORTER_REFINE_PASSES)):
            cfg = dr.RouterConfig(random_seed=0)
            t0 = time.perf_counter()
            try:
                if passes == 1:
                    lay = cdr.build_initial_layout(
                        circuit, hw, num_logical,
                        min_free_per_core=cfg.min_free_before_teleport)
                    st, sel_info = cdr.route(hw, cfg, circuit, lay)
                    s = st.stats
                else:
                    st, info = cdr.run_refinement_passes(
                        hw, cfg, circuit, cdr.build_initial_layout(
                            circuit, hw, num_logical,
                            min_free_per_core=cfg.min_free_before_teleport),
                        passes=passes)
                    # run_refinement_passes returns None only when the FIRST
                    # forward pass fails -- i.e. the same failure the one-pass
                    # leg already recorded, not a refinement-specific one.
                    if st is None:
                        rec[leg] = {"error": "first forward pass failed; "
                                             "see the one-pass leg",
                                    "failed_pass": info.get("failed_pass")}
                        continue
                    s = st.stats
                rec[leg] = dict(epr=s.epr, swaps=s.local_swap_count,
                                chosen_horizon=(sel_info.get("chosen_horizon")
                                                if passes == 1 else info.get("chosen_horizon")),
                                teleports=s.teleport_count,
                                telegates=s.telegate_count,
                                packets=s.telegate_packet_count,
                                depth=s.depth,
                                seconds=round(time.perf_counter() - t0, 3))
            except (RuntimeError, ValueError) as e:
                rec[leg] = {"error": f"{type(e).__name__}: {str(e)[:140]}"}

        # -- PORTER on dSABRE's own layout candidates (shared layout) ----
        # The fixed-layout control: same initial mapping for both routers, so
        # the comparison isolates the routing loop.  Both legs take the best
        # candidate, as dSABRE's own protocol does.
        try:
            rec["porter_on_dse"] = cr.run_sfc_sabre_layout(
                circuit, hw, num_logical, dag, layouts)
        except (RuntimeError, ValueError) as e:
            rec["porter_on_dse"] = {"error": f"{type(e).__name__}: {str(e)[:140]}"}
        prev, cr.PORTER_REFINE_PASSES = cr.PORTER_REFINE_PASSES, PORTER_REFINE_PASSES
        try:
            rec["porter_on_dse_refined"] = cr.run_sfc_sabre_layout_refined(
                circuit, hw, num_logical, dag, layouts)
        except (RuntimeError, ValueError) as e:
            rec["porter_on_dse_refined"] = {"error": f"{type(e).__name__}: {str(e)[:140]}"}
        finally:
            cr.PORTER_REFINE_PASSES = prev

        g = lambda k: (rec.get(k) or {}).get("epr")
        print(f"    dSE={g('dSE')} (pub {pub})  porter={g('porter')} "
              f"porter+R={g('porter_refined')} porter_on_dSE={g('porter_on_dse')} "
              f"porter+R_on_dSE={g('porter_on_dse_refined')}",
              flush=True)
        records.append(rec)
        out = _HERE / "paper" / "heavyhex_results.json"
        prev = json.loads(out.read_text()) if out.exists() else []
        prev = [r for r in prev if not (r["topology"] == topo
                                        and r["circuit"] == cname)]
        out.write_text(json.dumps(prev + [rec], indent=1))
    return records


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--topology", action="append", choices=("ring", "star"),
                    default=None)
    ap.add_argument("--circuits", default=None,
                    help="comma-separated subset of the nine-circuit suite")
    args = ap.parse_args()
    topos = args.topology or ["ring", "star"]
    circuits = ([c.strip() for c in args.circuits.split(",") if c.strip()]
                if args.circuits else None)
    for topo in topos:
        run_topology(topo, circuits)

    # Summarise from the results file, so a subset run still reports the
    # whole suite rather than only the rows it just recomputed.
    allrec = json.loads((_HERE / "paper" / "heavyhex_results.json").read_text())
    for topo in topos:
        rs = [r for r in allrec if r["topology"] == topo]
        print(f"\n=== {topo}: gmean EPR over {len(rs)} circuits ===", flush=True)
        for leg in ("dSE", "porter", "porter_refined", "porter_on_dse",
                    "porter_on_dse_refined"):
            vals = [(r.get(leg) or {}).get("epr") for r in rs]
            ok = [v for v in vals if v]
            if len(ok) < len(rs):
                miss = [r["circuit"] for r, v in zip(rs, vals) if not v]
                print(f"  {leg:<15} incomplete, missing {miss}", flush=True)
                continue
            d = gmean([(r.get("dSE") or {}).get("epr") for r in rs])
            print(f"  {leg:<15} {gmean(ok):8.1f}"
                  + (f"   vs dSABRE {100*(gmean(ok)/d - 1):+.1f}%" if leg != "dSE" else ""),
                  flush=True)
        dev = [(r["circuit"], r["dSE"]["DEVIATES_from_published"], r["dSE"]["epr"])
               for r in rs if r.get("dSE") and "DEVIATES_from_published" in r["dSE"]]
        print(f"  dSABRE reproduces its published numbers: "
              f"{'YES' if not dev else 'NO -> ' + str(dev)}", flush=True)


if __name__ == "__main__":
    main()
