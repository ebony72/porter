"""Shared loader for the adaptive-horizon experiments.

PORTER is imported from the frozen snapshot in ./snap/SFC (hashes in
snap/MANIFEST.txt), never from the live working tree, so a concurrent edit of
porter/router.py cannot change a running experiment.  Instance keys follow the
2026-09-01 sweep: main/<suite>/<circuit>, scaleup/<n>/<circuit>,
heavyhex/<topo>/<circuit>.
"""
import sys, math
from pathlib import Path

HERE = Path(__file__).resolve().parent
SNAP = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(SNAP))
sys.path.insert(0, str(SNAP / "experiments"))
import porter                      # noqa: E402
import compile_porter as cp        # noqa: E402
import compare_heavyhex as hh      # noqa: E402
import compare_routers as cr       # noqa: E402
import verify_porter as vp         # noqa: E402

CIRC = SNAP.parent / "other" / "telesabre" / "circuits"
DEV = SNAP.parent / "other" / "telesabre" / "devices"

MAIN = {
    "25": ("A", ["ae", "ghz", "graphstate", "qft", "qnn", "random"]),
    "64": ("H", ["ae", "ghz", "graphstate", "qft", "qnn_OLD_DEEP", "random",
                 "qpeexact", "qaoa", "multiplier"]),
    "80": ("H", ["ae", "ghz", "graphstate", "qft", "qnn_DEEP", "random",
                 "qpeexact", "qaoa", "multiplier"]),
}
SCALEUP = {"100": "H_grid_2_3_5_5", "200": "H_grid_3_4_5_5", "360": "H_grid_4_5_5_5"}
HEAVYHEX = ("ring", "star")
TRIVIAL = {"ghz", "graphstate"}       # EPR is horizon-independent on these


def find_qasm(sub: str, name: str) -> Path:
    d = CIRC / sub
    if name == "qnn_OLD_DEEP":
        c = sorted(d.glob("qnn_OLD_DEEP*"))
    elif name == "qnn_DEEP":
        c = sorted(d.glob("qnn_*_DEEP.qasm"))
    else:
        c = sorted(p for p in d.glob(f"{name}_*.qasm") if "DEEP" not in p.name)
    if not c:
        raise FileNotFoundError(f"{sub}/{name}")
    return c[0]


def instance_keys():
    out = []
    for suite, (_, names) in MAIN.items():
        out += [f"main/{suite}/{nm}" for nm in names]
    for suite in SCALEUP:
        out += [f"scaleup/{suite}/{nm}" for nm in ("qft", "qpeexact")]
    for topo in HEAVYHEX:
        out += [f"heavyhex/{topo}/{nm}" for nm in hh.CIRCUITS]
    return out


def family_of(key: str) -> str:
    c = key.split("/")[2]
    return "qnn" if c.startswith("qnn") else c


def group_of(key: str) -> str:
    a, b, _ = key.split("/")
    return a + b            # main25, main64, main80, scaleup100.., heavyhexring


def coarse_group_of(key: str) -> str:
    a, b, _ = key.split("/")
    return a if a == "scaleup" else a + b


def arch_of(key: str) -> str:
    a, b, _ = key.split("/")
    if a == "main":
        return MAIN[b][0]
    if a == "scaleup":
        return SCALEUP[b]
    return f"HeavyHex_{b}4_27"


def is_trivial(key: str) -> bool:
    return family_of(key) in TRIVIAL


def hardware_for(key: str) -> porter.Hardware:
    a, b, _ = key.split("/")
    if a == "main":
        return cp.hardware_for_name(MAIN[b][0])[1]
    if a == "scaleup":
        return cp.hardware_from_device_json(DEV / f"{SCALEUP[b]}.json")[1]
    arch = hh.build_heavy_hex_architecture(hh.NUM_CORES, b)
    hw = hh.dsabre_architecture_to_porter_hardware(arch)
    cr.verify_topology_match(hw, arch)
    return hw


def qasm_for(key: str) -> Path:
    a, b, c = key.split("/")
    if a == "main":
        return find_qasm(f"qasm_{b}", c)
    if a == "scaleup":
        return find_qasm(f"qasm_{b}", c)
    return hh.CIRCUIT_DIR / (hh.QNN_FILE if c == "qnn" else c + hh.SUFFIX)


def load(key: str):
    """(hw, gates, n) with gate ids assigned."""
    hw = hardware_for(key)
    gates, n = cp.parse_qasm2(qasm_for(key))
    porter.assign_gate_ids(gates)
    return hw, gates, n


# ---------------------------------------------------------------- features

def arch_features(hw: porter.Hardware) -> dict:
    cores = list(hw.cores)
    K = len(cores)
    dists = [hw.core_distance(a, b) for a in cores for b in cores if a != b]
    deg = [len(hw.core_neighbors(c)) for c in cores]
    phys = sum(len(hw.cores[c].physical_qubits) for c in cores)
    mean_deg = sum(deg) / K
    return {
        "K": K,
        "physical": phys,
        "diameter": max(dists) if dists else 0,
        "mean_path": (sum(dists) / len(dists)) if dists else 0.0,
        "max_degree": max(deg),
        "mean_degree": mean_deg,
        "hub_ratio": max(deg) / mean_deg,
        "degree_var": sum((d - mean_deg) ** 2 for d in deg) / K,
    }


def circuit_features(gates, n: int) -> dict:
    last = {}
    depth = 0
    cx_last = {}
    cx_depth = 0
    cx = 0
    partners = {}
    for g in gates:
        lay = 1 + max((last.get(q, 0) for q in g.qubits), default=0)
        for q in g.qubits:
            last[q] = lay
        depth = max(depth, lay)
        if g.is_cx():
            cx += 1
            q0, q1 = g.qubits
            partners.setdefault(q0, set()).add(q1)
            partners.setdefault(q1, set()).add(q0)
            cl = 1 + max(cx_last.get(q0, 0), cx_last.get(q1, 0))
            cx_last[q0] = cx_last[q1] = cl
            cx_depth = max(cx_depth, cl)
    pc = [len(v) for v in partners.values()] or [0]
    mp = sum(pc) / len(pc)
    return {
        "n": n, "cx": cx, "depth": depth, "cx_depth": cx_depth,
        "rho": cp.circuit_interaction_density(gates, n),
        "mean_partners": mp, "max_partners": max(pc),
        "partner_var": sum((p - mp) ** 2 for p in pc) / len(pc),
    }


def gmean(xs):
    xs = [max(float(x), 1.0) for x in xs]
    return math.exp(sum(map(math.log, xs)) / len(xs)) if xs else float("nan")
