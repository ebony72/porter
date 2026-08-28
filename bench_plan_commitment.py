"""Unit-of-commitment ablation: is the plan-committed remote stage load-bearing?

PORTER's headline contribution is that it commits to a whole RemotePlan and
generates preparation SWAPs for that plan alone, rather than re-scoring the
front after every move.  dSABRE's unit of commitment is one teleport hop,
re-scored every iteration (it ships commit_bonus=0, commit_hard_lock=False).
Every other experiment in the paper varies the action vocabulary, the relief
tiers, or the initial layout -- none isolates the commitment itself.

  committed    default RouterConfig (the shipped protocol)
  hopwise      remote_plan_commitment=False: the committed loop returns after
               ONE round of preparation SWAPs, so compile() re-classifies the
               front and re-generates/re-scores every plan before the next
               move.  Identical scoring, identical plan set, identical relief
               tiers -- only the persistence of the choice differs.

Run on the paper's ablation basis (6 circuits x 25/64/80q, canonical
temporal-locality layout, seed 0) plus the three 64q class-completion
circuits, so it shares a basis with tab:ablation.

Output: paper/plan_commitment_results.json
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

CIRCUITS_ROOT = _HERE.parent / "other" / "telesabre" / "circuits"
SUITES = [("25", "A", "qasm_25",
           ["ae", "ghz", "graphstate", "qft", "qnn", "random"]),
          ("64", "H", "qasm_64",
           ["ae", "ghz", "graphstate", "qft", "qnn", "random",
            "qpeexact", "qaoa", "multiplier"]),
          ("80", "H", "qasm_80",
           ["ae", "ghz", "graphstate", "qft", "qnn", "random"])]
FILES = {"64": {"qnn": "qnn_OLD_DEEP_nativegates_ibm_qiskit_opt3_64.qasm.bak"},
         "80": {"qnn": "qnn_nativegates_ibm_qiskit_opt3_80_DEEP.qasm"}}
CONFIGS = {"committed": dict(), "hopwise": dict(remote_plan_commitment=False)}
TIMEOUT_S = 1800


class _Timeout(Exception):
    pass


def main() -> None:
    signal.signal(signal.SIGALRM, lambda s, f: (_ for _ in ()).throw(_Timeout()))
    ref = {(r["suite"], r["circuit"]): r["out"]["full"].get("epr")
           for r in json.load(open(_HERE / "ablation_results.json"))}

    rows = []
    for suite, arch, sub, circs in SUITES:
        _, hw = hardware_for_name(arch)
        fmin = porter.RouterConfig().min_free_before_teleport
        for circ in circs:
            fname = FILES.get(suite, {}).get(circ) or \
                f"{circ}_nativegates_ibm_qiskit_opt3_{suite}.qasm"
            path = CIRCUITS_ROOT / sub / fname
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
                    out[label] = dict(epr=s.epr, swaps=s.local_swap_count,
                                      teleports=s.teleport_count,
                                      telegates=s.telegate_count,
                                      packets=s.telegate_packet_count,
                                      depth=s.depth, steps=st.step,
                                      seconds=round(time.perf_counter() - t0, 3))
                except (RuntimeError, ValueError, _Timeout) as e:
                    out[label] = dict(error=f"{type(e).__name__}: {str(e)[:120]}",
                                      seconds=round(time.perf_counter() - t0, 3))
                finally:
                    signal.alarm(0)
            r = ref.get((suite, circ))
            if r is not None and out["committed"].get("epr") not in (None, r):
                out["committed"]["REGRESSION_vs_ablation_results"] = r
            rows.append(dict(suite=suite, circuit=circ, ref_epr=r, out=out))
            c, h = (out[k].get("epr", "ERR") for k in CONFIGS)
            d = (f"{100*(h/c-1):+.1f}%" if isinstance(c, int) and isinstance(h, int)
                 else "  --")
            print(f"{suite:>3}q {circ:<11} committed={c!s:>7} hopwise={h!s:>7} {d:>8}"
                  f"   (ref={r})", flush=True)
            if "error" in out["hopwise"]:
                print(f"      hopwise: {out['hopwise']['error']}", flush=True)
            (_HERE / "paper" / "plan_commitment_results.json").write_text(
                json.dumps(rows, indent=1))

    def gm(v):
        return math.exp(sum(math.log(max(x, 1)) for x in v) / len(v))

    done = [r for r in rows if all("epr" in r["out"][k] for k in CONFIGS)]
    print(f"\n=== hopwise completes {len(done)}/{len(rows)} ===", flush=True)
    if done:
        c = gm([r["out"]["committed"]["epr"] for r in done])
        h = gm([r["out"]["hopwise"]["epr"] for r in done])
        print(f"  gmean EPR  committed={c:.1f}  hopwise={h:.1f}  "
              f"({100*(h/c-1):+.1f}%)", flush=True)
        cs = gm([r["out"]["committed"]["seconds"] for r in done])
        hs = gm([r["out"]["hopwise"]["seconds"] for r in done])
        print(f"  gmean time committed={cs:.2f}s hopwise={hs:.2f}s "
              f"({hs/cs:.2f}x)", flush=True)
        w = [r["circuit"] for r in done
             if r["out"]["hopwise"]["epr"] < r["out"]["committed"]["epr"]]
        l = [r["circuit"] for r in done
             if r["out"]["hopwise"]["epr"] > r["out"]["committed"]["epr"]]
        print(f"  hopwise better on {len(w)}, worse on {len(l)}, "
              f"tied on {len(done)-len(w)-len(l)}", flush=True)
    dead = [f"{r['suite']}q {r['circuit']}" for r in rows
            if "epr" not in r["out"]["hopwise"]]
    if dead:
        print(f"  hopwise did not complete: {', '.join(dead)}", flush=True)


if __name__ == "__main__":
    main()
