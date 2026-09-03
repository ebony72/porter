"""Classify the timeout re-runs from their progress traces.

The probe samples only when a gate is retired, so a route whose retirement
stops produces no further samples: the gap between the last sample and the end
of the run is itself the measurement.  Three outcomes:

  completed        -- the 300 s guard was the only thing stopping it
  frozen           -- retirement stopped early and the router span for the rest
                      of the run (the livelock signature: gates flat, EPR and
                      SWAPs still climbing)
  crawling         -- still retiring gates when the run ended, far too slowly

`retired` counts requested removals, some of which are already-inactive gates,
so it is an upper bound on gates actually retired; only its shape is used here.
"""
import json
import hz_common as H


def main():
    rows = [json.loads(l) for l in (H.HERE / "timeout_reruns.jsonl").read_text().splitlines() if l.strip()]
    print(f"## {len(rows)} cells that timed out at 300 s, re-run at 900 s (3x)\n")
    print(f"  {'instance':<24}{'L':>5}{'outcome':>10}{'run':>8}{'last':>8}{'idle':>8}"
          f"{'retired':>9}{'of':>8}  verdict")
    tally = {}
    for r in sorted(rows, key=lambda x: (x["key"], x["L"])):
        tr = r["trace"]
        last_t = tr[-1][0] if tr else 0.0
        idle = r["seconds"] - last_t
        if r["status"] == "completed":
            v = "completed with more time"
        elif idle > 0.5 * r["seconds"]:
            v = "FROZEN: retirement stopped, router span on"
        else:
            v = "crawling: still retiring at the guard"
        tally[v] = tally.get(v, 0) + 1
        print(f"  {r['key']:<24}{r['L']:>5}{r['status']:>10}{r['seconds']:>7.0f}s"
              f"{last_t:>7.1f}s{idle:>7.0f}s{r['retired']:>9}{r['gates_total']:>8}  {v}")
    print()
    for k, v in sorted(tally.items(), key=lambda x: -x[1]):
        print(f"  {v:>3}  {k}")
    done = [r for r in rows if r["status"] == "completed"]
    print(f"\n  {len(done)} of {len(rows)} completed when given 3x the time"
          + (f": {', '.join(r['key']+'@'+str(r['L']) for r in done)}" if done else ""))
    frozen = [r for r in rows if r["status"] != "completed"
              and (r["seconds"] - (r["trace"][-1][0] if r["trace"] else 0)) > 0.5 * r["seconds"]]
    if frozen:
        print(f"\n  In the frozen cases retirement stops after a median of "
              f"{sorted((r['trace'][-1][0] if r['trace'] else 0) for r in frozen)[len(frozen)//2]:.0f}s "
              f"and the router then spins for the rest of the guard.")
        print("  EPR and SWAP counts at the last sample vs the start, showing work continued:")
        for r in frozen[:8]:
            tr = r["trace"]
            if len(tr) >= 2:
                print(f"    {r['key']:<24}L={r['L']:<4} gates {tr[0][1]}->{tr[-1][1]}, "
                      f"epr {tr[0][2]}->{tr[-1][2]}, swaps {tr[0][3]}->{tr[-1][3]}")


if __name__ == "__main__":
    main()
