# Change log — round 3

Maps each edit to the review IDs it answers. Batches follow
`triage_round3.md`. Every changed passage is wrapped in `\chg{...}`, which
typesets dark red; set `\revisionhighlightfalse` in either preamble for a
clean copy.

Baseline tag: `paper-round3-pre`.

---

## Batch 1 — corrections of fact (applied)

Seven passages, five findings. **No numbers changed**;
`verify_paper_numbers.py` and `verify_tex_tables.py` both pass unchanged,
and both documents compile with zero errors and zero overfull boxes at 14
and 8 pages.

| ID | File | What changed |
|---|---|---|
| `B06` | `sfc_appendix.tex:1072` | "the runs of Table~V of the main paper" -> `\ref{tab:maineprs}`. Table V is the 6-row scale-up table; `tab:mainswaps` holds the 24 own-protocol rows. Typesets as "the runs of Table X". |
| `B06` | `sfc_appendix.tex:1079` | Same fix in `tab:mainswaps`'s caption. |
| `A01` | `sfc_appendix.tex:1131` | Appendix I no longer sums a per-iteration cost over the gate count. Introduces $C_\mathrm{iter}$, states the route cost as $T_\mathrm{pre} + O(I\cdot C_\mathrm{iter})$, keeps $I$ independent and says why ($N$ does not bound it: SWAP-only iterations, relief actions), points at III-H's guards for what does bound it, and labels the analysis as one route against the paper's complete-protocol timings. Removes the contradiction of carrying $KM^2\log M$ inside a bound declared to exclude precomputation. |
| `B07` | `sections/07-related-work.tex:32` | "no instance in this evaluation being left unrouted" -> scoped to the selected-horizon protocol of III/IV-E, which is what completes 48/48. Resolves the contradiction with Appendix K's fixed-horizon failure. |
| `B13` | `sections/03-porter-compiler.tex:8` | "Algorithm 1 charts one iteration" -> "charts the routing pass". It contains the whole `while` loop and the `return`. |
| `B13` | `sections/03-porter-compiler.tex` alg. line 1 | "active/frontier sets" -> "active and front sets". IV-B bans synonyms and the paper's term is *front*. |
| `B14` | `sections/03-porter-compiler.tex:184` | Self-reference removed. `sec:sfc-prep` resolves to III-D, the subsection the sentence sits in; it now states the condition inline ("no preparation SWAP improves readiness"). |

**New in both preambles:** `\chg`, `\ifrevisionhighlight`. **New in the
appendix:** the `\mainProgress` xr macro (III-H), needed by `A01`.

Checks run after the batch: generator idempotence not required (no table
touched); both verifiers; broken-sentence sweep (only TikZ paths and the
biography's "B.Sc./Ph.D." match, both false positives); orphaned-float sweep
(main clean; the appendix's three — `fig:arch`, `fig:catent-app`,
`tab:circuits` — are pre-existing at `paper-round3-pre`, unrelated to this
batch).

## Batches 2–4 — pending

## Batch 4 (part) — the A06 evidence (applied ahead of batch 2, which depends on it)

**Re-run result.** The fixed-horizon leg of `scaleup_results.json`
reproduces exactly under current code — all six EPR values identical, gmean
$1026.5$. That was the unverified half and it is now confirmed.

**One instance did not reproduce on the selected side.** 360q QPEexact came
back at $2{,}342$ (L=16), not the released $1{,}224$ (L=128), on an idle
machine. Diagnosed rather than worked around: L=128 reaches exactly $1{,}224$
but costs $14.4$–$14.9$ s against a speculative share of $14$ s derived from
its own first route. **It misses by under a second**, and the share widens as
the machine slows, so a slower machine is likelier to return the released
value. Released `probe_horizon_budget.py` measures all three quantities.

| ID | File | What changed |
|---|---|---|
| `A06` | `sections/05-results.tex` V-D | New paragraph: at the configured horizon the same six instances from the same layouts give $1{,}026.5$ against \dSABRE{}'s $705.7$ ($1.45\times$, losing all six); selection changes nothing else and reaches $507.7$ ($0.72\times$, winning all six). Notes that all six select $L_\mathrm{tp}{=}128$ and none the configured $16$. |
| — | `sections/04-methodology.tex` IV-C | The reproducibility paragraph now names the instance where the wall-clock budget binds, gives the share formula, and cites the probe. Author's decision: report the selected result and flag it, rather than raise `SPECULATIVE_TIME_FACTOR`, which would change every selected route in the paper. |
| — | `probe_horizon_budget.py` (new, released) | Reproduces the default-horizon route, the derived share, the L=128 route and whether it fits. Follows the `probe_front_limit.py` precedent for a corrected measurement. |
| — | `verify_paper_numbers.py` | Five new pins: the $1026.5$ gmean, that the default horizon loses all six, the $1.45\times$ ratio (its pin existed as a regression guard and is now quoted again), and 360q QPEexact's $1{,}224$/L=128 selected result and $2{,}342$ default-horizon fallback. |

## Batch 2 — attribution and claim scope (applied)

Nine passages, seven findings. **No numbers changed**; both verifiers pass.

| ID | File | What changed |
|---|---|---|
| `B05` | `08-conclusion.tex:18` | "the ablations attribute these results" was wrong on two of its three clauses. Now names the kind of evidence behind each: an ablation for relief, the fixed-layout control for the layout, and the fixed-vs-selected horizon comparison — now reportable, from `A06` — for the horizon, quoting $0.72\times$ against $1.45\times$. |
| `A02`/`B04` | `06-discussion.tex:20` | The portfolio no longer attributes the gain to "the plan-oriented stage, the relief tiers and the horizon". It states that each compiler reaches circuits the other does not, keeps both illustrative margins, and says plainly that the measurement cannot say which difference produces any given win — listing the seven that vary at once. Consistent with III-D and Appendix K, which decline the same attribution. |
| `B03` | `05-results.tex:145` | "The routing loops are equivalent within noise" — no noise model, deterministic routes, single measurements. Heading is now "Changing the routing loop moves less than changing the layout"; the body states the 3% proximity directly. |
| `A05`/`B01` | `05-results.tex:150` | "the initial layout is the weaker component" read as the opposite of the spread it follows from. Now "the larger source of variation in both compilers, and the component in which each has more to gain". Both reviewers flagged this independently. |
| `B09` | `05-results.tex` V-F | "slightly ahead at $0.91\times$" named no metric and sat beside an EPR ratio. Now names time and EPR separately. |
| `A10` | `00-abstract.tex:13` | "all three known inter-core primitives" was an exhaustiveness claim Related Work does not establish -> "the three inter-core primitives studied under this cost model". |
| `B08` | `00-abstract.tex` (3 places) | Bases added: the TeleSABRE percentages are "over the instances both complete"; the scale-up series is "of QFT and QPEexact"; the portfolio is "an oracle over both, costing both". |

## Batch 3 — pending

`A04`/`B02` (Algorithm 1's abandonment branch), `B10` (plan tuple),
`A08` (machine class), `A09` (tail-relief seed rule), `B11`, `B12`, `B15`,
`A07`.

`A08` and `A04` are confirmed from the code and the device files; the
findings are recorded in the session notes and reproduced in
`triage_round3.md`'s questions section.
