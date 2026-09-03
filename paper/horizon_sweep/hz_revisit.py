"""Does the revisit block end the shuttle, and what does it cost healthy routes?

Every non-completing route in `horizon_grid.jsonl` is the same cycle: one
logical qubit teleporting back and forth between two cores while nothing
retires.  `RouterConfig.teleport_revisit_block` drops a teleport that would
return a qubit to a core it has already occupied since the last gate
retirement, which makes that cycle unrepresentable.

This runs both arms on (a) every cell the shipped scorer fails and (b) every
cell it completes, so the rescue rate and the cost to healthy routes are
measured on the same grid.

Usage:
  python3 paper/horizon_sweep/hz_revisit.py --cells failed   # or: all
"""
import argparse, hashlib, json, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hz_common as hc                                     # noqa: E402
import porter                                              # noqa: E402
import compile_porter as cp                                # noqa: E402
import verify_porter as vp                                 # noqa: E402

GRID = HERE / "horizon_grid.jsonl"
GUARD = 300


def stream_sha(st):
    blob = json.dumps([[o.op_type, [g.gid for g in o.gates], list(o.qubits),
                        list(o.physical_qubits), list(o.cores), list(o.path),
                        o.epr_cost] for o in st.emitted], sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def run(hw, gates, n, L, block):
    cfg = porter.RouterConfig(dag_extended_max_layers=L,
                              teleport_revisit_block=block)
    lay = cp.build_initial_layout(gates, hw, n,
                                  min_free_per_core=cfg.min_free_before_teleport)
    lay0 = lay.clone()
    rec = {"L": L, "revisit_block": block}
    t0 = time.perf_counter()
    try:
        with cp._horizon_time_limit(GUARD):
            st, _ = cp.route(hw, cfg, list(gates), lay, selection=False)
        rec.update(status="completed", epr=st.stats.epr, sha=stream_sha(st),
                   swaps=st.stats.local_swap_count, depth=st.stats.depth,
                   ties=st.stats.seeded_tie_break_count)
        try:
            vp.verify_state(hw, lay0, list(gates), st)
            rec["verified"] = True
        except Exception as e:                              # noqa: BLE001
            rec["verified"] = f"FAIL:{type(e).__name__}:{str(e)[:100]}"
    except cp.HorizonTimeout:
        rec.update(status="timeout", epr=None)
    except RuntimeError as e:
        rec.update(status="stalled" if "retired no gate" in str(e) else "livelock",
                   epr=None, error=str(e)[:160])
    except Exception as e:                                  # noqa: BLE001
        rec.update(status=f"error:{type(e).__name__}", epr=None, error=str(e)[:160])
    rec["seconds"] = round(time.perf_counter() - t0, 2)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="failed",
                    choices=("failed", "all", "completed"))
    ap.add_argument("--only-L", type=int, default=0,
                    help="restrict to one horizon (0 = every horizon)")
    ap.add_argument("--out", default=str(HERE / "revisit_cells.jsonl"))
    args = ap.parse_args()

    base = [json.loads(l) for l in GRID.read_text().splitlines() if l.strip()]
    base = [r for r in base if r["arm"] == "base"]
    want = [(r["key"], r["L"], r["status"]) for r in base
            if (args.cells == "all"
                or (args.cells == "failed" and r["status"] != "completed")
                or (args.cells == "completed" and r["status"] == "completed"))
            and (not args.only_L or r["L"] == args.only_L)]
    want.sort()

    out = Path(args.out)
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                done.add((r["key"], r["L"]))
    fh = out.open("a")
    cache = {}
    for key, L, shipped_status in want:
        if (key, L) in done:
            continue
        if key not in cache:
            cache[key] = hc.load(key)
        hw, gates, n = cache[key]
        rec = {"key": key, "n": n, "shipped_status": shipped_status}
        rec["block"] = run(hw, gates, n, L, True)
        rec["plain"] = run(hw, gates, n, L, False)
        fh.write(json.dumps(rec) + "\n"); fh.flush()
        b, p = rec["block"], rec["plain"]
        print(f"{key:28s} L={L:4d}  shipped={p['status']:9s} epr={str(p['epr']):>6}"
              f"   +block={b['status']:9s} epr={str(b['epr']):>6}"
              f"   {'SAME STREAM' if b.get('sha') and b.get('sha')==p.get('sha') else ''}",
              flush=True)
    fh.close()


if __name__ == "__main__":
    main()
