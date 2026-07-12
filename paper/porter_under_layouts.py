"""PORTER under every available initial mapping (router held fixed = PORTER).

For each circuit we route PORTER from five layout sources and record EPR/SWAP:
  porter_balanced  : PORTER balanced-first-layer  (own, best of NUM_SEEDS)
  porter_locality  : PORTER seeded locality-greedy (own, best of NUM_SEEDS)
  sabre_dse        : dSABRE SabreLayout, corners-removed (best of its 3 cands)
  pytket           : pytket-dqc HypergraphPartitioning, corner-locked
  telesabre        : TeleSABRE built-in Hungarian initial layout

Reuses compare_routers' own building blocks so every cell is the identical
PORTER (RouterConfig seed 0) as the paper's shared-layout legs.
"""
import json, os, sys, time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))  # repo root holds compare_routers / compile_porter / porter

import compare_routers as cr
import compile_porter as cdr
import porter as dr

NUM_SEEDS = cr.NUM_SEEDS


def porter_best_over_builder(circuit, hw, num_logical, builder):
    """Best-EPR PORTER over NUM_SEEDS candidates from one own-layout builder."""
    best = None
    for seed in range(NUM_SEEDS):
        cfg = dr.RouterConfig(random_seed=seed)
        try:
            layout = builder(circuit, hw, num_logical, seed=seed,
                             min_free_per_core=cfg.min_free_before_teleport)
        except ValueError:
            continue
        router = dr.PorterRouter(hw, cfg)
        t0 = time.perf_counter()
        try:
            with cr._compiler_time_limit():
                state = router.compile(circuit, layout)
        except (RuntimeError, ValueError, cr.CompilerTimeout):
            continue
        elapsed = time.perf_counter() - t0
        if best is None or state.stats.epr < best["epr"]:
            best = dict(epr=state.stats.epr, swaps=state.stats.local_swap_count,
                        seed=seed, seconds=round(elapsed, 3))
    return best


def run_suite_layouts(suite_key):
    spec = cr.SUITES[suite_key]
    _, hw = cdr.hardware_for_name(spec["arch_name"])
    arch = cr.sfc_hardware_to_dsabre_architecture(hw)
    cr.verify_topology_match(hw, arch)
    corner_nodes = cr._locked_boundary_corner_nodes(arch)
    pytket_seeds = cr.PYTKET_NUM_SEEDS if suite_key != "80" else 1

    rows = []
    for fname in spec["files"]:
        qasm_path = spec["circuit_dir"] / fname
        cname = fname.split("_nativegates")[0].replace(".qasm.bak", "").replace(".qasm", "")
        print(f"[{suite_key}q] {cname} ...", flush=True)
        circuit, num_logical = cdr.parse_qasm2(qasm_path)
        n_cx = sum(1 for g in circuit if g.is_cx())
        qc, dag = cr.load_qasm(qasm_path)

        row = dict(suite=suite_key, circuit=cname, num_logical=num_logical, cx=n_cx)

        # PORTER own layouts, split
        row["porter_balanced"] = porter_best_over_builder(circuit, hw, num_logical, cdr.build_balanced_first_layer_layout)
        row["porter_locality"] = porter_best_over_builder(circuit, hw, num_logical, cr.build_seeded_locality_layout)
        print(f"    balanced={row['porter_balanced']}  locality={row['porter_locality']}", flush=True)

        # dSABRE SabreLayout (corners-removed) -> PORTER
        sabre_layouts = cr.sabre_locked_boundary_layout(qc, dag, arch, seed=0)
        row["sabre_dse"] = cr.run_sfc_sabre_layout(circuit, hw, num_logical, dag, sabre_layouts)
        print(f"    sabre_dse={row['sabre_dse']}", flush=True)

        # pytket-dqc (corner-locked) -> PORTER
        _cost, placement = cr.pytket_hypergraph_partition(qc, arch, corner_nodes, num_seeds=pytket_seeds)
        row["pytket"] = (cr.run_sfc_pytket_layout(circuit, hw, num_logical, dag, arch, placement, corner_nodes)
                         if placement is not None else None)
        print(f"    pytket={row['pytket']}", flush=True)

        # TeleSABRE Hungarian -> PORTER  (only if TeleSABRE yields a layout)
        ts = cr.run_telesabre(qasm_path, spec["device_json"])
        ts_p2v = ts.pop("initial_phys_to_virt", None) if ts else None
        row["telesabre"] = (cr.run_sfc_shared_layout(circuit, hw, num_logical, ts_p2v)
                            if ts_p2v is not None else None)
        print(f"    telesabre={row['telesabre']}", flush=True)

        rows.append(row)
    return rows


if __name__ == "__main__":
    suites = sys.argv[1:] or ["25", "64", "80"]
    suffix = "" if suites == ["25", "64", "80"] else "_" + "_".join(suites)
    out = os.path.join(_HERE, f"porter_under_layouts_results{suffix}.json")
    all_rows = []
    for s in suites:
        all_rows.extend(run_suite_layouts(s))
        json.dump(all_rows, open(out, "w"), indent=2)  # checkpoint after each suite
    print("\nSAVED", out, flush=True)
    print(json.dumps(all_rows, indent=2), flush=True)
