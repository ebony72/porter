"""PORTER inter-core action mix under the own protocol (Table: action mix).

Reproduces the own-protocol PORTER run of compare_routers.run_sfc for every
circuit in the three suites (single deterministic temporal locality-greedy
layout, router seed 0) and reports how the EPR budget decomposes into
actions: TeleData by provenance (normal / blocked-plan selected via
opportunistic relief / tail-relief BFS), single TeleGates, and
TeleGatePackets with their remote-CX sizes (total / mean / max), read from
the emitted cat_entangler "packet_start" op metadata (remote_cx_count).

This is ONE forward pass at the configured horizon, not PORTER's
best-of-four-horizon protocol: the table exists to support the mechanism
ablation of Sec. V-C, whose every column is that same single pass, so the
two have to be measured the same way.  Cross-checks the counters it shares
with ablation_results.json (EPR, single telegates, packets) and refuses to
emit rows that disagree (determinism guard).

Output: paper/action_mix_results.json + LaTeX rows on stdout.
"""
import json
import os
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

import compile_porter as cdr
import porter as dr

SUITES = {
    "25": ("A", "qasm_25", [
        "ae_nativegates_ibm_qiskit_opt3_25.qasm",
        "ghz_nativegates_ibm_qiskit_opt3_25.qasm",
        "graphstate_nativegates_ibm_qiskit_opt3_25.qasm",
        "qft_nativegates_ibm_qiskit_opt3_25.qasm",
        "qnn_nativegates_ibm_qiskit_opt3_25.qasm",
        "random_nativegates_ibm_qiskit_opt3_25.qasm",
    ]),
    "64": ("H", "qasm_64", [
        "ae_nativegates_ibm_qiskit_opt3_64.qasm",
        "ghz_nativegates_ibm_qiskit_opt3_64.qasm",
        "graphstate_nativegates_ibm_qiskit_opt3_64.qasm",
        "qft_nativegates_ibm_qiskit_opt3_64.qasm",
        "qnn_OLD_DEEP_nativegates_ibm_qiskit_opt3_64.qasm.bak",
        "random_nativegates_ibm_qiskit_opt3_64.qasm",
        "qpeexact_nativegates_ibm_qiskit_opt3_64.qasm",
        "qaoa_nativegates_ibm_qiskit_opt3_64.qasm",
        "multiplier_nativegates_ibm_qiskit_opt3_64.qasm",
    ]),
    "80": ("H", "qasm_80", [
        "ae_nativegates_ibm_qiskit_opt3_80.qasm",
        "ghz_nativegates_ibm_qiskit_opt3_80.qasm",
        "graphstate_nativegates_ibm_qiskit_opt3_80.qasm",
        "qft_nativegates_ibm_qiskit_opt3_80.qasm",
        "qnn_nativegates_ibm_qiskit_opt3_80_DEEP.qasm",
        "random_nativegates_ibm_qiskit_opt3_80.qasm",
    ]),
}
CIRCUIT_ROOT = os.path.join(os.path.dirname(_HERE), "..", "other", "telesabre", "circuits")

# The single-pass reference is the ablation's `full` column, which is the
# same protocol (default RouterConfig, temporal-locality layout, seed 0, one
# forward pass).  compare_results*.json cannot serve here: its `sfc` leg is
# the selected best-of-four-horizon route, a different protocol.
reference = {
    (r["suite"], r["circuit"]): r["out"]["full"]
    for r in json.load(open(os.path.join(os.path.dirname(_HERE),
                                         "ablation_results.json")))
    if "epr" in r["out"].get("full", {})
}

rows = []
for suite, (arch_name, qdir, files) in SUITES.items():
    _, hw = cdr.hardware_for_name(arch_name)
    for fname in files:
        cname = fname.split("_nativegates")[0].replace(".qasm.bak", "").replace(".qasm", "")
        path = Path(CIRCUIT_ROOT) / qdir / fname
        circuit, num_logical = cdr.parse_qasm2(path)
        cfg = dr.RouterConfig(random_seed=0)
        layout = cdr.build_initial_layout(
            circuit, hw, num_logical, min_free_per_core=cfg.min_free_before_teleport
        )
        state = dr.PorterRouter(hw, cfg).compile(circuit, layout)
        s = state.stats

        packet_sizes = [
            op.metadata["remote_cx_count"]
            for op in state.emitted
            if op.op_type == "cat_entangler" and op.metadata.get("cat_role") == "packet_start"
        ]
        assert len(packet_sizes) == s.telegate_packet_count

        ref = reference[(suite, cname.replace("_OLD_DEEP", ""))]
        for key, val in [
            ("epr", s.epr), ("telegates", s.telegate_count),
            ("packets", s.telegate_packet_count),
        ]:
            assert ref[key] == val, f"{suite}q {cname}: {key} {val} != recorded {ref[key]}"

        row = dict(
            suite=suite, circuit=cname.replace("_OLD_DEEP", ""), epr=s.epr,
            teleports_normal=s.teleport_normal_count,
            teleports_blocked=s.teleport_blocked_count,
            teleports_capacity_relief=s.teleport_capacity_relief_count,
            telegates=s.telegate_count, telegate_packets=s.telegate_packet_count,
            packet_cx_total=sum(packet_sizes),
            packet_cx_mean=round(sum(packet_sizes) / len(packet_sizes), 2) if packet_sizes else None,
            packet_cx_max=max(packet_sizes) if packet_sizes else None,
            packet_sizes=packet_sizes,
        )
        rows.append(row)
        print(f"[{suite}q] {row['circuit']}: {row}", flush=True)

out = os.path.join(_HERE, "action_mix_results.json")
with open(out, "w") as f:
    json.dump(rows, f, indent=2)
print(f"\nwrote {out}\n\n%% -- LaTeX rows (action-mix table) --")

for row in rows:
    mean = f"{row['packet_cx_mean']:.1f}" if row["packet_cx_mean"] is not None else "---"
    mx = row["packet_cx_max"] if row["packet_cx_max"] is not None else "---"
    print(
        f"{row['suite']}q & {row['circuit']:<11} & {row['teleports_normal']:>5} & "
        f"{row['teleports_blocked']:>3} & {row['teleports_capacity_relief']:>3} & "
        f"{row['telegates']:>4} & {row['telegate_packets']:>4} & "
        f"{row['packet_cx_total']:>5} & {mean:>4} & {mx:>2} & {row['epr']:>5} \\\\"
    )
