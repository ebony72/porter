# Does dSABRE's intra-core routing strategy help PORTER?

**Answer: no.** Under PORTER's shipped protocol the faithful port is $1.3\%$
*worse* over 48 instances and $2.6\%$ worse on the paper's main-24 basis. The
$5\%$ gain it shows at a fixed horizon is variance the horizon portfolio
already collects.

## The three differences

Read from `../../../dsabre/code/router.py` (`route()` lines 2073-2096,
`_best_intra_swap` line 1723, `_get_local_extended` line 675) against
`porter/router.py` (`compile()` local stage, `_generate_local_swap_actions`).
dSABRE has no SABRE-style recently-used-qubit decay, so these three are the
complete set.

| | dSABRE | PORTER |
|---|---|---|
| unit of application | best SWAP of **every** active core, per iteration | one SWAP chip-wide |
| score scope | core `c`'s own front and its own slice of `E`, normalised by those counts | every local CX on the chip, normalised by the chip-wide counts |
| extended weighting | `decay^depth`, decay $=0.9$ | flat |

Each is a `RouterConfig` flag, defaulting to PORTER's choice:
`local_per_core_parallel`, `local_score_per_core`, `local_ext_decay`.
All three defaults leave the shipped op stream byte-identical (SHA256 over the
serialized stream plus `seeded_tie_break_count`, 6 circuits).

## Why the per-core *unit* has nothing to work with

`probe_cores.py`: **92-99% of PORTER's local-stage calls have exactly one
active core**, and the mean local front is 1.03-1.18 gates. PORTER's
locality-first loop drains local work every iteration, so the front it reaches
the local stage with is almost always a single local CX. dSABRE's per-core
parallelism is a real speedup in dSABRE; in PORTER it is a no-op by
construction.

## Results

`ablate_local.py` -> `local_routing_ablation.jsonl`; read with
`report_local.py` (`ARMS=...`, `SEL=1` for the protocol rows). Every
completing stream is replay-verified by `verify_porter.verify_state`.

### One forward pass at the configured horizon (`selection=False`)

Common basis, gmean EPR:

| arm | flags | ALL(44) | vs PORTER | W/L/T |
|---|---|---|---|---|
| PORTER | -- | 154.9 | -- | -- |
| **per-core score** | `local_score_per_core` | **147.2** | **-5.0%** | 17/8/20 |
| decay only | `local_ext_decay=0.9` | 152.3 | -1.7% | 20/14/13 |
| per-core + parallel | `+ local_per_core_parallel` | 152.9 | -1.3% | 11/14/20 |
| per-core + decay | | 156.3 | +0.9% | 17/16/14 |
| full dSABRE | all three | 152.9 | -1.3% | 20/14/13 |
| per-core, $w_e{=}0.25$ | dSABRE's own weight | 156.0 | +0.8% | 11/17/19 |

Only the **per-core score** helps; the decay and the parallelism each give
most of it back, and dSABRE's own extended weight is worse than PORTER's 0.8.

### PORTER's shipped protocol (best-of-4 horizons, all 48 complete)

| arm | ALL(48) | vs PORTER | main-24 | vs PORTER | W/L/T |
|---|---|---|---|---|---|
| PORTER | 163.4 | -- | **175.0** | -- | -- |
| per-core score | 164.1 | **+0.4%** | 176.5 | +0.9% | 13/12/23 |
| full dSABRE | 165.5 | **+1.3%** | 179.6 | +2.6% | 17/20/11 |

The control arm reproduces the released `sfc` main-24 gmean of $175.0$
exactly.

**The fixed-horizon gain does not survive the portfolio.** Per-instance the
change is large in both directions -- 80q QFT $446 \to 321$, 64q QAOA
$775 \to 652$, against star/Multiplier $455 \to 721$ and 80q Multiplier
$2486 \to 3222$ -- and nets to nothing. This is the same pattern the horizon
work found repeatedly: an axis whose spread the four-horizon portfolio already
collects.

### The mechanism: it is a reweighting, not a structure

A local SWAP in core `c` cannot change a distance outside `c`, so the
out-of-core terms of PORTER's chip-wide sums are constant and cancel in the
ranking. What per-core scoping actually changes is the **normalisers**: the
extended term is divided by $|E_c|$ rather than $|E|$. Measured
(`probe_ext.py`), $|E|/|E_c|$ is $1.02$-$2.22\times$, so per-core scoping is
arithmetically a larger effective weight on the local lookahead.

Confirmed directly -- raising the chip-wide weight alone recovers most of the
gain (common basis, 40 instances):

| $w_e$ | 0.8 (shipped) | 1.2 | 1.6 | 2.4 | per-core @0.8 | per-core @1.6 |
|---|---|---|---|---|---|---|
| gmean | 135.5 | 132.5 | 133.3 | 132.7 | **130.9** | 135.3 |

Per-core at $w_e{=}1.6$ is back to baseline, i.e. per-core at $0.8$ is already
near that axis's optimum -- consistent with the two being the same knob.

**The whole axis trades fixed-horizon EPR against robustness.** Completions of
48 fall to 46 (per-core), 44 ($w_e{=}1.6$) and 41 ($w_e{=}2.4$); PORTER's own
$w_e{=}0.8$ loses only star/Multiplier. Under the portfolio every arm recovers
to 48/48.

## Not a compile-time win either

An early reading of $2\times$ was an artefact of summing wall time over each
arm's **own** completing set -- PORTER completes two expensive instances
(80q Random, 360q QFT) that per-core does not. On the common basis it is
$1.03\times$, and under the protocol $608$ s against $611$ s. dSABRE's
per-core traversal is a real saving in dSABRE, whose intra-core stage is
$\Theta(N_r)$ per call; PORTER's local stage is 9-33% of route time and
already peels a bounded number of layers.

## Verification

Default streams byte-identical on 6 circuits; 40/40 fuzz; fault injection
100 caught; both paper verifiers pass; released numbers reproduce.
