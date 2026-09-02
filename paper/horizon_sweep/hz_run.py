"""Compute harness for the horizon experiments.

Routes (instance, horizon, arm) cells with ``selection=False`` -- one
deterministic forward pass each -- under a fixed 300 s SIGALRM guard, from the
frozen snapshot.  Arms vary only the lookahead weight schedule
(w_min, gamma); everything else is the released RouterConfig.

  base    (0.50, 0.90)  the shipped schedule -- control, and a re-run of the
                        2026-09-01 sweep under the snapshot's selection key
  floor0  (0.00, 0.90)  a true geometric decay: L stops being a window
  floor25 (0.25, 0.90)
  flat    (0.90, 0.90)  floor == w0: no discount at all, pure window

One JSON line per route (append-only, resumable).  Every completed route is
replay-verified.  Failure classes: timeout / livelock (max_iterations) /
error:<type>.  Deterministic counters (RouterStats) are saved alongside the
wall time.
"""
import sys, json, time, argparse
import multiprocessing as mp
from pathlib import Path

import hz_common as H

HORIZONS = [4, 8, 16, 32, 64, 128]
EXTRA = [48, 256]                 # base arm only: completes the 8-point grid
GUARD = 300
ARMS = {
    "base": (0.5, 0.9),
    "floor0": (0.0, 0.9),
    "floor25": (0.25, 0.9),
    "flat": (0.9, 0.9),
    # Test 1 (2026-09-03): no floor, slow decay -- the discount itself bounds
    # the horizon instead of a hard window.  Effective reach (weight < 0.05):
    # ~60 layers at 0.95, ~130 at 0.97, ~400 at 0.99.
    "slow95": (0.0, 0.95),
    "slow97": (0.0, 0.97),
    "slow99": (0.0, 0.99),
}
SLOW = ("slow95", "slow97", "slow99")
OUT = H.HERE / "horizon_grid.jsonl"
PREV = H.HERE / "sweep_2026-09-01_main.json"
PREV_HH = H.HERE / "sweep_2026-09-01_heavyhex.json"

_cache = {}


def run_task(task):
    key, L, arm = task
    wmin, gamma = ARMS[arm]
    if key not in _cache:
        _cache[key] = H.load(key)
    hw, gates, n = _cache[key]
    cfg = H.porter.RouterConfig(
        dag_extended_max_layers=L,
        teleport_lookahead_weight_floor=wmin,
        teleport_lookahead_decay=gamma,
    )
    lay = H.cp.build_initial_layout(gates, hw, n, min_free_per_core=cfg.min_free_before_teleport)
    lay0 = lay.clone()
    rec = {"key": key, "L": L, "arm": arm, "w_min": wmin, "gamma": gamma,
           "guard": GUARD, "n": n}
    t0 = time.perf_counter()
    try:
        with H.cp._horizon_time_limit(GUARD):
            st, _ = H.cp.route(hw, cfg, list(gates), lay, selection=False)
        rec["status"] = "completed"
        rec["epr"] = st.stats.epr
        rec["stats"] = {k: v for k, v in vars(st.stats).items()
                        if isinstance(v, (int, float))}
        try:
            H.vp.verify_state(hw, lay0, list(gates), st)
            rec["verified"] = True
        except Exception as e:                       # noqa: BLE001
            rec["verified"] = f"FAIL:{type(e).__name__}:{str(e)[:120]}"
    except H.cp.HorizonTimeout:
        rec["status"] = "timeout"
        rec["epr"] = None
    except RuntimeError as e:
        rec["status"] = "livelock" if "max_iterations" in str(e) else "error:RuntimeError"
        rec["epr"] = None
        rec["error"] = str(e)[:200]
    except Exception as e:                           # noqa: BLE001
        rec["status"] = f"error:{type(e).__name__}"
        rec["epr"] = None
        rec["error"] = str(e)[:200]
    rec["seconds"] = round(time.perf_counter() - t0, 2)
    return rec


def done_set():
    s = set()
    if OUT.exists():
        for line in OUT.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                s.add((r["key"], r["L"], r["arm"]))
    return s


def cost_estimate():
    """Wall-time prior from the 2026-09-01 sweep, for LPT ordering."""
    est = {}
    for p in (PREV, PREV_HH):
        if p.exists():
            for k, r in json.loads(p.read_text()).items():
                for L, s in r["seconds"].items():
                    est[(k, int(L))] = float(s)
    return est


def horizons_for(arm, extra):
    if arm == "base" and extra:
        return HORIZONS + EXTRA
    if arm in SLOW:
        return HORIZONS + [256]      # deep L tests whether EPR goes flat in L
    return HORIZONS


def build_tasks(arms, keys, extra):
    tasks = []
    for arm in arms:
        Ls = horizons_for(arm, extra)
        for key in keys:
            for L in Ls:
                tasks.append((key, L, arm))
    return tasks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="base,floor0,floor25,flat")
    ap.add_argument("--keys", default="", help="comma list / substring filter")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--no-extra", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cheap-first", action="store_true")
    a = ap.parse_args()

    arms = [x for x in a.arms.split(",") if x]
    keys = H.instance_keys()
    if a.keys:
        pats = a.keys.split(",")
        keys = [k for k in keys if any(p in k for p in pats)]
    tasks = build_tasks(arms, keys, not a.no_extra)
    done = done_set()
    tasks = [t for t in tasks if t not in done]
    est = cost_estimate()

    def prior(t):
        key, L, _ = t
        if (key, L) in est:
            return est[(key, L)]
        near = [v for (k, l), v in est.items() if k == key]
        return max(near) if near else 1.0

    tasks.sort(key=prior, reverse=not a.cheap_first)
    total_prior = sum(prior(t) for t in tasks)
    print(f"{len(tasks)} routes to run ({len(done)} already done); "
          f"prior cost {total_prior/3600:.1f} core-hours on {a.workers} workers",
          flush=True)
    if a.dry_run:
        return
    n_done = 0
    t0 = time.time()
    with mp.get_context("spawn").Pool(a.workers) as pool, OUT.open("a") as f:
        for rec in pool.imap_unordered(run_task, tasks, chunksize=1):
            f.write(json.dumps(rec) + "\n")
            f.flush()
            n_done += 1
            print(f"[{n_done}/{len(tasks)} {time.time()-t0:7.0f}s] "
                  f"{rec['arm']:<8}{rec['key']:<26} L={rec['L']:<4} "
                  f"{rec['status']:<10} epr={rec['epr']} "
                  f"ver={rec.get('verified', '-')} ({rec['seconds']}s)",
                  flush=True)
    print("HZ RUN DONE", flush=True)


if __name__ == "__main__":
    main()
