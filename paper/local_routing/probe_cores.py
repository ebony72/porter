"""How many distinct cores are active in PORTER's local stage per call?

dSABRE applies one SWAP per active core per iteration; PORTER applies one
chip-wide.  The headroom for that change is exactly the distribution below.
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
orig = PorterRouter._generate_local_swap_actions

print(f"{'instance':22s} {'calls':>6s} {'mean cores':>10s} {'max':>4s}  distribution", flush=True)
for key in KEYS:
    hw, gates, n = H.load(key)
    cfg = porter.RouterConfig()
    lay = H.cp.build_initial_layout(gates, hw, n, min_free_per_core=cfg.min_free_before_teleport)
    hist = collections.Counter()
    fronts = []
    def gen(self, state, info, _o=orig):
        fg = [g for g in info.local_cx_need_swap if g.is_cx()]
        cores = {state.layout.core_of(g.qubits[0]) for g in fg}
        if fg:
            hist[len(cores)] += 1
            fronts.append(len(fg))
        return _o(self, state, info)
    PorterRouter._generate_local_swap_actions = gen
    try:
        H.cp.route(hw, cfg, list(gates), lay, selection=False)
    finally:
        PorterRouter._generate_local_swap_actions = orig
    tot = sum(hist.values())
    mean = sum(k*v for k,v in hist.items())/max(tot,1)
    dist = " ".join(f"{k}:{100*v/tot:.0f}%" for k,v in sorted(hist.items()))
    print(f"{key:22s} {tot:6d} {mean:10.2f} {max(hist) if hist else 0:4d}  {dist}", flush=True)
    print(f"{'':22s} {'':6s} mean |F_local| = {sum(fronts)/max(len(fronts),1):.2f}", flush=True)
