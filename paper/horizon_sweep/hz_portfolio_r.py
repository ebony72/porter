"""PORTER+R over a (schedule, horizon) portfolio, main suite.

The shipped +R selects the lookahead horizon ONCE, on the first forward pass,
from three candidates, and holds it for the remaining four passes -- so routes
are |H| + P - 1 = 7.  The natural extension to a schedule portfolio keeps that
shape: select the (schedule, horizon) pair on pass 1 from the portfolio, then
refine at the winner.  Routes are |portfolio| + P - 1, i.e. 10 for a six-pair
portfolio and 13 for the full nine.

Pass 1 for every pair is already measured in portfolio_head.jsonl, so only the
refinement from the winner is new.  Reported against the shipped +R on the same
instances.
"""
import json, time, argparse, math
import multiprocessing as mp
import hz_head as H

OUT = H.HERE / "portfolio_refined.jsonl"
PORTFOLIOS = {
    "six": [(w, L) for L in (4, 16, 128) for w in (0.5, 0.25)],
    "nine": [(w, L) for L in (4, 16, 128) for w in (0.5, 0.25, 0.0)],
}
PASSES = 5


def one(task):
    key, name = task
    pairs = PORTFOLIOS[name]
    cells = {r["key"]: r for r in
             (json.loads(l) for l in (H.HERE / "portfolio_head.jsonl").read_text().splitlines() if l.strip())}
    r = cells[key]
    got = [(c["epr"], w, L) for (w, L) in pairs
           if (c := r["cells"].get(f"{w}@{L}")) and c["epr"]]
    if not got:
        return {"key": key, "portfolio": name, "status": "no pass-1 winner"}
    epr1, w, L = min(got)
    sel_seconds = sum(r["cells"][f"{a}@{b}"]["seconds"] for a, b in pairs
                      if f"{a}@{b}" in r["cells"])
    hw, gates, n = H.load(key)
    cfg = H.porter.RouterConfig(dag_extended_max_layers=L,
                                teleport_lookahead_weight_floor=w)
    lay = H.cp.build_initial_layout(gates, hw, n, min_free_per_core=cfg.min_free_before_teleport)
    t0 = time.perf_counter()
    try:
        st, info = H.cp.run_refinement_passes(hw, cfg, list(gates), lay,
                                              passes=PASSES, selection=False)
        rec = {"epr": st.stats.epr if st else None, "status": "completed" if st else "failed",
               "forward_eprs": info.get("forward_eprs")}
    except Exception as e:                                    # noqa: BLE001
        rec = {"epr": None, "status": type(e).__name__}
    rec.update(key=key, portfolio=name, pair=f"w={w},L={L}", pass1_epr=epr1,
               routes=len(pairs) + PASSES - 1,
               seconds=round(sel_seconds + time.perf_counter() - t0, 2))
    return rec


def report():
    rows = [json.loads(l) for l in OUT.read_text().splitlines() if l.strip()]
    rel = {(str(r["suite"]), r["circuit"]): r
           for r in json.loads((H.SNAP / "paper" / "compare_results_selection.json").read_text())}
    def gm(v):
        return math.exp(sum(math.log(max(x, 1)) for x in v) / len(v))
    key2 = lambda k: (k.split("/")[1], k.split("/")[2])
    base_e = [rel[key2(r["key"])]["sfc_refined"]["epr"] for r in rows if r["portfolio"] == "six"]
    base_t = sum(rel[key2(r["key"])]["sfc_refined"]["seconds"] for r in rows if r["portfolio"] == "six")
    print(f"\n  main suite, {len(base_e)} instances")
    print(f"  {'protocol':<34}{'routes':>7}{'gmean EPR':>11}{'vs +R':>9}{'time':>10}{'vs +R':>8}")
    print(f"  {'PORTER+R (shipped, 3 horizons)':<34}{7:>7}{gm(base_e):>11.1f}{'---':>9}{base_t:>9.0f}s{'1.00x':>8}")
    for name in ("six", "nine"):
        sel = [r for r in rows if r["portfolio"] == name and r.get("epr")]
        if not sel:
            continue
        e = gm([r["epr"] for r in sel]); t = sum(r["seconds"] for r in sel)
        lbl = {"six": "+R over {4,16,128}x{.5,.25}", "nine": "+R over the full 3x3"}[name]
        print(f"  {lbl:<34}{sel[0]['routes']:>7}{e:>11.1f}{100*(e/gm(base_e)-1):>8.1f}%"
              f"{t:>9.0f}s{t/base_t:>7.2f}x")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--report-only", action="store_true")
    a = ap.parse_args()
    if not a.report_only:
        done = set()
        if OUT.exists():
            done = {(json.loads(l)["key"], json.loads(l)["portfolio"])
                    for l in OUT.read_text().splitlines() if l.strip()}
        keys = [k for k in H.instance_keys() if k.startswith("main/")]
        tasks = [(k, n) for n in PORTFOLIOS for k in keys if (k, n) not in done]
        print(f"{len(tasks)} (instance, portfolio) refinement schedules", flush=True)
        with mp.get_context("spawn").Pool(a.workers) as pool, OUT.open("a") as f:
            for i, r in enumerate(pool.imap_unordered(one, tasks), 1):
                f.write(json.dumps(r) + "\n"); f.flush()
                print(f"[{i}/{len(tasks)}] {r['key']:<26}{r['portfolio']:<6} "
                      f"pass1={r.get('pass1_epr')} -> +R={r.get('epr')} "
                      f"({r.get('pair')}) [{r.get('seconds')}s]", flush=True)
        print("PORTFOLIO+R DONE", flush=True)
    report()


if __name__ == "__main__":
    main()
