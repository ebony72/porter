"""Q3 + Q5: can a route prove, from its own execution, that a deeper horizon
cannot change anything -- and where does the deep lookahead gain actually sit?

Q3 (early exit).  The collector's walk stops for one of three reasons:
  cap        -- it found all the moving qubit's remaining CXs
  dag        -- the simulated DAG ran out
  budget     -- it used all `max_layers` layers and was still going
Only `budget` can be relieved by a larger L.  So if a route at horizon L never
once stops for `budget`, every collected set is already complete and routing at
any L' > L returns a byte-identical stream.  That is a proof, not a heuristic,
and it is observable from the route itself.

The reason is recovered without re-running the walk: after the call, the walk
was cap-bound iff |out| reached the cap, dag-bound iff the simulated frontier
is empty, and budget-bound otherwise.

Q5 (where the gain sits).  For every teleport scored, record each collected
gate's layer and its signed delta, so the cumulative gain profile over layers
can be read off and a truncation depth chosen that preserves the score.
"""
import json, argparse, collections
import hz_common as H

R = H.porter.PorterRouter


def instrument(collect_reasons=True, gain_profile=False):
    coll = R._collect_teleport_post_latent_lookahead_gates
    gain = R._collect_teleport_direct_latent_and_lookahead
    acc = {"reason": collections.Counter(), "maxlayer": collections.Counter(),
           "layer_gain": collections.defaultdict(float),
           "layer_absgain": collections.defaultdict(float),
           "layer_count": collections.Counter(), "calls": 0}

    def probe_coll(self, state, moving_qubit, exclude, sim, dag, max_cx, max_layers):
        out = coll(self, state, moving_qubit, exclude, sim, dag, max_cx, max_layers)
        acc["calls"] += 1
        cap = min(max_cx, state.active_cx_by_qubit.get(moving_qubit, 0))
        if cap <= 0 or max_layers <= 0:
            acc["reason"]["empty"] += 1
        elif len(out) >= cap:
            acc["reason"]["cap"] += 1
        elif not dag.frontier:
            acc["reason"]["dag"] += 1
        else:
            acc["reason"]["budget"] += 1
        acc["maxlayer"][max(( l for _, l in out), default=0)] += 1
        return out

    def probe_gain(self, state, info, seed_gate, moving_qubit, dst_core):
        direct, latent, look = gain(self, state, info, seed_gate, moving_qubit, dst_core)
        for g, layer in look:
            q0, q1 = g.qubits
            before = self.hw.core_distance(state.layout.core_of(q0), state.layout.core_of(q1))
            c0 = dst_core if q0 == moving_qubit else state.layout.core_of(q0)
            c1 = dst_core if q1 == moving_qubit else state.layout.core_of(q1)
            d = float(before - self.hw.core_distance(c0, c1))
            acc["layer_gain"][layer] += d
            acc["layer_absgain"][layer] += abs(d)
            acc["layer_count"][layer] += 1
        return direct, latent, look

    if collect_reasons:
        R._collect_teleport_post_latent_lookahead_gates = probe_coll
    if gain_profile:
        R._collect_teleport_direct_latent_and_lookahead = probe_gain
    return acc, (coll, gain)


def restore(orig):
    R._collect_teleport_post_latent_lookahead_gates = orig[0]
    R._collect_teleport_direct_latent_and_lookahead = orig[1]


def run(key, L, gain_profile=False):
    hw, gates, n = H.load(key)
    cfg = H.porter.RouterConfig(dag_extended_max_layers=L)
    lay = H.cp.build_initial_layout(gates, hw, n, min_free_per_core=cfg.min_free_before_teleport)
    acc, orig = instrument(gain_profile=gain_profile)
    try:
        st, _ = H.cp.route(hw, cfg, list(gates), lay, selection=False)
        epr = st.stats.epr
    finally:
        restore(orig)
    return acc, epr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["earlyexit", "profile"], default="earlyexit")
    ap.add_argument("--L", type=int, default=16)
    ap.add_argument("--keys", default="")
    a = ap.parse_args()
    keys = H.instance_keys()
    if a.keys:
        keys = [k for k in keys if any(p in k for p in a.keys.split(","))]

    if a.mode == "earlyexit":
        print(f"## Q3: termination reasons at L={a.L} -- 'budget' is the only one a deeper L can relieve")
        print(f"  {'instance':<26}{'calls':>9}{'cap':>9}{'dag':>9}{'budget':>8}{'bud%':>7}{'deepest':>8}  deeper-L can differ?")
        rows = []
        for k in keys:
            try:
                acc, epr = run(k, a.L)
            except Exception as e:                    # noqa: BLE001
                print(f"  {k:<26}  FAILED {type(e).__name__}")
                continue
            r = acc["reason"]; tot = acc["calls"]
            bud = r["budget"]
            deepest = max((l for l, c in acc["maxlayer"].items() if c), default=0)
            rows.append((k, tot, r["cap"], r["dag"], bud, deepest))
            print(f"  {k:<26}{tot:>9}{r['cap']:>9}{r['dag']:>9}{bud:>8}"
                  f"{100*bud/max(tot,1):>6.1f}%{deepest:>8}  {'yes' if bud else 'NO -- provably identical'}")
        json.dump([{"key": k, "calls": t, "cap": c, "dag": d, "budget": b, "deepest": x}
                   for k, t, c, d, b, x in rows],
                  open(H.HERE / f"earlyexit_L{a.L}.json", "w"), indent=1)
        n_free = sum(1 for r in rows if r[4] == 0)
        print(f"\n  {n_free} of {len(rows)} instances never hit the layer budget at L={a.L}: "
              f"for those, every deeper horizon is provably a wasted route.")
    else:
        for k in keys:
            acc, epr = run(k, a.L, gain_profile=True)
            cnt, absg, sg = acc["layer_count"], acc["layer_absgain"], acc["layer_gain"]
            tot_abs = sum(absg.values()) or 1.0
            print(f"\n## {k} at L={a.L}  (epr={epr}, {acc['calls']} collector calls, "
                  f"{sum(cnt.values())} gates scored)")
            print(f"  {'layer band':<14}{'gates':>9}{'share':>8}{'|gain|':>12}{'share':>8}{'cum':>8}{'net gain':>11}")
            cum = 0.0
            bands = [(1, 4), (5, 7), (8, 16), (17, 32), (33, 64), (65, 128), (129, 256)]
            for lo, hi in bands:
                c = sum(v for l, v in cnt.items() if lo <= l <= hi)
                ag = sum(v for l, v in absg.items() if lo <= l <= hi)
                sgn = sum(v for l, v in sg.items() if lo <= l <= hi)
                if c == 0:
                    continue
                cum += ag
                print(f"  {f'{lo}-{hi}':<14}{c:>9}{100*c/max(sum(cnt.values()),1):>7.1f}%"
                      f"{ag:>12.0f}{100*ag/tot_abs:>7.1f}%{100*cum/tot_abs:>7.1f}%{sgn:>11.0f}")
            for frac in (0.90, 0.95, 0.99):
                run_sum = 0.0
                for l in sorted(absg):
                    run_sum += absg[l]
                    if run_sum >= frac * tot_abs:
                        print(f"  {int(frac*100)}% of |gain| is reached by layer {l}")
                        break


if __name__ == "__main__":
    main()
