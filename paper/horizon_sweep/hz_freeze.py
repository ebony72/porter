"""Classify the failure mode of every route the shipped scorer does not finish.

Runs each failing cell of `horizon_grid.jsonl` with the stall guard on (so the
route aborts in seconds rather than burning the 300 s guard) while tracing the
action stream, then reports what the router was doing in the window after the
last gate retirement:

  teleport_shuttle  one logical qubit teleported back and forth between two
                    cores; the lookahead term is antisymmetric under reversing
                    a move, so with an intervening preparation SWAP each side
                    prefers the other indefinitely.
  local_only        no teleport in the window: an intra-core SWAP cycle.
  other             anything else (reported with its action histogram).

Usage:  python3 paper/horizon_sweep/hz_freeze.py
"""
import collections, json, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hz_common as hc                                     # noqa: E402
import porter                                              # noqa: E402
import compile_porter as cp                                # noqa: E402

GRID = HERE / "horizon_grid.jsonl"
OUT = HERE / "freeze_modes.jsonl"
GUARD = 300


def classify(hw, gates, n, L):
    cfg = porter.RouterConfig(dag_extended_max_layers=L)     # stall guard default on
    lay = cp.build_initial_layout(gates, hw, n,
                                  min_free_per_core=cfg.min_free_before_teleport)
    R = porter.PorterRouter(hw, cfg)
    trace = []
    orig = R._apply_action

    def apply(a, state):
        trace.append((a.kind, a.qubit, a.src_core, a.dst_core, a.swap,
                      len(state.dag_active)))
        return orig(a, state)
    R._apply_action = apply

    t0 = time.perf_counter()
    status = "completed"
    try:
        with cp._horizon_time_limit(GUARD):
            R.compile(list(gates), lay)
    except cp.HorizonTimeout:
        status = "timeout"
    except RuntimeError as e:
        status = "stalled" if "retired no gate" in str(e) else "livelock"
    except Exception as e:                                   # noqa: BLE001
        status = f"error:{type(e).__name__}"
    secs = round(time.perf_counter() - t0, 2)

    act = [t[5] for t in trace]
    last = max((i for i in range(1, len(act)) if act[i] < act[i - 1]), default=-1)
    tail = trace[last + 1:]
    kinds = collections.Counter(t[0] for t in tail)
    tele = [t for t in tail if t[0] == "teleport"]
    qubits = collections.Counter(t[1] for t in tele)
    mode, detail = "other", {}
    if not tele:
        mode = "local_only"
    else:
        q, cnt = qubits.most_common(1)[0]
        share = cnt / len(tele)
        cores = collections.Counter((t[2], t[3]) for t in tele if t[1] == q)
        pair = {c for mv, _ in cores.most_common(2) for c in mv}
        if share >= 0.5 and len(pair) <= 2:
            mode = "teleport_shuttle"
        detail = {"top_qubit": q, "top_qubit_share": round(share, 3),
                  "cores": sorted(pair),
                  "moves": {f"{a}->{b}": c for (a, b), c in cores.most_common(4)}}
    return {"status": status, "seconds": secs, "traced": len(trace),
            "tail": len(tail), "kinds": dict(kinds), "mode": mode, **detail}


def main():
    base = [json.loads(l) for l in GRID.read_text().splitlines() if l.strip()]
    fails = sorted((r["key"], r["L"], r["status"]) for r in base
                   if r["arm"] == "base" and r["status"] != "completed")
    done = set()
    if OUT.exists():
        for line in OUT.read_text().splitlines():
            if line.strip():
                r = json.loads(line); done.add((r["key"], r["L"]))
    fh = OUT.open("a")
    cache = {}
    for key, L, grid_status in fails:
        if (key, L) in done:
            continue
        if key not in cache:
            cache[key] = hc.load(key)
        hw, gates, n = cache[key]
        rec = {"key": key, "L": L, "grid_status": grid_status}
        rec.update(classify(hw, gates, n, L))
        fh.write(json.dumps(rec) + "\n"); fh.flush()
        print(f"{key:28s} L={L:4d} {rec['status']:9s} {rec['mode']:17s} "
              f"tail={rec['tail']:7d} {rec.get('moves','')}", flush=True)
    fh.close()


if __name__ == "__main__":
    main()
