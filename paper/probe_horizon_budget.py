#!/usr/bin/env python3
"""Reproduce the speculative-budget boundary named in Section IV-C.

Horizon selection routes cfg's own horizon first, unguarded, and that route's
wall time sets the share each speculative candidate gets:

    budget = max(SPECULATIVE_MIN_SECONDS, ceil(SPECULATIVE_TIME_FACTOR * t_first))

360-qubit QPEexact reaches 1224 EPR pairs at L_tp = 128, but its L=128 route
costs slightly more than that share, so whether the protocol returns 1224 or
falls back to the configured horizon and 2342 depends on the machine.  This
script measures all three quantities so the claim is checkable rather than
quoted.

    python probe_horizon_budget.py

Prints the default-horizon route, the derived budget, the L=128 route, and
whether L=128 fits.  The released tab:scaleup value is 1224.
"""
import math, os, sys, time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "experiments"))

import compile_porter as cdr           # noqa: E402
import porter as dr                    # noqa: E402
import bench_scaleup as B              # noqa: E402


def _route_at(hw, circuit, n, horizon):
    cfg = dr.RouterConfig(random_seed=0, dag_extended_max_layers=horizon)
    layout = cdr.build_initial_layout(
        circuit, hw, n, min_free_per_core=cfg.min_free_before_teleport)
    t0 = time.perf_counter()
    state, _ = cdr.route(hw, cfg, circuit, layout, selection=False)
    return state.stats.epr, time.perf_counter() - t0


def main():
    spec = B.SUITES["360"]
    _, hw = cdr.hardware_from_device_json(B.DEVICES / f"{spec['device']}.json")
    circuit, n = cdr.parse_qasm2(spec["circuit_dir"] / spec["files"][1])

    default = dr.RouterConfig().dag_extended_max_layers
    epr_d, t_d = _route_at(hw, circuit, n, default)
    print(f"360q QPEexact at the configured L_tp={default}: "
          f"{epr_d} EPR in {t_d:.1f} s", flush=True)

    budget = max(int(cdr.SPECULATIVE_MIN_SECONDS),
                 math.ceil(cdr.SPECULATIVE_TIME_FACTOR * t_d))
    print(f"speculative share per candidate: "
          f"max({cdr.SPECULATIVE_MIN_SECONDS}, ceil("
          f"{cdr.SPECULATIVE_TIME_FACTOR} x {t_d:.2f})) = {budget} s", flush=True)

    epr_l, t_l = _route_at(hw, circuit, n, 128)
    print(f"360q QPEexact at L_tp=128: {epr_l} EPR in {t_l:.1f} s", flush=True)
    print(f"-> L=128 {'FITS the share' if t_l <= budget else 'EXCEEDS the share'}"
          f" ({t_l:.1f} s against {budget} s); the protocol returns "
          f"{epr_l if t_l <= budget else epr_d}", flush=True)
    print("released tab:scaleup value: 1224", flush=True)


if __name__ == "__main__":
    main()
