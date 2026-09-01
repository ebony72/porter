# Triage — round 3

Every item from `copilot_A_round3.md` and `copilot_B_round3.md`, located in
the source and checked against the manuscript, the released JSON results and
the code. **No files have been edited.**

Labels: `ACCEPT` · `ACCEPT_WITH_SCOPE_CHANGE` · `NEEDS_EVIDENCE` · `REJECT`
· `UNCERTAIN`.

**Headline.** 18 of 20 distinct findings are real and fixable from material
that already exists. One is wrong (`A03`). One — the sharpest of the round —
is right that a claim is unsupported but wrong that the evidence is missing:
**the experiment `A06` says does not exist is in the released data**, and
reporting it turns the conclusion's weakest sentence into a supported one.

Two findings converge on the same defect from opposite directions and are
the most consequential: the **Conclusion claims the ablations attribute
results that came from controls, not ablations** (`B05`), and **Section VI
attributes the portfolio gain to three named mechanisms no experiment
isolates** (`A02`/`B04`). Both contradict Section III-D and Appendix K,
where the paper explicitly declines exactly that attribution.

Nothing in either report requires a new experiment. One item wants a
confirming re-run of six instances the code already supports.

---

## Summary

| Label | Items | n |
|---|---|---|
| `ACCEPT` | A01, A02/B04, A04/B02, A05/B01, A08, A10, B03, B05, B06, B07, B08, B09, B10, B11, B12, B13, B14, B15 | 18 |
| `ACCEPT_WITH_SCOPE_CHANGE` | A06 (evidence exists — report it), A07 (label the scope only), A09 (narrower than stated) | 3 |
| `NEEDS_EVIDENCE` | A06 numbers want a confirming re-run (6 instances, cheap) | 1 |
| `REJECT` | A03 | 1 |

---

## Major — the attribution pair

### `B05` · ACCEPT · Major · `sections/08-conclusion.tex:19-25`

> "Third, the ablations attribute these results rather than leaving them to
> the system as a whole: capacity relief is what lets a deterministic-greedy
> design complete in practice, the initial layout dominates the difference
> between the two compilers at the sizes both target, and the lookahead
> horizon is what carries PORTER past dSABRE as the machine grows."

**Verified — wrong on two of its three clauses.**

| clause | actual source | ablation? |
|---|---|---|
| capacity relief lets it complete | V-C, Table IV — 5 of 9 fail without relief | **yes** |
| initial layout dominates the difference | V-B, the layout×router grid | **no — a control** |
| the horizon carries PORTER past dSABRE | V-D, scale-up | **no — and the supporting figure is absent from the paper** (see `A06`) |

The paper is careful everywhere else to separate ablations from controls
(IV-A, Table I), and Section III-D and Appendix K state that mechanism
attribution is the clearest gap in the evidence. This sentence contradicts
both.

**Patch:** replace "the ablations attribute these results" with a
mixed-evidence formulation naming what each clause rests on — ablation for
relief, the layout-controlled grid for the layout, the fixed-vs-selected
horizon comparison for the horizon. Depends on `A06` landing first.

### `A02` / `B04` · ACCEPT · Major · `sections/06-discussion.tex:19-22`

> "A 9–12% gain instead means the plan-oriented stage, the relief tiers and
> the horizon reach circuits dSABRE's hop-granular, fixed-horizon loop does
> not"

**Verified.** The portfolio is an oracle over two complete compilers that
differ in vocabulary, granularity, preparation scoring, commitment, layout,
horizon policy *and* route budget simultaneously. It establishes that the
outputs differ; it cannot say which difference produced any particular win.
Naming three specific mechanisms is attribution the design does not support,
in the same paper that declines it for the plan abstraction.

**Patch:** keep the empirical statement (non-identical per-instance
outcomes, its cost, no predictor), drop the mechanism naming. The two
instances currently cited (80q Multiplier 4,841→2,411; 80q QPEexact
347→291) stay as illustration of magnitude, not of cause.

**Not accepted in full:** both reports also flag the abstract's "so the
designs reach different circuits rather than re-deriving each other" and the
introduction's counterfactual. Those attribute to *whole designs*, not to
named unisolated mechanisms, which is what the per-instance record does
support. Leave both; revisit only if `A02`'s fix makes them look stranded.

---

## Major — a claim whose evidence exists but is not in the paper

### `A06` · ACCEPT_WITH_SCOPE_CHANGE + NEEDS_EVIDENCE · `sections/08-conclusion.tex:22`, `sections/05-results.tex:326-329`

The referee says the causal claim needs "PORTER with and without horizon
selection on the same scale-up instances" and that **"the manuscript does
not contain this evidence … this would require an experiment that does not
currently exist."**

**That is wrong, and the correction is the most valuable outcome of this
round.** The comparison is in the released data. `scaleup_results.json`
(fixed configured horizon) and `scaleup_results_selection.json` (selected)
run the *same six instances on the same devices* — identical `device` and
`physical` fields, identical dSABRE columns (200/246/765/896/1890/1938) —
differing only in horizon policy:

| instance | fixed $L_\mathrm{tp}$ | selected | dSABRE |
|---|---|---|---|
| QFT-100 | 446 | 198 | 200 |
| QPEexact-100 | 262 | 200 | 246 |
| QFT-200 | 1128 | 579 | 765 |
| QPEexact-200 | 1343 | 528 | 896 |
| QFT-360 | 2822 | 1156 | 1890 |
| QPEexact-360 | 2342 | 1224 | 1938 |
| **gmean** | **1026.5** | **507.7** | **705.7** |

Fixed horizon: **1.45× dSABRE, 0 of 6**. Selected: **0.72×, 6 of 6**.
Same compiler, same layout, same everything else. That is a horizon
ablation, and it is exactly what the conclusion's claim needs.

**Verified separately: `1.45` appears nowhere in the manuscript.** The
`CLAUDE.md` note saying it "survives in Sec VI" is stale — V-D's
interpretive paragraphs were removed on 2026-09-01 and the Sec VI mention
went with a later trim. So the claim is currently unsupported *as printed*,
and the referee is right about that much.

**Patch:** add the fixed-vs-selected row to V-D (two sentences and three
numbers), then let the conclusion keep its claim. This *strengthens* the
paper rather than softening it.

**`NEEDS_EVIDENCE` caveat — yours to approve.** `scaleup_results.json` is
the pre-selection released file. Its `sfc` leg should equal
`route(..., selection=False)` under current code, but I have not re-run it.
Before this goes in the paper I recommend a confirming re-run of the six
instances at `selection=False` — cheap, and it removes any question of the
number coming from a superseded code path. **I will not put an unconfirmed
figure into the manuscript.**

---

## Major — remaining

### `A01` · ACCEPT · `sfc_appendix.tex:1109-1124` (Appendix I)

Two distinct defects, both confirmed by reading the appendix:

1. **The iteration count is not the gate count.** The analysis derives a
   per-iteration cost, then writes "Summing over $N$ iterations" with $N$ =
   gate count. Nothing bounds routing-loop iterations by $N$: an iteration
   may apply a local or preparation SWAP retiring no gate, and relief adds
   more. The repo's own record contradicts it — 128k iterations across 21
   instances, and documented livelocks where iterations grow while retired
   gates stand still. There is no proof that $I = O(N)$ and the paper does
   not offer one.
2. **The total contradicts its own exclusion.** Precomputation is
   $O(KM^2\log M + K^2\log K)$; none of the three per-iteration costs listed
   is $KM^2\log M$. Yet the total is $O(N(Mn + KM^2\log M))$ **"excluding
   precomputation"** — the precomputation term multiplied by $N$ inside a
   bound that says it is excluded.

**Patch:** parameterise by the actual iteration count $I$ and state
$T_\mathrm{pre} + O(I\cdot C_\mathrm{iter})$ with $C_\mathrm{iter}$ built
only from the per-iteration terms actually derived. Do not substitute $N$
for $I$. No experiment needed.

### `B06` · ACCEPT · `sfc_appendix.tex:1017-1018` and `1061-1062`

Two hardcoded references to **"Table V of the main paper"** for the row
order of `tab:mainswaps`. **Verified wrong:** main Table V is `tab:scaleup`
(6 rows, 100–360q QFT/QPEexact). `tab:mainswaps` has **24 data rows in the
same order as `tab:maineprs`**, both ending on `80q multiplier` — that is
the own-protocol suite, summarised by main Table II.

A reader sent to Table V finds different circuits, widths and row count.
Hardcoded numbers, not `xr` macros, which is why nothing caught it.

**Patch:** point both at `Table~\ref{tab:maineprs}` (same document, same row
order). Note `tab:maineprs`'s own caption already pairs the two correctly —
only the reverse direction is broken.

### `B07` · ACCEPT · `sections/07-related-work.tex:32-33`

> "…has completion empirically, no instance in this evaluation being left
> unrouted."

**Verified inconsistent** with Appendix K, which states that one instance
(heavy-hex star Multiplier) does not complete at a fixed horizon, and with
Section VI, which uses that failure to characterise the failure mode.
Under the *reported protocols* 48/48 complete; "this evaluation" is broader
than that and includes the fixed-horizon configurations.

**Patch:** scope to the selected-horizon protocol.

### `B03` · ACCEPT · `sections/05-results.tex:145`

> "The routing loops are equivalent within noise; the layouts are not."

**Verified unsupported.** Routes are deterministic (a documented
invariant), the table reports point values, there are no repeated
measurements and no equivalence margin is defined. "Within 3%" is numerical
proximity, not equivalence. It also softens the paper's own more useful
controlled finding — that dSABRE is ahead in most cells.

**Patch:** state the observation directly; drop "noise" and "equivalent".

---

## Moderate

### `A05` / `B01` · ACCEPT · `sections/05-results.tex:150-153`

> "The spread down a column is two to four times the spread across a row in
> both blocks, so the initial layout is the weaker component of both
> compilers rather than an advantage to either."

Both reviewers read this independently and both read it as self-contradictory.
The intended sense — *the layout is where both compilers have more headroom,
because changing it moves results more than changing the router* — is
defensible, but "weaker component" also reads as "contributes less", which
is the opposite of what the spread shows. Two independent readers tripping
on the same clause settles it.

**Patch:** "the initial layout is the larger observed source of variation in
both compilers, and the component with more headroom in each". Note the
conclusion's clause 2 (`B05`) quotes this same finding and must match.

### `A04` / `B02` · ACCEPT · `sections/03-porter-compiler.tex` Algorithm 1, line 23

Algorithm 1's last statement is *"apply $p^*$'s own preparation SWAPs until
ready, then execute it"* — unconditional. **Verified against III-D:376+**,
which gives commitment three exits: ready → execute; no improving SWAP →
abandon; decision state (plan, layout, RNG) repeats → **raise**, not loop.
Two of the three are invisible in the pseudocode, in the section whose
subject is commitment.

**Patch:** expand line 23 into three exits, and state where control returns
on abandonment and whether the abandoned plan can be reselected under an
unchanged state. Both reports rank this among their top items; `B02` adds
that this is also the main break in Section III's readability.

### `B10` · ACCEPT · `sections/03-porter-compiler.tex:156,161,170`

The plan tuple includes $\mathrm{ready}(\pln{p},\ell)$ as a **component**,
while line 161 calls it "the predicate that holds when it can fire" and 170
uses it as a hypothesis that changes as preparation mutates $\ell$. Putting
a layout-dependent predicate inside the plan makes the committed object look
layout-dependent — precisely the opposite of the paper's thesis that the
plan is stable while preparation changes the layout.

**Patch:** define the tuple with static fields only; define
$\mathrm{ready}(\pln{p},\ell)$ immediately after as a predicate *derived
from* a plan and a layout.

### `B12` · ACCEPT · `sections/04-methodology.tex:216-218`

> "No instance above the threshold ever selected the long horizon, so
> pruning costs no EPR…"

**Verified circular as written.** Above the threshold the candidate set is
$\{4,8,16\}$ (`PORTER_HORIZONS_DENSE`); 128 is *not offered*, so no
above-threshold run could select it. As a statement about the protocol it is
vacuous; the non-vacuous claim is about the offline sweep, where "selected"
is the wrong verb.

**Patch:** name the value and the basis — no above-threshold instance had an
offline optimum beyond 16 — and use a sweep verb.

### `B15` · ACCEPT · `sections/05-results.tex:301` vs `sections/04-methodology.tex:283,292`

$P$ denotes **physical-qubit count** in Table V and **passes per layout** in
Table I. Two main-paper tables, two meanings, and $P$ is never defined in
Table V's caption or nearby prose. This is the same defect class a prior
round already fixed once ($\ell$ as layout *and* ASAP layer).

**Patch:** rename Table V's column and define it in the caption; keep $P$
for passes.

### `A08` · ACCEPT · `sections/02-background.tex:16-18`

"pairs of cores **may** be joined by an inter-core link whose endpoints are
communication ports" does not delimit the admissible machine class: at most
one link per core pair? one port per link? a port incident to several links?
several admissible port pairs per plan, and if so how is one chosen? These
change readiness, preparation distance and candidate multiplicity. The
paper's own Future Work ("a second link turns an occupied port from an
obstacle into an alternative") *implies* one link per adjacent pair — but
that restriction is never stated.

**Patch:** one sentence in II-A stating the assumed class and the port-pair
selection rule.

### `B11` · ACCEPT · `sections/03-porter-compiler.tex:57`

"PORTER routes from **any** initial layout" is broader than true: III-H
legalizes a supplied layout containing a full core, and refuses an input
with no spare capacity anywhere. Matters at first use, because V-B's whole
argument rests on externally supplied layouts.

**Patch:** qualify, forward-reference III-H, and state in IV-D whether the
controlled layout is compared before or after legalization.

### `B08` · ACCEPT · `sections/00-abstract.tex`

Three headline figures without their basis: the TeleSABRE percentages are
over jointly completed instances; the 0.72× series is QFT and QPEexact only;
the 9.3% portfolio is an oracle requiring both compilers. Verified against
the abstract text — none of the three states its basis, and the body narrows
all three.

**Patch:** three compact basis phrases. The 1.02×/0.91× sentence already
carries "under each compiler's own protocol" and needs nothing.

---

## Minor

| ID | Location | Finding | Patch |
|---|---|---|---|
| `A10` | `00-abstract.tex:13` | "supports **all three known** inter-core primitives" is an exhaustiveness claim about the literature that Related Work does not establish | "the three inter-core primitives considered here" |
| `B09` | `05-results.tex:442` | "Pooled over all twenty-four PORTER is slightly ahead at $0.91\times$" — metric unnamed, and sits beside an EPR ratio in the next clause | name the metric twice: time, then EPR |
| `B13` | `03-porter-compiler.tex:8-9` | "Algorithm 1 charts one iteration" — it contains the whole `while` loop and the `return`. Line 1 also says "active/**frontier** sets" where the paper's term is *front* (IV-B bans synonyms) | "charts the routing pass"; `frontier` → `front` |
| `B14` | `03-porter-compiler.tex:184-185` | "the abandonment test of Section~\ref{sec:sfc-prep}" — **verified: `sec:sfc-prep` resolves to III-D**, the subsection the sentence is already in | state the condition inline, or point at the new Algorithm 1 branch from `A04` |

---

## Partially accepted

### `A07` · ACCEPT_WITH_SCOPE_CHANGE · Appendix I

The referee argues the timings do not validate the asymptotic bound. **True,
but the paper never claims they do** — the phrase is "in line with other
core-local distributed compilers", a comparison to the literature. The
premise is partly the referee answering the rubric's question rather than
the manuscript's claim.

**Accepted narrowly:** Appendix I analyses **one route**, while every
reported time is **complete protocol** time over multiple routes. Labelling
that boundary is correct and costs one clause. Reject the implication that a
withdrawal is needed.

### `A09` · ACCEPT_WITH_SCOPE_CHANGE · `sections/03-porter-compiler.tex:394-412`

III-G specifies more than the referee credits: BFS from the congested core
to the nearest reservoir, move one qubit from the penultimate core, all
candidates in that core scored by the ordinary plan machinery, **grouped by
hop count so shorter paths are tried first**. That is a lexicographic order,
and it answers the "what score does a relief TELEDATA get" question — the
ordinary one.

**One real gap survives:** Algorithm 1 line 15 says *"best tail-relief plan
seeded from $\mathcal{B}$"* without saying how the blocked destination is
chosen when $\mathcal{B}$ has several. Opportunistic relief specifies this
($\arg\max$ total); tail relief does not.

**Patch:** state the tail-relief seed rule. Ignore the rest of `A09`.

---

## Rejected

### `A03` · REJECT · `sections/05-results.tex:231`

The referee says the paper converts a cost ratio into a saving with the
wrong denominator, citing "packets save 10.9%".

**The manuscript does not say that.** It says *"Disabling TELEGATEPACKET
makes every shared-control remote CX pay per gate, **costing** $10.9\%$
EPR"* — increase relative to Full, which is the correct denominator for
$537.9/484.9 - 1 = 10.9\%$. Verified as the only occurrence of the figure
in either document; `packets (save|reduce|lower|cut)` matches nothing.

**The defect is in my `paper_brief.md`, claim C7**, which paraphrased it as
"Packets save 10.9% EPR at 80q" — the 9.9% form. The referee's reasoning is
correct and the catch is a good one; it just lands on the brief, not the
paper. **I will fix C7 before the delta audit so it does not propagate.**
No manuscript change.

---

## Proposed batches

Risk-ordered per the protocol. Approve by batch or by ID.

**Batch 1 — corrections of fact.** `B06` (stale Table V ×2), `A01`
(complexity), `B07` (unrouted), `B14`, `B13`. Nothing here is a judgement
call; all five are verifiably wrong as printed.

**Batch 2 — attribution and claim scope.** `B05`, `A02`/`B04`, `B03`,
`A05`/`B01`, `A10`, `B08`, `B09`. The heart of the round. `B05` should land
after `A06`.

**Batch 3 — specification and exposition.** `A04`/`B02` (Algorithm 1
branch), `B10` (plan tuple), `A08` (machine class), `A09` (tail-relief
seed), `B11`, `B12`, `B15`, `A07`.

**Batch 4 — evidence.** `A06`: confirming re-run of the six scale-up
instances at `selection=False`, then the V-D paragraph, then `B05`'s third
clause. **Blocked on your approval of the re-run.**

Batches 1–3 touch prose, pseudocode and one appendix cross-reference only —
no numbers change, so `verify_paper_numbers.py` and `verify_tex_tables.py`
should pass unchanged throughout. Batch 4 adds figures and will need new
pins.

## Questions for you

1. **`A06` re-run — approve?** Six instances at `selection=False`. Without
   it the conclusion's horizon clause has to be softened instead of
   supported, which is the weaker outcome.
2. **`A08`** — confirm the machine class so I state it correctly: at most
   one link per core pair, one port per link endpoint, no port shared
   between links? I can read it off the device files if you'd rather.
3. **`A04`** — on abandonment, does control return to plan generation at the
   same DAG state with the plan excluded, or is it eligible for immediate
   reselection? I will read `router.py` rather than guess, but tell me if
   the intended semantics differ from what the code does.
