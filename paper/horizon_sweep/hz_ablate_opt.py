"""Isolate each optimisation on one basis: all 48 instances, shipped protocol.

Four things changed how a route or the protocol spends time this session.  Two
are per-route and output-preserving; two are protocol-level and change only how
long a doomed or expensive candidate is allowed to run.  Each is toggled
independently here, in one process on one machine, so the times are comparable
with each other rather than with numbers taken under different load.

  walk bound      per route   cap the walk by the moving qubit's remaining CXs
  frontier scan   per route   drop the per-layer sort of the whole frontier
  stall guard     protocol    abandon a route retiring no gate for 1,000 iters
  work budget     protocol    bound a speculative horizon by peeled layers,
                              not by a share of wall-clock time

EPR and the emitted stream must be identical in every configuration; the point
of the table is that only the time moves.
"""
import json, time, argparse, hashlib
import multiprocessing as mp
import hz_head as H

OUT = H.HERE / "optimisation_ablation.jsonl"
R = H.porter.PorterRouter

CONFIGS = [
    ("shipped",            dict(walk=True,  scan=True,  guard=True,  work=True)),
    ("no work budget",     dict(walk=True,  scan=True,  guard=True,  work=False)),
    ("no stall guard",     dict(walk=True,  scan=True,  guard=False, work=True)),
    ("no frontier fix",    dict(walk=True,  scan=False, guard=True,  work=True)),
    ("no walk bound",      dict(walk=False, scan=True,  guard=True,  work=True)),
    ("none of the four",   dict(walk=False, scan=False, guard=False, work=False)),
]


def _legacy_collector(use_walk_bound, use_fast_scan):
    """The collector as it stood before each fix, reassembled from its parts."""
    def collect(self, state, moving_qubit, exclude, sim, dag, max_cx, max_layers):
        if use_walk_bound:
            cap = min(max_cx, state.active_cx_by_qubit.get(moving_qubit, 0))
        else:
            cap = max_cx                      # pre-2026-09-02: bounded by N_tp only
        if cap <= 0 or max_layers <= 0:
            return []
        seen = set(exclude)
        out = []
        for layer in range(1, max_layers + 1):
            if not dag.frontier or len(out) >= cap:
                break
            current = sim.current_layer(dag)
            if not current:
                break
            sim.remove_gate_ids(dag, current)
            state.stats.lookahead_layers_peeled += 1
            budget = getattr(self, "_lookahead_layer_budget", 0)
            if budget and state.stats.lookahead_layers_peeled > budget:
                raise RuntimeError("Lookahead work budget exceeded")
            if use_fast_scan:
                for gid in dag.frontier:
                    if gid in seen:
                        continue
                    g = state.gate_by_id.get(gid)
                    if g is not None and g.is_cx() and moving_qubit in g.qubits:
                        out.append((g, layer)); seen.add(gid); break
            else:
                for gid in sorted(dag.frontier):   # the pre-fix scan
                    if len(out) >= cap:
                        break
                    if gid in seen:
                        continue
                    g = state.gate_by_id.get(gid)
                    if g is not None and g.is_cx() and moving_qubit in g.qubits:
                        out.append((g, layer)); seen.add(gid)
        return out
    return collect


def sha(state):
    ops = [[o.op_type, [g.gid for g in o.gates], list(o.qubits), list(o.physical_qubits),
            list(o.cores), list(o.path), o.epr_cost] for o in state.emitted]
    return hashlib.sha256(json.dumps(ops, sort_keys=True, default=str).encode()).hexdigest()[:16]


def one(task):
    key, name, opts = task
    pristine = R._collect_teleport_post_latent_lookahead_gates
    if not (opts["walk"] and opts["scan"]):
        R._collect_teleport_post_latent_lookahead_gates = _legacy_collector(
            opts["walk"], opts["scan"])
    H.cp.SPECULATIVE_WORK_FACTOR = 7.0 if opts["work"] else 0.0
    hw, gates, n = H.load(key)
    cfg = H.porter.RouterConfig(
        max_iterations_without_progress=1000 if opts["guard"] else 0)
    lay = H.cp.build_initial_layout(gates, hw, n, min_free_per_core=cfg.min_free_before_teleport)
    t0 = time.perf_counter()
    try:
        st, info = H.cp.route(hw, cfg, list(gates), lay, selection=True)
        rec = {"epr": st.stats.epr, "sha": sha(st), "horizon": info.get("chosen_horizon"),
               "status": "completed"}
    except Exception as e:                                    # noqa: BLE001
        rec = {"epr": None, "sha": None, "horizon": None, "status": type(e).__name__}
    finally:
        R._collect_teleport_post_latent_lookahead_gates = pristine
    rec.update(key=key, config=name, seconds=round(time.perf_counter() - t0, 2))
    return rec


def report():
    rows = [json.loads(l) for l in OUT.read_text().splitlines() if l.strip()]
    by = {}
    for r in rows:
        by.setdefault(r["config"], {})[r["key"]] = r
    base = by.get("shipped", {})
    keys = [k for k in base if base[k]["status"] == "completed"]
    tb = sum(base[k]["seconds"] for k in keys)
    print(f"\n  basis: {len(keys)} instances, shipped protocol (3 routes each), one process\n")
    print(f"  {'configuration':<20}{'routes':>7}{'total time':>12}{'vs shipped':>12}"
          f"{'EPR identical':>15}")
    for name, _ in CONFIGS:
        cells = by.get(name)
        if not cells:
            continue
        t = sum(cells[k]["seconds"] for k in keys if k in cells)
        same = sum(1 for k in keys if k in cells and cells[k]["sha"] == base[k]["sha"])
        print(f"  {name:<20}{3:>7}{t:>11.1f}s{t/tb:>11.2f}x"
              f"{f'{same}/{len(keys)}':>15}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--report-only", action="store_true")
    a = ap.parse_args()
    if not a.report_only:
        done = set()
        if OUT.exists():
            done = {(json.loads(l)["key"], json.loads(l)["config"])
                    for l in OUT.read_text().splitlines() if l.strip()}
        tasks = [(k, n, o) for n, o in CONFIGS for k in H.instance_keys()
                 if (k, n) not in done]
        print(f"{len(tasks)} (instance, configuration) routes", flush=True)
        with mp.get_context("spawn").Pool(a.workers) as pool, OUT.open("a") as f:
            for i, r in enumerate(pool.imap_unordered(one, tasks), 1):
                f.write(json.dumps(r) + "\n"); f.flush()
                if i % 24 == 0:
                    print(f"  [{i}/{len(tasks)}] {r['config']:<18}{r['key']}", flush=True)
        print("ABLATE DONE", flush=True)
    report()


if __name__ == "__main__":
    main()
