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
    ts_matched, sfc_matched, dse_matched, ref_matched = [], [], [], []
    n_failed = 0
    for r in rows:
        ts = r["telesabre"]
        dse = r["dSE"]
        sfc = r["sfc"]
        ref = r.get("sfc_refined")
        ts_epr = ts["epr"] if ts else None
        sfc_epr = sfc["epr"] if sfc else None
        dse_epr = dse["epr"] if dse else None
        ref_epr = ref["epr"] if ref else None
        delta = pct_delta(ref_epr if ref_epr is not None else sfc_epr, ts_epr)
        cname = r["circuit"].replace("_OLD_DEEP", "")
        if ts_epr is None:
            n_failed += 1
        else:
            ts_matched.append(ts_epr)
            sfc_matched.append(sfc_epr)
            dse_matched.append(dse_epr)
            ref_matched.append(ref_epr)
        star = "$^{\\ast}$" if ts_epr is None else ""
        line = (
            f"{cname:<11}{star} & {fmt_i(ts_epr):>4} & {fmt_i(ts['swaps'] if ts else None):>5} & "
            f"{fmt_i(dse_epr):>4} & {fmt_i(dse['swaps'] if dse else None):>5} & "
            f"{fmt_i(sfc_epr):>4} & {fmt_i(sfc['swaps'] if sfc else None):>5} & "
            f"{fmt_i(ref_epr):>4} & {fmt_i(ref['swaps'] if ref else None):>5} & "
            f"${fmt_pct(delta)}$ \\\\"
        )
        print(line)
    g_ts = gmean(ts_matched)
    g_sfc = gmean(sfc_matched)
    g_dse = gmean(dse_matched)
    g_ref = gmean(ref_matched)
    g_delta = pct_delta(g_ref if g_ref is not None else g_sfc, g_ts)
    n = len(ts_matched)
    print("\\midrule")
    if g_ts is not None:
        print(
            f"\\textbf{{gmean}} ({n}) & {g_ts:.1f} & & {g_dse:.1f} & & {g_sfc:.1f} & & "
            f"{g_ref:.1f} & & $\\mathbf{{{fmt_pct(g_delta)}}}$ \\\\"
        )
        print(f"%% gmean(n={n}, failed={n_failed}) TS={g_ts:.2f} dSE={g_dse:.2f} "
              f"SFC={g_sfc:.2f} SFC+R={g_ref:.2f} delta_vs_TS={g_delta:.1f}%")
    else:
        print(f"%% TeleSABRE converged on 0 circuits in {label}; no gmean vs TS possible")
        g_dse_all = gmean([r["dSE"]["epr"] for r in rows if r["dSE"]])
        g_sfc_all = gmean([r["sfc"]["epr"] for r in rows if r["sfc"]])
        print(f"%% dSE-only gmean={g_dse_all}, SFC-only gmean={g_sfc_all} (no TS baseline)")


def shared_layout_table(rows, label, ts_key, sfc_key, name, ref_key=None):
    print(f"\n%% -- {label}: shared-layout table ({name}) --")
    ts_matched, sfc_matched, dse_matched, ref_matched = [], [], [], []
    for r in rows:
        ts = r["telesabre"]
        dse = r.get(ts_key)
        sfc = r.get(sfc_key)
        ref = r.get(ref_key) if ref_key else None
        ts_epr = ts["epr"] if ts else None
        sfc_epr = sfc["epr"] if sfc else None
        dse_epr = dse["epr"] if dse else None
        ref_epr = ref["epr"] if ref else None
        cname = r["circuit"].replace("_OLD_DEEP", "")
        if ts_epr is not None and dse_epr is not None and sfc_epr is not None:
            ts_matched.append(ts_epr)
            sfc_matched.append(sfc_epr)
            dse_matched.append(dse_epr)
            ref_matched.append(ref_epr if ref_epr is not None else sfc_epr)
        delta_sfc = pct_delta(ref_epr if ref_epr is not None else sfc_epr, ts_epr)
        delta_dse = pct_delta(dse_epr, ts_epr)
        star = "$^{\\ast}$" if not (ts_epr is not None and dse_epr is not None and sfc_epr is not None) else ""
        line = (
            f"{cname:<11}{star} & {fmt_i(ts_epr):>4} & {fmt_i(ts['swaps'] if ts else None):>5} & "
            f"{fmt_i(dse_epr):>4} & {fmt_i(dse['swaps'] if dse else None):>5} & ${fmt_pct(delta_dse)}$ & "
            f"{fmt_i(sfc_epr):>4} & {fmt_i(ref_epr):>5} & ${fmt_pct(delta_sfc)}$ \\\\"
        )
        print(line)
    g_ts = gmean(ts_matched)
    g_sfc = gmean(sfc_matched)
    g_dse = gmean(dse_matched)
    g_ref = gmean(ref_matched)
    n = len(ts_matched)
    print("\\midrule")
    if g_ts is not None:
        g_delta_sfc = pct_delta(g_ref if g_ref is not None else g_sfc, g_ts)
        g_delta_dse = pct_delta(g_dse, g_ts)
        print(
            f"\\textbf{{gmean}} ({n}) & {g_ts:.1f} & & {g_dse:.1f} & & $\\mathbf{{{fmt_pct(g_delta_dse)}}}$ & "
            f"{g_sfc:.1f} & {g_ref:.1f} & $\\mathbf{{{fmt_pct(g_delta_sfc)}}}$ \\\\"
        )
        print(
            f"%% gmean(n={n}) TS={g_ts:.2f} dSE={g_dse:.2f} SFC={g_sfc:.2f} "
            f"SFC+R={g_ref:.2f} delta_dSE_vs_TS={g_delta_dse:.1f}% "
            f"delta_SFC+R_vs_TS={g_delta_sfc:.1f}%"
        )
    return ts_matched, dse_matched, ref_matched


def pytket_table(all_rows):
    print("\n%% -- pytket-mapping shared-layout table (25q + 64q) --")
    dse_matched, sfc_matched, ref_matched = [], [], []
    for r in all_rows:
        if r["suite"] not in ("25", "64"):
            continue
        pk = r.get("pytket_ebits")
        dse = r.get("dSE_pytket")
        sfc = r.get("sfc_pytket")
        ref = r.get("sfc_pytket_refined")
        dse_epr = dse["epr"] if dse else None
        sfc_epr = sfc["epr"] if sfc else None
        ref_epr = ref["epr"] if ref else None
        cname = r["circuit"].replace("_OLD_DEEP", "")
        if dse_epr is not None:
            dse_matched.append(dse_epr)
        if sfc_epr is not None:
            sfc_matched.append(sfc_epr)
        if ref_epr is not None:
            ref_matched.append(ref_epr)
        line = (
            f"{r['suite']}q & {cname:<11} & {fmt_i(pk):>5} & "
            f"{fmt_i(dse_epr):>4} & {fmt_i(dse['swaps'] if dse else None):>5} & "
            f"{fmt_i(sfc_epr):>4} & {fmt_i(ref_epr):>5} \\\\"
        )
        print(line)
    print("\\midrule")
    g_dse = gmean(dse_matched)
    g_sfc = gmean(sfc_matched)
    g_ref = gmean(ref_matched)
    print(f"%% gmean over rows where present: dSE={g_dse}, SFC={g_sfc}, SFC+R={g_ref} "
          f"(n_dse={len(dse_matched)}, n_sfc={len(sfc_matched)}, n_ref={len(ref_matched)})")


def main():
    results_path = Path(sys.argv[1]) if len(sys.argv) > 1 else _HERE / "compare_results.json"
    records = json.loads(results_path.read_text())

    all_ts, all_dse, all_sfc = [], [], []   # all_sfc holds the REFINED column
    for suite in ("25", "64", "80"):
        rows = [r for r in records if r["suite"] == suite]
        if not rows:
            continue
        print(f"\n%% ================ suite {suite}q ================")
        own_protocol_table(rows, f"{suite}q")
        ts_m, dse_m, sfc_m = shared_layout_table(
            rows, f"{suite}q", "dSE_shared", "sfc_shared", "TeleSABRE mapping",
            ref_key="sfc_shared_refined",
        )
        all_ts += ts_m
        all_dse += dse_m
        all_sfc += sfc_m

    print(f"\n%% -- shared-layout table (TeleSABRE mapping): gmean over all {len(all_ts)} circuits --")
    g_ts, g_dse, g_sfc = gmean(all_ts), gmean(all_dse), gmean(all_sfc)
    g_delta_dse = pct_delta(g_dse, g_ts)
    g_delta_sfc = pct_delta(g_sfc, g_ts)
    print(
        f"%% NOTE: all_sfc is the REFINED column; the 1-pass pooled gmean is "
        f"computed separately in the paper's table row."
    )
    print(
        f"\\textbf{{gmean, all}} ({len(all_ts)}) & {g_ts:.1f} & & {g_dse:.1f} & & "
        f"$\\mathbf{{{fmt_pct(g_delta_dse)}}}$ & & {g_sfc:.1f} & $\\mathbf{{{fmt_pct(g_delta_sfc)}}}$ \\\\"
    )
    print(
        f"%% gmean(n={len(all_ts)}) TS={g_ts:.2f} dSE={g_dse:.2f} SFC={g_sfc:.2f} "
        f"delta_dSE_vs_TS={g_delta_dse:.1f}% delta_SFC_vs_TS={g_delta_sfc:.1f}%"
    )

    pytket_table(records)


if __name__ == "__main__":
    main()
