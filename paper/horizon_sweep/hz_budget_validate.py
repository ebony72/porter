"""Definitive validation of the stall guard, under the protocol PORTER ships.

For every one of the 48 instances, route twice from the same layout under
`route(..., selection=True)` -- once with the guard disabled (the shipped
behaviour) and once with it at 1,000 -- and compare:

  * the emitted op stream, byte for byte (SHA over the serialized ops)
  * EPR, SWAP count, depth and the seeded tie-break counter
  * which horizon the protocol selected
  * wall time

The guard may only ever turn a route that was going to be abandoned anyway
into one abandoned sooner.  If any selected stream changes, it is unsafe.
"""
import hashlib, json, time, argparse
import multiprocessing as mp
import hz_head as H

OUT = H.HERE / "budget_validation.jsonl"



def sha(state):
    ops = [[o.op_type, [g.gid for g in o.gates], list(o.qubits), list(o.physical_qubits),
            list(o.cores), list(o.path), o.epr_cost] for o in state.emitted]
    return hashlib.sha256(json.dumps(ops, sort_keys=True, default=str).encode()).hexdigest()[:16]


def one(key):
    hw, gates, n = H.load(key)
    out = {"key": key}
    for tag, factor in (("clock", 0.0), ("work", 7.0)):
        H.cp.SPECULATIVE_WORK_FACTOR = factor
        cfg = H.porter.RouterConfig()
        lay = H.cp.build_initial_layout(gates, hw, n, min_free_per_core=cfg.min_free_before_teleport)
        t0 = time.perf_counter()
        try:
            st, info = H.cp.route(hw, cfg, list(gates), lay, selection=True)
            rec = {"status": "completed", "epr": st.stats.epr, "sha": sha(st),
                   "swaps": st.stats.local_swap_count, "depth": st.stats.depth,
                   "ties": st.stats.seeded_tie_break_count,
                   "horizon": info.get("chosen_horizon"),
                   "horizon_eprs": {str(k): v for k, v in (info.get("horizon_eprs") or {}).items()},
                   "failed": sorted((info.get("failed_horizons") or {}).keys(), key=str)}
        except Exception as e:                                # noqa: BLE001
            rec = {"status": f"failed:{type(e).__name__}", "epr": None, "sha": None,
                   "error": str(e)[:160]}
        rec["seconds"] = round(time.perf_counter() - t0, 2)
        out[tag] = rec
    a, b = out["clock"], out["work"]
    out["identical"] = (a.get("sha") == b.get("sha") and a.get("epr") == b.get("epr")
                        and a.get("swaps") == b.get("swaps") and a.get("depth") == b.get("depth")
                        and a.get("ties") == b.get("ties") and a.get("horizon") == b.get("horizon"))
    out["speedup"] = round(a["seconds"] / max(b["seconds"], 1e-6), 2)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    done = set()
    if OUT.exists():
        done = {json.loads(l)["key"] for l in OUT.read_text().splitlines() if l.strip()}
    keys = [k for k in H.instance_keys() if k not in done]
    print(f"{len(keys)} instances to validate (guard off vs on, protocol route)", flush=True)
    with mp.get_context("spawn").Pool(a.workers) as pool, OUT.open("a") as f:
        for i, r in enumerate(pool.imap_unordered(one, keys), 1):
            f.write(json.dumps(r) + "\n"); f.flush()
            print(f"[{i}/{len(keys)}] {r['key']:<26} "
                  f"clock={r['clock']['status']}/{r['clock']['epr']} ({r['clock']['seconds']}s)  "
                  f"work={r['work']['status']}/{r['work']['epr']} ({r['work']['seconds']}s)  "
                  f"{'IDENTICAL' if r['identical'] else 'DIFFERS'}  {r['speedup']}x", flush=True)
    print("GUARD VALIDATION DONE", flush=True)


if __name__ == "__main__":
    main()
