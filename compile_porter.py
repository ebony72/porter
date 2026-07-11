from __future__ import annotations

import argparse
import csv
import json
import math
import random
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
    seed: int,
    *,
    min_free_per_core: int,
) -> porter.Layout:
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
            seed,
            min_free_per_core=router_config.min_free_before_teleport,
        )
        initial_layout_label = "porter.balanced_first_layer"
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

    router = porter.PorterRouter(hw, router_config)

    start = time.perf_counter()
    state = router.compile(circuit_gates, initial_layout)
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
        "seconds": seconds,
    }

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
        help="porter uses the standalone balanced first-layer mapper; telesabre reuses qlimt.initial_layout.",
    )
    parser.add_argument("--max-iterations", type=int, default=None)
    args = parser.parse_args()

    summary = compile_qasm(
        args.qasm,
        args.architecture,
        args.seed,
        args.out_dir,
        initial_layout_mode=args.initial_layout,
        max_iterations=args.max_iterations,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
