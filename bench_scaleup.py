"""Scale-up benchmark: QFT and QPEexact at 100, 200, and 360 logical qubits.

Architectures follow dSABRE's own scalability protocol exactly: 5x5 cores
throughout, core count 6 -> 12 -> 20 (H_grid_2_3_5_5, H_grid_3_4_5_5,
H_grid_4_5_5_5), so core occupancy is held roughly constant while the core
graph grows. This is what its bench_large.py uses and what its paper reports.

Own-protocol only -- dSABRE from its SabreLayout two-corner candidates,
PORTER from its single deterministic temporal locality-greedy layout, and
PORTER+R with backward refinement (compile_porter.run_refinement_passes).
TeleSABRE is included where its device file lets it converge.

Since 2026-08-28 the fixed-layout control is included too: PORTER routing
dSABRE's own SabreLayout candidates (`sfc_on_dse_layout`, and the refined
variant), so the two routers can be compared with the initial layout held
identical at these widths.  The pytket-dqc legs of compare_routers.py stay
omitted: its hypergraph partitioner does not finish in reasonable time on
7k-14k-CX circuits at these widths.

Architectures are read straight from the baselines' own device files via
compile_porter.hardware_from_device_json, so all three routers see identical
physical qubit ids.

    python3 bench_scaleup.py --out scaleup_results.json
"""
import argparse
import json
import time
from pathlib import Path

import compare_routers as C
import compile_porter as cdr
import porter as dr
from config import HardwareConfig
from qiskit.converters import circuit_to_dag

HERE = Path(__file__).resolve().parent
CIRCUITS = HERE.parent / "other" / "telesabre" / "circuits"
DEVICES = HERE.parent / "other" / "telesabre" / "devices"

SUITES = {
    # 100 logical on 150 physical (2x3 cores of 5x5)
    "100": dict(device="H_grid_2_3_5_5", circuit_dir=CIRCUITS / "qasm_100",
                files=["qft_nativegates_ibm_qiskit_opt3_100.qasm",
                       "qpeexact_nativegates_ibm_qiskit_opt3_100.qasm"]),
    # 200 logical on 300 physical (3x4 cores of 5x5)
    "200": dict(device="H_grid_3_4_5_5", circuit_dir=CIRCUITS / "qasm_200",
                files=["qft_nativegates_ibm_qiskit_opt3_200.qasm",
                       "qpeexact_nativegates_ibm_qiskit_opt3_200.qasm"]),
    # 360 logical on 500 physical (4x5 cores of 5x5)
    "360": dict(device="H_grid_4_5_5_5", circuit_dir=CIRCUITS / "qasm_360",
                files=["qft_nativegates_ibm_qiskit_opt3_360.qasm",
                       "qpeexact_nativegates_ibm_qiskit_opt3_360.qasm"]),
}


def run_suite(key, with_telesabre, refine_passes):
    spec = SUITES[key]
    device_json = DEVICES / f"{spec['device']}.json"
    hw_name, hw = cdr.hardware_from_device_json(device_json)
    arch = C.sfc_hardware_to_dsabre_architecture(hw)
    C.verify_topology_match(hw, arch)
    # dSABRE's own convention: every budget derived from the architecture.
    hw_cfg = HardwareConfig(deadlock_limit=None, max_backup_attempts=None,
                            max_iterations=None)
    print(f"\n=== {key}q on {hw_name}: {len(hw.cores)} cores x "
          f"{len(hw.cores[0].physical_qubits)} = {len(hw.phys_to_core)} physical ===",
          flush=True)

    records = []
    for fname in spec["files"]:
        qasm = spec["circuit_dir"] / fname
        cname = fname.split("_nativegates")[0]
        circuit, num_logical = cdr.parse_qasm2(qasm)
        n_cx = sum(1 for g in circuit if g.is_cx())
        print(f"[{key}q] {cname} ({num_logical}q, {n_cx} CX) ...", flush=True)

        ts = C.run_telesabre(qasm, device_json) if with_telesabre else None
        if with_telesabre:
            ts.pop("initial_phys_to_virt", None) if ts else None
            print(f"  TeleSABRE        : {ts}", flush=True)

        qc, dag = C.load_qasm(qasm)
        rev_dag = circuit_to_dag(qc.reverse_ops())
        _t_lay = time.perf_counter()
        sabre_layouts = C.dsabre_layout_candidates(qc, dag, arch, seed=0)
        lay_s = time.perf_counter() - _t_lay
        dse = C.run_dsabre(C.dSE, arch, hw_cfg, dag, rev_dag, sabre_layouts,
                           layout_seconds=lay_s)
        print(f"  dSABRE           : {dse}", flush=True)

        sfc = C.run_sfc(circuit, hw, num_logical)
        print(f"  PORTER  (1 pass) : {sfc}", flush=True)

        prev, C.PORTER_REFINE_PASSES = C.PORTER_REFINE_PASSES, refine_passes
        try:
            sfc_r = C.run_sfc_refined(circuit, hw, num_logical)
            # Fixed-layout control: PORTER routing the SAME SabreLayout
            # candidates dSABRE just routed, so the two differ only in the
            # routing loop.  Both take their best candidate, as dSABRE does.
            sfc_on_dse = C.run_sfc_sabre_layout(
                circuit, hw, num_logical, dag, sabre_layouts)
            sfc_on_dse_r = C.run_sfc_sabre_layout_refined(
                circuit, hw, num_logical, dag, sabre_layouts)
        finally:
            C.PORTER_REFINE_PASSES = prev
        print(f"  PORTER+R ({refine_passes}p)  : {sfc_r}", flush=True)
        print(f"  PORTER  (dSE lay): {sfc_on_dse}", flush=True)
        print(f"  PORTER+R(dSE lay): {sfc_on_dse_r}", flush=True)

        records.append(dict(suite=key, circuit=cname, device=spec["device"],
                            num_logical=num_logical, cx=n_cx,
                            physical=len(hw.phys_to_core), cores=len(hw.cores),
                            telesabre=ts, dSE=dse, sfc=sfc, sfc_refined=sfc_r,
                            sfc_on_dse_layout=sfc_on_dse,
                            sfc_on_dse_layout_refined=sfc_on_dse_r))
    return records


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--suite", action="append", choices=list(SUITES), default=None)
    ap.add_argument("--out", type=Path, default=HERE / "scaleup_results.json")
    ap.add_argument("--passes", type=int, default=5)
    ap.add_argument("--telesabre", action="store_true",
                    help="also run TeleSABRE (slow, and it does not converge "
                         "on most circuits at these widths)")
    args = ap.parse_args()

    out = []
    for key in (args.suite or list(SUITES)):
        out.extend(run_suite(key, args.telesabre, args.passes))
        args.out.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {len(out)} records to {args.out}", flush=True)


if __name__ == "__main__":
    main()
