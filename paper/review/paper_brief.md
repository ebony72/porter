# Paper brief — PORTER

Grounding document for external review. It states what the manuscript
claims and where, and what each experiment controls, so that a reviewer can
judge whether each claim exceeds the evidence behind it. It is not part of
the manuscript.

*Manuscript:* **PORTER: A Plan-Committed Router for Multi-Core Distributed
Quantum Computers**. 14 pages + 8-page appendix, IEEE two-column.
Venue class: quantum computing / compilers (TCAD-style).

---

## 1. Problem and cost model

A distributed quantum computer runs one circuit across several small cores
joined by links that distribute entanglement on demand. Any two-qubit gate
whose operands sit in different cores must be paid for with an EPR pair.

**Objective (Sec. II-B).** Given a circuit DAG $C$ on $n$ logical qubits, a
machine of $K$ cores with intra-core coupling graphs, inter-core links and
designated communication ports, and an initial layout $\ell_0$, emit a legal
operation stream realising every gate of $C$ while minimising EPR pairs
consumed. SWAP count, depth and compile time are recorded but are never
traded against EPR pairs by any rule in the paper.

**Cost model.** One pair per TELEDATA, per TELEGATE and per packet — one per
packet however many remote CX gates it amortises — charged the same on any
link; multi-hop relocation is charged once per hop. This is the model
TeleSABRE and dSABRE use, which is what makes the three comparable in one
unit. Excluded and stated as excluded: link contention, entanglement latency
and fidelity, purification, classical communication, decoherence during a
held cat resource.

**Primitives.** TELEDATA (teleport a state), TELEGATE (teleport a gate via
cat-entangler), and TELEGATEPACKET (hold the cat resource across a run of
remote CXs sharing a control — one pair for the run, following AutoComm).
None dominates; which is cheapest depends on local circuit structure.

---

## 2. Central design claim

The choice among inter-core actions must be made **before its price is
known**: each alternative becomes executable only after its own preparation
(operand beside the right port, port free, destination holding a spare
slot), and a compiler stages only the alternative it selects. Scoring an
action *together with* the preparation it currently needs therefore ranks
candidates by the layout the compiler happens to occupy rather than by the
progress they buy, and staging a loser still perturbs the layout.

PORTER's unit of choice is a **plan**: a complete specification of one
inter-core action and the readiness conditions it needs, omitting the SWAP
sequence that would establish them. Plans are compared on gate progress,
one is committed, and only then are preparation SWAPs generated for it.

Around that loop: two-tier **capacity relief** (manufactures free slots when
every candidate is blocked), a single **deterministic initial layout**
(temporal locality-greedy, replacing the best-of-$N$ search its predecessors
run), and **per-circuit selection of the lookahead horizon**.

**Terminology the paper is strict about** (Sec. IV-B, no synonyms, "attempt"
banned): *route* = one invocation of the routing loop on one circuit from
one layout; *candidate layout*; *protocol* = layout source + route budget +
selection rule; *candidate horizon*; *complete compile cost* = wall clock of
an entire protocol, not of the winning route.

---

## 3. Contributions as stated (Sec. I)

1. **The PORTER compiler** — plan-oriented remote stage (III-D), capacity
   discipline with two-tier relief (III-G), deterministic initial layout
   (III-A).
2. **Per-circuit selection of the lookahead horizon** (IV-E1). Every
   SABRE-descended router fixes this by constant; no tested constant is best
   across the benchmark, the best value spanning a factor of 32. PORTER
   prunes a three-value candidate set by interaction density, routes each,
   keeps the lowest EPR. The configured horizon always competes and wins
   ties, so selection cannot return a worse route than routing once.
3. **A controlled study over 48 instances** under native, shared-layout and
   cross-layout protocols, with mechanism ablations including a negative
   finding. Every PORTER route is certified by a separately implemented
   replay verifier; baselines are **not** replay-verified (stated).

---

## 4. Headline claims, and where each is evidenced

| # | Claim | Where | Basis / control |
|---|---|---|---|
| C1 | 59.6% / 41.6% / 68.2% fewer EPR than TeleSABRE at 25/64/80q | Abs, I, V-A, Tab. II(a) | Geometric mean over instances **both** complete (6/8/3); three routes each |
| C2 | Completes 24 of 24 where TeleSABRE completes 17 | Abs, I, V-A | Includes an 80q, 23,381-CX circuit |
| C3 | 1.02× dSABRE pooled EPR at 0.91× its compile time | Abs, I, V-A, Tab. II(b) | Each compiler's **own** protocol; PORTER 3 routes, dSABRE 9; all 24 |
| C4 | 0.72× dSABRE EPR on a 100–360q scale-up series, 6/6 wins, 0.54× compile cost | Abs, I, V-D, Tab. V | dSABRE's own scalability architectures and circuit files; our dSABRE column reproduces its published series |
| C5 | The two are complementary: neither wins >11 of 24; best-of-two is 9.3% (11.6% with +R) below dSABRE alone | Abs, I, VI, Tab. II | Oracle over both routes; costs 2.1× dSABRE's time; 8.0%/9.0% on the 18 excluding GHZ/Graphstate |
| C6 | With the layout controlled at equal route count, **dSABRE wins** | V-B, Tab. III | Explicitly labelled the controlled test and a loss for PORTER |
| C7 | Disabling packets *costs* 10.9% EPR at 80q (gmean 484.9 -> 537.9) | V-C, Tab. IV | One mechanism disabled, layout+horizon fixed; 2 of 9 circuits cheaper without. Note the denominator: the equivalent saving from enabling packets is 9.9% |
| C8 | TELEGATE earns its place on **completion**, not termination | V-C | Strict removal fails all but two rows |
| C9 | Relief earns its place on **completion**, not cost (4.0% EPR) | V-C | 5 of 9 fail without it; Multiplier cheaper without |
| C10 | TELEDATA-only is 21.4% cheaper at 80q and never dearer on a circuit it completes | V-C, VI, VIII | Vocabulary variant, not a strict one-factor ablation (stated); completes 21 of 24 overall |
| C11 | Robust to non-grid core graphs; PORTER's layout suits a star badly | V-E, Tab. VI | 4 heavy-hex 27q cores as ring / star; fixed-layout control is the row minimum on both |

**Numbers are machine-checked.** `verify_paper_numbers.py` (over 250
assertions) pins prose claims against the released JSON results and the live
`RouterConfig`; `verify_tex_tables.py` parses **every** LaTeX table row and
summary line against the same JSON. Both pass on the submitted manuscript. **Review
attention is therefore better spent on whether a number supports the
sentence built on it than on whether the number is right.**

---

## 5. What the paper concedes (Appendix K, Threats to Validity)

Ten threats are stated. The load-bearing ones:

- **Mechanism attribution.** No experiment replaces a plan with a hop, so
  the plan *abstraction*'s share of the gains is not isolated — only the
  commitment *rule* was ablated, and separately. Named as the clearest gap.
- **Completion is empirical.** PORTER guarantees correctness and
  termination but not completion; dSABRE carries a
  termination-with-success proof under stated hypotheses. The one failure
  observed is a local-SWAP livelock (heavy-hex star Multiplier at a fixed
  horizon), not the capacity deadlock that proof rules out.
- **Parameter rules fitted in-sample.** The horizon candidate sets and the
  0.80 density threshold were fixed by inspecting the same 48 instances the
  paper reports on. There is no held-out family. Bounded by construction:
  the rule is a portfolio, not a predictor.
- **Unequal native budgets** in the own-protocol comparison (3 routes vs 9).
- **Implementation and timing.** PORTER and dSABRE are Python, TeleSABRE is
  C; single measurement, no warm-up.
- Benchmark coverage; reconstructed 80q AE and QNN instances; a patched
  TeleSABRE binary; aggregation over jointly completed instances only.

---

## 6. Structure

I Introduction · II Model, Primitives, Problem Formulation · III The PORTER
Compiler (one routing pass; states no results) · IV Experimental Methodology
(RQs, terminology, setup, layout protocols, operating protocols, budgets,
metrics) · V Results (RQ1–RQ4 + operating frontier) · VI Discussion and
Future Work · VII Related Work · VIII Conclusion.

Main tables: I `tab:budgets`, II `tab:main`, III `tab:shared`,
IV `tab:ablation`, V `tab:scaleup`, VI `tab:heavyhex`, VII `tab:protocols`,
VIII `tab:taxonomy`. Appendices A–K.

Two boundaries are deliberate: **Section III describes exactly one routing
pass** (multi-pass protocols live in IV-E), and **Section III states no
results**. Interpretation spanning several results is collected in VI.

## 7. Baselines

- **TeleSABRE** (Russo et al.) — flat candidate pool over teleport and
  telegate; C implementation; the strongest published router identified
  under this cost model.
- **dSABRE** (Li et al.) — concurrent work, closest point of reference.
  TELEDATA only, hop-granular commitment, re-scores every iteration, carries
  a termination-with-success proof. Shares four design decisions with PORTER,
  set out in Sec. VII so neither is credited with the other's.
- **pytket-dqc** — hypergraph partitioner, used as an external layout source;
  its network model is more permissive than the device.
