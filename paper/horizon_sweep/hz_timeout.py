"""Q4: why do routes time out, and what happens with more time?

Re-runs every cell the grid recorded as a timeout under a 6x guard (1800 s),
with a progress probe attached, so each failure can be classified rather than
just recorded:

  completed_with_more_time -- it was converging, the 300 s guard was the only
                              thing stopping it
  livelock                 -- retired-gate count is flat while EPR/SWAP counts
                              keep growing (the signature CLAUDE.md records)
  slow                     -- still making progress at 1800 s, just far too
                              slow to be usable

The probe wraps ``_remove_gate_ids``, the single retirement point, and samples
(wall time, gates retired, EPR, SWAPs) on a fixed stride, so it adds one
counter increment per retirement and cannot change any routing decision.
"""
import json, time, sys, argparse
import multiprocessing as mp
import hz_common as H

GUARD = 900
STRIDE = 2.0                      # seconds between progress samples
OUT = H.HERE / "hz_timeout.jsonl"


def run_task(task):
    key, L, arm, wmin, gamma = task
    hw, gates, n = H.load(key)
    cfg = H.porter.RouterConfig(dag_extended_max_layers=L,
                                teleport_lookahead_weight_floor=wmin,
                                teleport_lookahead_decay=gamma)
    lay = H.cp.build_initial_layout(gates, hw, n, min_free_per_core=cfg.min_free_before_teleport)
    R = H.porter.PorterRouter
    pristine = R._remove_gate_ids
    total = len([g for g in gates])
    trace = []
    st = {"retired": 0, "next": 0.0, "t0": time.perf_counter(), "state": None}

    def probe(self, state, gids):
        st["retired"] += len(gids)
        st["state"] = state
        now = time.perf_counter() - st["t0"]
        if now >= st["next"]:
            st["next"] = now + STRIDE
            trace.append((round(now, 1), st["retired"],
                          state.stats.epr, state.stats.local_swap_count))
        return pristine(self, state, gids)

    R._remove_gate_ids = probe
    rec = {"key": key, "L": L, "arm": arm, "guard": GUARD, "gates_total": total}
    t0 = time.perf_counter()
    try:
        with H.cp._horizon_time_limit(GUARD):
            state, _ = H.cp.route(hw, cfg, list(gates), lay, selection=False)
        rec["status"] = "completed"; rec["epr"] = state.stats.epr
    except H.cp.HorizonTimeout:
        rec["status"] = "timeout"; rec["epr"] = None
    except RuntimeError as e:
        rec["status"] = "livelock" if "max_iterations" in str(e) else "error"
        rec["epr"] = None; rec["error"] = str(e)[:160]
    except Exception as e:                                   # noqa: BLE001
        rec["status"] = f"error:{type(e).__name__}"; rec["epr"] = None
        rec["error"] = str(e)[:160]
    finally:
        R._remove_gate_ids = pristine
    rec["seconds"] = round(time.perf_counter() - t0, 1)
    rec["trace"] = trace[-400:]
    rec["retired"] = st["retired"]
    # classify from the last third of the trace
    if rec["status"] == "completed":
        rec["verdict"] = "completed_with_more_time"
    elif len(trace) >= 6:
        tail = trace[len(trace) * 2 // 3:]
        dg = tail[-1][1] - tail[0][1]
        de = tail[-1][2] - tail[0][2]
        ds = tail[-1][3] - tail[0][3]
        rec["tail_delta"] = {"gates": dg, "epr": de, "swaps": ds}
        rec["verdict"] = ("livelock_signature" if dg == 0 and (de > 0 or ds > 0)
                          else "slow_but_progressing" if dg > 0 else "stalled")
    else:
        rec["verdict"] = "no_progress_samples"
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--arms", default="base")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    ARMS = {"base": (0.5, 0.9), "floor0": (0.0, 0.9), "floor25": (0.25, 0.9),
            "flat": (0.9, 0.9), "slow95": (0.0, 0.95), "slow97": (0.0, 0.97),
            "slow99": (0.0, 0.99)}
    tasks = []
    for line in (H.HERE / "horizon_grid.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r["status"] == "timeout" and r["arm"] in ARMS and r["arm"] in a.arms.split(","):
            w, g = ARMS[r["arm"]]
            tasks.append((r["key"], r["L"], r["arm"], w, g))
    done = set()
    if OUT.exists():
        for line in OUT.read_text().splitlines():
            r = json.loads(line); done.add((r["key"], r["L"], r["arm"]))
    tasks = [t for t in tasks if (t[0], t[1], t[2]) not in done]
    print(f"{len(tasks)} timed-out cells to re-run at {GUARD}s "
          f"(worst case {len(tasks)*GUARD/3600:.1f} core-hours)", flush=True)
    if a.dry_run:
        for t in tasks:
            print("  ", t)
        return
    with mp.get_context("spawn").Pool(a.workers) as pool, OUT.open("a") as f:
        for i, rec in enumerate(pool.imap_unordered(run_task, tasks), 1):
            f.write(json.dumps(rec) + "\n"); f.flush()
            print(f"[{i}/{len(tasks)}] {rec['arm']:<8}{rec['key']:<26} L={rec['L']:<4} "
                  f"{rec['status']:<10} {rec['verdict']:<26} "
                  f"retired={rec['retired']}/{rec['gates_total']} ({rec['seconds']}s)",
                  flush=True)
    print("TIMEOUT STUDY DONE", flush=True)


if __name__ == "__main__":
    main()
