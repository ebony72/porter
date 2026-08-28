"""64q action-vocabulary ablation: PORTER's full action set vs TeleData only.

Runs PORTER's own protocol (canonical temporal-locality initial layout,
router seed 0, single forward pass) over the nine-circuit 64q suite under
three action vocabularies:

  full          : default RouterConfig (TeleData + TeleGate + TeleGatePacket)
  no_packets    : max_packet_size=1  -- packets forbidden, single TeleGates
                  still available (the paper's existing no-packets ablation)
  teledata_only : telegate_enabled=False -- no TeleGate, no TeleGatePacket;
                  state teleportation is the only inter-core primitive,
                  i.e. dSABRE's action vocabulary inside PORTER's framework

The full leg is cross-checked against paper/compare_results.json so a
regression in the shared code path is caught rather than reported.

Output: paper/teledata_only_results.json + a table on stdout.
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

CIRCUIT_DIR = _HERE.parent / "other" / "telesabre" / "circuits" / "qasm_64"
ARCH = "H"
FILES = [
    ("ae", "ae_nativegates_ibm_qiskit_opt3_64.qasm"),
    ("ghz", "ghz_nativegates_ibm_qiskit_opt3_64.qasm"),
    ("graphstate", "graphstate_nativegates_ibm_qiskit_opt3_64.qasm"),
    ("qft", "qft_nativegates_ibm_qiskit_opt3_64.qasm"),
    ("qnn_OLD_DEEP", "qnn_OLD_DEEP_nativegates_ibm_qiskit_opt3_64.qasm.bak"),
    ("random", "random_nativegates_ibm_qiskit_opt3_64.qasm"),
    ("qpeexact", "qpeexact_nativegates_ibm_qiskit_opt3_64.qasm"),
    ("qaoa", "qaoa_nativegates_ibm_qiskit_opt3_64.qasm"),
    ("multiplier", "multiplier_nativegates_ibm_qiskit_opt3_64.qasm"),
]
CONFIGS = {
    "full": dict(),
    "no_packets": dict(max_packet_size=1),
    # Control: default vocabulary WITH the extra relief tier, so the
    # teledata-only column can be attributed to the action vocabulary rather
    # than to the relief tier that had to be added to make it terminate.
    # (Measured inert: identical EPR to `full` on all nine circuits.)
    "full_relief": dict(capacity_relief_from_adjacent_blocked=True),
    "teledata_only": dict(telegate_enabled=False),
    # Same vocabulary, plus the extra relief tier that the TeleGate was
    # silently providing: with no TeleGate, an all-adjacent capacity-blocked
    # front has no normal plan and the tail-relief BFS is never offered the
    # adjacent-blocked candidates, so the router deadlocks.
    "teledata_only_relief": dict(telegate_enabled=False,
                                 capacity_relief_from_adjacent_blocked=True),
}
TIMEOUT_S = 1800


class _Timeout(Exception):
    pass


def main() -> None:
    signal.signal(signal.SIGALRM, lambda s, f: (_ for _ in ()).throw(_Timeout()))
    reference = {
        r["circuit"]: r["sfc"]
        for r in json.load(open(_HERE / "paper" / "compare_results.json"))
        if r["suite"] == "64"
    }

    _, hw = hardware_for_name(ARCH)
    fmin = porter.RouterConfig().min_free_before_teleport
    rows = []
    for cname, fname in FILES:
        gates, nl = parse_qasm2(CIRCUIT_DIR / fname)
        out = {}
        for label, kw in CONFIGS.items():
            layout = build_initial_layout(gates, hw, nl, min_free_per_core=fmin)
            cfg = porter.RouterConfig(random_seed=0, **kw)
            router = porter.PorterRouter(hw, cfg)
            t0 = time.perf_counter()
            signal.alarm(TIMEOUT_S)
            try:
                st = router.compile(gates, layout)
                s = st.stats
                out[label] = dict(
                    epr=s.epr,
                    teleports=s.teleport_count,
                    tele_normal=s.teleport_normal_count,
                    tele_blocked=s.teleport_blocked_count,
                    tele_relief=s.teleport_capacity_relief_count,
                    telegates=s.telegate_count,
                    packets=s.telegate_packet_count,
                    local_swaps=s.local_swap_count,
                    depth=s.depth,
                    seconds=round(time.perf_counter() - t0, 3),
                )
            except (RuntimeError, ValueError, _Timeout) as e:
                out[label] = dict(error=f"{type(e).__name__}: {str(e)[:160]}",
                                  seconds=round(time.perf_counter() - t0, 3))
            finally:
                signal.alarm(0)

        ref = reference.get(cname, {})
        if "epr" in ref and out["full"].get("epr") not in (None, ref["epr"]):
            out["full"]["REGRESSION_vs_compare_results"] = ref["epr"]
        rows.append(dict(circuit=cname, ref_epr=ref.get("epr"), out=out))

        vals = "  ".join(f"{k}={out[k].get('epr', 'ERR')!s:>6}" for k in CONFIGS)
        print(f"{cname:<13} {vals}   (ref={ref.get('epr')})", flush=True)
        for k in CONFIGS:
            if "error" in out[k]:
                print(f"    {k}: {out[k]['error']}", flush=True)

    (_HERE / "paper" / "teledata_only_results.json").write_text(json.dumps(rows, indent=1))

    def gm(key, subset):
        vs = [r["out"][key]["epr"] for r in subset]
        return math.exp(sum(math.log(max(v, 1)) for v in vs) / len(vs)) if vs else float("nan")

    # Each leg is summarised over the circuits *it* completes, paired against
    # `full` on that same subset -- a leg that deadlocks on 7/9 must not be
    # compared on a gmean taken over the 2 it survives.
    print("\n--- gmean EPR, each leg vs full on the leg's own completing subset ---",
          flush=True)
    for k in CONFIGS:
        subset = [r for r in rows if "epr" in r["out"][k] and "epr" in r["out"]["full"]]
        if not subset:
            print(f"  {k:<22} no completing circuits", flush=True)
            continue
        base = gm("full", subset)
        print(f"  {k:<22} {gm(k, subset):8.1f}  vs full {base:8.1f} "
              f"({100*(gm(k, subset)/base - 1):+.1f}%)  on {len(subset)}/{len(rows)} circuits",
              flush=True)
        dead = [r["circuit"] for r in rows if "epr" not in r["out"][k]]
        if dead:
            print(f"  {'':<22} did not complete: {', '.join(dead)}", flush=True)


if __name__ == "__main__":
    main()
