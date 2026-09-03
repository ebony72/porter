"""When does a deeper lookahead horizon pay?  Static DAG features vs the sweep.

The collector walks the MOVING QUBIT's own future CX chain, peeling whole ASAP
layers of the residual DAG, and stops at `dag_extended_max_layers` layers or
`teleport_lookahead_cx_count` collected gates.  Each collected gate contributes
w(layer) * Delta with Delta in {-1,+1} (every core graph here is bipartite) and
w floored at `teleport_lookahead_weight_floor`.  So a horizon buys signal only
through the gates it newly reaches, and it buys DISTINCT information only
through the distinct partners among them.

This script computes, per instance and per horizon L, purely static features of
the circuit DAG:

  reach(L)     mean number of the moving qubit's own future CXs within L ASAP
               layers (capped at N_tp, so it is what the walk can collect)
  distinct(L)  mean number of DISTINCT partners among those
  novelty(L)   distinct(L) / reach(L)

and joins them with the measured EPR(L) curve from `horizon_grid.jsonl`.

Usage:  python3 paper/horizon_sweep/hz_depth.py [--out features.json]
"""
import json, math, sys, argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hz_common as hc                                    # noqa: E402

N_TP = 50                       # teleport_lookahead_cx_count
HORIZONS = [4, 8, 16, 32, 48, 64, 128, 256]


def asap_layers(gates):
    """ASAP layer (1-based) of every gate over ALL gate types, which is what
    the collector peels."""
    last, out = {}, []
    for g in gates:
        lay = 1 + max((last.get(q, 0) for q in g.qubits), default=0)
        for q in g.qubits:
            last[q] = lay
        out.append(lay)
    return out


def depth_features(gates, n):
    """reach/distinct/novelty at every horizon, averaged over all (qubit, position)
    walk origins the router could start from."""
    lay = asap_layers(gates)
    # per qubit: ordered list of (asap_layer, partner) over its CX gates
    chain = {}
    for g, l in zip(gates, lay):
        if not g.is_cx():
            continue
        q0, q1 = g.qubits
        chain.setdefault(q0, []).append((l, q1))
        chain.setdefault(q1, []).append((l, q0))

    acc = {L: [0.0, 0.0, 0] for L in HORIZONS}     # sum reach, sum distinct, count
    for q, seq in chain.items():
        m = len(seq)
        for i in range(m):
            l0 = seq[i][0]
            # walk forward once, recording the prefix at each horizon boundary
            seen, k = set(), 0
            j = i + 1
            for L in HORIZONS:                      # horizons ascending
                while j < m and seq[j][0] - l0 <= L and k < N_TP:
                    seen.add(seq[j][1])
                    k += 1
                    j += 1
                a = acc[L]
                a[0] += k
                a[1] += len(seen)
                a[2] += 1
    out = {}
    for L in HORIZONS:
        s_reach, s_dist, cnt = acc[L]
        if not cnt:
            out[L] = {"reach": 0.0, "distinct": 0.0, "novelty": 1.0}
            continue
        r, d = s_reach / cnt, s_dist / cnt
        out[L] = {"reach": r, "distinct": d, "novelty": (d / r) if r else 1.0}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "depth_features.json"))
    args = ap.parse_args()

    feats = {}
    for key in hc.instance_keys():
        hw, gates, n = hc.load(key)
        cf = hc.circuit_features(gates, n)
        af = hc.arch_features(hw)
        df = depth_features(gates, n)
        feats[key] = {"circuit": cf, "arch": af,
                      "depth": {str(L): v for L, v in df.items()}}
        print(f"{key:28s} n={n:4d} cx={cf['cx']:6d} rho={cf['rho']:.3f} "
              f"reach16={df[16]['reach']:5.1f} reach128={df[128]['reach']:5.1f} "
              f"dist16={df[16]['distinct']:5.1f} dist128={df[128]['distinct']:5.1f} "
              f"nov128={df[128]['novelty']:.3f}", flush=True)
    Path(args.out).write_text(json.dumps(feats, indent=1))
    print("wrote", args.out)


if __name__ == "__main__":
    main()
