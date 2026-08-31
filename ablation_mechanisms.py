"""Mechanism ablation for PORTER: isolate the EPR contribution of the
same-control telegate-packet primitive and the two-tier capacity relief,
each toggled off via RouterConfig, all on the canonical temporal-locality
initial layout at router seed 0 (single run, no layout search).

Configs:
  full          : default RouterConfig (packets + both relief tiers on)
  no-packets    : max_packet_size=1 (a packet needs >=2 remote CX, so this
                  forbids packet formation; each shared-control remote CX
                  falls back to a single telegate)
  no-relief     : capacity_relief_assist_enabled=False and
                  capacity_relief_chain_enabled=False (blocked plans can no
                  longer pull qubits toward reservoir cores)

Emits EPR per (suite, circuit, config) and per-suite / overall geometric
means, so the evaluation can attribute EPR to each claimed contribution.
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
# Per-suite QNN overrides: the deep ZZFeatureMap QNN, not the shallow chain the
# stock generator emits (64q: real MQT-1.1.0 file; 80q: faithful reconstruction).
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
    "no_packets": dict(max_packet_size=1),
    "no_relief": dict(capacity_relief_assist_enabled=False,
                      capacity_relief_chain_enabled=False),
}


class _Timeout(Exception):
    pass


def main() -> None:
    signal.signal(signal.SIGALRM, lambda s, f: (_ for _ in ()).throw(_Timeout()))
    rows = []
    for suite, arch, sub in SUITES:
        _, hw = hardware_for_name(arch)
        for circ in CIRCUITS_BY_SUITE[suite]:
            fname = FILES.get(suite, {}).get(circ)
            fname = fname or f"{circ}_nativegates_ibm_qiskit_opt3_{suite}.qasm"
            path = TELESABRE_CIRCUITS / sub / fname
            if not path.exists():
                continue
            gates, nl = parse_qasm2(path)
            fmin = porter.RouterConfig().min_free_before_teleport
            layout_src = build_initial_layout(gates, hw, nl, min_free_per_core=fmin)
            out = {}
            for cname, kw in CONFIGS.items():
                # rebuild layout each time (compile mutates it)
                layout = build_initial_layout(gates, hw, nl, min_free_per_core=fmin)
                cfg = porter.RouterConfig(random_seed=0, **kw)
                router = porter.PorterRouter(hw, cfg)
                signal.alarm(900)
                try:
                    st = router.compile(gates, layout)
                    out[cname] = dict(epr=st.stats.epr,
                                      packets=st.stats.telegate_packet_count,
                                      telegates=st.stats.telegate_count)
                except (RuntimeError, _Timeout) as e:
                    out[cname] = dict(error=str(e)[:60])
                finally:
                    signal.alarm(0)
            rows.append(dict(suite=suite, circuit=circ, out=out))
            e = {k: out[k].get("epr", "ERR") for k in CONFIGS}
            print(f"{suite:>3}q {circ:<11} full={e['full']!s:>6} "
                  f"no_packets={e['no_packets']!s:>6} no_relief={e['no_relief']!s:>6} "
                  f"(pk={out['full'].get('packets')})", flush=True)
    (_HERE / "ablation_results.json").write_text(json.dumps(rows, indent=1))

    def gm(key):
        vs = [r["out"][key]["epr"] for r in rows
              if all("epr" in r["out"][k] for k in CONFIGS)]
        return math.exp(sum(math.log(v) for v in vs) / len(vs)) if vs else None
    n = sum(1 for r in rows if all("epr" in r["out"][k] for k in CONFIGS))
    print(f"\ngmean over {n} complete rows: "
          + " ".join(f"{k}={gm(k):.1f}" for k in CONFIGS), flush=True)


if __name__ == "__main__":
    main()
