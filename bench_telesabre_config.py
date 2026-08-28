"""Does the init_layout_hun_min_free_qubit key typo change TeleSABRE's 64q results?

PORTER's compare_routers._telesabre_config writes the key as
`init_layout_hun_free_qubit` (missing `min_`); TeleSABRE's config parser
silently ignores unknown keys, so the binary falls back to its built-in
default of 3.  dSABRE's benchmark.py writes `init_layout_hun_min_free_qubit: 4`.
Everything else in the two configs is identical.

Runs the 64q suite best-of-3 under both spellings, on both binaries.
"""
import json, os, subprocess, tempfile, time, sys
from pathlib import Path

CD = Path("/Users/sanjiangli/Documents/pyzoo/other/telesabre/circuits/qasm_64")
DEV = "/Users/sanjiangli/Documents/pyzoo/other/telesabre/devices/H_grid_2_3_4_4.json"
BINS = {
    "patched": "/Users/sanjiangli/Documents/pyzoo/SFC/patched_telesabre/telesabre",
    "stock":   "/Users/sanjiangli/Documents/pyzoo/other/telesabre/telesabre",
}
FILES = [("ae","ae"),("ghz","ghz"),("graphstate","graphstate"),("qft","qft"),
         ("qnn","qnn_OLD_DEEP"),("random","random"),("qpeexact","qpeexact"),
         ("qaoa","qaoa"),("multiplier","multiplier")]

def cfg(seed, rpt, key):
    c = {"config": {
        "name":"cmp","seed":seed,"energy_type":"extended-set",
        "usage_penalties_reset_interval":5,"optimize_initial":True,
        "initial_layout_type":"hungarian","teleport_bonus":100,"telegate_bonus":100,
        "safety_valve_iters":100,"extended_set_size":20,"extended_set_factor":0.05,
        "inter_core_edge_weight":2,"full_core_penalty":10,
        "max_solving_deadlock_iterations":1000,"gate_usage_penalty":0.0,
        "swap_usage_penalty":0.002,"teledata_usage_penaly":0.005,
        "telegate_usage_penalty":0.005,"init_layout_hun_min_free_gate":5,
        key: 4,
        "enable_passing_core_emptying_teleport_possibility":False,
        "max_iterations":200000,"save_report":False,"report_filename":rpt,
        "required_successes":1,"max_attempts":10}}
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(c,f); f.close(); return f.name

def run(binp, path, key, timeout):
    best=None
    for seed in range(3):
        cf = cfg(seed, tempfile.mktemp(suffix=".json"), key)
        try:
            p = subprocess.run([binp, cf, DEV, str(path)], capture_output=True,
                               text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            os.unlink(cf); continue
        os.unlink(cf)
        out = p.stdout + p.stderr
        td=tg=0; ok=False
        for l in out.splitlines():
            s=l.strip()
            if "Teledata:" in s: td=int(s.split(":")[1])
            elif "Telegate:" in s: tg=int(s.split(":")[1])
            elif "Success: true" in s: ok=True
        if ok and (best is None or td+tg < best):
            best = td+tg
    return best

KEYS = {"porter(typo->default 3)":"init_layout_hun_free_qubit",
        "dsabre(correct = 4)":"init_layout_hun_min_free_qubit"}
timeout = int(sys.argv[1]) if len(sys.argv)>1 else 300
print(f"timeout={timeout}s/seed, best-of-3\n")
print(f"{'circuit':<12}" + "".join(f"{b+'/'+k:>34}" for b in BINS for k in KEYS))
for cname, stem in FILES:
    f = CD/f"{stem}_nativegates_ibm_qiskit_opt3_64.qasm"
    if not f.exists():
        f = CD/f"{stem}_nativegates_ibm_qiskit_opt3_64.qasm.bak"
        tmp = Path(tempfile.mktemp(suffix=".qasm")); tmp.write_text(f.read_text()); f = tmp
    row = []
    for b, binp in BINS.items():
        for kl, k in KEYS.items():
            row.append(run(binp, f, k, timeout))
    print(f"{cname:<12}" + "".join(f"{str(v):>34}" for v in row), flush=True)
