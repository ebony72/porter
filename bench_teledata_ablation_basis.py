"""TeleData-only column for the paper's mechanism-ablation table.

Runs the ablation table's own basis (ae/ghz/graphstate/qft/qnn/random at
25q/64q/80q, canonical temporal-locality layout, seed 0) under two further
action-vocabulary configs:

  teledata_only        : telegate_enabled=False -- TeleData is the only
                         inter-core primitive (dSABRE's vocabulary inside
                         PORTER's plan-committed framework)
  teledata_only_relief : the same, plus capacity_relief_from_adjacent_blocked,
                         the extra relief tier the TeleGate was silently
                         providing (a TeleGate needs no free destination slot,
                         so it is always a normal plan for an adjacent remote
                         CX; without it an all-adjacent capacity-blocked front
                         never reaches the tail-relief BFS)
  full_relief          : control -- default vocabulary WITH that extra tier,
                         to confirm it is inert and the deltas are vocabulary

`full` is recomputed here and cross-checked against ablation_results.json so
a regression in the shared path is caught rather than reported.

Output: paper/teledata_ablation_basis.json + a table on stdout.
"""
from __future__ import annotations

import json
import math
import signal
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import porter
from compile_porter import parse_qasm2, hardware_for_name, build_initial_layout

TELESABRE_CIRCUITS = _HERE.parent / "other" / "telesabre" / "circuits"
SUITES = [("25", "A", "qasm_25"), ("64", "H", "qasm_64"), ("80", "H", "qasm_80")]
FILES = {
    "64": {"qnn": "qnn_OLD_DEEP_nativegates_ibm_qiskit_opt3_64.qasm.bak"},
    "80": {"qnn": "qnn_nativegates_ibm_qiskit_opt3_80_DEEP.qasm"},
}
CIRCUITS_BY_SUITE = {
    # The 25q suite holds only these six; 64q and 80q add three more, and
    # since 2026-08-31 the ablation covers all nine where they exist so the
    # table is not a subset of the main comparison.
    "25": ["ae", "ghz", "graphstate", "qft", "qnn", "random"],
    "64": ["ae", "ghz", "graphstate", "qft", "qnn", "random",
           "qpeexact", "qaoa", "multiplier"],
    "80": ["ae", "ghz", "graphstate", "qft", "qnn", "random",
           "qpeexact", "qaoa", "multiplier"],
}
CIRCUITS = CIRCUITS_BY_SUITE["25"]  # back-compat for callers that import it
CONFIGS = {
    "full": dict(),
    "full_relief": dict(capacity_relief_from_adjacent_blocked=True),
    "teledata_only": dict(telegate_enabled=False),
    "teledata_only_relief": dict(telegate_enabled=False,
                                 capacity_relief_from_adjacent_blocked=True),
}
TIMEOUT_S = 3600


class _Timeout(Exception):
    pass


def main() -> None:
    signal.signal(signal.SIGALRM, lambda s, f: (_ for _ in ()).throw(_Timeout()))
    ref = {(r["suite"], r["circuit"]): r["out"]["full"].get("epr")
           for r in json.load(open(_HERE / "ablation_results.json"))}

    rows = []
    for suite, arch, sub in SUITES:
        _, hw = hardware_for_name(arch)
        fmin = porter.RouterConfig().min_free_before_teleport
        for circ in CIRCUITS_BY_SUITE[suite]:
            fname = FILES.get(suite, {}).get(circ) or \
                f"{circ}_nativegates_ibm_qiskit_opt3_{suite}.qasm"
            path = TELESABRE_CIRCUITS / sub / fname
            if not path.exists():
                print(f"MISSING {path}", flush=True)
                continue
            gates, nl = parse_qasm2(path)
            out = {}
            for label, kw in CONFIGS.items():
                layout = build_initial_layout(gates, hw, nl, min_free_per_core=fmin)
                cfg = porter.RouterConfig(random_seed=0, **kw)
                t0 = time.perf_counter()
                signal.alarm(TIMEOUT_S)
                try:
                    st = porter.PorterRouter(hw, cfg).compile(gates, layout)
                    s = st.stats
                    out[label] = dict(epr=s.epr, teleports=s.teleport_count,
                                      telegates=s.telegate_count,
                                      packets=s.telegate_packet_count,
                                      local_swaps=s.local_swap_count,
                                      depth=s.depth,
                                      seconds=round(time.perf_counter() - t0, 3))
                except (RuntimeError, ValueError, _Timeout) as e:
                    out[label] = dict(error=f"{type(e).__name__}: {str(e)[:120]}",
                                      seconds=round(time.perf_counter() - t0, 3))
                finally:
                    signal.alarm(0)

            r = ref.get((suite, circ))
            if r is not None and out["full"].get("epr") not in (None, r):
                out["full"]["REGRESSION_vs_ablation_results"] = r
            rows.append(dict(suite=suite, circuit=circ, ref_epr=r, out=out))
            vals = "  ".join(f"{k}={out[k].get('epr', 'ERR')!s:>7}" for k in CONFIGS)
            print(f"{suite:>3}q {circ:<11} {vals}  (ref={r})", flush=True)
            (_HERE / "paper" / "teledata_ablation_basis.json").write_text(
                json.dumps(rows, indent=1))

    print("\n--- gmean EPR, each leg vs full on the leg's own completing subset ---",
          flush=True)

    def gm(key, subset):
        vs = [r["out"][key]["epr"] for r in subset]
        return math.exp(sum(math.log(max(v, 1)) for v in vs) / len(vs)) if vs else float("nan")

    for k in CONFIGS:
        sub = [r for r in rows if "epr" in r["out"][k] and "epr" in r["out"]["full"]]
        if not sub:
            print(f"  {k:<22} no completing instances", flush=True)
            continue
        print(f"  {k:<22} {gm(k, sub):8.1f}  vs full {gm('full', sub):8.1f} "
              f"({100*(gm(k, sub)/gm('full', sub) - 1):+.1f}%)  on {len(sub)}/{len(rows)}",
              flush=True)
        dead = [f"{r['suite']}q {r['circuit']}" for r in rows if "epr" not in r["out"][k]]
        if dead:
            print(f"  {'':<22} did not complete: {', '.join(dead)}", flush=True)


if __name__ == "__main__":
    main()
