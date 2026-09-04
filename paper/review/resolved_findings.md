# Already reviewed and settled — do not re-report

This manuscript has been through **two prior review rounds**. Both were
answered in full and the changes are in the version you are reading. The
items below are closed. Re-reporting them costs review budget without
improving the paper.

**How to use this list.** If you believe a settled item is still wrong *in
the current text*, say so — but cite the current wording and explain what is
still defective about it, rather than restating the original finding. Where
a section below invites a specific challenge, that challenge is welcome.

---

## A. Errors already found and corrected

Do not report these; they are fixed. Listed so you can recognise them.

1. **`f_min` is not a maintained invariant.** Sec. III-A once claimed every
   core keeps at least $f_\mathrm{min}=2$ free positions. The router tests
   `free(dst) >= f_min` *before* a TELEDATA, so a core admitted at exactly
   two drops to one. III-A now separates the three roles $f_\mathrm{min}$
   plays and explicitly does not claim an invariant. **Do not ask for the
   invariant language back.**
2. **The front-size cap is gone.** A prior round showed the claim that it
   never binds --- because front gates are pairwise qubit-disjoint --- was
   false: disjointness bounds the front by $n$, and 1Q gates are not
   excluded. It binds on all three QPEexact scale-up instances. Rather than
   document it, the parameter was **removed** (2026-09-01): routing capped
   and uncapped was measured on all six scale-up instances and agrees on
   EPR, SWAPs, depth and tie count, byte-identical on the three QFT
   instances and a permutation differing only in single-qubit gates on the
   three QPEexact ones. `dag_front_limit`, its row in the parameter table
   and its probe script no longer exist, and no released number changed.
   The manuscript you are reading has no front cap in it.
3. **Notation collision.** $\ell$ denoted both the layout and a gate's ASAP
   layer; the ASAP layer is now $\mathrm{asap}(g)$.
4. **The tie-break order was misstated, and the key has since been cut to
   three terms.** The order is displayed in III-E and is now
   $(-\mathrm{total}, \mathrm{prep}, -f_\mathrm{dst})$: the readiness flag
   is subsumed by preparation cost, which is zero exactly when a plan is
   ready, and the plan-kind rank and the trailing lookahead term were
   measured to be unreachable and removed. III-E states that measurement.
   **Do not ask for the six-term key back.**
5. **Baseline configuration defect.** A misspelled TeleSABRE config key made
   the baseline run at the wrong parameter. Fixed; all dependent legs re-run;
   the headline margins moved as a result and the current figures are post-fix.

## B. Claims already narrowed

Each of these was overstated in an earlier version and has been scoped. Do
not ask for the same hedge again; do report a *new* overstatement.

| Was | Now |
|---|---|
| "the figure of merit that matters" | the primary metric **under the stated cost model** |
| "completes every instance" | scoped to the evaluated instances under the selected-horizon protocol; success distinguished from a completion guarantee |
| "architecture independence" | robustness on two non-grid core graphs |
| "scaling to 360 qubits" | scale-up **on QFT and QPEexact only** |
| exact reproducibility | a single route is byte-identical; the *protocol* is reproducible only up to its wall-clock budget |
| "independent replay verifier" | separately implemented, sharing no routing/scoring/layout code — **and baselines are not replay-verified**, stated |
| "a search-budget gap, not a routing deficit" | increased deterministic search closes and reverses the gap; the causal conclusion is explicitly declined |
| relief turns failure into "a non-event" | the measured statement plus the explicit note that it is not a guarantee |
| "no constant is best" | no **tested** constant is best |
| "the plan abstraction produces the reductions" | withdrawn; the ablations do not isolate its share |

Removed vocabulary, deliberately: "decisively better", "one-sided", "the
cleanest comparison", "the honest description", "earns its place outright",
"a non-event", "all three favour the baseline", and "attempt" in any sense.

## C. Structural decisions taken, with reasons

Challenge these only with an argument that engages the stated reason.

1. **The title keeps "Plan-Committed."** A prior review argued the ablation
   shows commitment does not lower EPR, so the branding mismatches the
   evidence. The paper's position: that conflates the plan-oriented
   *framework* (whole-plan candidates, scored on gain, preparation demoted
   to a tie-break) with the commitment *rule* (do not reopen until ready).
   The ablation held the plan set, scoring and relief tiers fixed and varied
   only the rule. No experiment removes the abstraction, and Sec. III-D says
   so as the clearest gap in the attribution.
2. **Section III describes exactly one routing pass and states no results.**
   Horizon selection and backward refinement are multi-pass operating
   protocols and live in IV-E by design.
3. **The per-circuit main table is in the appendix** (`tab:maineprs`); the
   main paper carries a suite-level summary. This was adopted from review.
4. **Algorithm 1 was not split into three**; the relief branch is described
   in consolidated prose in III-G and the failure taxonomy in III-H.
5. **Protocol names `+R` / `+S` are kept** and expanded in every caption;
   they are established across the released harness and results files.
6. **Compile time is reported everywhere and never led with.** Against
   TeleSABRE the result is an EPR reduction; against dSABRE it is
   competitiveness at a stated operating point.
7. **PORTER+S is in Appendix J, not the main paper** — it costs 1.9× the
   wall clock of +R for 1.8% EPR (improving six instances of twenty-four and
   tying the other eighteen), adds a second in-sample-fitted quantity,
   and its mechanism *is* choosing the layout, so it can never appear in the
   layout×router grid without destroying that control.
8. **Table III carries no +S column**, for the reason in (7).

## D. Caveats the paper already declares

Do **not** report these as undisclosed. You may argue a declaration is
**inadequate** — that the paper concedes a limitation and then relies on the
claim anyway, or that a threat is understated relative to what it threatens.
That is a genuinely useful finding.

- Horizon selection is fitted **in-sample** on the same 48 instances
  reported on; no held-out family; bounded only by the portfolio argument
  (the configured horizon always competes and wins ties).
- **No completion guarantee.** Correctness and termination hold; completion
  is empirical. dSABRE has a termination-with-success proof; PORTER does not.
- **The plan abstraction's share is not isolated** by any experiment.
- Own-protocol budgets are **unequal** (4 routes vs 9), stated in Table I.
- **Equal-route, layout-controlled comparison is a loss for PORTER**, stated
  as such in V-B.
- Two 80-qubit instances (AE, QNN) are **reconstructed**, not stock generator
  output.
- TeleSABRE runs from a **patched binary** (the stock one segfaults on two of
  three suites); not otherwise audited.
- Timing is a **single measurement, no warm-up**, Python vs C across
  compilers.
- Geometric means are over **jointly completed** instances only; excluding
  failures flatters a baseline that fails its hardest instances, which is why
  completion counts are reported alongside every mean.

## E. Where review attention is worth spending

Not instructions — an honest statement of where the authors believe the
manuscript is thinnest. You are not bound by it.

1. **Whether each claim's basis matches its scope.** Different tables use
   different bases (jointly completed vs all 24; with vs without the two
   cheapest circuit families). A claim quoted on one basis and generalised on
   another is the defect class most likely to remain.
2. **Whether the portfolio result (C5) is presented as more than it is.** It
   is an oracle over both compilers' routes, costs both, and no rule predicts
   the winner. It is used in the abstract and introduction to answer "what
   does a second compiler add".
3. **Section III (≈3,000 words)** is the longest section and the only one
   with real slack. Whether its length is earned, and whether a reader can
   follow the plan lifecycle from it, is open.
4. **Whether the negative results are integrated or merely admitted** — the
   TELEDATA-only result in particular, which is reported as a currency
   mismatch in the scorer rather than a verdict on packets.
5. **Whether the dSABRE comparison reads as fair.** dSABRE is concurrent
   work, deliberately not framed as a baseline PORTER must beat. Whether
   that framing holds consistently, or slips into competitive language
   somewhere, is worth checking.
