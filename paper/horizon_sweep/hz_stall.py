"""Longest run of router iterations with no gate retired, over every instance
that completes -- the number a stall guard's threshold has to clear."""
import json, sys
import hz_common as H
R = H.porter.PorterRouter
rm, cf = R._remove_gate_ids, R._classify_front
OUT = H.HERE / "stall_gaps.json"

def measure(key, L):
    st = {"since": 0, "iters": 0, "worst": 0}
    def p_rm(self, state, gids):
        before = len(state.dag_active); out = rm(self, state, gids)
        if len(state.dag_active) < before:
            st["worst"] = max(st["worst"], st["since"]); st["since"] = 0
        return out
    def p_cf(self, *a, **k):
        st["iters"] += 1; st["since"] += 1
        return cf(self, *a, **k)
    R._remove_gate_ids, R._classify_front = p_rm, p_cf
    try:
        hw, gates, n = H.load(key); cfg = H.porter.RouterConfig(dag_extended_max_layers=L)
        lay = H.cp.build_initial_layout(gates, hw, n, min_free_per_core=cfg.min_free_before_teleport)
        with H.cp._horizon_time_limit(300):
            s, _ = H.cp.route(hw, cfg, list(gates), lay, selection=False)
        st["worst"] = max(st["worst"], st["since"])
        return {"key": key, "L": L, "status": "completed", "epr": s.stats.epr,
                "iters": st["iters"], "worst_gap": st["worst"]}
    except Exception as e:                                    # noqa: BLE001
        return {"key": key, "L": L, "status": type(e).__name__,
                "iters": st["iters"], "worst_gap": max(st["worst"], st["since"])}
    finally:
        R._remove_gate_ids, R._classify_front = rm, cf

res = json.loads(OUT.read_text()) if OUT.exists() else []
seen = {(r["key"], r["L"]) for r in res}
for L in (16, 128):
    for key in H.instance_keys():
        if (key, L) in seen: continue
        r = measure(key, L); res.append(r)
        OUT.write_text(json.dumps(res, indent=1))
        print(f"  {r['key']:<26} L={r['L']:<4} {r['status']:<16} iters={r['iters']:>7} "
              f"worst gap={r['worst_gap']}", flush=True)
print("STALL SWEEP DONE", flush=True)
