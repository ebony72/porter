"""Does dSABRE's intra-core routing strategy help PORTER?

Six arms over all 48 paper instances, one forward pass at the configured
horizon (selection=False) so the local stage is the only thing that varies.
Every completing stream is replay-verified.
"""
import sys, json, time, argparse
import multiprocessing as mp
sys.path.insert(0, "/Users/sanjiangli/Documents/pyzoo/SFC")
sys.path.insert(0, "/Users/sanjiangli/Documents/pyzoo/SFC/paper/horizon_sweep")

OUT = "/private/tmp/claude-504/-Users-sanjiangli-Documents-pyzoo-SFC/198b52a7-cff4-4249-bd07-be4853d9b249/scratchpad/local_ablation.jsonl"
GUARD = 300

ARMS = {
    "porter":         dict(),
    "percore":        dict(local_score_per_core=True),
    "decay":          dict(local_ext_decay=0.9),
    "percore_decay":  dict(local_score_per_core=True, local_ext_decay=0.9),
    "dsabre":         dict(local_score_per_core=True, local_per_core_parallel=True,
                           local_ext_decay=0.9),
    "dsabre_w025":    dict(local_score_per_core=True, local_per_core_parallel=True,
                           local_ext_decay=0.9, local_swap_extended_weight=0.25),
    # round 2: decay in isolation (the first run's `decay` arm predated the fix
    # that wired local_ext_decay into the chip-wide path, so it was a no-op)
    "decay_fixed":    dict(local_ext_decay=0.9),
    "percore_w025":   dict(local_score_per_core=True, local_swap_extended_weight=0.25),
    "parallel_only":  dict(local_score_per_core=True, local_per_core_parallel=True),
    # round 4 control: per-core normalisation drops the extended term's
    # normaliser from |E| to |E_c|, which is arithmetically just a larger
    # effective lookahead weight.  If raising the chip-wide weight recovers the
    # gain, the finding is a mistuned weight, not dSABRE's per-core structure.
    "w12":            dict(local_swap_extended_weight=1.2),
    "w16":            dict(local_swap_extended_weight=1.6),
    "w24":            dict(local_swap_extended_weight=2.4),
    "percore_w16":    dict(local_score_per_core=True, local_swap_extended_weight=1.6),
}


def cell(task):
    key, arm, selection = task
    import hz_common as H
    import porter
    hw, gates, n = H.load(key)
    cfg = porter.RouterConfig(**ARMS[arm])
    lay = H.cp.build_initial_layout(gates, hw, n, min_free_per_core=cfg.min_free_before_teleport)
    t0 = time.perf_counter()
    try:
        with H.cp._horizon_time_limit(GUARD):
            st, info = H.cp.route(hw, cfg, list(gates), lay, selection=selection)
        H.vp.verify_state(hw, lay, list(gates), st)
        r = {"epr": st.stats.epr, "swaps": st.stats.local_swap_count,
             "depth": st.stats.depth, "status": "completed",
             "L": info.get("chosen_horizon")}
    except Exception as e:                                    # noqa: BLE001
        r = {"epr": None, "status": f"{type(e).__name__}"}
    r.update(key=key, arm=arm, selection=selection,
             seconds=round(time.perf_counter() - t0, 3))
    return r


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selection", action="store_true")
    ap.add_argument("--arms", default=",".join(ARMS))
    a = ap.parse_args()
    import hz_common as H
    keys = H.instance_keys()
    arms = a.arms.split(",")
    tasks = [(k, arm, a.selection) for k in keys for arm in arms]
    print(f"{len(tasks)} routes ({len(keys)} instances x {len(arms)} arms), "
          f"selection={a.selection}", flush=True)
    done = 0
    with open(OUT, "a") as f, mp.Pool(6) as pool:
        for r in pool.imap_unordered(cell, tasks):
            f.write(json.dumps(r) + "\n"); f.flush()
            done += 1
            if done % 24 == 0:
                print(f"  {done}/{len(tasks)}", flush=True)
    print("done", flush=True)
