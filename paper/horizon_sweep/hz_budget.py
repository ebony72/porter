"""Would a deterministic work budget select the same horizons as the clock?

`run_horizon_selection` gives each speculative candidate
`max(5, ceil(4 * t_first))` SECONDS, derived from the first route's wall time.
That is why 360q QPEexact returns 1,224 or 2,342 depending on the machine.

A deterministic replacement has to be a *work* counter, not an iteration count:
CLAUDE.md already records that an iteration cap is the wrong guard, because a
deep peel makes each iteration ~400x costlier, so 20k iterations at L=128 burn
471 s where the whole L=16 route takes 1.2 s.  The counter used here is the
number of DAG layers the lookahead walk peels, which is the dominant cost
inside the collector and rises with the horizon exactly as the run time does.

For every instance this measures, per candidate horizon, the wall time, the
peeled-layer count and the router iterations.  It then replays selection under
each rule and reports whether the selected horizon would differ.
"""
import json, time, argparse
import multiprocessing as mp
import hz_head as H

OUT = H.HERE / "budget_probe.jsonl"
FACTOR = 4.0
MIN_SECONDS = 5


def measure(task):
    key, horizon = task
    hw, gates, n = H.load(key)
    cfg = H.porter.RouterConfig(dag_extended_max_layers=horizon)
    lay = H.cp.build_initial_layout(gates, hw, n, min_free_per_core=cfg.min_free_before_teleport)
    R = H.porter.PorterRouter
    rm = R._collect_teleport_post_latent_lookahead_gates
    sim_rm = H.porter.router.DagFrontierSimulator.remove_gate_ids
    counters = {"layers": 0, "walks": 0}

    def probe_sim(self, dag, gids):
        counters["layers"] += 1
        return sim_rm(self, dag, gids)

    def probe_walk(self, *a, **k):
        counters["walks"] += 1
        return rm(self, *a, **k)

    H.porter.router.DagFrontierSimulator.remove_gate_ids = probe_sim
    R._collect_teleport_post_latent_lookahead_gates = probe_walk
    rec = {"key": key, "L": horizon}
    t0 = time.perf_counter()
    try:
        with H.cp._horizon_time_limit(300):
            st, _ = H.cp.route(hw, cfg, list(gates), lay, selection=False)
        rec.update(status="completed", epr=st.stats.epr)
    except Exception as e:                                    # noqa: BLE001
        rec.update(status=type(e).__name__, epr=None)
    finally:
        H.porter.router.DagFrontierSimulator.remove_gate_ids = sim_rm
        R._collect_teleport_post_latent_lookahead_gates = rm
    rec["seconds"] = round(time.perf_counter() - t0, 3)
    rec["peeled_layers"] = counters["layers"]
    rec["walks"] = counters["walks"]
    return rec


def replay(rows):
    """Compare the clock rule with a peeled-layer rule on the same data."""
    by = {}
    for r in rows:
        by.setdefault(r["key"], {})[r["L"]] = r
    out = []
    for key, cells in sorted(by.items()):
        hw_gates = None
        horizons, _ = H.cp.select_horizons(*(lambda g, n: (g, n))(*H.load(key)[1:]))
        cfg_h = H.porter.RouterConfig().dag_extended_max_layers
        order = [cfg_h] + [h for h in horizons if h != cfg_h]
        first = cells.get(order[0])
        if first is None or first["status"] != "completed":
            continue
        t_budget = max(MIN_SECONDS, FACTOR * first["seconds"])
        w_budget = max(1, FACTOR * first["peeled_layers"])
        picks = {}
        for rule, admits in (("clock", lambda c: c["seconds"] <= t_budget),
                             ("work", lambda c: c["peeled_layers"] <= w_budget)):
            best = (first["epr"], 0)
            chosen = order[0]
            for pos, h in enumerate(order[1:], start=1):
                c = cells.get(h)
                if c is None or c["status"] != "completed" or not admits(c):
                    continue
                if (c["epr"], pos) < best:
                    best, chosen = (c["epr"], pos), h
            picks[rule] = (chosen, best[0])
        out.append((key, order, picks, first["seconds"], first["peeled_layers"]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--replay-only", action="store_true")
    a = ap.parse_args()
    if not a.replay_only:
        tasks = []
        for key in H.instance_keys():
            _, gates, n = H.load(key)
            horizons, _ = H.cp.select_horizons(gates, n)
            for h in sorted(set(horizons) | {16}):
                tasks.append((key, h))
        done = set()
        if OUT.exists():
            done = {(json.loads(l)["key"], json.loads(l)["L"])
                    for l in OUT.read_text().splitlines() if l.strip()}
        tasks = [t for t in tasks if t not in done]
        print(f"{len(tasks)} (instance, horizon) cells to measure", flush=True)
        with mp.get_context("spawn").Pool(a.workers) as pool, OUT.open("a") as f:
            for i, r in enumerate(pool.imap_unordered(measure, tasks), 1):
                f.write(json.dumps(r) + "\n"); f.flush()
                print(f"[{i}/{len(tasks)}] {r['key']:<26} L={r['L']:<4} {r['status']:<12} "
                      f"{r['seconds']:>7.2f}s  layers={r['peeled_layers']}", flush=True)
    rows = [json.loads(l) for l in OUT.read_text().splitlines() if l.strip()]
    res = replay(rows)
    diff = [r for r in res if r[2]["clock"][0] != r[2]["work"][0]]
    print(f"\n## selection under a wall-clock budget vs a peeled-layer budget "
          f"({len(res)} instances)")
    print(f"  same horizon selected: {len(res)-len(diff)}/{len(res)}")
    for key, order, picks, ts, ls in res:
        flag = "  <-- DIFFERS" if picks["clock"][0] != picks["work"][0] else ""
        print(f"  {key:<26} clock L={picks['clock'][0]:<4} epr={picks['clock'][1]:<6} "
              f"work L={picks['work'][0]:<4} epr={picks['work'][1]:<6}{flag}")


if __name__ == "__main__":
    main()
