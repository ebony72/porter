# The horizon sets two things at once, and one of them is the failure mode

*2026-09-03. Data: `horizon_grid.jsonl` (released), `scale_cells.jsonl`,
`freeze_modes.jsonl`, `depth_features.json`. Scripts: `hz_depth.py`,
`hz_scale.py`, `hz_freeze.py`, `hz_revisit.py`, `hz_ratio.py`,
`report_scale.py`.*

Two questions were asked: when is a deeper lookahead horizon worth taking, and
why does PORTER time out as often as it does. They have one answer.

## 1. The scorer's two terms are in different units

`_score_remote_plan` sets

```
total = direct_gain + lookahead_gain
```

`direct_gain` counts front and latent-direct CX gates the plan resolves, so it
is O(1) — a handful of gates at most. `lookahead_gain` is a **sum** over the
gates the lookahead walk collects, and the walk collects up to
`min(dag_extended_max_layers, teleport_lookahead_cx_count)` of them. Every
core graph in this corpus is bipartite, so each collected gate contributes
exactly ±w(layer), and `teleport_lookahead_weight_floor = 0.5` floors the
weight from layer 7 on. Past layer 7 the term is therefore a signed count
whose magnitude grows linearly in the horizon, bounded only by
`teleport_lookahead_cx_count = 50` — i.e. up to ±25 against a direct term of
about ±1.

So `dag_extended_max_layers` controls two different things at once:

1. **how much of the future is sampled** — the intended effect; and
2. **how heavily the future outweighs the present** — an unintended one.

Measured over every scored teleport candidate (`hz_ratio.py` instrumentation),
mean |lookahead| / mean |direct|:

| instance | L=16 (complete route) | L=128 (bounded probe) |
|---|---|---|
| heavyhex/ring/ae | 0.48 | 1.4 |
| main/64/multiplier | 0.53 | 5.4 |
| main/25/qft | 0.63 | 2.4 |
| scaleup/100/qft | 0.69 | 13.3 |
| main/64/qft | 0.90 | **28.5** |
| main/80/qpeexact | 0.93 | 8.7 |
| main/64/qaoa | 1.79 | **23.4** |

The L=16 column is over complete routes (`domination.jsonl`, all 48
instances); the L=128 column has to come from a bounded probe of 3,000 router
iterations, because four of these seven routes never finish — which is the
subject of Section 3. Measured the same bounded way at both horizons the L=16
figures run 0.2–1.8, so the shift is not an artefact of the two measurements
differing. The share of decisions on which dropping the lookahead term would
change which plan wins moves the same way: 1.7–40% at L=16, 33–99% at L=128.

**The premise behind "53% of the lookahead magnitude sits in layers 65–128"
generalises, and that is the point.** Because the weight floors at layer 7, a
gate found at layer 8 and one found at layer 128 count the same. Any circuit
whose walks reach deep therefore carries most of its magnitude in the deep
layers; scale-up is not special in *where* the magnitude is. What differs
between circuits is whether that magnitude is information or merely pressure.

## 2. "When to go deeper" has no useful predictor, and now we know why

If the horizon were only a sampling width, the best depth would be a property
of the circuit. It is not.

* **The same circuit wants different depths on different machines.** The 64q
  suite is routed on arch H, on heavy-hex ring and on heavy-hex star. QFT's
  best horizon is 16 on H and 256 on both heavy-hex graphs; QPEexact's is 32,
  64 and 16 respectively. No circuit-only feature can express that.
* **Partner novelty, the obvious mechanism-level candidate, is flat.** For each
  qubit, over the next *W* gates of its own CX chain, the fraction of distinct
  partners (`hz_depth.py`) is 0.51 for QAOA, 0.50 for QFT, 0.51 for QNN and
  0.51 for the scale-up series — the deep-helps and deep-harms groups are
  indistinguishable. (The value sits at ~0.5 because each CRZ decomposes into
  two CX on the same pair.) Only Multiplier (0.32) and Random (0.44–0.49)
  separate at all, and they fall on both sides.
* **Circuit ASAP depth is the best static signal and it is not enough.**
  Spearman against the deep-vs-shallow EPR ratio over 36 non-trivial
  instances: depth **+0.68**, cx-depth +0.63, density **−0.60**, CX count
  +0.42, n +0.30, K +0.04, core-graph diameter +0.04, mean core path +0.19.
  Depth is the strongest, which is mechanistically unsurprising — the horizon
  is counted in ASAP layers — but expressing the horizon as a fraction of
  circuit depth does not concentrate the optimum: the best `L*/D` ranges from
  0.001 to 0.574, a **420× spread**.
* **No feature gate beats not having one.** Taking the protocol's real
  semantics — the configured horizon L=16 is routed first and always counts,
  a rule only decides whether to *add* a deep route — an exhaustive search over
  single-threshold gates on {depth, density, CX, n, cx-depth, physical qubits},
  in both directions, at every threshold, finds an in-sample optimum of
  **373.3** gmean EPR. Ungated `{16,128}` scores **373.3**: the best gate the
  data admits never usefully fires. Held out leave-one-family-out (threshold
  refitted on the other families) it is 373.3 for depth and 378.5 for density.
* **There is almost nothing left to win.** The shipped 4-route portfolio
  `{4,8,16,128}` scores 361.6; an oracle over all eight horizons scores 350.4.
  The entire gap a perfect predictor could close is **3.1%**.

This is consistent with, and explains, what this repo had already measured
piecemeal: density recovers only 8% of the oracle gain, K/D scaling rules fail
held out, and refitting the density form out of sample is worse than a fixed
set. The reason is that the best depth is not a circuit property. It is where
the sampling benefit and the re-weighting cost happen to cross for that
(circuit, machine, layout), and the re-weighting cost is an artefact of the
score's units rather than anything about the circuit.

### 2.1 A runtime predictor does not work either

Static circuit features are not the only candidate. Because the protocol
routes the configured horizon first and unguarded, anything measurable during
that route is free. `hz_ratio.py` records, over every scored teleport
candidate at L=16, the domination ratio |lookahead| / |direct|, the share of
decisions the lookahead flips, and the mean number of gates the walk collects
(48 instances, `domination.jsonl`).

None of them predicts whether a deeper route will pay:

| runtime feature at L=16 | Spearman vs deep-vs-shallow EPR ratio |
|---|---|
| domination ratio | **+0.02** |
| flip rate | −0.11 |
| mean gates collected | −0.41 |

The best gated 2-route policy over the domination ratio is, once again,
indistinguishable from not gating at all (373.3 both), and held out
leave-one-family-out it reaches 382.6 — **worse** than ungated `{16,128}` and
worse than the shipped 4-route portfolio. A seven-instance eyeball of the
ratio looked promising; on all 38 it is noise.

So both families are exhausted: nothing about the circuit, and nothing
measurable from a cheap route, says whether the next route should be deeper.
That is the honest answer to "establish rules for when to go deeper" under the
present scorer — **there is no such rule, and the portfolio is already within
3.1% of what a perfect one could achieve.** The lever worth pulling is not a
better predictor; it is removing the reason depth is risky in the first place.

## 3. The timeouts are the same effect, taken to its limit

### 3.1 What "PORTER times out" actually means

It is not the compiler that fails. The shipped protocol routes four candidate
horizons and keeps the best, so a candidate that fails costs time, not a
result — which is why PORTER completes 48/48 instances in the paper while
**8.3% of individual routes in the grid do not complete** (32 of 384).

The failure rate is monotone in the horizon:

| L | 4 | 8 | 16 | 32 | 48 | 64 | 128 | 256 |
|---|---|---|---|---|---|---|---|---|
| routes failed (of 48) | 0 | 2 | 1 | 1 | 1 | 2 | **11** | **14** |

25 of the 32 failures sit at L ≥ 128. And across the released weight-schedule
arms, the failure rate tracks the lookahead term's **magnitude**, not the
circuit mix — the arms in which the term saturates instead of accumulating
fail roughly eight times less often:

| arm | `base` (shipped, floor 0.5) | `flat` | `g95` | `floor25` | `slow95` | `floor0` (true decay) |
|---|---|---|---|---|---|---|
| non-completions | 8.3% | 8.0% | 4.5% | 3.8% | 1.2% | **1.0%** |

That is an independent confirmation, from data already released, that depth's
risk is a weight effect: `floor0` sees the same circuits at the same horizons
and differs only in that its weights decay to zero, so its lookahead sum
saturates instead of growing.

The redundancy the protocol relies on is real but not wide. Of the 48
instances, 35 complete on all four shipped candidates, 12 on three, and
**80q Random on only two** (L=4 and L=16).

### 3.2 The failure is a forced-move shuttle, and it is exact

Tracing a frozen route (`main/64/qft` at L=128, stall guard off) shows the
router doing the same three things 38,741 times: one local SWAP, one teleport,
nothing retired. The tail is **exactly periodic with period 3** and the active
gate count never moves off 2,700.

The teleports are one qubit going back and forth:

```
2371 x  teleport q45  core 2 -> 5
2370 x  teleport q45  core 5 -> 2
2370 x  local_swap (46,47)      1190 x local_swap (81,82)      1180 x local_swap (82,83)
```

The score decomposition names the cause. At the two ends of the shuttle:

```
teleport q45  2 -> 5    direct -1.0   lookahead -11.16   total -12.16
teleport q45  5 -> 2    direct +1.0   lookahead +11.16   total +12.16
```

The lookahead term is **exactly antisymmetric under reversing the move**, and
it must be: `delta(g)` is `d(core(q), c_other) - d(dst, c_other)` summed over
the same collected set with the same weights, and while nothing retires the
DAG is unchanged and local SWAPs do not change any qubit's core. So the walk
collects the same gates and the two directions negate.

Antisymmetry alone would be harmless — the reverse of a good move scores
badly. What closes the loop is that **the remote stage has no null action**.
Every iteration it must commit to some plan, and when the deep lookahead makes
every candidate negative it commits to the least negative one. At core 2 the
full candidate list was

```
q30 -23.0   q31 -25.0   q32 -25.0   q33 -25.0   q34 -26.5
q39 -18.0   q42 -14.0   q44 -12.19  q45 -12.16   <- least bad, and it is the undo
```

so the least-bad plan is precisely the reverse of the move just made, whose
lookahead is the negation of a large positive number and therefore the
smallest magnitude available. From core 5 the same qubit's return scores
`+12.16` outright. The router shuttles because at one end the move is the best
available and at the other end its undo is the least bad available.

**This is the same effect as Section 1, at its limit.** The direct term is the
only part of the score tied to retiring a gate; once the lookahead outweighs
it by 20:1 the router optimises position instead of progress, and position
optimisation under forced moves has no fixed point.

### 3.3 Every failure, classified

`hz_freeze.py` re-runs all 32 non-completing cells of the shipped arm with the
stall guard on, traces the action stream, and reports what the router was
doing after the last gate retirement (`freeze_modes.jsonl`):

| mode | cells |
|---|---|
| teleport shuttle | **28** |
| local-SWAP cycle | 2 |
| other | 2 |

* All 28 shuttles span **exactly two cores**, and the single most active qubit
  accounts for ≥99.5% of the teleports in the frozen window (exactly 100% in
  13 of them).
* The two local-SWAP cycles are `heavyhex/ring/multiplier` at L=32 and
  `heavyhex/star/multiplier` at L=16 — the intra-core livelock this repo
  already knew about. Their frozen windows contain **no teleport at all**, so
  they are a different failure and nothing in this report addresses them.
* Of the two "other" cells, `main/80/qft`@128 is a shuttle spread over several
  qubits rather than one (its busiest qubit still runs 131 moves each way
  between cores 0 and 1); and **`main/80/random`@64 is not a failure at all** —
  re-run it completes in 145 s, so the grid's 300 s wall-clock guard cut off a
  slow route rather than a stuck one. That is one more argument against
  wall-clock as the instrument: it cannot tell slow from stuck, which is
  exactly what the iteration-based stall guard was introduced to fix.

Broken down by horizon, the shuttle is overwhelmingly a deep-horizon event:
10 of 11 failures at L=128 and 14 of 14 at L=256.

The shipped stall guard already handles the *cost*: it abandons these in a
median of **36.9 s** (min 1.1, max 144.7) where the grid spent 300 s on each.
It does not address the cause.

## 4. Two fixes, measured

Two `RouterConfig` flags were added, both defaulting to the shipped behaviour.
With both off the emitted op stream is **byte-identical** on eight routes
spanning four horizons (SHA256 of the serialized stream, plus
`seeded_tie_break_count`, SWAP count and depth), and both paper verifiers still
pass.

### 4.1 `teleport_lookahead_scaling` — divide the growth out

`sum` (shipped) leaves the term a signed count. `mean` divides it by the weight
it accumulated; `sqrt` by the square root of that weight, which keeps some of
the count information while removing most of the growth.
`teleport_lookahead_coefficient` then sets the weight explicitly.

Swept over all 48 instances × 7 horizons (`hz_scale.py` →
`scale_cells.jsonl`, 336 routes, every completed route replay-verified):

| | shipped `sum` | `sqrt`, coefficient 1 |
|---|---|---|
| non-completions (of 336) | **31** | **5** |
| gmean EPR, best of {4,8,16,128}, n=38 | **361.6** | 371.6 (+2.8%) |
| main-24 | **175.0** | 183.0 (+4.6%) |
| scale-up (6) | **508.7** | 518.0 (+1.8%) |
| heavy-hex ring (9) | 86.1 | **84.2 (−2.2%)** |
| heavy-hex star (9) | **116.7** | 117.4 (+0.6%) |

*(The `sum` column reproduces the released `sfc` numbers exactly on main-24,
scale-up and ring. The star row reads 116.7 against the released 121.2 because
the grid routes each candidate unguarded, where the shipped protocol's work
budget abandons some deep star candidates.)*

**Read it as a completion fix that costs EPR, not as an EPR win.** Cell by
cell it fixes **28** of the 31 failures and breaks **2** that the shipped
scorer completes, for a net 31 → 5. At a fixed deep horizon the difference is
large — at L=128, 36 of 38 instances complete against 27, and at L=256, 37
against 24. But across the portfolio it is 17 better / 20 worse / 1 tied, and
the extra completions do not pay for the lost signal: normalising throws away
the count information that earns the scale-up win in the first place.

Three caveats worth keeping:

* **It breaks two cells the shipped scorer completes** — `scaleup/360/qft` at
  L=16 (2720 under `sum`) and `heavyhex/ring/multiplier` at L=128. Fewer
  failures overall, but not a superset of the shipped scorer's completions.
* **It does not flatten the horizon.** Under `sqrt` the portfolio still pays:
  best-of-2 `{16,128}` scores 395.3, best-of-4 371.6, best-of-7 356.8. So this
  does not buy a smaller candidate set.
* **`mean` is too weak and larger coefficients are unstable.** In a probe at
  L=128 over nine instances, `mean` at coefficient 1–4 rescues every frozen
  route but costs the deep winners badly (`scaleup/100/qft` 198 → 230,
  `heavyhex/ring/ae` 69 → 113), while `sqrt` at coefficient 4–8 starts failing
  again. `sqrt` at 1–2 is the only stable region found.

This is, in the paper's own words (Sec. VI-A future work), "a scale on which a
resolved gate and a latent distance reduction are commensurable", and it does
come "from the summation, not from a tie-break". The measurement says that
scale exists and fixes the failure mode — and that on this corpus it is not
free.

### 4.2 `teleport_revisit_block` — forbid the undo

The narrower flag: drop a teleport that would return a qubit to a core it has
already occupied since the last gate retirement. The record clears on every
retirement, so it constrains only the no-progress episode it is trying to end;
the filter is skipped when it would empty the plan set, so it can remove
choices but never the last one. Between two retirements each qubit may then
enter each core at most once, which bounds the remote stage's no-progress work
at `num_logical × num_cores` teleports.

`hz_revisit.py` runs both arms on every cell the shipped scorer fails
(`revisit_cells.jsonl`), and on every instance at the configured horizon
(`revisit_healthy16.jsonl`).

| failure mode | cells | rescued by the revisit block |
|---|---|---|
| local only | 2 | **0** |
| other | 2 | **1** |
| teleport shuttle | 28 | **18** |
| **all** | **32** | **19** |

Every one of the 47 instances routed at the configured horizon is unaffected: **47/47 byte-identical op streams**, 47/47 identical EPR.

What it does **not** do:

* **It does not buy EPR.** A rescued route is a valid route, not a good one:
  `heavyhex/ring/qaoa`@128 completes at 1015 against a four-route portfolio
  best of 244, and `main/64/qnn`@128 at 1874 against 638. Only **1 of 19** rescued routes beats what its instance's four-route portfolio already achieves.
  Since the stall guard already abandons a failed candidate cheaply, turning a
  failure into a bad route is worth nothing to the portfolio — and costs more
  time, because the route now runs to completion instead of being abandoned.
* **It does not reach a guarantee.** The `n × K` bound is up to 480 teleports
  on an 80-qubit instance, and each teleport costs several iterations of
  preparation, so the bound exceeds the stall guard's 1,000-iteration window
  before it can bite. That is why the ten unrescued shuttles are the widest
  instances — seven of them 80-qubit, plus `scaleup/360/qpeexact`. Dropping
  the soft fallback (`teleport_revisit_block_strict`) rescues one more of four
  probed, and leaves ten healthy controls spanning four horizons and four
  suites byte-identical.
* **It does not touch the local-SWAP cycles.** Correctly: their frozen windows
  contain no teleport.

## 5. What to change

**Nothing in the shipped protocol.** Three measurements say so independently:
the four-route portfolio is within 3.1% of an eight-horizon oracle; the stall
guard already reduces a failed candidate from 300 s to a median 36.9 s; and
both fixes buy completion at an EPR cost on this corpus.

Concretely:

* **Keep `PORTER_HORIZONS = (4, 8, 16, 128)`.** Adding the other three
  horizons of the grid moves the portfolio from 361.6 to 356.8 — 1.3% for
  three more routes per instance.
* **Stop looking for a depth predictor.** Four families are now refuted, and
  the ceiling on any of them is 3.1%. The remaining uncertainty is not worth
  the routes an evaluation would cost.
* **Adopt `teleport_revisit_block` only if completion is wanted for its own
  sake** — for a single-route deployment, or to narrow the gap the paper's
  completeness argument has to close. It is free on healthy routes and worth
  nothing to the portfolio.
* **Treat `sqrt` scaling as the answer to a question the paper already
  asks,** not as a config change. Section VI-A wants "a scale on which a
  resolved gate and a latent distance reduction are commensurable", coming
  "from the summation, not from a tie-break". This is that scale; it fixes
  the failure mode; and on this corpus it costs 2.8%. Shipping it would mean
  re-deriving every released number, and the evidence does not justify that.

**One paper claim needs refining.** Section VI says PORTER's guarantee "needs
a progress argument for the intra-core stage, not a stronger capacity
transaction", citing heavy-hex star Multiplier as "the one failure we
observe". That is true of the configurations the paper reports. Across the
horizon grid it is not the whole picture: the dominant failure is a
**remote-stage shuttle, 28 cells against 2**. The remote stage has a livelock
of its own, and unlike the intra-core one it now has an identified cause and a
rule that bounds it. A completeness argument for PORTER has to handle both.

**Two things worth trying next**, in order of expected value:

1. **Give the direct term the horizon's growth instead of taking it from the
   lookahead.** Both terms should scale together, or neither. `sqrt` removes
   the growth; the untested alternative is to let the direct term count the
   same latent-direct closure at the same horizon, which would keep the deep
   signal that earns the scale-up win. Nothing here tested that.
2. **Teleport-only plus the revisit block.** Section VI already names a
   TeleData-only PORTER as where dSABRE's proof is likeliest to transfer.
   That configuration fails 3 of 24 instances today; the shuttle bound is the
   remote-stage half of what a proof would need, so the pair is worth
   measuring together rather than separately.

## Appendix: EPR at every horizon

Shipped `sum` scorer, then `sqrt` scaling; `x` is a route that did not
complete. GHZ and Graphstate are horizon-invariant and omitted.

| instance | L=4 | L=8 | L=16 | L=32 | L=64 | L=128 | L=256 | best |
|---|---|---|---|---|---|---|---|---|
| `heavyhex/ring/ae` sum | 113 | 113 | 116 | 132 | 78 | 69 | 68 | **68** @256 |
| &nbsp;&nbsp;· sqrt | 113 | 113 | 113 | 122 | 115 | 74 | 74 | **74** @128 |
| `heavyhex/ring/multiplier` sum | 554 | 832 | 506 | x | 456 | 573 | 657 | **456** @64 |
| &nbsp;&nbsp;· sqrt | 556 | 916 | 715 | x | 455 | x | 497 | **455** @64 |
| `heavyhex/ring/qaoa` sum | 247 | 244 | 248 | 254 | 397 | x | x | **244** @8 |
| &nbsp;&nbsp;· sqrt | 247 | 240 | 243 | 246 | 292 | 333 | 810 | **240** @8 |
| `heavyhex/ring/qft` sum | 132 | 125 | 141 | 134 | 112 | 109 | 102 | **102** @256 |
| &nbsp;&nbsp;· sqrt | 132 | 125 | 151 | 129 | 135 | 100 | 100 | **100** @128 |
| `heavyhex/ring/qnn` sum | 249 | 244 | 240 | 185 | 264 | 289 | 303 | **185** @32 |
| &nbsp;&nbsp;· sqrt | 249 | 240 | 244 | 247 | 231 | 240 | 218 | **218** @256 |
| `heavyhex/ring/qpeexact` sum | 113 | 113 | 116 | 132 | 87 | 105 | 105 | **87** @64 |
| &nbsp;&nbsp;· sqrt | 113 | 113 | 113 | 122 | 134 | 82 | 82 | **82** @128 |
| `heavyhex/ring/random` sum | 472 | 465 | 506 | 442 | 555 | 556 | x | **442** @32 |
| &nbsp;&nbsp;· sqrt | 457 | 457 | 459 | 494 | 552 | 629 | 624 | **457** @4 |
| `heavyhex/star/ae` sum | 154 | 149 | 161 | 155 | 154 | 190 | 171 | **149** @8 |
| &nbsp;&nbsp;· sqrt | 154 | 156 | 166 | 186 | 140 | 120 | 120 | **120** @128 |
| `heavyhex/star/multiplier` sum | 754 | 1489 | x | 609 | 749 | 455 | 709 | **455** @128 |
| &nbsp;&nbsp;· sqrt | 754 | 1540 | 1212 | 754 | 748 | 1095 | 1025 | **748** @64 |
| `heavyhex/star/qaoa` sum | 401 | 405 | 473 | 534 | 539 | x | x | **401** @4 |
| &nbsp;&nbsp;· sqrt | 401 | 340 | 733 | 740 | 567 | 469 | 660 | **340** @8 |
| `heavyhex/star/qft` sum | 128 | 144 | 124 | 122 | 150 | 117 | 110 | **110** @256 |
| &nbsp;&nbsp;· sqrt | 128 | 132 | 142 | 117 | 131 | 101 | 101 | **101** @128 |
| `heavyhex/star/qnn` sum | 449 | 645 | 535 | 507 | 653 | 318 | 381 | **318** @128 |
| &nbsp;&nbsp;· sqrt | 449 | 460 | 736 | 417 | 495 | 700 | 782 | **417** @32 |
| `heavyhex/star/qpeexact` sum | 181 | 181 | 162 | 182 | 188 | 240 | 206 | **162** @16 |
| &nbsp;&nbsp;· sqrt | 181 | 181 | 177 | 190 | 145 | 127 | 127 | **127** @128 |
| `heavyhex/star/random` sum | 510 | 547 | 609 | 529 | 547 | 578 | x | **510** @4 |
| &nbsp;&nbsp;· sqrt | 510 | 533 | 499 | 484 | 543 | 605 | 567 | **484** @32 |
| `main/25/ae` sum | 68 | 69 | 65 | 78 | 117 | 90 | 90 | **65** @16 |
| &nbsp;&nbsp;· sqrt | 68 | 68 | 63 | 68 | 104 | 98 | 98 | **63** @16 |
| `main/25/qft` sum | 109 | 111 | 74 | 99 | 112 | 119 | 119 | **74** @16 |
| &nbsp;&nbsp;· sqrt | 109 | 109 | 76 | 104 | 97 | 131 | 131 | **76** @16 |
| `main/25/qnn` sum | 165 | 174 | 119 | 169 | 245 | 244 | 225 | **119** @16 |
| &nbsp;&nbsp;· sqrt | 164 | 130 | 158 | 184 | 227 | 188 | 213 | **130** @8 |
| `main/25/random` sum | 452 | 415 | 393 | 428 | 413 | 508 | 586 | **393** @16 |
| &nbsp;&nbsp;· sqrt | 429 | 414 | 382 | 433 | 425 | 499 | 530 | **382** @16 |
| `main/64/ae` sum | 222 | 229 | 177 | 188 | 265 | 157 | x | **157** @128 |
| &nbsp;&nbsp;· sqrt | 222 | 233 | 181 | 196 | 233 | 224 | 224 | **181** @16 |
| `main/64/multiplier` sum | 1391 | 1619 | 1358 | 1420 | 989 | 1076 | 1318 | **989** @64 |
| &nbsp;&nbsp;· sqrt | 1387 | 1820 | 1816 | 1684 | 989 | 1302 | 1054 | **989** @64 |
| `main/64/qaoa` sum | 914 | 775 | 854 | 915 | 1145 | x | x | **775** @8 |
| &nbsp;&nbsp;· sqrt | 914 | 922 | 1021 | 1095 | 1175 | 1602 | 1828 | **914** @4 |
| `main/64/qft` sum | 396 | 322 | 262 | 313 | 265 | x | x | **262** @16 |
| &nbsp;&nbsp;· sqrt | 396 | 306 | 348 | 369 | 299 | 343 | 368 | **299** @64 |
| `main/64/qnn_OLD_DEEP` sum | 658 | 638 | 864 | 832 | 888 | x | x | **638** @8 |
| &nbsp;&nbsp;· sqrt | 658 | 995 | 786 | 567 | 908 | 734 | 936 | **567** @32 |
| `main/64/qpeexact` sum | 323 | 236 | 222 | 209 | 309 | x | x | **209** @32 |
| &nbsp;&nbsp;· sqrt | 323 | 291 | 223 | 202 | 204 | 228 | 228 | **202** @32 |
| `main/64/random` sum | 751 | 741 | 737 | 805 | 773 | x | x | **737** @16 |
| &nbsp;&nbsp;· sqrt | 697 | 788 | 910 | 689 | 872 | 826 | 913 | **689** @32 |
| `main/80/ae` sum | 405 | 390 | 490 | 426 | 330 | 299 | 325 | **299** @128 |
| &nbsp;&nbsp;· sqrt | 405 | 476 | 357 | 332 | 427 | 409 | 370 | **332** @32 |
| `main/80/multiplier` sum | 4321 | 4098 | 3501 | 2586 | 3126 | 2486 | 2556 | **2486** @128 |
| &nbsp;&nbsp;· sqrt | 4323 | 4032 | 3830 | 3858 | 3202 | 2989 | 2760 | **2760** @256 |
| `main/80/qaoa` sum | 1370 | 1334 | 1122 | 1331 | 1941 | x | x | **1122** @16 |
| &nbsp;&nbsp;· sqrt | 1370 | 1209 | 1275 | 1047 | 1698 | 2255 | 3270 | **1047** @32 |
| `main/80/qft` sum | 448 | 506 | 446 | 406 | 369 | x | x | **369** @64 |
| &nbsp;&nbsp;· sqrt | 448 | 467 | 435 | 430 | 413 | 343 | 343 | **343** @128 |
| `main/80/qnn_DEEP` sum | 1070 | 1600 | 1517 | 1419 | x | x | x | **1070** @4 |
| &nbsp;&nbsp;· sqrt | 1207 | 1890 | 1459 | 1019 | 1229 | 2480 | 1805 | **1019** @32 |
| `main/80/qpeexact` sum | 608 | 403 | 526 | 391 | 340 | 291 | 393 | **291** @128 |
| &nbsp;&nbsp;· sqrt | 539 | 459 | 320 | 346 | 417 | 393 | 371 | **320** @16 |
| `main/80/random` sum | 11149 | x | 11040 | 11507 | x | x | x | **11040** @16 |
| &nbsp;&nbsp;· sqrt | 11323 | 11034 | 11106 | 11974 | 12583 | x | x | **11034** @8 |
| `scaleup/100/qft` sum | 499 | 502 | 446 | 431 | 363 | 198 | 198 | **198** @128 |
| &nbsp;&nbsp;· sqrt | 499 | 515 | 523 | 446 | 472 | 171 | 171 | **171** @128 |
| `scaleup/100/qpeexact` sum | 277 | 299 | 262 | 277 | 314 | 200 | 200 | **200** @128 |
| &nbsp;&nbsp;· sqrt | 277 | 279 | 255 | 293 | 279 | 216 | 216 | **216** @128 |
| `scaleup/200/qft` sum | 1011 | 1152 | 1131 | 1096 | 1110 | 579 | 579 | **579** @128 |
| &nbsp;&nbsp;· sqrt | 1011 | 1355 | 1126 | 978 | 1072 | 475 | 531 | **475** @128 |
| `scaleup/200/qpeexact` sum | 1084 | 1104 | 1343 | 1098 | 741 | 528 | 531 | **528** @128 |
| &nbsp;&nbsp;· sqrt | 1084 | 939 | 882 | 996 | 877 | 563 | 612 | **563** @128 |
| `scaleup/360/qft` sum | 2477 | 2702 | 2720 | 2572 | 2120 | 1170 | 1186 | **1170** @128 |
| &nbsp;&nbsp;· sqrt | 2477 | 2645 | x | 2841 | 2399 | 1621 | 1446 | **1446** @256 |
| `scaleup/360/qpeexact` sum | 2744 | x | 2342 | 1909 | 1906 | 1224 | 1317 | **1224** @128 |
| &nbsp;&nbsp;· sqrt | 2744 | 2919 | 2197 | 2293 | 1915 | 1207 | 1225 | **1207** @128 |
