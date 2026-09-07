"""PORTER's local extended set is chip-wide and undiscounted.

dSABRE's E_c is (i) restricted to the core being routed and (ii) weighted
decay^depth.  Measure how much each matters: what fraction of PORTER's
extended set can the candidate swap actually move, and how deep it reaches.
"""
import sys, collections
from pathlib import Path as _P
_ROOT = _P(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "paper" / "horizon_sweep"))
import hz_common as H
import porter
from porter.router import PorterRouter

KEYS = ["main/25/ae", "main/25/random", "main/64/ae", "main/64/qft",
        "main/64/qaoa", "main/64/multiplier", "main/80/qft", "main/80/qpeexact"]
orig_gen = PorterRouter._generate_local_swap_actions
orig_ext = PorterRouter._local_swap_extended_local_cx_gates

print(f"{'instance':22s} {'calls':>6s} {'|E|':>6s} {'|E_c|':>6s} {'in-core%':>8s} {'dilution':>8s}", flush=True)
for key in KEYS:
    hw, gates, n = H.load(key)
    cfg = porter.RouterConfig()
    lay = H.cp.build_initial_layout(gates, hw, n, min_free_per_core=cfg.min_free_before_teleport)
    tot_e = tot_ec = calls = 0
    def gen(self, state, info, _o=orig_gen):
        global tot_e, tot_ec, calls
        fg = [g for g in info.local_cx_need_swap if g.is_cx()]
        if fg:
            cores = {state.layout.core_of(g.qubits[0]) for g in fg}
            ext = orig_ext(self, state, state.layout, {g.gid for g in fg})
            in_core = [g for g in ext if state.layout.core_of(g.qubits[0]) in cores]
            tot_e += len(ext); tot_ec += len(in_core); calls += 1
        return _o(self, state, info)
    PorterRouter._generate_local_swap_actions = gen
    try:
        H.cp.route(hw, cfg, list(gates), lay, selection=False)
    finally:
        PorterRouter._generate_local_swap_actions = orig_gen
    e = tot_e/max(calls,1); ec = tot_ec/max(calls,1)
    print(f"{key:22s} {calls:6d} {e:6.2f} {ec:6.2f} {100*ec/max(e,1e-9):8.1f} "
          f"{e/max(ec,1e-9):8.2f}x", flush=True)
