# What is the right shape for PORTER's teleport-lookahead horizon?

*Working note, 2026-09-02. Background and evidence for an open design
question in PORTER's remote-plan scorer. Everything here is measured on the
released 48-instance corpus unless stated otherwise.*

---

## The question

`RouterConfig.dag_extended_max_layers` ($L_\mathrm{tp}$) is the only parameter
PORTER does not fix by constant. No single value is best: the per-instance
optimum spans a factor of 32, PORTER routes at three candidate values and
keeps the lowest-EPR result, and the rule that picks those three candidates is
a circuit statistic fitted on the same corpus the paper reports on.

**Is a layer count the right thing to bound at all, and if it is, can anything
predict the right value?**

Two answers below are settled by measurement — one bound has been tried and
refuted, and no circuit statistic can work in principle. What remains open is
narrower and better posed than when we started.

---

## Background: what the horizon actually controls

When PORTER scores a `TeleData` plan, it estimates the gates the relocation
will make local. `_collect_teleport_post_latent_lookahead_gates`
(`porter/router.py:1559`) simulates the DAG forward and collects the CX gates
**of the one moving qubit**, each tagged with the layer it was found at. The
score is

```
lookahead_gain = Σ  max(w_min, w₀ · γ^(layer−1)) · delta(g)
```

with `w₀ = 0.9`, `γ = 0.9`, `w_min = 0.5`.

Three facts about this loop drive everything else.

**1. The weight floors at layer 7.** `0.9 · 0.9^(layer−1)` drops below
`w_min = 0.5` at layer 7 and is clamped from then on. A gate found at layer 8
and one found at layer 128 contribute *identically*. Past layer 7 the horizon
does not discount — it admits or excludes.

**2. The walk peels whole DAG layers.** Each iteration removes a full
simulated layer and re-sorts the entire frontier, so cost is
`O(L × |frontier| log|frontier|)` regardless of whether the moving qubit has
anything left to find. A qubit has at most one front gate at a time, so at
most one gate is collected per layer and `|out| ≤ L`.

**3. A second parameter exists and never binds.**
`teleport_lookahead_cx_count` ($N_\mathrm{tp} = 50$) caps the *gate* count, but
`|out| ≤ L` means it cannot bind while $N_\mathrm{tp} ≥ L_\mathrm{tp}$. The
paper states it is inert. Section "The bound that was refuted" below shows this
is the correct assignment rather than an accident.

### What a deep horizon buys

| | mean gates found | walks finding nothing | found beyond layer 16 |
|---|---|---|---|
| 64q QFT, *L*=16 | 2.41 | 28% | 0% |
| 64q QFT, *L*=128 | **34.69** | 7% | **92%** |
| 200q QFT, *L*=16 | 2.18 | 58% | 0% |
| 200q QFT, *L*=128 | **23.74** | 25% | **92%** |

A deep horizon finds 10–16× more gates, almost all of them beyond what a
shallow one can see, and 97% of them at the flat floor weight.

### Why cost is unpredictable

At 64q QFT, *L*=128 makes **434,417** collector calls against 3,830 at *L*=16 —
113× more, because the deeper horizon changes the routing *trajectory* into far
more router iterations. At 200q QFT it goes the other way: 10,468 against
16,744, because the better trajectory finishes sooner. Per-call cost is not
what makes deep horizons expensive; the trajectory is. This is why *L*=128
times out on some circuits and runs faster than *L*=16 on others.

---

## Evidence: a full sweep of the corpus

All 48 circuit–architecture instances routed at every horizon in
{4, 8, 16, 32, 64, 128}, plus 48 and 256 on the 30 main and scale-up instances
— 288 single deterministic forward passes. Ten instances (GHZ and Graphstate at
each width) are identical at every horizon and are excluded from the summaries;
38 remain.

**Selection already captures most of what is available.**

| configuration | routes | gmean | vs current | optimum found |
|---|---|---|---|---|
| fixed *L*=16 | 1 | — | +25.3% | — |
| **current: 3 candidates, density-split** | 3 | 365.4 | — | 27/38 |
| best 5-subset `{4,16,32,64,128}` | 5 | 353.8 | −3.2% | 33/38 |
| oracle over all six | — | 351.5 | −3.8% | 38/38 |

A fixed horizon costs 25.3%; the three-candidate rule recovers **87%** of the
oracle gain. A single set of five recovers 84% of what remains and would remove
the density rule entirely, at +44% wall clock.

**The objective is multimodal, so no local search can replace a portfolio.**
Convex in *L* on 2 of 38 instances, unimodal on 11 of 38, mean 1.9 strict local
minima. 64q AE bottoms out at *L* = 4, 16 *and* 128. Adjacent grid points move
by up to 69%. A worse neighbour says nothing about whether a better minimum
lies beyond it.

---

## Settled: no circuit statistic can predict the horizon

The shipped rule prunes the candidate set with $\rho$, the mean fraction of
other logical qubits each qubit shares a CX with. Three findings bound how well
any such rule can do.

**$\rho$ is largely a size proxy.** $\rho$ = mean partners / (n−1), and mean
partners saturates (~30–37 for QFT at every width above 25), so $\rho$ mostly
tracks 1/n. Rank correlation of $\rho$ with n is **−0.741**; n alone predicts
the best horizon at +0.640 against $\rho$'s −0.760, while mean partners *before*
dividing manages only +0.149. Nearly all the predictive power is in the
denominator.

**Depth beats CX count; both are weak.** Spearman against log₂ of the best
horizon over 38 instances: circuit depth **+0.464** (p = .003), $\rho$ −0.446,
n +0.434, **CX count +0.198 (p = .23, not significant)**. Normalising by n
destroys what signal exists, so it is *absolute* depth that matters — consistent
with the horizon being an absolute layer budget.

**And the architecture matters, which caps any circuit-only predictor.** The
heavy-hex suite reuses the 64q QASM files verbatim, so CX count, depth and
$\rho$ are *identical* across three architectures. The best horizon differs on
**7 of 7** shared circuits:

| circuit | cx | depth | ρ | 64q grid | hh ring | hh star |
|---|---|---|---|---|---|---|
| ae | 1,962 | 1,058 | 0.49 | 128 | 128 | **8** |
| qft | 1,966 | 446 | 0.47 | **16** | 128 | 128 |
| qnn | 8,126 | 650 | 1.00 | **8** | **32** | **128** |
| qpeexact | 2,139 | 626 | 0.53 | 32 | 64 | 16 |
| random | 1,627 | 403 | 0.33 | 16 | 32 | **4** |
| qaoa | 3,920 | 493 | 0.49 | 8 | 8 | 4 |
| multiplier | 13,040 | 22,469 | 0.47 | 64 | 64 | 128 |

QNN spans the entire candidate range from one circuit file. This is why
$\rho$'s correlation collapses from −0.760 to −0.446 when heavy-hex is
included, and it means a predictor would have to see the core graph, not just
the circuit.

**A live failure mode follows.** QNN has $\rho = 1.00$ by construction, so it
is pinned to the dense set {4, 8, 16} at every width — and on heavy-hex star it
wants 128, paying 449 against 318 (**+41%**) for a horizon it can never reach.
Eleven of the 38 horizon-sensitive instances have their optimum outside the set
the density rule assigns.

---

## Refuted: the per-qubit gate budget

Since the weight is flat past layer 7, the horizon looks like a *counter*, which
suggests bounding the moving qubit's future **gates** rather than layers. That
would be scale-free where a layer budget is not, and would explain why depth
correlates with the best horizon while CX count does not.

**No code is needed to test it**: $N_\mathrm{tp}$ *is* the gate budget, merely
dominated. `RouterConfig(teleport_lookahead_cx_count=k,
dag_extended_max_layers=512)` is a per-qubit horizon directly.

Swept *k* ∈ {16, 24, 32, 48, 64} on the six 80q/200q/360q instances:

| configuration | routes | gmean | vs best-*L* | completes |
|---|---|---|---|---|
| fixed *L*=16 | 1 | 1152.9 | +95% | 6/6 |
| **shipped best-of-3 *L*** | 3 | **618.8** | **+5%** | 6/6 |
| gate budget *k*=16 | 1 | 925.6 | +56% | 6/6 |
| gate budget *k*=24 | 1 | 856.4 | +45% | 6/6 |
| best *k* per instance (oracle) | 5 | 650.5 | +10% | 6/6 |
| best *L* per instance (oracle) | 8 | 592.0 | — | 6/6 |

The best *k* loses to the best *L* on **all six** (+1% to +24%); an oracle over
*k* is beaten by the shipped three-route protocol; *k* ≥ 32 times out on half
the instances. It is also worse at 25q AE (75 vs 65) and 64q QFT (268 vs 262).

**Why: the layer bound is a relevance window, not a counter.** The flat weight
past layer 7 makes it *look* like pure counting, but *L* also excludes gates
beyond it outright. A gate budget deletes that window and counts the first *k*
gates however distant — at 360 qubits a qubit's 48th future CX can lie 900
layers ahead, and scoring it at half weight is a claim about a layout that will
be unrecognisable by then. The window is the more important of the two bounds,
and `N_tp` inert / `L_tp` live is the correct assignment.

---

## What remains open

1. **A predictor that sees the architecture.** Every circuit statistic is
   capped by the 7-of-7 result above. A rule combining a per-qubit, horizon-
   limited density with core-graph properties (diameter, hub degree) is untried.
   Note the horizon acts *per moving qubit* while $\rho$ averages over all of
   them and over the whole circuit.

2. **A horizon that scales with the core count *K*.** $L_\mathrm{tp}$ is an
   absolute layer count, so a plan at twenty cores is scored over
   proportionally less of the circuit than at four, and every scale-up instance
   picks the longest candidate offered. The refutation above does not touch
   this: it rules out replacing layers with gates, not scaling layers with *K*.

3. **The weight floor itself.** `w_min = 0.5` is what makes the horizon a
   sharp-edged window rather than a decay. Nothing has tested whether the floor
   is load-bearing — lowering it would turn *L* back into a genuine discount
   and might change which value is best.

4. **A fourth or fifth candidate.** Measured at −1.5% EPR for +25% routes over
   all 48; on the 24-instance main suite the best 5-set reaches parity with
   dSABRE (1.00×) but does not improve the portfolio result. Cheap to adopt,
   small return.

5. **Cost is trajectory-driven, so the wall-clock budget is fragile.** Two
   scale-up instances sit within a second of their speculative share, and the
   selected result flips with machine load. A budget derived from something
   other than the first route's wall time would make the protocol reproducible.

---

## Reproducing any of this

```bash
python compile_porter.py <file.qasm> -a H --out-dir compile_outputs   # one route
python verify_porter.py --qasm <file.qasm> -a H --seed 0              # replay check
```

A route at a fixed horizon, bypassing selection, is
`compile_porter.route(hw, cfg, circuit, layout, selection=False)` with
`RouterConfig(dag_extended_max_layers=L)`. The sweep data behind every table
here is in the session scratchpad (`horizon_sweep.json`,
`horizon_sweep_heavyhex.json`, `phase2.json`); it is **not** a released results
file, and the paper's own reference to an offline sweep is likewise not
reproducible from the repository.
