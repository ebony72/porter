# Responses to the PORTER Reviews

*Manuscript:* **PORTER: A Plan-Committed Router for Multi-Core Distributed
Quantum Computers**

This document answers both reviews, most recent first. Part I responds to
the additional review of the revised manuscript; Part II is the response to
the original presentation-and-organisation review, retained for reference.
Section numbers refer to the current manuscript.

---

# Part I --- Response to the Second (Additional) Review

The second review found ten Priority-1 issues; we accept all ten, and all
of the Priority-2 and most of the Priority-3 items. Two of its findings
were errors in the manuscript, not only in its wording, and we describe
those first. Section numbers refer to the current manuscript.

## Errors it uncovered

**The `f_min` invariant did not hold (its §4).** Section III-A said every
core "keeps at least `f_min = 2` free positions". The router tests
`free(dst) >= f_min` *before* a TELEDATA, so a core admitted at exactly two
free drops to one. We instrumented four circuits and confirmed cores do
reach one free position during routing. III-A now separates the three roles
`f_min` plays — the initial condition, the pre-action admission threshold
(leaving at least one free afterward), and the reservoir threshold — and no
longer claims a maintained invariant.

**PORTER+S was described wrongly (its §5).** Chasing the reported 9–13
routes against a stated four-γ sweep showed the method text was wrong in
three ways: the sweep is over **five** values `{0.80, 0.90, 0.95, 0.99,
1.0}`, not four — and `γ = 0.80` in fact wins phase 1 on nine of the
twenty-four instances, so the omitted value is the most frequent winner —
and the protocol then runs the five-pass refinement schedule from **two**
seed layouts, phase 1's winner and the `γ = 0.99` layout. IV-F3 now gives
the composition and derives the counts: `5 + 4 = 9` routes when `γ = 0.99`
wins, `5 + 4 + 4 = 13` otherwise.

**The stated tie-break order was also wrong.** Answering §25 required
reading the selection key, which is
`(−total, ¬ready, prep, rank(π), cap, −lookahead)`. The paper had said
readiness cost enters "after gain and plan kind"; it enters *before* plan
kind, and a readiness flag precedes it. III-E now displays the key.

## The central correction: budget language (its §1, §2, §3)

The review is right that we presented a five-route PORTER result as a
matched-budget shared-layout result and generalised it into the Abstract and
Conclusion. Under equal three-route budgets DSABRE has the lower pooled
count (100.9 against 107.7); PORTER leads only with its five-route
refinement schedule against DSABRE's three.

V-B is now split into an **equal-route** comparison, labelled as the
controlled test and reported as a loss for PORTER, and a
**refinement-schedule** comparison, explicitly stated not to be
budget-matched and not to isolate the router. RQ2 no longer says "matched
routing budgets"; the pooled grid states both budgets; "single-shot" is
gone; and the Abstract and Conclusion now say that the outcome depends on
both layout and routing budget, giving both directions.

## Other accepted items

| Item | Change |
|---|---|
| §6 | All uses of "attempt" removed outside the sentence banning it |
| §7 | Table V now reports complete protocol time for **both** compilers, replacing the single per-route DSABRE column |
| §8 | VI no longer claims the plan abstraction produces the reductions; it is the defining structural difference, and the ablations do not isolate its share |
| §9 | The TELEDATA column is presented as two configurations — strict removal (ten failures) and a vocabulary variant with generalised relief — and no longer as a one-factor ablation |
| §10 | "TELEGATE is what makes PORTER terminate" → essential to successful *completion*, since the guards give termination regardless |
| §11–15 | Causal and threshold language scoped: "of the interventions we tested"; evaluated sizes rather than "above 150"; core graph matters *more than* core shape; the star gap is the *dominant observed* source; "no *tested* constant is best" |
| §16 | The portfolio guarantee is now conditional on the configured route completing, and notes it can raise compile time and that selection depends on the wall-clock budget |
| §17 | Byte-identical reproducibility scoped to the released environment and revision |
| §18 | The baseline verification asymmetry is stated at the first comparison table, not only in Methodology |
| §19 | Introduction compressed again; the 41-instance, heavy-hex, 0.72× and 0.6% figures moved to Results |
| §20 | **Accepted.** The per-circuit table moved to the appendix; the main paper carries a suite-level summary with completion counts and complete times. The reviewer is right that our earlier reason — that the harness parses it — was not a reason; the harness now parses it in the appendix |
| §21 | Ablation gmean rows are self-labelling (`paired n=14/16/12`) |
| §22 | Protocol names expanded in each table caption (we keep `+R`/`+S`/`+SR` rather than renaming) |
| §23 | "published state of the art" → "the strongest published router we identified under this cost model" |
| §24 | III-C now states that local candidates *minimise* distance while remote plans *maximise* gain |
| §26 | `D(p)` now reads "including the plan's seed gate" |
| §27 | Packet gain described as a committed executable sequence, not "current work" |
| §28 | IV-H adds timing methodology: machine, OS, interpreter, single measurement per configuration, no warm-up, and what that implies for reading the ratios |
| §29 | "0.27× DSABRE's speed" → "takes 3.7× as long per route" |

## Declined

**§22, renaming the protocols.** We expand `PORTER+R`, `+S` and `+SR` in
every table caption but keep the names, which are established across the
released harness and results files.

**§30, shortening this document.** The format here is issue, action and
location, as suggested; we have kept the reasoning on the two declined
items and on the errors, since those are where a reader most needs it.

Every number in the manuscript remains checked by two harnesses — 186
checks on what the paper states, 46 on the LaTeX rows that will typeset —
and both pass, including new checks on the suite-level summary table's
cells, its completion counts, and the two new complete-time columns.

---

# Part II --- Response to the Presentation and Organisation Review

We thank the reviewer for a detailed and constructive reading. The review's
central diagnosis — that the paper had more technical content than its
presentation could carry, and that a reader could not quickly tell which
claim rested on which experiment — was correct, and we have restructured the
manuscript around it.

We have adopted the great majority of the recommendations. We decline two,
and we explain our reasoning rather than simply noting the disagreement. The
review also led us to two **factual errors** in the manuscript, which we
describe first because they matter more than any presentational point.

Section numbers below refer to the revised manuscript unless marked
*(previous)*.

---

---

## 1. Two factual errors the review uncovered

### 1.1 The front-size cap claim was wrong

The reviewer wrote (§4.5):

> The assertion that the front-size cap never binds because front gates are
> pairwise qubit-disjoint is incomplete: pairwise disjointness bounds the
> front by roughly half the number of qubits for two-qubit gates, but
> one-qubit gates can also be present, and the stated benchmark maximum
> should be reported if the cap truly never binds.

This is correct and the previous claim was false. Disjointness bounds the
front by the logical-qubit count *n*, not by 96, and single-qubit gates are
not excluded by it. We instrumented the router and measured the maximum front
size on every instance:

| instance | *n* | max &#124;front&#124; | cap 96 |
|---|---|---|---|
| 25q random | 25 | 22 | — |
| 64q QFT | 64 | 17 | — |
| 64q random | 64 | 47 | — |
| 80q QFT | 80 | 6 | — |
| 100q QFT | 100 | 8 | — |
| **100q QPEexact** | 100 | **100** | **binds** |
| 200q QFT | 200 | 8 | — |
| **200q QPEexact** | 200 | **200** | **binds** |
| 360q QFT | 360 | 8 | — |
| **360q QPEexact** | 360 | **360** | **binds** |

The cap binds on **all three QPEexact instances** of the scale-up suite, not
on none of them. We then checked whether it changes any reported result:
re-routing all three with the cap removed leaves EPR **and** SWAP counts
identical (262, 1343, 2342 EPR; 2940, 9840, 18834 SWAPs). The reason is
structural — truncation is by ascending gate index, and directly executable
gates drain before any routing decision is taken, so discarded gates return
on the following iteration.

Section III-B now reports this as a measurement rather than asserting it, and
a new released script, `probe_front_limit.py`, reproduces both the maximum
front sizes and the capped/uncapped equivalence. No reported number changes.

### 1.2 A notation collision

Following §7.5, we found that `\ell` denoted both the layout (`\ell_0`, `\ell`)
and a gate's as-soon-as-possible layer (`\ell(g)`) — twice within the same
subsection. The ASAP layer is now written `asap(g)`.

---

## 2. The one substantive recommendation we decline

### 2.1 The title, and what the ablation actually shows (§2.2, §4.1, §5.7, §11)

The review's argument is that the title foregrounds plan commitment, that the
ablation shows commitment does not improve EPR consumption, and that the
paper's branding therefore mismatches its evidence.

**We believe this conflates two separable things**, and that the fault lies
with our terminology rather than with the title. The manuscript used "plan
commitment" for both:

1. the **plan-oriented framework** — generating whole inter-core actions as
   candidates, scoring each on the gate progress it buys under the hypothesis
   that its readiness conditions hold, and demoting preparation cost to a
   tie-break; and
2. the **commitment rule** — that once a plan is selected it is not reopened
   until it is ready.

The `Hop-wise` ablation column holds the plan set, the scoring function and
both relief tiers fixed, and varies **only (2)**. It re-derives and re-scores
the same whole plans every iteration. It therefore measures when the choice is
revisited and nothing else. That it reaches the same EPR on the same number of
routing moves is evidence that the *commitment rule* is not where routing
quality comes from. It is **not** evidence that the plan abstraction is idle,
because no column in the table removes it.

We have therefore:

- kept the title;
- separated the two terms throughout, and defined a plan formally as a tuple
  in Section III-D, distinguishing plan *utility*, *readiness cost* and
  *preparation policy*;
- stated in the Introduction, where the negative result is reported, that the
  ablation removes the commitment rule and not the abstraction it rests on;
- and, in Section VI, named this explicitly as **the clearest gap in our
  attribution**: isolating the abstraction would require a hop-granular
  candidate set, which is a different router and one we have not built.

We think this is a stronger and more honest position than the retitling would
produce, because it states a limitation the review did not identify rather
than resolving the tension by renaming.

We also note the reviewer's related suggestion (§4.1) that if the title is
retained, the Introduction should say that commitment is primarily an
efficiency mechanism. It now does — but we deliberately do not lead with
compile time anywhere. Against TELESABRE the paper's result is a substantial
reduction in EPR pairs; against DSABRE it is competitiveness at a stated
operating point. Compile time is reported in every table and is never the
headline.

### 2.2 One structural recommendation partially declined (§4.7)

We agree Table II (the main comparison) is dense, and we have not split it into a suite-level
summary with per-circuit rows in an appendix. It is the paper's primary
evidence for the TELESABRE comparison, and our table-checking harness parses
its rows directly against the raw results. We have instead reduced the load
around it: completion counts are now stated separately from the geometric
means (§6 below), the bolding rule is stated in the caption, and the
interpretive material that previously surrounded it has moved to Section VI.
We are willing to make this change if the reviewer considers it important.

We likewise did not split Algorithm 1 into three algorithms (§4.5). The
capacity-relief branch is now described in consolidated form in Section III-G
and the failure taxonomy in III-H, which we believe addresses the underlying
readability concern at lower cost in space.

---

## 3. Structural revisions adopted

### 3.1 Research questions and reorganised evaluation (§2.1, §3)

The manuscript now states four research questions (Section IV-A) and Section V
is organised around them:

| | |
|---|---|
| **RQ1** End-to-end cost under each compiler's own protocol | §V-A |
| **RQ2** Routing quality with the layout controlled | §V-B |
| **RQ3** Mechanism attribution | §V-C |
| **RQ4** Robustness to scale and topology | §V-D, §V-E |
| | EPR/time operating frontier, §V-F |

Each subsection opens with its question, what is held fixed, and the metric,
in the two-or-three-sentence form the review proposed.

### 3.2 Method separated from operating protocols (§3, §4.5)

We accept the reviewer's point that backward refinement and horizon selection
are not part of a single routing pass:

> They are better described as **evaluation-time operating protocols** or
> **meta-strategies**, because they execute the router repeatedly rather than
> defining a single routing pass.

**Section III now describes exactly one routing pass.** Horizon selection,
backward refinement and the layout-discount search have moved to Section IV-F,
"Operating Protocols", where they are presented as strategies that invoke the
router repeatedly and select among the results.

### 3.3 Method separated from retrospective interpretation (§2.4)

Section III no longer anticipates results. We removed the empirical passages
("where it pays it pays well", the per-instance improvement examples, the
free-slot vectors), the forward references to outcomes, and the inline
comparisons against both baselines — the last of these now appear in Related
Work, alongside the new taxonomy table.

### 3.4 New Discussion and Limitations (§3, §4.7)

Section VI collects the interpretations that were previously distributed as
qualifications, in the "Interpretation paragraph" form the review requested,
covering: what the plan abstraction buys versus what commitment buys; the
layout-versus-horizon regimes; why TELEDATA-only can beat the richer
vocabulary; and what the completion record does and does not show.

### 3.5 New Threats to Validity (§6.3)

Section VI-A covers benchmark coverage, in-sample parameter rules,
reconstructed instances, the patched baseline binary, the evolving concurrent
baseline, unequal native budgets, aggregation over failures, implementation
and timing fairness, and the cost model.

### 3.6 Protocol and budget table (§2.5)

Table I (`tab:budgets`) gives, for **every** configuration appearing in the
results: compiler, layout source, layout count, routing passes per layout,
total routes, and selection criterion — grouped by purpose (own protocol,
shared layout, cross layout, ablation). We also adopted the reviewer's point
that the three fairness notions are complementary rather than ranked:

> Do not imply that one is universally fair. Present them as complementary
> controls.

The text now states which notion each comparison equalises, and notes that
equal route counts favour PORTER on time while equal layout budgets do not,
since PORTER costs more per pass.

### 3.7 Terminology (§6.1)

Section IV-B fixes *route*, *candidate layout*, *protocol*, *candidate
horizon* and *complete compile cost*, and the machine and failure vocabulary.
Per the review, "attempt" is no longer used, since the baselines use it in two
senses.

### 3.8 Mechanism-to-evidence map (§6.2)

The Introduction now closes its contributions with the mapping from each
mechanism to the experiment that assesses it.

### 3.9 Contributions, one per item (§4.3, §8)

The contributions are now six enumerated items, each labelled *algorithmic*,
*empirical* or *infrastructural*, rather than one item bundling several
components.

### 3.10 Scope and assumptions (§4.4)

New Section II-B states the optimisation objective formally, the one-EPR-pair
cost model, and — explicitly — what the model excludes: entanglement latency
and fidelity, purification, link contention and concurrency, classical
communication and measurement latency, decoherence during a reserved cat
resource, and gate error. It closes by stating what this scopes, which is the
review's §5.1 point.

### 3.11 Related Work taxonomy (§4.8)

Table VIII classifies TELESABRE, DSABRE, pytket-dqc and PORTER by paradigm,
primitives, staging, commitment granularity, preparation-cost treatment,
layout strategy, capacity handling, termination guarantee and metric. The
version history of DSABRE has moved to Methodology, leaving Related Work to
conceptual distinctions.

### 3.12 Abstract and Conclusion rewritten (§2.3, §4.2, §4.9)

The Abstract now follows the five-element order the review proposed:
problem and metric; the central design idea; the supporting mechanisms; one
headline comparison against TELESABRE and one qualified comparison against
DSABRE; and the ablation summary with the availability statement. Its
numeric load is down from twelve figures to eight, and the operating-point
detail the review singled out — the shared-layout figures, the forty-one
instances, the heavy-hex results and the 1.45x/0.72x scale-up reversal — has
moved to the main text. Two comparisons remain in the Abstract, against
TELESABRE and against DSABRE, and we state the basis of each rather than
leaving the denominator implicit.

The Conclusion is now four paragraphs: the design contribution, three
supported conclusions, the two negative findings and what they bound, and
limitations with future work. It no longer repeats the numerical catalogue.
Following §4.9 we removed "two of the four mechanism answers are negative,
and we think they are the more useful half", and the closing paragraph now
names theoretical and validation work — a completion guarantee, an
out-of-sample validation of the horizon rule, and a richer cost model —
rather than implementation improvements alone.

### 3.13 Numerical reporting (§7.3)

We adopted the convention the review suggested and applied it uniformly:
percentage reductions where a baseline is unambiguous (comparisons against
TELESABRE), ratios where operating points are being compared (comparisons
against DSABRE and the time/EPR frontier), and raw geometric means in
tables. Every table caption states that lower EPR is better.

---

## 4. Claims narrowed

All ten items of the review's §5 have been acted on.

| # | Previous | Revised |
|---|---|---|
| 1 | "the figure of merit that matters" | the primary optimisation metric **under the stated cost model** (§II-B) |
| 2 | "completes every instance" | scoped to the evaluated instances under the selected-horizon protocol; success distinguished from a completion guarantee (§III-H, §VI) |
| 3 | "Architecture Independence" | "Robustness to Heavy-Hex Cores and Non-Grid Core Graphs" |
| 4 | "Scaling to 360 Logical Qubits" | "Scale-Up on QFT and QPEexact to 360 Logical Qubits" |
| 5 | exact reproducibility | a single route is byte-identical; the **protocol** is reproducible only up to its wall-clock budget (§IV-C, §VI-A) |
| 6 | "independent replay verifier" | written separately from the router, sharing no routing, scoring or layout code, consuming only the emitted stream — **and baselines are not replay-verified**, now stated |
| 7 | plan commitment distinguishes PORTER | see §2.1 above: framework and commitment rule separated; the ablation's scope stated |
| 8 | packets outperformed by removing gate teleportation | framed as an interaction between action vocabulary and scorer, with the currency mismatch explained (§VI) |
| 9 | "a search-budget gap, not a routing deficit" | increased deterministic search closes and reverses the gap; we explicitly decline the causal conclusion, noting the schedules vary layouts too and that route counts rather than wall-clock are matched |
| 10 | relief converts failure into "a non-event" | the measured statement: no instance reached the deadlock path with relief enabled, four did without it, and this is not a robustness guarantee |

On item 6 we also adopted the review's precise formulation, describing the
verifier by what it does not share with the router rather than by the word
"independent" alone.

---

## 5. In-sample tuning of the horizon rule (§4.7)

We regard this as the review's most important empirical point:

> The current density threshold of 0.80 and candidate values may appear
> hand-tuned. This is perhaps the largest empirical-validity risk because
> horizon selection drives the strongest scale-up claims.

The reviewer is right, and the manuscript did not disclose it. The sweep, both
candidate sets and the 0.80 threshold were fixed by inspecting the same 48
benchmark instances the paper reports on. There is no held-out family.

Section IV-F now says so directly, and bounds the risk with the one argument
that survives:

- **The rule is a portfolio, not a predictor.** The configured horizon is
  always among the candidates and wins ties, so a poorly chosen candidate set
  can cost compile time but **cannot** make the selected route worse than
  routing once. The downside is bounded by construction, independently of how
  the candidates were chosen.
- **The direction is robust to the values.** That no single constant serves
  circuits whose interaction densities differ by an order of magnitude does
  not depend on which candidates were picked.
- **The magnitude is in-sample and we label it so.** An out-of-sample
  validation — leave-one-family-out, or a fresh benchmark — has not been
  performed. It is named in Threats to Validity and in the Conclusion's
  future work.

We have not added the held-out experiment for this revision, and we do not
claim out-of-sample generalisation.

---

## 6. Style and presentation (§7)

- **Neutral comparative language (§7.2).** Removed: "decisively better",
  "one-sided", "the cleanest comparison in the paper", "the honest
  description", "a target that moved", "takes all six", "earns its place
  outright", "a non-event", and "all three favour the baseline" (now: each
  decision avoids disadvantaging the baseline). Comparative statements now
  give effect size and basis, e.g. "over the instances both complete".
- **Paired quality separated from completion (§4.6).** Section IV-H defines
  the geometric mean, states that failures are never imputed, and states
  plainly that excluding failures **flatters a baseline that fails its
  hardest instances** — which is why completion counts are reported alongside
  every mean.
- **Sentence length and captions (§7.1, §7.4).** The abstract, Introduction
  and Conclusion were rewritten to one principal claim per sentence; the
  Conclusion no longer repeats the numerical catalogue and closes on
  limitations and openings, including the theoretical ones the review asked
  for. Interpretive material has been moved out of captions into prose.
- **Baseline provenance (§4.6).** The DSABRE revision, date and configuration
  are stated once in Methodology; the TELESABRE patch is described there, and
  its validation status — that architecture-H results are unchanged by it, and
  that we have not otherwise audited it — is stated in Threats to Validity.
- **"Degenerate" (§4.6).** Replaced with a neutral description of the stock
  QNN generator's output.

---

## 7. On the AI-assistance disclosure (§4.10)

We accept the reviewer's point that the verifier's independence must be
defined rather than asserted. The manuscript now describes it as separately
implemented, sharing no routing, scoring or layout code with the router, and
consuming only the emitted operation stream and the operation schema. We also
now state that **baseline routes are not replay-verified** — we report the EPR
counts their own harnesses produce, as their published evaluations do — rather
than leaving that to be inferred.

---

## 8. Summary of the revision

- Eight sections: Introduction; Model, Primitives and Problem Formulation; The
  PORTER Compiler; Experimental Methodology; Results (RQ1–RQ4); Discussion and
  Limitations; Related Work; Conclusion.
- Section III describes one routing pass and states no results.
- Two new tables — comparison protocols and budgets, and the Related Work
  taxonomy — alongside the five data tables and the operating-point frontier
  retained from the previous version.
- Four new subsections: research questions, terminology, metrics and
  aggregation, scope and assumptions — plus Discussion and Threats to
  Validity.
- Two factual corrections (front-size cap, notation collision) and one new
  released script reproducing the corrected measurement.
- Ten claims narrowed; the in-sample provenance of the horizon rule disclosed.

Every number in the manuscript is checked against the raw results by two
harnesses released with it: one encoding what the paper states (186 automated
checks) and one parsing the LaTeX table rows that will actually typeset. Both
pass on the revised manuscript.

We are grateful for the review. The reorganisation it prompted, and the two
errors it led us to, have improved the paper considerably.
