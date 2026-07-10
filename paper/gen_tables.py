"""Generate LaTeX table rows + gmean summaries from compare_results.json.

Emits, per suite (25/64/80): own-protocol table, TeleSABRE-shared-layout
table, and a combined pytket-shared-layout table across all suites.
"""
import json
import math
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def gmean(xs):
    xs = [x for x in xs if x is not None and x > 0]
    if not xs:
        return None
    return math.exp(sum(math.log(x) for x in xs) / len(xs))


def pct_delta(a, base):
    if a is None or base is None or base == 0:
        return None
    return 100.0 * (a - base) / base


def fmt_i(v):
    return str(v) if v is not None else "---"


def fmt_pct(v):
    if v is None:
        return "---"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.1f}"


def own_protocol_table(rows, label):
    print(f"\n%% -- {label}: own-protocol table --")
    ts_matched, sfc_matched, dse_matched = [], [], []
    n_failed = 0
    for r in rows:
        ts = r["telesabre"]
        dse = r["dSE"]
        sfc = r["sfc"]
        ts_epr = ts["epr"] if ts else None
        sfc_epr = sfc["epr"] if sfc else None
        dse_epr = dse["epr"] if dse else None
        delta = pct_delta(sfc_epr, ts_epr)
        cname = r["circuit"].replace("_OLD_DEEP", "")
        if ts_epr is None:
            n_failed += 1
        else:
            ts_matched.append(ts_epr)
            sfc_matched.append(sfc_epr)
            dse_matched.append(dse_epr)
        star = "$^{\\ast}$" if ts_epr is None else ""
        line = (
            f"{cname:<11}{star} & {fmt_i(ts_epr):>4} & {fmt_i(ts['swaps'] if ts else None):>5} & "
            f"{fmt_i(dse_epr):>4} & {fmt_i(dse['swaps'] if dse else None):>5} & "
            f"{fmt_i(sfc_epr):>4} & {fmt_i(sfc['swaps'] if sfc else None):>5} & "
            f"${fmt_pct(delta)}$ \\\\"
        )
        print(line)
    g_ts = gmean(ts_matched)
    g_sfc = gmean(sfc_matched)
    g_dse = gmean(dse_matched)
    g_delta = pct_delta(g_sfc, g_ts)
    n = len(ts_matched)
    print("\\midrule")
    if g_ts is not None:
        print(
            f"\\textbf{{gmean}} ({n}) & {g_ts:.1f} & & {g_dse:.1f} & & {g_sfc:.1f} & & "
            f"$\\mathbf{{{fmt_pct(g_delta)}}}$ \\\\"
        )
        print(f"%% gmean(n={n}, failed={n_failed}) TS={g_ts:.2f} dSE={g_dse:.2f} SFC={g_sfc:.2f} delta_vs_TS={g_delta:.1f}%")
    else:
        print(f"%% TeleSABRE converged on 0 circuits in {label}; no gmean vs TS possible")
        g_dse_all = gmean([r["dSE"]["epr"] for r in rows if r["dSE"]])
        g_sfc_all = gmean([r["sfc"]["epr"] for r in rows if r["sfc"]])
        print(f"%% dSE-only gmean={g_dse_all}, SFC-only gmean={g_sfc_all} (no TS baseline)")


def shared_layout_table(rows, label, ts_key, sfc_key, name):
    print(f"\n%% -- {label}: shared-layout table ({name}) --")
    ts_matched, sfc_matched, dse_matched = [], [], []
    for r in rows:
        ts = r["telesabre"]
        dse = r.get(ts_key)
        sfc = r.get(sfc_key)
        ts_epr = ts["epr"] if ts else None
        sfc_epr = sfc["epr"] if sfc else None
        dse_epr = dse["epr"] if dse else None
        cname = r["circuit"].replace("_OLD_DEEP", "")
        if ts_epr is not None and dse_epr is not None and sfc_epr is not None:
            ts_matched.append(ts_epr)
            sfc_matched.append(sfc_epr)
            dse_matched.append(dse_epr)
        delta_sfc = pct_delta(sfc_epr, ts_epr)
        delta_dse = pct_delta(dse_epr, ts_epr)
        star = "$^{\\ast}$" if not (ts_epr is not None and dse_epr is not None and sfc_epr is not None) else ""
        line = (
            f"{cname:<11}{star} & {fmt_i(ts_epr):>4} & {fmt_i(ts['swaps'] if ts else None):>5} & "
            f"{fmt_i(dse_epr):>4} & {fmt_i(dse['swaps'] if dse else None):>5} & ${fmt_pct(delta_dse)}$ & "
            f"{fmt_i(sfc_epr):>4} & {fmt_i(sfc['swaps'] if sfc else None):>5} & ${fmt_pct(delta_sfc)}$ \\\\"
        )
        print(line)
    g_ts = gmean(ts_matched)
    g_sfc = gmean(sfc_matched)
    g_dse = gmean(dse_matched)
    n = len(ts_matched)
    print("\\midrule")
    if g_ts is not None:
        g_delta_sfc = pct_delta(g_sfc, g_ts)
        g_delta_dse = pct_delta(g_dse, g_ts)
        print(
            f"\\textbf{{gmean}} ({n}) & {g_ts:.1f} & & {g_dse:.1f} & & $\\mathbf{{{fmt_pct(g_delta_dse)}}}$ & "
            f"{g_sfc:.1f} & & $\\mathbf{{{fmt_pct(g_delta_sfc)}}}$ \\\\"
        )
        print(
            f"%% gmean(n={n}) TS={g_ts:.2f} dSE={g_dse:.2f} SFC={g_sfc:.2f} "
            f"delta_dSE_vs_TS={g_delta_dse:.1f}% delta_SFC_vs_TS={g_delta_sfc:.1f}%"
        )


def pytket_table(all_rows):
    print("\n%% -- pytket-mapping shared-layout table (25q + 64q) --")
    dse_matched, sfc_matched = [], []
    for r in all_rows:
        if r["suite"] not in ("25", "64"):
            continue
        pk = r.get("pytket_ebits")
        dse = r.get("dSE_pytket")
        sfc = r.get("sfc_pytket")
        dse_epr = dse["epr"] if dse else None
        sfc_epr = sfc["epr"] if sfc else None
        cname = r["circuit"].replace("_OLD_DEEP", "")
        if dse_epr is not None:
            dse_matched.append(dse_epr)
        if sfc_epr is not None:
            sfc_matched.append(sfc_epr)
        line = (
            f"{r['suite']}q & {cname:<11} & {fmt_i(pk):>5} & "
            f"{fmt_i(dse_epr):>4} & {fmt_i(dse['swaps'] if dse else None):>5} & "
            f"{fmt_i(sfc_epr):>4} & {fmt_i(sfc['swaps'] if sfc else None):>5} \\\\"
        )
        print(line)
    print("\\midrule")
    g_dse = gmean(dse_matched)
    g_sfc = gmean(sfc_matched)
    print(f"%% gmean over rows where present: dSE={g_dse}, SFC={g_sfc} (n_dse={len(dse_matched)}, n_sfc={len(sfc_matched)})")


def main():
    results_path = Path(sys.argv[1]) if len(sys.argv) > 1 else _HERE / "compare_results.json"
    records = json.loads(results_path.read_text())

    for suite in ("25", "64", "80"):
        rows = [r for r in records if r["suite"] == suite]
        if not rows:
            continue
        print(f"\n%% ================ suite {suite}q ================")
        own_protocol_table(rows, f"{suite}q")
        shared_layout_table(rows, f"{suite}q", "dSE_shared", "sfc_shared", "TeleSABRE mapping")

    pytket_table(records)


if __name__ == "__main__":
    main()
