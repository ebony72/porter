"""Harvest and cache TeleSABRE's initial layouts for the shared-layout legs.

The shared-layout protocol hands PORTER *TeleSABRE's own initial mapping*, so
re-running PORTER's legs after a protocol change needs those layouts -- not
TeleSABRE's routing results, which are unaffected by anything PORTER does.
`run_telesabre` already extracts the layout (iteration 0 of report.json) but
`compare_routers` drops it before writing compare_results.json, so it has to
be recovered.

Two things make that much cheaper than a full re-run:
  * the WINNING seed is recorded in compare_results.json, so one TeleSABRE
    invocation per circuit suffices instead of NUM_SEEDS;
  * TeleSABRE is deterministic, so the harvested layout is cached here once
    and never needs recomputing -- which is what should have happened
    originally.

Each run is cross-checked against the recorded EPR/swaps; a mismatch means the
layout does not belong to the recorded winner and is reported, not silently
cached.

    python harvest_shared_layouts.py [suite ...]   -> paper/shared_layouts.json
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent   # repo root: porter/, compile_porter.py
sys.path.insert(0, str(_ROOT))

import compare_routers as cr

OUT = _ROOT / "paper" / "shared_layouts.json"


def harvest_one(qasm_path: Path, device_json: Path, seed: int):
    """Run TeleSABRE at one known seed; return (phys_to_virt, epr, swaps)."""
    tmp_qasm = None
    clean = qasm_path
    if qasm_path.name.count(".") > 1:          # main.c parses the LAST dot
        tmp_qasm = Path(tempfile.mktemp(suffix=".qasm"))
        tmp_qasm.write_text(qasm_path.read_text())
        clean = tmp_qasm
    rpt = tempfile.mktemp(suffix=".json")
    cfg_path = cr._telesabre_config(seed, rpt, save_report=True)
    try:
        proc = subprocess.run(
            [str(cr.TELESABRE_BIN), cfg_path, str(device_json), str(clean)],
            capture_output=True, text=True, timeout=cr.COMPILER_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return None, None, None
    finally:
        Path(cfg_path).unlink(missing_ok=True)
        if tmp_qasm is not None:
            tmp_qasm.unlink(missing_ok=True)

    out = proc.stdout + proc.stderr
    td = tg = swaps = 0
    ok = False
    for line in out.splitlines():
        s = line.strip()
        if "Teledata:" in s:
            td = int(s.split(":")[1])
        elif "Telegate:" in s:
            tg = int(s.split(":")[1])
        elif "Swaps:" in s:
            swaps = int(s.split(":")[1])
        elif "Success: true" in s:
            ok = True
    p2v = None
    if ok and Path(rpt).exists():
        try:
            p2v = json.loads(Path(rpt).read_text())["iterations"][0]["phys_to_virt"]
        except (json.JSONDecodeError, KeyError, IndexError):
            p2v = None
    Path(rpt).unlink(missing_ok=True)
    return (p2v, td + tg, swaps) if ok else (None, None, None)


PYTKET_OUT = _ROOT / "paper" / "pytket_placements.json"


def harvest_pytket() -> None:
    """Cache pytket-dqc's KaHyPar placements, the same way and for the same
    reason as TeleSABRE's layouts: PORTER's leg needs the partition, not
    pytket's own ebit count, and the partitioner is deterministic per seed.
    Each placement is cross-checked against the recorded `pytket_ebits`."""
    rows = json.loads((_ROOT / "paper" / "compare_results.json").read_text())
    cache = json.loads(PYTKET_OUT.read_text()) if PYTKET_OUT.exists() else {}
    for row in rows:
        key = f"{row['suite']}_{row['circuit']}"
        if row.get("pytket_ebits") is None:
            print(f"[{key}] no recorded pytket partition -- skipping", flush=True)
            continue
        if key in cache and cache[key].get("placement"):
            print(f"[{key}] cached", flush=True)
            continue
        spec = cr.SUITES[row["suite"]]
        fname = next(f for f in spec["files"]
                     if f.split("_nativegates")[0].replace(".qasm", "")
                     in (row["circuit"], row["circuit"] + "_OLD_DEEP")
                     or f.startswith(row["circuit"] + "_"))
        qc, dag = cr.load_qasm(spec["circuit_dir"] / fname)
        _, hw = cr.cdr.hardware_for_name(spec["arch_name"])
        arch = cr.sfc_hardware_to_dsabre_architecture(hw)
        corners = cr._locked_boundary_corner_nodes(arch)
        t0 = time.perf_counter()
        seeds = cr.PYTKET_NUM_SEEDS if row["suite"] != "80" else 1
        cost, placement = cr.pytket_hypergraph_partition(qc, arch, corners, seeds)
        match = (cost == row["pytket_ebits"])
        cache[key] = dict(placement={str(k): v for k, v in (placement or {}).items()},
                          corner_nodes=sorted(corners), num_seeds=seeds,
                          reproduced_ebits=cost, recorded_ebits=row["pytket_ebits"],
                          reproduces=bool(match))
        print(f"[{key}] ebits={cost} (recorded {row['pytket_ebits']}) "
              f"{'MATCH' if match else '*** MISMATCH ***'} "
              f"placement={'yes' if placement else 'NO'}  "
              f"[{time.perf_counter()-t0:.0f}s]", flush=True)
        PYTKET_OUT.write_text(json.dumps(cache, indent=1))
    PYTKET_OUT.write_text(json.dumps(cache, indent=1))
    ok = sum(1 for v in cache.values() if v.get("placement") and v.get("reproduces"))
    print(f"\nwrote {PYTKET_OUT}: {ok}/{len(cache)} placements cross-checked", flush=True)


def main() -> None:
    if "--pytket" in sys.argv:
        harvest_pytket()
        return
    want = set(sys.argv[1:]) or set(cr.SUITES)
    rows = json.loads((_ROOT / "paper" / "compare_results.json").read_text())
    cache = json.loads(OUT.read_text()) if OUT.exists() else {}
    for row in rows:
        if row["suite"] not in want:
            continue
        key = f"{row['suite']}_{row['circuit']}"
        ts = row.get("telesabre")
        if not ts:
            print(f"[{key}] TeleSABRE never completed -- no shared layout", flush=True)
            continue
        if key in cache and cache[key].get("phys_to_virt"):
            print(f"[{key}] cached", flush=True)
            continue
        spec = cr.SUITES[row["suite"]]
        fname = next(f for f in spec["files"]
                     if f.split("_nativegates")[0].replace(".qasm", "")
                     in (row["circuit"], row["circuit"] + "_OLD_DEEP")
                     or f.startswith(row["circuit"] + "_"))
        t0 = time.perf_counter()
        p2v, epr, swaps = harvest_one(
            spec["circuit_dir"] / fname, spec["device_json"], int(ts["seed"]))
        match = (epr == ts["epr"] and swaps == ts["swaps"])
        cache[key] = dict(seed=int(ts["seed"]), phys_to_virt=p2v,
                          reproduced_epr=epr, recorded_epr=ts["epr"],
                          reproduces=bool(match))
        print(f"[{key}] seed={ts['seed']} epr={epr} (recorded {ts['epr']}) "
              f"{'MATCH' if match else '*** MISMATCH ***'} "
              f"layout={'yes' if p2v else 'NO'}  [{time.perf_counter()-t0:.0f}s]",
              flush=True)
        OUT.write_text(json.dumps(cache, indent=1))
    OUT.write_text(json.dumps(cache, indent=1))
    n_ok = sum(1 for v in cache.values() if v.get("phys_to_virt") and v.get("reproduces"))
    print(f"\nwrote {OUT}: {n_ok}/{len(cache)} layouts harvested and cross-checked",
          flush=True)


if __name__ == "__main__":
    main()
