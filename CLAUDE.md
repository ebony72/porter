# PORTER — Plan-Oriented Router for Teleportation-Enabled aRchitectures

Router for multi-core (distributed) quantum hardware with teleport
(TeleData), telegate, and same-control telegate-packet actions.  It routes
over the zero-predecessor DAG frontier with a locality-first priority
(local work always precedes inter-core work) and a **plan-committed remote
stage**: whole `RemotePlan` alternatives are compared first, one is
committed, and preparation SWAPs are then generated for that plan alone.
Compared against TeleSABRE (`../other/telesabre/`) and dSABRE
(`../dsabre/`).  The algorithm is documented in
`paper/对比实验结果及算法概述.pdf`, whose Algorithm 1 and config table map 1:1
onto `RouterConfig` defaults (`f_min=min_free_before_teleport`,
`m_assist=capacity_relief_assist_margin`, …).

(Historical names: the project was briefly called "SFC"; the router class
was `DistributedRouter`, kept as an alias of `PorterRouter`; the original
balanced-first-layer layout heuristic was called "try15".)

**Initial layout** (since 2026-07-12): ONE deterministic, seed-free
heuristic — temporal locality-greedy (`compile_porter.build_initial_layout`,
label `porter.temporal_locality`): temporally discounted CX weights
(γ=0.99 per ASAP layer), qubits visited in first-CX-appearance order,
heaviest-placed-neighbour core assignment respecting the `f_min`
reservation, within-core slots by descending weight onto
ascending-centrality positions. It replaced the balanced-first-layer /
seeded-locality best-of-6 search, which it beats on 14/16 paper instances
(gmean EPR 55.4 vs 92.0) and 14/15 held-out circuits; with it PORTER's
own-protocol gmean beats dSABRE's best-of-3 on all three suites. Legacy
builders survive only for the paper's layout study
(`paper/porter_under_layouts.py`): `compile_porter.build_balanced_first_layer_layout`
and `compare_routers.build_seeded_locality_layout`. Benchmark harness:
`merged_layout_prototype.py`.

## Files

| File | Description |
|------|-------------|
| `porter/` | The router package: `PorterRouter(hw, cfg).compile(circuit, layout) -> RouterState` |
| `porter/hardware.py` | `Core`, `Hardware` (cores, ports, cached distances), `bfs_distances`, `canonical_edge` |
| `porter/layout.py` | `Layout` (logical↔physical map with O(1) occupancy cache) |
| `porter/model.py` | `Gate`, `CompiledOp`, `RouterState/Stats/Config`, `Action`, `RemotePlan`, `assign_gate_ids` |
| `porter/router.py` | `PorterRouter`, `DagFrontierSimulator`, `CapacityReliefPlanner` |
| `compile_porter.py` | CLI: QASM parsing, A/H grid hardware, initial layout (`hardware_for_name`, `build_initial_layout`), backward refinement (`run_refinement_passes`, `--passes`), JSON/CSV outputs |
| `verify_porter.py` | Independent replay verifier + fuzz suite (see below) |
| `verify_fault_injection.py` | Verifier-of-the-verifier: mutates passing op streams (10 corruption classes) and asserts every mutant is rejected; also rebuilds the paper's Sec III-G running example (`toy_stream()`) |
| `compare_routers.py` | Head-to-head benchmark vs TeleSABRE / dSABRE / pytket-dqc. Since 2026-07-13 the dSE own-protocol leg uses `sabre_two_corner_layout` (2 min-degree corners removed per core, chosen farthest by total BFS distance from all other qubits) instead of dSABRE's stock `sabre_locked_boundary_layout` (4 chip-wide = core 0's corners); the pytket legs keep the stock 4-corner convention. PORTER still wins every suite's own-protocol gmean (43.1/86.4/14.0 vs dSE 47.0/89.0/15.8) but dSE now wins the 80q five-circuit basis |
| `patched_telesabre/` | Patched TeleSABRE binary used by `compare_routers.py` — the stock `../other/telesabre/telesabre` segfaults on architecture A. Rebuild with `build.sh`; see its README |
| `bench_plan_commitment.py` | Unit-of-commitment ablation (committed vs hop-wise re-scoring) -> `paper/plan_commitment_results.json`; see the section below |
| `bench_teledata_only.py` | 64q action-vocabulary ablation (full / no-packets / TeleData-only, + relief-tier control) -> `paper/teledata_only_results.json`; see the section below |
| `compare_heavyhex.py` | PORTER vs dSABRE on the dSABRE paper's two heavy-hex architectures (ring/star, 4x27q) -> `paper/heavyhex_results.json`; see the section below |
| `paper/action_mix.py` | Regenerates the paper's action-mix table (TeleData by provenance, telegates, packets + sizes) by rerunning PORTER own-protocol; cross-checks every counter against `paper/compare_results.json` |

## Paper rewritten to 12 pages, reframed (2026-08-28)

**Ablation section audit (same day).** After the compression the Mechanism
Ablation section was read line by line against the JSONs. Every table cell,
every percentage and every gmean checked out, but four defects were found
and fixed, three of them introduced by the compression itself:

1. **Factual error**: the text said relief hurts on "the one instance"
   (64q QNN). There are **two** --- 25q Random also improves without relief
   ($401 \to 395$). Now stated as two, and
   `verify_paper_numbers.py` pins the count *and the identity* of both the
   relief-hurts and no-packets-helps sets so it cannot regress by eye.
2. **Internal contradiction**: "Of PORTER's four mechanisms this is the one
   that earns its place outright" contradicted the intro, which credits the
   initial layout too. The table ablates four things but not the layout;
   reworded to "of the four mechanisms this table ablates", with a pointer
   to where the layout earns its own place.
3. **Two load-bearing bridge sentences** had been trimmed away: the one
   telling the reader the packet column is overturned by the next, and the
   one connecting the TeleData result to the open question dSABRE states.
   Both the intro and the conclusion assert that connection, so the
   supporting section has to make it. Restored.
4. **Two orphaned appendix sections** (`appOptin`, `appMix`) had zero
   references after the cuts. Re-attached. A quick
   `for m in app*; do grep -c` loop catches this class.

**Own-Protocol, Shared-Layout and Related Work audited too.** Same method,
four more defects, all introduced by the compression:

5. **Scope lost**: "64q QFT ($262$ against $179$) is its worst case" --- the
   20-page original correctly said "weakest **64-qubit** result". The true
   worst is 80q QPEexact ($526$ vs $347$, $1.52\times$). Now states both
   worst losses at $1.5\times$.
6. **Sign error**: "removing plan commitment **costs** $0.6\%$ EPR" --- it
   *saves* $0.6\%$ (hop-wise 148.0 vs committed 148.8). Reworded to "moves
   EPR by only $0.6\%$, and in PORTER's favour at that".
7. **Rounding**: PORTER's gain from dSABRE's layout is $8.653\%$, quoted as
   $8.6\%$; corrected to $8.7\%$.
8. **Broken sentence** in Related Work: removing the (i)-(iv) enumeration
   left "...credited with the other's ideas. both rank moves by SABRE's..."
   --- full stop before a lowercase clause. Now a colon. A
   `grep -nE "\. +[a-z]"` sweep (excluding TikZ paths and e.g./i.e.) catches
   this class.

Also **pinned in `verify_paper_numbers.py`**, since all of these were
unverified: the dTS range and its all-negative property, PORTER+R's
7W/13L/4T record, the identity of the widest win and worst loss, both
cross-layout gain percentages, the two single-pass shared-layout figures
quoted in prose but no longer visible in the compacted table, the hop-wise
delta *and its sign*, that our dSABRE 64q column never exceeds what dSABRE
publishes, and --- most importantly --- **the three single-pass headline
percentages (59.6/35.8/61.3), which appear four times including the
abstract and were entirely unchecked.** That gap is how the stale 49.8%
survived earlier.

**Remaining sections audited (Scaling, Compile Time, Architecture
Independence, Setup, Section III).** Three more defects, all in the two
timing-related passages:

9. **Range wrong**: "\PORTER{} remains $4$--$6\times$ faster per attempt at
   these widths" --- true only at 360q. Across the six scale-up instances
   the range is $1.77$--$6.51\times$ (gmean $2.86$). Now stated as
   $1.8$--$6.5\times$ with $4.5\times$ on the largest instance.
10. **Count wrong, and unverifiable figures**: the per-routing-pass paragraph
   said PORTER is slower on "seven of nine" 64q circuits with Multiplier at
   $1.23\times$ and AE at $0.90\times$ "turning". Re-derived from
   `compare_results.json` (dSABRE runs 3 passes per candidate, 3 candidates
   at 64q, so 9 routes): PORTER is slower on **eight of nine**, gmean
   $0.47\times$, and **only Multiplier turns** ($1.08\times$). Those figures
   came from `tab:timedecomp`, which the compression deleted -- they were an
   independent median-of-three measurement not in any released results file,
   so the paragraph was citing numbers nothing could check. Rewritten from
   the released harness output, and now pinned.
11. **Rounding**: the 64q complete-cost advantage is $4.955\times$; briefly
   written as $4.9$, corrected to $5.0$.

**Clean on audit**: Architecture Independence (every claim --- the 6W-2L-1T
ring record, the three star wins, both fixed-layout deltas, the 462-vs-722
Multiplier reduction, and dSABRE matching its published numbers on all 18);
Section III (**all 16 parameter values match `RouterConfig` exactly**, both
refinement examples, and both 64q AE free-slot vectors reproduce live);
Setup (both architectures, all four circuit sizes).

`verify_paper_numbers.py` now carries **158 checks**, including the Section III
parameters against the live `RouterConfig`, the architecture shapes, the
per-pass timing derivation, and the scale-up per-attempt range.

The "+7% overall gmean" figure that looked wrong on first check is correct
--- it is over the 14-instance gmean basis including the omitted
GHZ/Graphstate rows, not over the 12 rows shown.

`paper/sfc.tex` was compressed to 13 pages here; the 2026-08-29 review
restructure took it back to 17. It is framed as: PORTER is a
new DQC compiler that **beats published TeleSABRE** and is **competitive
with a concurrent compiler, dSABRE**. dSABRE is described as concurrent
work throughout, not as a baseline PORTER must beat; §III-A's
"Relationship to dSABRE" was folded into Related Work, where the four
shared design decisions are stated so neither is credited with the other's.

The contributions list now matches what is measured. Plan commitment is
presented as an **efficiency** mechanism (1.3-3x compile time at EPR
parity), not a quality one, and the packet result is stated as measured
including that TeleData-only wins at 80q. Both were previously claimed the
other way.

**What moved to `sfc_appendix.tex`** (now 6 pages, and it needed
`tikz`/`pgfplots` + the main file's `\tikzset` block copied into its
preamble): the running example (+ its figure and table), the
cat-entangler and architecture figures, the action-mix section and table,
the benchmark CX table, the parameter table, the cross-layout table, the
timing table, the per-circuit shared-layout and heavy-hex tables, and a
new SWAP-count table. Appendix letters are A-H and are hardcoded in
`sfc.tex`'s `\app*` macros -- **re-check them whenever an appendix section
is added or reordered**.

**Main-text tables are now five**: `tab:main` (three suites merged into
one, replacing tab:main25/64/80), `tab:shared` and `tab:heavyhex`
(per-suite summaries, per-circuit rows in the appendix), `tab:scaleup`,
`tab:ablation` (now with the Hop-wise column), plus `tab:protocols`.

`paper/verify_tex_tables.py` was rewritten for this structure and now
parses **both** `sfc.tex` and `sfc_appendix.tex`, checking summary rows
against recomputed gmeans and per-circuit rows against the JSONs. It
asserts a row count for every table, so a table that silently stops
matching fails rather than passing vacuously. Run it with
`verify_paper_numbers.py` after any edit.

Corrected in passing: the instance count claimed in the abstract and
intro was 42; it is **48** (24 main + 6 scale-up + 18 heavy-hex), and
`verify_paper_numbers.py` now pins it.

## Unit-of-commitment ablation (added 2026-08-28) — the headline claim does NOT buy EPR

`RouterConfig(remote_plan_commitment=False)` makes `_commit_remote_plan`
return after ONE round of preparation SWAPs, so `compile()` re-classifies the
front and re-generates/re-scores every plan before the next move — dSABRE's
unit of commitment (one hop, re-scored every iteration) inside PORTER's plan
machinery. Identical scoring, identical plan set, identical relief tiers.
Default True; the shipped op stream is byte-identical (SHA256-verified).

Harness: `bench_plan_commitment.py` -> `paper/plan_commitment_results.json`
(21 instances: the ablation basis plus the three 64q class-completion
circuits). All 21 hopwise streams pass `verify_porter`.

**Result: plan commitment is a compile-time optimisation, not a routing-quality
mechanism.**

| | committed | hopwise | |
|---|---|---|---|
| gmean EPR (21) | 148.8 | **148.0** | hopwise −0.6% |
| 25q / 64q / 80q | 43.1 / 213.3 / 299.2 | 43.6 / 216.6 / **283.4** | +1.1% / +1.6% / **−5.3%** |
| dense only (EPR>=400, n=9) | 1009.0 | **969.0** | **−4.0%** |
| completion | 21/21 | **21/21** | commitment not needed to terminate |
| router iterations (total) | 128,222 | 128,565 | **1.00x — same number of moves** |
| wall time (total) | 53.0s | 150.9s | **2.85x** (gmean 1.31x; 3.07x on 80q Random) |

- EPR: 8 circuits better without commitment, 5 worse, 8 tied. It is a wash,
  and it tilts *against* commitment on the dense and 80q circuits.
- The identical iteration count is the key number: both disciplines make the
  same number of moves. Commitment does not change what the router does — it
  changes what each decision costs, by not re-deriving the plan set every
  iteration.
- **Do not describe the plan-committed remote stage as what makes PORTER
  route better.** The intro's contribution 1 currently implies that; the
  measurement says it buys 1.3-3x compile time at EPR parity.

## Action-vocabulary ablation: TeleData only (added 2026-08-28)

Two default-off `RouterConfig` knobs, added to answer "what if PORTER may
only teleport?" (= dSABRE's vocabulary inside PORTER's plan-committed
framework). Both defaults leave the shipped op stream **byte-identical**
(verified by SHA256 over the serialized stream + `seeded_tie_break_count`
on 6 circuits).

- `telegate_enabled=False` — `_generate_remote_plans` emits no TeleGate and
  no TeleGatePacket alternatives.
- `capacity_relief_from_adjacent_blocked=True` — when *no* normal plan
  exists, also feed `blocked_capacity_adjacent` plans (single relief hop)
  to the tail-relief BFS.

Harnesses: `bench_teledata_only.py` -> `paper/teledata_only_results.json`
(64q nine-circuit suite) and `bench_teledata_ablation_basis.py` ->
`paper/teledata_ablation_basis.json` (the paper's ablation basis: 6 circuits
x 25/64/80q, which is what `tab:ablation`'s TeleData column and
`verify_paper_numbers.py` read). Both own protocol, seed 0. Findings:

- **The TeleGate underwrites PORTER's empirical completeness, not just its
  EPR.** With `telegate_enabled=False` alone, 7/9 64q circuits raise "No
  legal action available". A TeleGate is the only remote action needing no
  free destination slot, so it is *always* a normal plan for an adjacent
  remote CX; remove it and an all-adjacent front whose neighbouring cores
  all sit at/below `f_min` has an empty normal set, while the relief BFS
  fallback only ever sees `blocked_capacity_distance_reducing` (non-adjacent)
  candidates. Hence the second flag.
- With both flags, 8/9 complete and all 8 streams pass `verify_porter`
  (`telegate_count=0`, `telegate_packet_count=0`, `epr == teleport_count`).
  64q `random` **livelocks**: gates retired freeze at 3925/5446 while EPR
  and SWAPs grow exactly linearly (~1 teleport + 1 SWAP per 2 steps)
  until `max_iterations` fires. Not slow convergence — do not "fix" it by
  raising the budget.
- Control `full_relief` (default vocabulary + the extra tier) is EPR-identical
  to `full` on all 9, so every delta below is pure vocabulary.
- EPR over the 8 completing 64q circuits: gmean 179.8 vs 182.6 (**-1.6%**)
  but strongly bimodal. TeleData-only **wins** qft -17.6% (216 vs 262), qnn
  -19.7% (694 vs 864), qaoa -21.7% (669 vs 854); **loses** qpeexact +23.9%,
  multiplier +22.8%, ae +11.9%; ties ghz/graphstate.
- **On the paper's 3-suite basis the advantage grows monotonically with
  scale**: 25q +1.9%, 64q mixed, 80q **-32.8%** gmean (ae 490->354,
  qft 446->307, qnn 1517->926). Overall **-8.5%** vs full on the 16 of 18
  instances it completes (71.7 vs 78.3 gmean). The two it cannot complete
  (64q/80q random) are the two most telegate-heavy in the suite (228 and
  3538 single telegates) — the primitive is load-bearing exactly where it
  is used most.
- **This complicates the packet claim in Sec. `sec:ablation`.** The three
  circuits TeleData-only wins are the packet-heaviest (qft 45, qnn 240,
  qaoa 331 packets). On those the ordering is `teledata_only < full <
  no_packets`: packets beat single TeleGates, but *pure teleportation beats
  both*. So `no_packets` (which degrades packets into single TeleGates) is
  the wrong control for "packets are what wins" — it only shows packets beat
  the fallback they degrade into. The likely cause is comparator myopia in
  `_score_remote_plan`: a packet's direct gain is immediate and large, while
  a teleport's value is latent and discounted over
  `teleport_lookahead_cx_count=50` / `dag_extended_max_layers=16`. Untested.
  Conversely multiplier (384 TeleGates) and qpeexact show the single TeleGate
  is genuinely load-bearing for one-off remote CXs.
- Landed in the paper 2026-08-28 as the `TeleData` column of `tab:ablation`
  plus a "TeleData only" paragraph in `sec:ablation`; every quoted number is
  pinned in `paper/verify_paper_numbers.py` (including that `full_relief`
  reproduces `full` exactly, without which the column is not a pure
  vocabulary comparison).

## PORTER's routing protocol: horizon selection (headline since 2026-08-29)

`compile_porter.route(hw, cfg, circuit, layout)` is the ONE entry point every
caller uses to route a layout, so "what PORTER does" is defined in one place.
It runs **density-adaptive best-of-3 lookahead-horizon selection**
(`run_horizon_selection`) and keeps the lowest-EPR result.
`route(..., selection=False)` is the old single forward pass, kept for
ablations and for the paper's single-pass column.

**There is only ONE lookahead horizon, and it is not the one the parameter
table implies.** `_collect_teleport_post_latent_lookahead_gates` collects only
CXs of the ONE moving qubit, and a qubit has at most one zero-predecessor gate
at a time, so the collected count can never exceed the layer budget:
`teleport_lookahead_cx_count` is **inert at any value >=
`dag_extended_max_layers`** (proved: changing it 50 -> 200 alone gives a
byte-identical stream; instrumented over 3830-11395 calls the cap was hit
zero times, max |out| = 10-11). `dag_extended_max_layers` carries the whole
effect. Section III of the paper still presents both as live parameters.

- Candidate set comes from `select_horizons` /
  `circuit_interaction_density` (mean fraction of the other logicals each
  qubit shares a CX with): density >= `DENSE_INTERACTION_THRESHOLD` (0.80)
  gets `PORTER_HORIZONS_DENSE = (4, 8, 16)`, everything else
  `PORTER_HORIZONS = (8, 16, 128)`. Density is a **pruning** rule, not a
  picker — as a picker it recovers only 8% of the 17% oracle gain (Spearman
  -0.765 on log2 of the best horizon; the 0.42-0.53 band is unresolvable,
  64q QAOA wants 8 and 64q AE wants 128 at the same density).
- **`cfg`'s own horizon is routed FIRST, unguarded**, and its wall time sets
  a `SPECULATIVE_TIME_FACTOR` (4x, floor `SPECULATIVE_MIN_SECONDS`=5) budget
  for the rest via SIGALRM. Ties go to `cfg`'s horizon, so the result is
  never worse than routing at `cfg` alone.
- **An iteration cap is the WRONG guard.** A deep peel makes each router
  iteration ~400x costlier AND can stop it converging: 64q QFT at L=128 runs
  ~24 ms/iteration against ~0.06 ms at L=16, so 20k iterations alone burn
  471 s where the whole L=16 route takes 1.2 s. Only a relative *time*
  budget works.
- All horizons start from the SAME layout, so the winning stream replays
  against the layout passed in — no `start_layout` to thread through a
  verifier, unlike `run_refinement_passes`.
- `run_refinement_passes` and `run_layout_search` select the horizon **once**
  (on the first forward pass) and hold it fixed; `info["horizon_routes"]`
  records the extra routes so callers can report the complete protocol.
  `run_layout_search` phase 1 still ranks gammas at `cfg`'s horizon — making
  it select per gamma would cost `len(gammas) x len(horizons)` routes for a
  ranking, and the horizon is a property of the circuit, not the layout.

Measured over all 48 paper instances (`bench_horizon.py` ->
`paper/horizon_results.json`), 48/48 replay-verified, **23 wins / 0 losses /
24 ties** against the single pass:

Re-run through the real harnesses (`rerun_porter_legs.py` ->
`paper/{compare,scaleup,heavyhex}_results_selection.json`; the released
`*_results.json` files are untouched until the migration completes):

| | 1 pass | best-of-3 | dSABRE | ratio |
|---|---|---|---|---|
| main (24) | 194.6 | 174.9 (-10.1%) | 163.9 | 1.19x -> **1.07x** |
| heavy-hex ring (9) | 96.0 | 86.1 (-10.3%) | 85.2 | 1.13x -> **1.01x** |
| heavy-hex star (8) | 111.5 | 103.8 (-6.9%) | 79.1 | 1.41x -> **1.31x** |
| scale-up (6) | 1026.5 | **507.7 (-50.5%)** | 705.7 | 1.45x -> **0.72x** |

No regressions anywhere. **Scale-up flips from 0/6 to 6/6 against dSABRE**
(360q QFT 2822 -> 1156, 360q QPEexact 2342 -> 1224, 200q QPEexact 1343 ->
528), and **heavy-hex star/multiplier goes from livelock to 455** against
dSABRE's 722, so PORTER now completes all 18 heavy-hex instances — this
supersedes the centrality-aware-reservation livelock fix, which is not
shipped.

**Compile time: PORTER stays ahead of dSABRE.** Measured through the harness
path (`paper/compare_results_selection.json`), the main suite costs **338 s
against dSABRE's 396 s (0.85x)** -- 5.1x PORTER's own former single pass, but
still faster than the baseline. (An earlier 713 s / "1.80x slower" figure came
from a contended `bench_horizon.py` run and is superseded.)

**Refinement and the gamma search deliberately do NOT select**
(`run_refinement_passes` / `run_layout_search` default `selection=False`), so
`sfc_refined`, `sfc_search` and every `*_refined` leg keep their published
numbers. The two levers stay independent, and they compose badly: a horizon
that converges on the initial layout can oscillate on the refined layouts
later passes start from.

**Nested SIGALRM guards are a trap here.** `_horizon_time_limit` and
`compare_routers._compiler_time_limit` both call `signal.alarm`, which
*replaces* a pending alarm rather than queueing it. The speculative budget
must be installed INNERMOST or the caller's 900 s guard silently overwrites
it (64q AE: 907 s for one instance before the fix, 10 s after).

## Backward refinement (opt-in, added 2026-08-23)

`compile_porter.run_refinement_passes(hw, cfg, circuit, layout, passes=N)` is
SABRE's bidirectional layout refinement applied to whole routes: forward, then
the **reversed** circuit from that final layout (route discarded, layout kept),
then forward again. `passes` must be odd; 1 reproduces the default single-pass
protocol byte-for-byte. **The best forward pass by EPR is returned**, so more
passes can never report worse. Deterministic and seed-free; the only cost is
routing passes (5 calls vs dSABRE's 9 = 3 seeds x 3 passes).

- `info["start_layout"]` is the **winning pass's own starting layout**. A
  refined route MUST be replayed against that, not against `layout` — the
  emitted stream belongs to that pass. `verify_porter.py --passes N` does this.
- PORTER's headline protocol stays one forward pass; the harness reports
  `sfc_refined` / `sfc_shared_refined` / `sfc_pytket_refined` alongside, so the
  extra passes' contribution is isolated. `PORTER_REFINE_PASSES = 5`.
- **Why it recovers less than it does for dSABRE**: refinement consumes a
  post-routing layout, and routing destroys what `build_initial_layout` built.
  On 64q AE the initial layout is `(2,2,2,2,8,16)` free-per-core — packed cores
  plus reservoirs — and one pass scrambles it to `(14,1,12,2,1,2)`. Intermediate
  passes therefore often regress (64q AE 177->308, QFT 262->326); only the
  best-pass rule keeps that harmless. Restoring the `f_min` reservation between
  passes fixes QFT (326->269) but not AE, so the loss is interaction structure,
  not capacity — a rebalance was tested and NOT shipped.
- Where it pays: 64q QNN 864->537, 64q graphstate 20->16, 25q graphstate 7->4,
  25q random 401->383. Where it does nothing: 80q AE (490 at 1/3/5 passes) —
  a pure initial-layout deficit.

## CLI shapes

```bash
# Compile one circuit (architecture A = 2x2 cores of 3x3, H = 3x2 cores of 4x4):
python compile_porter.py <file.qasm> -a A --seed 0 --out-dir compile_outputs

# Verify one circuit end-to-end (compile + independent replay check):
python verify_porter.py --qasm <file.qasm> -a A --seed 0

# Route with backward refinement (odd pass counts; 1 = default single pass):
python compile_porter.py <file.qasm> -a H --passes 5 --out-dir compile_outputs
python verify_porter.py --qasm <file.qasm> -a H --seed 0 --passes 5

# Fuzz: random circuits on A/H, compile + verify each:
python verify_porter.py --trials 60
```

Benchmark QASM circuits live in `../other/telesabre/circuits/` (`qasm_25/` fits
architecture A, `qasm_64/` fits H; only basis `id, rz, sx, x, cx` is supported).
The QNN benchmark needs the **deep** ZZ-feature-map variant, not the stock
mqt.bench 2.2.2 output (a near-linear chain identical to GHZ): `qasm_64/` uses
`qnn_OLD_DEEP_...64.qasm.bak` (real MQT 1.1.0), `qasm_80/` uses
`qnn_nativegates_ibm_qiskit_opt3_80_DEEP.qasm` (reconstructed, byte-identical
CNOT sequence to the 64q file at n=64; built by `bench/MQTBench/qnn_extract_80.py`).
Both are wired into `SUITES` in `compare_routers.py`.

## Key invariants

- **Determinism**: for a fixed `(circuit, hardware, RouterConfig.random_seed,
  protocol)` the emitted op stream is byte-identical across runs. Any refactor
  must preserve this — compare SHA256 of the serialized `compiled_ops` JSON and
  the `seeded_tie_break_count` stat (identical RNG consumption) before/after.
  Since 2026-08-29 "protocol" is load-bearing: `compile_porter.route(...,
  selection=False)` reproduces the pre-2026-08-29 single-pass stream exactly
  (verified byte-identical on 25q ae/random and 64q ae/qft), while the default
  `selection=True` picks a per-circuit lookahead horizon and so emits a
  different — and usually shorter — stream.
  (Last verified 2026-07-12 after the temporal-locality layout switch:
  8 circuits byte-identical with matching tie counts, 60/60 fuzz trials
  pass. Note the initial layout itself is now seed-free, so the op stream
  depends on the seed only through router tie-breaks.)
- The verifier replays ops against its own layout copy and checks gate
  coverage (each gate exactly once), per-qubit dependency order, coupling-edge
  legality, port rules for teleport/telegate/packets, and stats consistency.
  Run it after any router change.
- `stats.telegate_count` counts **single** telegates only; remote CXs executed
  inside a packet are counted via `telegate_packet_count` (1 per packet) and
  `emitted_gate_count`. The depth rule matches TeleSABRE: 1 per local op,
  5 per teleport/telegate on the touched physical qubits.

## Performance-sensitive internals (do not regress)

- `RouterState.dag_frontier` is the incrementally maintained zero-predecessor
  set; `_current_dag_front` must NOT rescan `state.remaining` (which is stale
  during compile and synced only at exit points via `_sync_remaining`).
- `DagSimState` snapshots are copy-on-write over the live DAG (`active` and
  `pred_base` are shared read-only; decrements go to `pred_overlay`). A sim
  state must not be used after the real DAG mutates.
- `Layout.free_count` is O(1) via the lazily built `_occupancy_cache`; all
  layout mutations must go through `move_logical_to_physical` /
  `swap_physical`, or the cache desyncs.
- `Hardware.core_distance` / `core_neighbors` / `local_neighbors` return
  cached structures — treat them as read-only.
- Candidate-SWAP scoring uses `_score_with_temp_swap` (apply + exact restore)
  instead of `layout.clone()`.
- `Hardware.local_distance` returns `math.inf` (float) for unreachable pairs —
  never wrap it in `int()`.

## Positioning vs dSABRE / TeleSABRE (paper framing)

Avoid describing PORTER as "SABRE-like" — the shared ancestry is only the
lookahead-scored SWAP heuristic.

**Do NOT claim PORTER is "staged" and the baselines are not.** Verified
2026-08-23 by reading source: dSABRE's `route()` main loop is
`if front_intra: <best intra-core SWAP per active core> elif front_inter:
<teleport candidates>` — it is locality-first staged exactly like PORTER,
and never scores a local SWAP against a teleport. Only **TeleSABRE** uses
a flat pool (`telesabre.c`: `collect_candidate_tele_ops` then
`collect_candidate_swap_ops`, then one argmin over both).

The load-bearing differences:

- **Action vocabulary**: dSABRE ships TeleData only; TeleSABRE adds
  telegate; PORTER additionally batches same-control remote CXs into
  telegate packets. dSABRE's teledata-only choice is *measured, not an
  omission* — see `../dsabre/TELEGATE.md`: they implemented single-gate
  telegate, swept 18 variants on 3 architectures, and none beat teledata,
  because teledata amortises **15.75 gates per EPR pair** on the 64q suite
  while a single-gate telegate serves exactly 1. Their stated open problem
  is *grouping*, which is exactly what PORTER's packet does. Frame it that
  way; do not frame it as a gap they overlooked.
- **Unit of commitment**: dSABRE's candidate is one teleport hop of one
  qubit across one link; PORTER's is a whole `RemotePlan`.
- **Where preparation cost enters**: dSABRE's score is
  `d_prep + c_cap − dF − w_e·dE`, so staging + eviction cost is additive
  and cheap staging can outrank valuable progress. PORTER's
  `_score_remote_plan` sets `total = direct_gain + lookahead_gain` only;
  `prep` is the *third tiebreaker* in `_remote_plan_selection_key`.
- **Persistence of the choice**: dSABRE re-scores the whole front every
  iteration (`commit_bonus=0.0`, `commit_hard_lock=False` ship off, though
  the knobs exist); PORTER's `_commit_remote_plan` will not reopen the
  choice until the committed plan is ready.
- **Capacity handling is now convergent, not contrasting.** Since
  2026-08-09 dSABRE defaults to `safe_mode=True`: capacity is a *legality*
  condition (`tier1_floor=2` ≈ PORTER's `f_min=2`), and `_relay_slack_to` /
  `_find_donor_core` do a BFS donor search and chain-relay a free slot —
  the same shape as PORTER's tail-relief BFS. The difference is
  granularity: dSABRE relays as one atomic all-or-nothing transaction,
  PORTER as re-planned single hops scored by the same plan machinery.
  **`_force_make_room` is dead code in safe mode** — do not describe
  dSABRE as "reacting with forced evictions".
- **Failure model**: dSABRE's safe mode carries a *termination-with-success
  proof* under stated hypotheses (connected core graph, connected
  intra-core couplings, `P − n ≥ core_reserve·K + 1`, `core_reserve ≥ 2`,
  every core ≥ `r+3` physical). PORTER is safe but **not** complete: it
  always terminates and never emits an invalid circuit, but termination may
  be by exception. Its completeness is empirical (both relief tiers on ⇒ no
  benchmark deadlocks). State this asymmetry honestly.
  **CORRECTED 2026-08-30: there is no unpreparable-plan case, and the
  pytket full-core infeasibility no longer occurs.** `repair_full_cores`
  defaults **True** and `compile()` always runs `_repair_full_cores`, which
  evicts from any full core into the one with most room; it raises only if
  *no* core has spare capacity at all (the circuit does not fit the machine
  with any headroom). Combined with the `free(dst) >= f_min` admission rule,
  no core is ever full, so `_nearest_free_distance_to_port` never returns
  inf and `_remote_prep_side_score` is always finite. Instrumented over
  ~83k side evaluations on 5 circuits: **0 infinite sides, 0 unpreparable
  plans**, min free/core = 1. The infinite-cost guard is defensive code
  that never fires. And PORTER routes **all 15 pytket-dqc layouts**,
  qnn-25 included (127 EPR) — the old "stranded qubits" note predates the
  entry repair. Do not describe infeasibility as a full-core condition.

## Timing convention: COMPLETE protocol, not one attempt

`seconds` in `compare_results.json` is the **whole compile cost that produced
the reported EPR**, matching dSABRE's own convention ("layout generation and
all nine routes"):

| leg | what `seconds` covers |
|---|---|
| dSABRE own-protocol | layout generation + 3 passes over **every** candidate |
| TeleSABRE | **all** `NUM_SEEDS` attempts, not just the winning seed |
| PORTER own-protocol | `build_initial_layout` + its single routing pass |
| PORTER+R | layout build + every pass actually run |
| PORTER on dSABRE's layouts | sum over every candidate it routes |

`seconds_best_attempt` keeps the single winning attempt for reference, and
`layout_seconds` / `n_candidates` let a reader renormalise. Do NOT report
`seconds_best_attempt` as compile time — that was the old behaviour and it
flattered PORTER, which runs one attempt where the baselines run three or more.

## RESOLVED 2026-08-28: TeleSABRE config key fixed and all legs re-run

**Fixed.** `compare_routers._telesabre_config` used to write
`init_layout_hun_free_qubit`; the key TeleSABRE actually reads is
**`init_layout_hun_min_free_qubit`**.
`config_set_parameter` (`../other/telesabre/src/config.c:149`) returns
silently on an unknown key, so the binary falls back to its built-in
default of **3** (`config.c:41`) instead of the intended 4. dSABRE's
`code/benchmark.py` spells it correctly. Nothing else differs between the
two configs; circuits, device JSON, best-of-3, `max_attempts=10` and
EPR=teledata+telegate all match, and PORTER's per-seed timeout (900 s) is
more generous than dSABRE's (300 s).

Probe: `bench_telesabre_config.py` -> `paper/telesabre_config_probe.json`
(both spellings x both binaries x all three suites).

- The typo'd config reproduces dSABRE's **superseded** May-2026 run
  (`../dsabre/code/results_verify/results_64q.json`) exactly; the correct
  config reproduces the **current** dSABRE paper's `tab:main` 64q block
  exactly. dSABRE's git history matches: `df0a274` introduced the typo,
  `9832ba6` fixed it back — PORTER copied the config inside that window.
- 64q impact: TeleSABRE gmean 269.5 -> 284.5; PORTER single-pass margin
  45.6% -> 35.8%; **QNN collapses from +36.7% to +2.8%**; **TeleSABRE
  converges on QAOA (956)**, so "fails on Random and QAOA" becomes
  "Random only". `sfc.tex` line ~1832 cites 1,365 EPR / 6,292 SWAPs as
  dSABRE's published TeleSABRE QNN figure to argue the harness "reproduces
  it faithfully" — that is the stale table; the current one says 889/5471.
- 25q/80q go the other way (correct config is *worse* for TeleSABRE), so
  PORTER's margin there improves: 54.3->59.6% and 65.8->70.6%. The
  direction is architecture-dependent (3x3 vs 4x4 cores), so this is not a
  uniform correction in either party's favour.
- The patched binary is irrelevant at 64q (identical to stock on all nine),
  but stock segfaults on the **whole** 25q and 80q suites — broader than
  `patched_telesabre/README.md`'s arch-A-only description.
- Unrelated but found alongside: the abstract's 64q headline **49.8%** is
  not reproducible from the paper's own data (45.6%), and
  `verify_paper_numbers.py` does not check the three abstract percentages.

### What was re-run and what moved

`rerun_telesabre_legs.py` re-ran exactly the four TeleSABRE-dependent legs
(`telesabre`, `dSE_shared`, `sfc_shared`, `sfc_shared_refined`) using
`compare_routers`' own functions, and merged them into
`paper/compare_results.json` (`.bak` keeps the pre-fix file). Every other
leg is independent of the TeleSABRE config and was carried over untouched,
so no unrelated table shifted. 65 leg values changed.
`bench_telesabre_timing.py` re-measured the TeleSABRE column of
`paper/timing_results.json` (median of 3, complete protocol).

- Headline single-pass margins vs TeleSABRE: 25q **54.3 -> 59.6%**,
  64q **45.6 -> 35.8%**, 80q **65.8 -> 61.3%**. (The abstract had claimed
  49.8% at 64q, which was never reproducible from the data.)
- Completion: TeleSABRE now completes **17 of 24** (was 15) — it gains 64q
  QAOA and 80q QPEexact. The shared-layout table therefore has 17 rows,
  and the pooled fixed-layout grid 41 instances (was 39).
- 64q TS-matched gmeans moved 269.5/119.3/146.5/122.1 ->
  284.5/144.6/182.6/149.2 (TS / dSE / PORTER / PORTER+R).
- Two narrative claims were **retracted**, both of which had rested on
  dSABRE's superseded May-2026 table: (i) the "our harness reproduces
  TeleSABRE faithfully" cross-check cited QNN 1,365/6,292 — the current
  table says 889/5,471, and the paper now lists all eight matching
  circuits instead; (ii) "dSABRE regresses against TeleSABRE on GHZ
  (14 vs 11)" is false in dSABRE's current table (6 vs 16), so the GHZ
  paragraph no longer says it.
- Stale counts fixed alongside: the paper said "twenty-one instances" in
  three places where the harness has 24.

### Guarding it

`paper/verify_tex_tables.py` (new) **parses the LaTeX rows of
`tab:main25/64/80` and `tab:shared` out of `sfc.tex`** and checks every
cell, gmean and delta against `compare_results.json`. This catches a
transcription slip that `verify_paper_numbers.py` — which encodes what the
paper is *supposed* to say — cannot. Run both.

## CORRECTED 2026-08-28: the scale-up suite ran on the wrong 360q device

`paper/scaleup_results.json` (and `tab:scaleup`) used to report 360q on a
**486-physical, 6-core** machine — 81-slot cores, which is not dSABRE's
scalability protocol at all. `bench_scaleup.py`'s `SUITES` names
`H_grid_4_5_5_5` = **20 cores x 5x5 = 500 physical**, which is what it now
runs. The old dSABRE column was also worse than dSABRE's own published
figures across the board (234/262/923/873/554/759 vs 200/246/765/896/1890/1938).

The current run **reproduces dSABRE's published scalability series**
(`dsabre.tex` tab:main): 246, 896, 1890, 1938 exact; 200 vs 201 and 765 vs
766, both lower because `compare_routers` hands it six candidate layouts
where its own protocol uses three. `verify_paper_numbers.py` now fails if
our dSABRE column is ever *worse* than the published one.

A whole paragraph of the old scale-up prose was an artefact of the wrong
device ("not a monotone difficulty ladder ... six 81-slot cores ... fewer
EPR at 360q than 200q") and has been deleted: on the correct series
dSABRE's own cost rises 200 -> 765 -> 1890 on QFT.

## dSABRE restricted to its OWN layout rule (2026-08-31) --- results re-run

`compare_routers.dsabre_layout_candidates` used to hand dSABRE **two**
families of initial layouts and take its best: its own
`sabre_locked_boundary_layout` (adaptive per-core corner reservation) and
`sabre_two_corner_layout`, the same rule with the count pinned to 2. **The
second family is OURS, not dSABRE's** -- we added it when an older dSABRE
reserved four corners chip-wide (all landing in core 0 under core-major
numbering). The current `adaptive_corner_count` fixes that at source, so the
extra family only meant benchmarking a configuration dSABRE does not ship.

Now it gets its own rule alone: **3 layouts, 9 routes, uniformly** (was 3--6
and 9--18; adaptive k=1 at 25/80q, k=2 at 64q, k=4 at 100/200q, so the two
families coincided only at 64q).

Re-run with `rerun_dsabre_default_layouts.py` (new). Only three legs depend
on the candidate set -- `dSE`, `sfc_on_dse_layout`, `sfc_on_dse_layout_refined`
-- and every other leg was verified bit-identical. **Heavy-hex never used the
second family** (`compare_heavyhex.py` calls `sabre_locked_boundary_layout`
directly), so it needed no re-run.

| | before | after |
|---|---|---|
| dSABRE pooled (24) | 163.9 | **171.9** |
| dSABRE 25q / 64q / 80q | 44.0 / 173.1 / 372.7 | 45.8 / **173.1** / 412.1 |
| dSABRE complete time | 2.26 s | **1.38 s** (half the candidates) |
| PORTER / dSABRE EPR | 1.07x | **1.02x** |
| PORTER+R / dSABRE | 1.05x | **1.00x** |
| PORTER / dSABRE time | 0.58x | **0.91x** |
| scale-up dSABRE | 705.7 | **705.7 (unchanged)** |

**The scale-up headline survives untouched** (0.72x): at 100/200/360q the
adaptive rule was already winning, so dropping our variant cost dSABRE
nothing there. Its scale-up *time* halved (41.1 s -> 15.4 s), so
"0.20x complete cost" became **0.54x**.

**Two readings flipped and were rewritten:**
- **Cross-layout inverts for dSABRE.** V-B used to say "dSABRE's candidate
  set is the better start for *both*". Now dSABRE does marginally better
  from PORTER's layout (171.2 vs 171.9); the claim holds for PORTER only
  (+3.0%).
- **PORTER now wins 25q and 80q** on the TS-matched basis (43.1 vs 45.8;
  38.5 vs 44.9) and loses only 64q. GHZ flips from tie to PORTER win at both
  25q and 80q.

**The standalone timing table was deleted.** `verify_paper_numbers`'s own
TIMING DRIFT check fired: on 80q Random the table said dSABRE 249 s /
PORTER 64 s while the harness said 74 s / 206 s -- a 3x disagreement in
BOTH directions. It was a single-shot measurement, it mixed a fresh
PORTER/dSABRE run with a stale TeleSABRE one, and `tab:main` already
carries complete times for all four compilers from the same run as the EPR.
Removed: V-F's five-circuit paragraph, appendix `tab:timing`, `app_timing`
in the generator, and 32 lines of pins.

## Second review round (2026-08-29) --- two more real errors

`additional_review_revised_PORTER.md` (vault) reviewed the revised paper and
the response. All ten of its Priority-1 items were accepted, and two were
**errors, not wording**:

1. **`f_min` was never a maintained invariant.** III-A claimed every core
   "keeps at least f_min=2 free positions". The router tests
   `free(dst) >= min_free` **before** a TeleData (`router.py:1044,1655`), so
   a core admitted at exactly 2 drops to 1. Instrumented on four circuits:
   the minimum free-per-core reached during routing is **1** every time.
   III-A now separates the three roles f_min plays (initial condition,
   pre-action admission threshold, reservoir threshold). **Do not restore
   invariant language.**
2. **PORTER+S was described wrongly.** The paper said four gammas
   `{0.90,0.95,0.99,1.0}`; `DEFAULT_LAYOUT_GAMMAS` is **five**, including
   **0.80 --- which wins phase 1 on 9 of 24 instances**, i.e. the omitted
   value is the most frequent winner. And `run_layout_search(refine_from=
   "both")` runs the 5-pass refinement from **two** seeds (phase-1 winner +
   the gamma=0.99 layout), so routes = 5+4 = 9 when 0.99 wins, 5+4+4 = 13
   otherwise. That is the 9--13 in `tab:budgets`.
3. Also wrong: the stated tie-break order. The real key is
   `(-total, not ready, prep, rank(kind), cap, -lookahead)` --- prep cost
   comes **before** plan kind, and a readiness flag precedes both. The paper
   had said readiness cost enters "after gain and plan kind". III-E now
   displays the key.

**The central correction is budget language.** We had presented a
five-route PORTER+R result as a *matched-budget* shared-layout result and
generalised it to the abstract and conclusion. Under **equal three-route**
budgets dSABRE wins (100.9 vs 107.7); PORTER leads only at 5 routes against
dSABRE's 3. V-B is now split into an equal-route comparison (labelled the
controlled test, and a loss for PORTER) and a refinement-schedule
comparison (explicitly *not* budget-matched). RQ2 no longer says "matched
routing budgets". **Never call 5-vs-3 a matched budget.**

**Structural changes:** the per-circuit main table moved to the appendix as
`tab:maineprs`; the main paper now carries a hand-maintained suite-level
summary (`tab:main`) with EPR gmeans over jointly-completed circuits,
completion counts and complete times. `verify_tex_tables.py` parses
`tab:maineprs` from APP and adds 12 checks on the new summary's cells;
`gen_tables_selection.py` routes `tab:main`'s generator to the appendix via
`APP_MAIN`. `tab:scaleup`'s `t` column changed from one dSABRE route
(`seconds_best_attempt`) to **complete protocol time for both** compilers.

**`verify_tex_tables.gmean` clamps with `max(x,1)`** for EPR counts, which
silently inflates sub-second times; use the new `gmean_raw` for timing.

Other accepted: no positive attribution of EPR reductions to the plan
abstraction (VI); the TeleData column presented as strict removal + a
vocabulary variant rather than a one-factor ablation; "TeleGate makes
PORTER terminate" -> essential to *completion* (guards give termination
either way); causal/threshold language scoped throughout; the portfolio
guarantee made conditional on the configured route completing;
reproducibility scoped to the released environment; timing methodology
added (Apple M2, macOS 26.5, CPython 3.13, one measurement, no warm-up);
"0.27x speed" -> "3.7x as long"; "attempt" eliminated.

Response letter is now `paper/responses_to_reviews.md` (Part I second
review, Part II first).

## Compression + framing pass (2026-08-29, after the review restructure)

Five author instructions, all applied:

1. **Contributions merged to three**: the compiler (plan-oriented stage +
   capacity relief + deterministic layout); the horizon finding; the
   controlled study (verifier and harness folded into it).
2. **No mention of dSABRE's previous version anywhere.** We compare only
   against the current default. Removed from abstract, intro, methodology,
   results, discussion (the "evolving baseline" threat) and related work:
   the "substantially revised", "re-ran rather than quoted", "up to 40% /
   97x", "published tables" and "target that moved" material. The pinned
   revision `cb5515b` stays in IV-D as provenance, nothing more.
3. **The standalone SABRE paragraph is gone from Section II**; its content
   is one sentence at the head of III-C, where the scoring form is used.
4--5. **Concise language, section by section.** Prose is down **10.3%**
   (12,703 -> 11,400 words) and the paper from 17 to **15 pages**. Per
   section: intro -17.5%, results -20%, related work -14.6%, discussion
   -9.8%, background -8.8%, methodology -7.7%, conclusion -4.5%,
   Section III -5%.

Two structural improvements landed alongside:

- **III-E now names its summation sets** (`D(p)`, `L(p)`, `A_k(p)`) instead
  of overloading "direct/latent/la" as both concepts and domains. The
  side-by-side `align` overflowed the column; it is stacked now.
- **Terminology moved to IV-B**, ahead of its first use (it had been sitting
  after two subsections that already used the terms it defines).

**Watch for lost `\ref`s when tightening.** Two rounds of compression
silently orphaned `tab:main` and `tab:heavyhex` --- the sentences that cited
them were the ones cut. The label/ref sweep catches this; run it after any
prose pass:

```python
labels=set(re.findall(r'\\label\{([^}]+)\}',main)); refs=set(re.findall(r'\\ref\{([^}]+)\}',main))
sorted({l for l in labels if l.startswith(('tab:','fig:'))}-refs)
```

`paper/response_to_organisation_review.md` answers the review point by
point and is kept in step with the manuscript.

## Restructured after an organisation review (2026-08-29)

`porter_presentation_organisation_review.md` (Obsidian vault) was reviewed
claim by claim; most of it was adopted. The paper is now **17 pages** with
eight sections:

I Introduction, II Model/Primitives/Problem Formulation, III The PORTER
Compiler, IV Experimental Methodology, V Results (RQ1--RQ4), VI Discussion
and Limitations, VII Related Work, VIII Conclusion.

**Two boundaries are load-bearing; do not undo them.**
1. **Section III describes ONE routing pass.** Horizon selection, backward
   refinement and the gamma-search are multi-pass *operating protocols* and
   live in IV-E, because they invoke the router repeatedly rather than
   changing what a pass does.
2. **Section III states no results.** No numbers, no win/loss records, no
   forward references to outcomes. Interpretation spanning several results
   goes in VI, not in the results subsections.

**Rejected: the review's proposal to retitle away from "Plan-Committed."**
Its argument was that the ablation shows commitment does not lower EPR. That
conflates two things the paper now keeps apart: the **plan-oriented
framework** (whole-plan candidates, ranked on gain with preparation cost as a
tie-break) and the **commitment rule** (do not reopen the choice until the
plan is ready). `tab:ablation`'s hop-wise column holds the plan set, scoring
and relief tiers fixed and varies ONLY the commitment rule -- so it says
nothing about the abstraction, which no experiment removes. Sec VI states
that gap explicitly as the weakest point in the attribution. The paper's
theme, per the author: an effective, efficient, arguably robust DQC compiler
that saves EPR against TeleSABRE and is competitive with dSABRE. **Compile
time is not a selling point** -- report it, never lead with it.

**Factual defects the review surfaced, both confirmed:**
- **The front-cap claim was wrong.** "A cap that never binds since front
  gates are pairwise qubit-disjoint" -- disjointness bounds the front by $n$,
  not by 96, and 1Q gates are not excluded. The cap **bound on all three
  QPEexact scale-up instances** (front reaches 100/200/360); max front
  elsewhere is 47 (64q random). **SUPERSEDED 2026-09-01: the cap is gone**
  -- see "dag_front_limit removed" below. `paper/probe_front_limit.py` was
  deleted with it.
- **Notation collision**: `\ell` was the layout *and* `\ell(g)` the ASAP
  layer. The ASAP layer is now `\mathrm{asap}(g)`.

**Claims narrowed** (all were overstated): "the figure of merit that matters"
-> primary metric under the stated cost model; "architecture independence" ->
robustness on two non-grid core graphs; "Scaling to 360 qubits" -> scale-up
on QFT and QPEexact only; "capacity relief ... a non-event" -> the measured
completion statement; "the residual gap is a search-budget gap" -> increased
search closes it, without the causal claim (the +S schedule varies layouts
too, and route counts are matched but wall-clock is not); "independent replay
verifier" -> written separately from the router, sharing no routing/scoring/
layout code, **and baselines are NOT replay-verified** (now stated).
Removed: "decisively better", "one-sided", "the cleanest comparison",
"the honest description", "a target that moved", "all three favour the
baseline".

**Horizon selection is disclosed as in-sample.** The sweep, both candidate
sets and the 0.80 density threshold were fixed by inspecting the same 48
instances the paper reports on; there is no held-out family. Sec IV-E now
says so, and bounds the risk: the rule is a *portfolio*, not a predictor --
the configured horizon is always a candidate and wins ties, so a bad
candidate set costs compile time but cannot make the selected route worse
than routing once.

**Added**: research questions (IV-A) with each results subsection opening on
its question/controls/metric; a terminology subsection fixing
route/candidate-layout/protocol/candidate-horizon (no synonyms -- "attempt"
is banned); `tab:budgets`, which states layout source, layout count, passes
per layout, total routes and selection rule for **every** configuration in
the paper; a metrics-and-aggregation subsection defining the geometric mean
and the failure policy; a scope-and-assumptions subsection (II-B) stating the
one-pair-per-action cost model and everything it excludes; `tab:taxonomy` in
Related Work; and VI's threats to validity.

**Not done** (deliberate): `tab:main` was not split into a suite-level
summary with per-circuit rows in the appendix, though the review is right
that it is dense -- it is the headline evidence and `verify_tex_tables.py`'s
main check parses it. Algorithm 1 was not split into three.

**`sfc_appendix.tex` no longer hardcodes main-paper numbers.** It loads
`sfc.aux` via `xr` (`\externaldocument[main-]{sfc}`), so the main paper can
be renumbered freely; shared labels (`tab:shared`, `tab:heavyhex`) are
disambiguated by the `main-` prefix. **Compile `sfc.tex` first** or the
appendix's cross-references render as `??`. Its own `\app*` letters (A--I)
are still hardcoded in `sfc.tex`.

## Ablation basis widened, then compacted (2026-08-31)

**The basis was the six circuits common to all three suites** --- because the
25q suite has only six --- which made the 64q and 80q ablation rows a subset
of the main comparison for no reason. `ablation_mechanisms.py` and
`bench_teledata_ablation_basis.py` now take `CIRCUITS_BY_SUITE`, so 64q and
80q run all nine: **24 instances**, 18 non-trivial.

**The table shows 80q per circuit and 25q/64q as one line each** (author's
call: "for ablation purpose we don't need all circuits"). Pure 80q-only was
rejected because it costs two findings --- the data:

| | packets | relief | TeleData |
|---|---|---|---|
| 25q | +2.4% | +26.4% (0 fail) | +1.3% |
| 64q | +7.9% | +24.0% (0 fail) | -1.6% |
| 80q | +10.9% | **+4.0%** (5 fail) | **-21.4%** |

- The TeleData result is a **monotone scale trend**, not a level; 80q alone
  leaves only the endpoint and the weaker claim.
- **Relief inverts with scale**: below 80q it is a large EPR saving with no
  failures; at 80q it barely saves EPR and is what makes 5 of 9 routable.
  80q alone would make relief look weak. V-C now leads with that inversion.
- Both trends are pinned, including that the TeleData one is monotone.

**Every summary line averages ALL circuits of its group** (2026-08-31, second
pass). The first compact version stacked two reductions --- drop GHZ/Graphstate
as no-ops, then require a circuit to complete in *all four* EPR columns ---
giving "25q, gmean over 4" and "64q over 6". Both were defensible and the
combination was **wrong**, because the prose quoted a different basis: table
said relief +42.2% at 25q, text said +26.4%. Dropping no-op rows is not
neutral either --- it *inflates* every effect (25q relief +26.4% -> +42.2%).

The rule now: **a line carries one Full value, so columns share a line only
when they complete on the same circuits**; where they do not, the comparison
gets its own line and `$n$` states the basis. That yields 1 line for 25q,
2 for 64q, 3 for 80q and 3 pooled, and **every ratio in the table equals the
one its prose claim uses**. No circuit is ever excluded for being
uninformative; the 80q per-circuit rows still omit GHZ/Graphstate for space,
but those two are inside the 80q summary lines.

`tab:ablation` is **generated** by `gen_tables_selection.py` now, not
hand-maintained. Two defects the generator fixed: the `$^\ddagger$` marker
(needs the extra relief tier) had been applied to 25q QFT and QNN, which
complete under *strict* removal --- `verify_tex_tables.py` now pins the
marker cell by cell; and the relief-failure count is **five**, not four
(80q QPEexact joins AE/QFT/QNN/Random).

Numbers that moved with the wider basis: packets +7% -> **+7.6%** over 24;
relief **+20.2%** over the 19 that complete; TeleData **-7.9%** over 21.
Three circuits are cheaper *without* packets (64q/80q Multiplier, 80q QFT)
and three without relief.

## Table II carries five compilers in two blocks (2026-08-31)

`tab:main` gained a **PORTER+S** pair and split, because its two comparisons
need different bases:

- **(a)** circuits *all five* configurations complete --- 6/8/3. The only
  basis \TeleSABRE{} can be compared on.
- **(b)** *every* circuit, TeleSABRE dashed --- 6/9/9 plus a pooled all-24
  row. **This is the basis used against dSABRE**; V-A no longer says "on the
  TeleSABRE-matched basis" there. PORTER is 0.94x at 25q, 0.96x at 80q,
  1.13x at 64q --- and 64q is also the suite the extra search nearly closes
  (+R 1.07x, +S 1.02x).

`verify_tex_tables.py` distinguishes the blocks **by the dashed TeleSABRE
cell**, not by row count: at 25q the matched set and the full suite coincide,
so the dash is the only reliable marker.

**`tab:shared` (Table III) gets no +S column, and must not.** That table holds
the initial layout fixed and **+S's mechanism *is* choosing the layout**, so a
cell would destroy the control --- which is also why no `sfc_pytket_search`
leg exists. Its own-layout figure (159.1) is stated in the caption instead,
and it is *not* below every cell: PORTER+R on pytket's partition is 155.2.

**Table V's PORTER column is three horizon routes**, same protocol as Table
II, and all six instances select L=128; the caption says so now.

## Refinement stacks on horizon selection (2026-08-31) --- +R and +S now bound PORTER

`run_refinement_passes` and `run_layout_search` both default
**`selection=True`**. The horizon is chosen once, on the first forward pass,
and held for the rest of the schedule, so **pass 1 IS PORTER's own selected
route** and the best-forward-pass rule makes the schedule incapable of
reporting more EPR than PORTER. At a fixed horizon it could and did.

| protocol | routes | EPR (24) | vs dSE | time | vs dSE |
|---|---|---|---|---|---|
| dSABRE | 9 | 171.9 | 1.00 | 1.38 s | 1.00 |
| PORTER | 3 | 174.9 | 1.02 | 1.25 s | **0.91** |
| PORTER+R | **7** | **163.0** | **0.95** | 3.22 s | 2.34 |
| PORTER+S | 10--17 | **159.1** | **0.93** | 9.01 s | 6.55 |

- **0 of 24 worse than PORTER** for both +R and +S (was 2 losses for +R).
  80q carries it: QPEexact 526->291, AE 490->299, Multiplier 2699->2132.
- **PORTER+SR is retired.** `run_layout_search` phase 2 always refines the
  gamma=0.99 seed, which IS `build_initial_layout`'s default, so the search
  now contains the selected route. **Identical to +S on all 24**, at 19% more
  time. Row deleted from `tab:protocols`.
- **Two 64q cells got worse**: QNN 537->638, Multiplier 763->1076, where the
  selected horizon (8 and 128) leaves refinement nothing to recover. Not a
  uniform improvement --- say so.
- **Cost is wall-clock, not routes**: refined legs ran **5.6x** their former
  time (25q 1.26x, 64q 1.98x, **80q 4.78x**) because a deep selected horizon
  can make a later pass oscillate until the 900 s per-pass guard fires. One
  80q instance runs four passes of five for that reason.

**A V-B finding was overturned.** "Refinement repairs a poor starting layout
and adds little to a good one" rested on +R gaining 5.1% on dSABRE's layout
and **nothing** on pytket's. With the horizon free to move it gains 9.5% /
6.8% / 6.8% across the three sources --- the old reading was an artefact of
the fixed horizon, and V-B now says that explicitly.

**Tables V and VI are own-layout, own-protocol only** (author's call):
the PORTER+R and PORTER-on-dSABRE-layout columns are gone from `tab:scaleup`
and `tab:heavyhex`, and **+R/+S are measured on the main suite alone**. The
appendix heavy-hex table keeps `porter_on_dse` (the fixed-layout control V-E
cites) but also drops +R. **No scale-up refined leg is run at all** ---
`rerun_refined_legs.py`'s `section_scaleup` is a documented no-op, which is
what saved ~6 h.

Consequences to remember: heavy-hex under own layout is **86.1 vs 85.2 ring
(parity) and 122.3 vs 101.1 star** --- the old "+R leads dSABRE on the ring"
result is no longer shown. V-D's "backward refinement loses on all six
scale-up instances" was **deleted, not restated**: it was measured under the
superseded fixed-horizon +R and we are not re-running it.

**The plan-commitment ablation is gone from the paper** (author's call): the
Hop-wise column, the V-C paragraph, the Discussion's separability paragraph,
the Conclusion's second negative result, and the Intro's mechanism-map entry.
The title still reads "A Plan-Committed Router", so **III-B now motivates the
rule structurally** (a preparation SWAP is meaningless except relative to its
plan; committing makes preparation and action one unit and gives the
abandonment test something to fire on) and states plainly that no experiment
isolates it. `plan_commitment_results.json` is no longer read by any verifier.

**Two wording defects fixed**: V-A's "at its own three-route protocol" never
said what the three routes were (the candidate horizons); and "the TeleGate
is the only remote action needing no free destination slot" conflated the
port with a data slot --- telegate and teleport both need the two
communication qubits free, and what is special is that the cat copy lives on
the target-side communication qubit, so only teleport carries the
`free(dst) >= f_min` test (verified: `_generate_remote_plans` emits the
telegate plan with no `free_count` check at all).

**Trap hit twice this session.** (1) `verify_tex_tables.gmean` clamps
`max(x,1)`, which silently inflates sub-second **times** --- use `gmean_raw`
for timing; I recomputed tab:main's `t` column wrong before catching it.
(2) A background waiter written as `while pgrep -f rerun_refined_legs.py;
do sleep; done` **matches its own command line** and loops forever --- the
+S/+SR run sat idle ~2 h. Match on something the waiter itself does not
contain.

## PORTER+S moved to Appendix J; Sec VI compressed (2026-08-31)

**+S is out of the main paper entirely** (author's call: "cost much, gain
little"). The measurement behind that: pooled over 24 it reaches 159.1 against
+R's 163.0 --- **-2.4% EPR for 2.9x the wall clock** (4,267 s vs 1,468 s, and
**23x dSABRE's 182 s**). It improves 10 instances, ties 14, loses 0. The
spend is badly distributed: 80q burns 4,045 of the 4,267 s for -1.2%, and
**80q AE alone takes 928 s against +R's 14.9 s (62x)** to go 299 -> 284. Its
one qualitative effect was 64q vs dSABRE 1.07x (+R) -> 1.02x.

Three structural reasons beyond the return, all now stated in Appendix J:
it can never appear in `tab:shared`'s layout x router grid (its mechanism
*is* choosing the layout), so it is only ever a fourth own-protocol column;
it adds a **second in-sample-fitted quantity** (the gamma set) next to the
horizon candidate sets IV-E already declares in-sample; and at 10--17 routes
/ 6.55x dSABRE's time it sits on the wrong side of V-F's own argument that
PORTER's time advantage is the *count* of routes.

What moved and what it cost:

- `tab:main` lost 2 of 10 data columns (now 8, four compilers). **Block (a)'s
  basis is unchanged at 6/8/3** --- it is TeleSABRE-limited, and every other
  leg completes all 24, so no cell was recomputed. Caption "all five" ->
  "all four"; bold moved to +R on three rows (25q both blocks, 80q(b), all).
- `tab:protocols` lost its +S row; `tab:budgets` lost its +S row and the
  caption clause, and now names Appendix J as the one configuration not
  listed. IV-B's terminology bullet no longer defines a protocol as "a named
  row of `tab:budgets`", which that omission would have contradicted.
- `tab:shared`'s caption lost the four-line "+S has no column here" apology.
- V-F lost the whole **PORTER+SR retirement paragraph** (it existed only to
  explain a retired variant of +S); the surviving frontier prose keeps the
  0.93x/6.55x point as one clause pointing at the appendix.
- **New `sfc_appendix.tex` Appendix J** with the protocol definition, a
  24-row per-circuit table (`tab:layoutsearch`: PORTER / +R / +S EPR, delta,
  gamma*, both times), the buys/costs reading, and the +SR retirement.
  Appended as **J so A--I keep their letters**; `\appLayoutSearch` added to
  `sfc.tex`, front matter A--I -> A--J, plus `\mainRefine` / `\mainHorizon`
  xr macros. **Two pointers into it** (IV-E and V-F) so it is not orphaned.

**Paper is 15 pages (was 16); appendix 7 (was 6).**

**Sec VI: the tensions half was half recap.** Kept the section --- it is
referenced from six places and III-B *promises* it --- but rewrote it
534 -> 428 words and **reordered so the two syntheses come first and the
concessions last** (it had opened by undercutting the title).

- The layout/horizon paragraph was the **third** statement of that reading
  (V-D's closing, V-E's closing, then VI). It is now a pointer-style
  synthesis whose only new content is the *K*-scaling hypothesis.
- **It also overstated, and that was a real defect.** It said PORTER trails
  "under RQ2 ... and controlling the layout at a matched budget erases the
  difference." On the main suite it does **not**: PORTER/dSABRE is
  1.019/1.022/1.014 across the three grid rows and 1.017 under the own
  protocol --- controlling the layout leaves the ratio where it was, and V-B
  says outright "this is the controlled test and PORTER loses it." The
  erasure is **heavy-hex only** (82.9 vs 85.2 ring, 98.5 vs 101.1 star, 9
  routes each side), and that is the *cross-layout* control, not the
  equal-route one --- two different matched budgets IV-F is careful to
  separate. Now scoped to the heavy-hex control and labelled as such.
- The attribution paragraph duplicated III-B nearly verbatim; it now states
  only what that leaves open and cites III-B for the fact. Merged with the
  completion paragraph into one concession.
- **Threats to Validity kept verbatim** --- it was added answering the second
  review round, and cutting it would regress an answered review.

**Verifier changes.** `verify_tex_tables._MAIN_LEGS` drops `sfc_search`, and
a new **`tab:layoutsearch` parser** checks all 24 appendix rows (three EPR
columns, delta, gamma*, both times) and its four gmean lines --- times via
`gmean_raw`, per the clamping trap. `verify_paper_numbers.py` keeps the +S
pins and **adds ten more** for Appendix J's claims (never worse than +R,
10W/14T, all four wall-clock figures, the 80q share, the 80q AE 62x, and
that gamma=0.80 wins 9 of 24 while all five win somewhere). 197 checks.
The `narrative` per-instance check still reads +S as the strongest reported
PORTER protocol, which is correct --- +S is still reported, in the appendix.

## Sec I and II trimmed (2026-09-01) --- every section has now had a pass

**I 892 -> 794 words ($-11\%$), II 678 -> 630 ($-7\%$).**

**The one real duplication was between them.** The intro's \textbf{Problem}
paragraph restated II-B's \textbf{Objective} paragraph almost clause for
clause --- "Given a circuit DAG on $n$ logical qubits, a machine of $K$
cores with intra-core coupling graphs, inter-core links and designated
communication ports, and an initial layout, emit a legal operation
stream..." appeared in both. The intro's is now one sentence pointing at
II-B, which keeps the notation and the "never traded against EPR" clause.

Also cut from I: the second \textbf{Results} paragraph's editorialising
("Reaching parity with a concurrent compiler from a different design ...
Section~\ref{sec:results} gives every operating point behind it"); the
scale-up claim in contribution (ii), which the Results paragraph already
makes; the "last two work for any controlled two-qubit gate" aside; and
**the closing mechanism-to-experiment map**, which listed the same five
pairings the contributions list and IV-A both give --- now a pointer.

From II: the cat-entangler's gate-level construction (\appCatent{} carries
it in full), and phrasing in II-A and the cost model.

**Everything the abstract and conclusion rely on survives** --- the three
headline percentages, $1.02\times$/$0.91\times$/$0.72\times$, "forty-eight
instances", the $23{,}381$-CX circuit.

## Table II carries the portfolio and became a `table*` (2026-09-01)

**Two columns added**, headed *best of \dSABRE{} with* / \PORTER{} / $+$R:
the per-instance minimum of \dSABRE{} and that \PORTER{} configuration, on
whatever basis the row uses. Values: (a) $42.0$/$38.8$, $140.5$/$140.5$,
$34.4$/$34.4$; (b) $42.0$/$38.8$, $168.8$/$168.8$, $345.1$/$340.4$, and
pooled $155.9$/$152.1$.

**The table had to span both columns.** At 11 columns its natural width is
$345$\,pt against a $252$\,pt column --- the shrink-only resizebox would
have cut it to $73\%$ of `\small`, far smaller than any other table. As a
`table*` with `\tabcolsep` $4 \to 12.5$\,pt it measures $502$\,pt against
`\textwidth` $516$\,pt: **no scaling at all**. Its resizebox now guards
against `\textwidth`, not `\columnwidth` --- **any future `table*` needs
that same change** or it will be squeezed into one column's width.

**Bolding: the portfolio is deliberately NOT bold.** The first version
bolded whichever portfolio cell beat both compilers, which (i) contradicted
the caption on the $25$q rows, and (ii) read as if the portfolio were a
fifth configuration --- exactly what the text denies, since it costs both
routes and predicts nothing. **The bold EPR cell in every row is the best
single compiler**, and the caption says so. `verify_tex_tables` now pins
both halves of that rule: the bold cell equals the row minimum over the
four compiler columns, and both portfolio cells are unbold. Verified
non-vacuous by corrupting a portfolio cell and watching it fail.

59 tex checks, 252 numeric checks, generator idempotent, 14 pages.

## Four author queries on IV-D/IV-E answered (2026-09-01)

**(1) $\rho$ is a scalar, one per circuit.** `circuit_interaction_density`
returns a single float: partners are counted **over the whole circuit**,
averaged over qubits, divided by $n-1$. The text now says so explicitly
("one scalar summarising the whole circuit, not a per-qubit or
horizon-limited quantity"), because the old wording left it open. The
author's instinct is right and is now stated as untried work: **the
horizon acts per moving qubit while $\rho$ averages over all of them**,
which is a plausible reason one scalar cannot separate the $0.42$--$0.53$
band, and a per-qubit or horizon-limited density has not been tested.

**Spearman needs no citation** --- it is a standard statistic, used
uncited in this literature --- but the sentence did need fixing: it said
"$\rho$ ranks the best horizon at Spearman $-0.765$" without saying what
was correlated with what. Now "its rank correlation with the per-instance
best horizon is $-0.765$ (Spearman)". Note the **latent symbol clash**:
Spearman's coefficient is conventionally $\rho$ too, so never write it
symbolically here.

**(2) The candidate sets are now stated in IV-E's opening**, not buried
three paragraphs down: $\{4,8,16\}$ near all-to-all, $\{8,16,128\}$
otherwise, chosen by $\rho$.

**(3) The configured horizon IS the default, $L_\mathrm{tp}{=}16$.** The
paper used both terms without connecting them. IV-E now says so and adds
the fact that makes the guarantee work: **16 lies in both candidate
sets**, which is why the configured horizon always competes.

**(4) "Qubits withheld as communication slots" was wrong, and it was
wrong in two places.** `sabre_locked_boundary_layout` removes the most
remote **minimum-degree (corner)** qubits of each core **from the coupling
map given to SabreLayout**, so no logical qubit is placed there: they
begin **free and hold spare capacity** for arriving teleports and
evictions. They are **not** communication ports --- those are the
designated qubits at the link endpoints. Corrected in IV-D and in
Appendix B.

Appendix B carried a second, related error: it attributed the **chip-wide
four-corner** rule to "\dSABRE{}'s stock corner-removal convention" and
pointed at IV-D, which now describes the **per-core adaptive** count.
Both rules are real --- the pytket legs kept the chip-wide one --- so the
appendix now says which is which instead of conflating them.

## IV-E reorganised around the two protocols (2026-09-01)

**The section now names its subject up front**: "We evaluate two protocols
built on it. \PORTER{} routes its own layout once at each of three
candidate lookahead horizons and keeps the lowest-EPR result;
\PORTER{}+R refines backward from that selected route." The subsubsections
were retitled from mechanism names to protocol names --- "\PORTER{}:
choosing the horizon per circuit" and "\PORTER{}+R: refining backward from
that route" --- so E1 reads as \PORTER{}'s own protocol rather than as a
standalone technique. 833 -> 794 words.

**`\ell'` was undefined at its subscripts.** The text defined "$\ell'$ the
layout it ends on" and then used $\ell'_1$ and $\ell'_2$ with no
antecedent. Now: "**write $\ell'_i$ for the layout pass $i$ ends on**",
after which pass~1 computes $R(C,\ell_0)$ and ends on $\ell'_1$; pass~2
computes $R(C^{\mathrm{rev}},\ell'_1)$ and keeps only $\ell'_2$; pass~3
computes $R(C,\ell'_2)$. The subscript indexes the pass, not the layout
generation --- worth stating because $\ell_0$ (no prime) is the initial
layout and the two indices look alike.

Note the author commented out the \PORTER{}+S pointer here;
`\appLayoutSearch` still has two references (`tab:budgets`' caption and
`tab:protocols`' caption), so Appendix J is not orphaned --- checked.

## VI-A's completion paragraph reduced (2026-09-01)

**428 -> 302 words.** Every load-bearing step of the argument survives ---
the capacity half is already shared, the difference is atomicity, giving
it up would cost the opportunistic tier, and it would not fix the failure
we actually see (livelock, not deadlock) --- but each is now one clause
instead of a sentence, and the two paragraphs of justification collapse
into one.

**Dropped: the identity of the three instances teleport-only fails on**
(64q Random, 80q Multiplier, 80q Random). The count, twenty-one of
twenty-four, is still quoted; the names are kept only as a regression
guard in `verify_paper_numbers`, and its comment now says so. The
livelock's own instance (heavy-hex star Multiplier) is kept, since it is
the only place in the paper that names it --- V-E's livelock paragraph
was removed earlier.

Sec VI is 861 words; paper still 14 pages.

## Conclusion cut to two paragraphs (2026-09-01)

Author's call: the last two paragraphs --- the negative ablation result and
the bounds-plus-future-work summary --- were removed. **Neither needed
relocating: both were summaries of material that already lives elsewhere**,
so nothing was lost:

- the negative finding is stated in V-C and interpreted in \S VI (which is
  what the intro's contribution (iii) promises --- **that pointer still
  resolves**, so do not remove \S VI's \TeleData{} paragraph without fixing
  the intro);
- the teleport-only / completion-guarantee synthesis added the same day
  survives in VI-A;
- the bounds are Appendix K, still cited from II-B and IV-A (**two
  `\appThreats` references remain, so it is not orphaned**);
- the future-work list is \S VI-A itself.

Side effect: `sec:future` is now unreferenced from the main paper. Harmless
--- it is a subsection anchor, and nothing in the appendix uses it via `xr`
--- but a pointer to \S VI-A would have to be re-added if the conclusion
ever wants one.

Conclusion 395 -> 221 words, and it now ends on the complementarity result,
which is the strongest note available. Paper still 14 pages.

## Teleport-only + \dSABRE{}'s proof named as the configuration to try (2026-09-01)

**Author's idea, and two of our own results converge on it.** \dSABRE{}'s
termination-with-success proof is written for a **teleport-only** router,
and a teleport-only vocabulary is also the **cheapest we measure at 80
qubits** ($-21.4\%$). So a \PORTER{} restricted to \TeleData{} --- keeping
plan scoring, the relief tiers and horizon selection, dropping the
\TeleGate{} family --- is simultaneously where the guarantee is likeliest
to transfer and where the vocabulary result says the pairs are. Stated in
VI-A's completion paragraph and one clause of the conclusion.

**With the honest caveat, which is pinned:** that configuration completes
**21 of 24** here, failing **64q Random, 80q Multiplier and 80q Random**.
So the guarantee would still need the atomic relay *and* a local-stage
progress argument --- it is a promising starting point, not a proof
waiting to be written.

**Proofreading the conclusion also found a claim that had lost its
support.** "The lookahead horizon [dominates] at the larger [sizes]" was
supported by \S VI's "Which component binds changes with scale" paragraph,
deleted earlier today; V-D reports only that \PORTER{} wins all six
scale-up instances. Rewritten to what the paper still shows --- "the
lookahead horizon is what carries \PORTER{} past \dSABRE{} as the machine
grows" --- with the layout half scoped to "the sizes both target".
**Every deletion from VI needs this check: the conclusion's third
sentence summarises VI, so it goes stale whenever VI does.**

Verified in passing: the author's ">40\%" replacement for the three
TeleSABRE percentages is correct (the minimum is $41.6\%$).

## Sec VII: \dSABRE{} condensed to one paragraph; `tab:taxonomy` moved (2026-09-01)

**Three \dSABRE{} paragraphs -> one.** Everything downstream depends on
this paragraph, so all of it survives: the **four shared decisions** (the
intro says "share four design decisions"), the **four differences**, and
the **three guarantees** --- Sec VI-A's completion argument cites the
shared capacity floor and BFS relay, and Appendix K's "Completion is
empirical" cites the correctness/termination/completion split. Verified by
count after the edit: 4 / 4 / 3.

**`tab:taxonomy` appeared before \texttt{pytket-dqc} was introduced**, even
after moving its source below the "Other approaches" paragraph --- a `[t]`
float still rises to the top of its column, above the text that declares
it. **Changing the source position is not enough; the placement specifier
has to change too.** `[t]` -> `[b]` puts it at the foot of the column, so
the reading order is now: pytket-dqc introduced, the reference sentence,
then the table. Same trap applies to any float whose caption names
something the surrounding text introduces.

Sec VII prose 464 -> 440 words. Paper still 14 pages, zero overfull.

## VI: "dearer of the two" fixed; completion opening answers dSABRE (2026-09-01)

**"never the dearer of the two" was ambiguous** --- "the two" meant the full
action set and the teleport-only vocabulary, but neither had been named in
the sentence. Both occurrences (Sec VI and the conclusion) now say it
directly: "a vocabulary with gate teleportation removed altogether ---
\TeleData{} and nothing else --- uses no more EPR pairs than the full
action set on any 80-qubit circuit it completes, and fewer on most."

**"On the compiler itself" is now the first future-work item**, and the
completion opening answers *why not just adopt \dSABRE{}'s recovery*:

- **The capacity half is nearly in place already.** Both compilers treat
  free slots as a legality condition with the same floor of two, and both
  manufacture a slot by BFS to a reservoir. What \dSABRE{} has is
  **atomicity** --- it relays the chain as one all-or-nothing transaction,
  so post-recovery state is legal by construction, where \PORTER{} re-plans
  each hop through the ordinary plan machinery.
- **That difference is not free to give up**: scoring relief like any other
  plan is exactly what lets the *opportunistic* tier compete with normal
  work (III-G). An atomic drain removes that.
- **And it would not buy the missing guarantee.** \PORTER{} never reaches
  the capacity deadlock \dSABRE{}'s proof rules out --- with both tiers on,
  no instance in this evaluation does --- while the one failure observed is
  a **local-SWAP livelock** (heavy-hex star Multiplier at a fixed horizon,
  capacity healthy, EPR frozen). **A guarantee for \PORTER{} needs a
  progress argument for the intra-core stage, not a stronger capacity
  transaction.** This is the substantive answer; keep it if the section is
  trimmed again.

Note the livelock's *nature* is now stated only here --- V-E's livelock
paragraph was removed earlier, and Appendix K says only that one instance
fails at a fixed horizon. Pinned: no deadlock with relief on, \PORTER{}
completes all 48, and star/Multiplier completes under selection. 255 checks.

## Threats moved to Appendix K (2026-09-01)

Restored as **`sfc_appendix.tex` Appendix K, "Threats to Validity"** ---
all ten, in the trimmed form they had before the deletion, including the
two folded in from VI's dropped concession paragraph (`Mechanism
attribution`, `Completion is empirical`). Appended as **K so A--J keep
their letters**; `\appThreats` added to `sfc.tex`, front matter A--J -> A--K.

**Six new `xr` macros** for the cross-document references the threats need:
`\mainPlanFirst`, `\mainOwnProtocol`, `\mainRelated`, `\mainBaselines`,
`\mainScope` (plus the existing `\mainHorizon`, `\mainSharedTable`).

**LaTeX trap that cost a debugging round: a control sequence cannot
contain a digit.** `\newcommand{\mainRQ1}{...}` parses as `\mainRQ`
followed by `1`, which produced `Missing \begin{document}` plus three
`Undefined control sequence` errors *and silently inflated the appendix
from 7 to 9 pages* before it was caught. Renamed `\mainOwnProtocol`.
**Never put a digit in a macro name** --- and note the page count moved
before the error surfaced, so page count alone is not a compile check.

**Three pointers** keep it attached: II-B's cost-model sentence, IV-A's
research-questions paragraph, and the conclusion's "the evaluation is
bounded" sentence. Verified each threat's `\ref` resolves in the built
appendix (II-B, III-D, IV-C, IV-E1, V-A, VII, Appendix A, Table III).

Main paper **14 pages**, appendix **8** (was 7). Both compile with zero
errors and zero overfull boxes.

## Threats to Validity deleted; Sec VI is now Discussion and Future Work (2026-09-01)

**VI-B Threats to Validity is gone** (author's call), and the section is
retitled **"Discussion and Future Work"**: two findings, then VI-A Future
Work. $1{,}193 \to 665$ words.

**Checked before deleting: every one of the ten threats is stated
elsewhere.** The subsection was a consolidation, not a unique source ---
benchmark coverage and the cost-model bounds in the conclusion and II-B;
in-sample fitting, the reconstructed circuits, the patched binary, the
aggregation policy and the timing caveat in IV; unequal budgets in
`tab:budgets` and V; mechanism attribution in III-D; completion in VII.
**If any of those sections is trimmed in future, its caveat is now the only
copy** --- there is no backstop.

**Three pointers into `sec:threats` had to be rewritten**, since the label
no longer exists: II-B's cost-model sentence now ends on "every conclusion
in this paper is relative to that model"; the conclusion points at
`sec:future`; and **III-D's forward pointer** ("Section~\ref{sec:discussion}
states what that leaves open") was replaced by the substance itself, so the
attribution concession survives where the claim is made. One of these
edits dropped a full stop --- caught by the `grep -nE "\. +[a-z]"` sweep,
which is worth running after every pointer rewrite.

**"The $2\%$ pooled difference" was unexplained.** VI used the phrase twice
with no antecedent --- V-A states $174.9$ against $171.9$ but that is
several pages earlier. Now written out inline: "their pooled means differ
by only $2\%$ ($174.9$ against $171.9$)", and the second use is "that gap"
/ "the pooled figure".

Paper back to **14 pages**, 10,682 prose words; Sec III (3,008) is now more
than four times the size of Sec VI.

## Sec VI rebuilt: two findings + Future Work (2026-09-01)

Author's call --- "I can't see the value of Sec VI". It now holds only the
**two discussions worth keeping** (complementarity, and why \TeleData{}-only
can win), a new **VI-A Future Work**, and VI-B Threats.

**Dropped, and what each one cost:**
- **"Which component binds changes with scale"** --- the layout-below-108 /
  horizon-above-150 reading. Its one durable idea, the **$K$-scaled
  horizon**, moved into Future Work, where the motivation (an absolute gate
  count, and every scale-up instance picking the longest candidate offered)
  reads better as an opening than as a finding. **V-E pointed at this
  paragraph** and now points at V-D instead.
- **"Two things the evaluation does not establish"** --- split into two
  compact **threats** (`Mechanism attribution`, `Completion is empirical`).
  This keeps III-D's promise ("Section~\ref{sec:discussion} states what that
  leaves open") valid, since Threats is inside VI. **Do not delete those two
  threats without fixing III-D.**

**New VI-A Future Work**, informed by \dSABRE{}'s own future-work section
(`../dsabre/paper/dsabre.tex` §Future Work) but scoped to \PORTER{}:
scheduling/makespan and fidelity (the emitted trace is unscheduled);
**entanglement lifetime, which bites \PORTER{} specifically** --- a packet
holds one cat resource across a whole run, so a lifetime bound caps packet
length in a way our cost model does not, and the vocabulary result would
have to be re-read under it; richer interconnects (a second link turns an
occupied port into an alternative, and interacts with the capacity
discipline); then the four compiler-side openings. Cites
`baker2020time` and `ferrari2021compiler`, both already in `sfc.bib`.

**The conclusion's "Five openings follow: ..." list was deleted** --- it now
points at \S VI-A rather than duplicating it.

Sec VI $1{,}072 \to 1{,}193$ words: it lost ~290 of restatement and gained
~330 of future work and ~85 of threats. **The paper is 15 pages, but the
body still ends on 14** --- p15 is 18 lines of bibliography, pushed over by
the two new citations.

## The portfolio result is now a headline (2026-09-01)

**Author's framing, and it is the right one**: a $2\%$ pooled difference
invites "why another compiler that is not significantly better than
\dSABRE{}?" The portfolio answers it --- **a compiler that merely
re-derived \dSABRE{}'s decisions would leave a best-of-two with nothing to
choose between, and the gain would be zero.** A $9$--$12\%$ gain is
positive evidence that the designs are not interchangeable.

**Checked for the pytket trap first, and it holds.** Unlike the
`pytket-dqc` layout result, this one does NOT invert when the two cheapest
families are removed:

| basis | dSE+\PORTER{} | dSE+\PORTER{}+R |
|---|---|---|
| gmean, all 24 | $-9.3\%$ | $-11.6\%$ |
| gmean, the 18 non-trivial | $-8.0\%$ | $-9.0\%$ |
| **total EPR, the 18** | $-12.4\%$ | $-13.7\%$ |

Both bases are quoted in the paper and both are pinned. **Always run this
check before promoting a gmean result** --- it is what separated this
finding from the pytket one.

**Landed in the abstract, the intro (as the explicit answer to "what does a
second compiler add"), Sec VI and the conclusion.** Cost is stated wherever
the claim is made at length: $2.1\times$ \dSABRE{}'s compile time, twelve
routes to nine, an oracle with no predictor for the winner. Sec VI names
the two instances that carry it (80q Multiplier $4{,}841\to2{,}411$, 80q
QPEexact $347\to291$).

## Table II gains a W/L/T row; the portfolio result (2026-09-01)

**`tab:main` has a `W/L/T` row** giving each \PORTER{} configuration's
per-instance record against \dSABRE{} over all 24: **\PORTER{} 10/12/2,
\PORTER{}+R 11/11/2**. Per suite (not shown): 25q 4/1/1 and 5/0/1,
64q 2/6/1 for both, 80q 4/5/0 for both. \TeleSABRE{} and \dSABRE{} get
dashes --- \dSABRE{} is the reference. `verify_tex_tables` parses the row
and recomputes both cells; **confirmed non-vacuous** by corrupting a cell
and watching it fail.

**New finding: the two compilers are complementary, and a portfolio beats
either.** Taking the lower EPR count of the two per instance:

| portfolio | gmean | vs \dSABRE{} | vs the \PORTER{} leg |
|---|---|---|---|
| \dSABRE{} + \PORTER{} | 155.9 | $-9.3\%$ | $-10.9\%$ |
| \dSABRE{} + \PORTER{}+R | 152.1 | $-11.6\%$ | $-6.7\%$ |

Per suite the gain tracks disagreement: **$-16.3\%$ at 80q** (where
\PORTER{} goes 4W/5L) against **$-2.5\%$ at 64q** (where \dSABRE{} takes
six of nine). Total EPR over the 24 falls $12.4\%$ / $13.7\%$.

Landed as a paragraph in **Sec VI** --- it is a reading across V's results,
which is VI's stated job --- plus one clause in the conclusion. **Stated as
a property of the pair, not of either compiler**: it needs both routes, it
is an oracle over them, and no rule we tested predicts the winner in
advance. Its real force is that **the $2\%$ pooled difference understates
how differently the two behave**. Ten pins added (both records, both
portfolio gmeans, both ratios, the 80q/64q split); 244 checks.

## Table fonts: `\resizebox{\columnwidth}` was MAGNIFYING tables (2026-09-01)

**Root cause of "the fonts in several tables are too large".**
`\resizebox{\columnwidth}{!}{...}` scales a box to *exactly* the column
width --- **it enlarges a narrow table as readily as it shrinks a wide
one.** Every table trimmed this session got narrower, so several started
being blown up. Column width is $252.0$\,pt; measured natural widths:

| table | natural | effect of the old resizebox |
|---|---|---|
| tab:main | 252.7 | shrink 0.3\% |
| tab:shared | 286.8 | shrink 12\% |
| tab:ablation | 247.4 | **magnify 1.9\%** |
| **tab:scaleup (Table V)** | **227.9** | **magnify 10.6\%** |
| tab:protocols | 279.2 | shrink 10\% |
| tab:taxonomy | 307.7 | shrink 18\% |
| app tab:pytket | 229.4 | **magnify 9.9\%** |
| app tab:pytkettime | 218.9 | **magnify 15.1\%** |
| app tab:heavyhex | 230.4 | **magnify 9.4\%** |

**Fix, applied to all 16 resizeboxes in both documents:**

```latex
\resizebox{\ifdim\width>\columnwidth \columnwidth\else\width\fi}{!}{%
```

which shrinks when too wide and otherwise leaves the box alone. **Use this
form for every new table** --- it is also what \dSABRE{}'s paper uses --- so
a future trim cannot silently magnify.

Then `\tabcolsep` was raised on the five narrow tables so they *fill* the
column at true `\small` rather than sitting short: tab:scaleup
$3.5\to5$\,pt, tab:ablation $3\to3.4$\,pt, app tab:pytket $3\to4.9$\,pt,
app tab:pytkettime $4\to7.3$\,pt, app tab:heavyhex $4\to6.7$\,pt. All nine
resizeboxed tables now measure $251.9$--$337.8$\,pt, i.e. at or above the
column, so none is scaled up.

**To re-measure after changing a table**, box the tabular and print its
width against `\columnwidth`:

```latex
\setlength{\tabcolsep}{<value>}\small
\sbox0{\begin{tabular}...\end{tabular}}
\typeout{WIDTH = \the\wd0 col=\the\columnwidth}
```

Found and fixed in passing: `fig:trace`'s tabular in the verification
appendix was $5.58$\,pt overfull (pre-existing, no resizebox);
`p{4.0cm}` $\to$ `p{3.8cm}`. **Both documents now compile with zero
overfull boxes.**

## V-F cut to three short paragraphs (2026-09-01)

**246 -> 158 prose words**, on the author's instruction: paragraph 2 keeps
only its first two sentences, paragraph 3 only its first and last.

Gone, and worth knowing they are gone:

- **"Increasing \PORTER{}'s deterministic search budget therefore closes and
  reverses the own-protocol gap"** and the caveat that followed it ("We stop
  short of calling that gap a search-budget gap: refinement changes the
  layout each pass starts from as well as the route..."). That caveat came
  from the second review round --- but it existed **only** to qualify the
  sentence before it, so removing both together is safe. **Do not restore
  the claim without the caveat.**
- The \PORTER{}+S operating point ($0.93\times$ for $6.55\times$) and its
  \appLayoutSearch{} pointer. Appendix J still has **three** references
  (two in IV-E, one in `tab:protocols`'s caption), so it is not orphaned ---
  checked.
- The per-route paragraph's middle sentence: \PORTER{} is dearer per route
  on all nine 64q circuits, $3.6\times$ in gmean, so \dSABRE{} is cheaper
  end to end there ($1.77$ vs $1.98$\,s). **The surviving text still claims
  \PORTER{}'s advantage "is in the count of routes, not their price", which
  is exactly what that sentence evidenced** --- the claim now rests on the
  reader taking it, with the numbers in `tab:main`'s $t$ column. Pins kept
  as regression guards and commented as unquoted.

V-F now states the frontier, the trade, and that complete-protocol time is
the metric. Section V is 1,900 prose words; paper still 14 pages.

## Trimming round complete (2026-09-01)

| section | before | after | |
|---|---|---|---|
| abstract | 263 | 263 | --- |
| I introduction | 892 | 794 | $-11\%$ |
| II background | 678 | 630 | $-7\%$ |
| III compiler | 3,190 | 2,992 | $-6\%$ |
| IV methodology | 2,481 | 2,359 | $-5\%$ |
| V results | ~2,800 | 1,988 | $-29\%$ |
| VI discussion | 866 | 779 | $-10\%$ |
| VII related work | 522 | 468 | $-10\%$ |
| VIII conclusion | 382 | 375 | $-2\%$ |

Plus main-paper captions $899 \to 432$ ($-52\%$) and `tab:ablation` from 18
per-circuit rows to 7. **Paper 16 -> 14 pages.** Section V absorbed most of
the reduction because it held most of the restatement; I--IV are dense and
their small percentages reflect that, not a light pass.

## Sec III and IV trimmed (2026-09-01) --- the small percentages are the point

**III 3,190 -> 2,992 words ($-6\%$), IV 2,481 -> 2,359 ($-5\%$).** These are
the densest sections in the paper and the least compressible: III carries
**every parameter value the verifier pins against the live `RouterConfig`**,
and much of IV was written answering the two review rounds. Do not read the
small percentages as a light pass --- every paragraph was gone over; there
simply is not 20\% of restatement in them.

Where the words came from, all phrasing or genuine duplication:

- **III-A**: the $f_\mathrm{min}$ derivation ("a core with no free physical
  qubit is dead ... alive but cannot accept a \TeleData{}") argued the point
  twice. The **three roles stay, and so does the explicit non-invariant
  sentence** --- that wording was a review fix, do not lose it.
- **III-D**: the formal tuple's gloss re-described the paragraph above it;
  the full-core illustration became a clause; the trailing
  "Section~\ref{sec:related} places both against the baselines' choices"
  pointer went.
- **III-E**: "The order of the components is the design" filler; the
  $N_\mathrm{tp}$-inertness argument compressed to a clause pointing at
  \appTables{}, which carries it in full; the $\Delta$ and $L(\pln{p})$
  paragraphs each justified themselves twice.
- **III-F/G/H**: phrasing throughout; the four defences in III-H read as one
  long sentence and are now four.
- **IV-C Setup**: the benchmark and baseline paragraphs restated detail the
  appendix and \dSABRE{}'s own paper carry.
- **IV-E horizon**: the $\rho$ definition took five sentences to say one
  thing; the in-sample paragraph overlapped Sec VI's threat of the same name.
- **IV-E refinement**: the "+R can never report a higher EPR count" bound was
  stated **twice**, once per paragraph. Merged.

**Verified after**: all twelve numeric parameters III quotes are still
present (checked by regex, and `verify_paper_numbers` still matches them
against the live `RouterConfig`), no broken sentences, no orphaned labels,
no unresolved refs.

**Whole paper 10,881 prose words, 14 pages.** Section III at 2,992 is now
the largest by a wide margin and is the only place left with meaningful
slack --- but cutting it further means cutting algorithm description, not
restatement.

## Sec VII and VIII trimmed and audited (2026-09-01)

**VII 522 -> 468 words, VIII 382 -> 357.** Both were already dense; the cuts
are phrasing plus two real removals:

- VII's "Its capacity handling is also more proactive: ... an explicit
  blocked-plan set with a tail-relief search and a pre-emptive relief
  comparator" re-described Section III's mechanism. Folded into one clause.
- **VII and VI both ended on "the clearest piece of theory this design
  leaves open".** The judgement now appears once, in VI; VII states the gap
  factually and stops. (Checked: `grep -n "clearest"` returns one line.)

**One scoping fix.** My first pass changed the conclusion to "completes every
instance", which is *true* --- \PORTER{} completes 48/48 (main 24, scale-up
6, heavy-hex 18) --- but the sentence is about the MQT-Bench suites and the
\TeleSABRE{} comparison, so it now says "all twenty-four", matching the
abstract. Worth remembering: since horizon selection landed, **48/48 is
accurate and the old "scoped to the three MQT-Bench suites" caveat recorded
below is obsolete** --- the star-Multiplier exception it guarded against is
gone.

**Audit clean.** All `\ref`s in both sections resolve. VII's two enumerations
still match their announced counts (four shared decisions --- which the intro
also claims --- and four differences), the three-guarantee taxonomy VI cites
is intact, "no instance left unrouted" holds at 48/48, and VIII's "five
openings" really lists five. Every figure VIII quotes was re-verified
earlier today.

**Whole paper: 11,880 prose words, 14 pages** (abstract 256, intro 884,
background 1,026, Sec III 3,357, Sec IV 2,744, Sec V 1,925, VI 775, VII 468,
VIII 358). **Sections III and IV are now by far the largest** --- together
6,101 words, more than half the paper --- and are the only places left with
real slack if more is needed.

## Sec VI trimmed and audited against the trimmed Sec V (2026-09-01)

**866 -> 775 words, only $11\%$** --- the section resists cutting because
every paragraph carries a finding and every threat was added answering a
review. Where the cuts came from: **four threats were re-deriving Section
IV's setup** rather than stating a threat (the patched binary, the
reconstructed circuits, the 9-vs-3 budget, the Python/C timing caveat).
Each now states its threat and cites IV for the setup. Do not read the
small percentage as "nothing was cut" --- read it as the section already
being close to its floor.

**Two consistency defects found, both introduced by earlier edits in this
session:**

1. **VI claimed \TeleData{}-only is "cheaper still on \emph{every} 80-qubit
   circuit it completes".** GHZ and Graphstate **tie** ($7\to7$,
   $28\to28$), so the correct form is "never the dearer of the two" ---
   which is what V-C and the conclusion already said. This is the *same*
   overstatement I fixed in the conclusion earlier the same day; it had been
   introduced into VI when the stale "packet-heaviest" qualifier was
   replaced. **When fixing a claim, grep for its siblings.**
2. **VI attributed to V-D a fact V-D no longer states** (dSABRE's layout is
   worse for PORTER on scale-up). Now attributed to the released results,
   which is where it lives after V-D's interpretive paragraphs were removed.

**Full audit run and clean.** All thirteen `\ref`s in VI resolve; `sec:terms`
really lists four failure modes; `sec:sfc-plan-first` really states the
no-experiment-isolates-it claim; `sec:related` really separates
correctness/termination/completion and carries \dSABRE{}'s
termination-with-success proof. Every quantitative claim recomputed from the
JSONs: routing loops within $3\%$ (max exactly $3.00\%$), the heavy-hex
control beating \dSABRE{} on both graphs, \dSABRE{}'s layout worse for
\PORTER{} on scale-up ($678.9$ vs $507.7$), $0.72\times$, zero 80q circuits
where \TeleData{}-only is dearer, five relief failures.

## V-E refocused; Table VI gains the fixed-layout column (2026-09-01)

**The star-Multiplier livelock is out of V-E** (author's call: not helpful
for the section's purpose, which is only to show \PORTER{} runs on both core
graphs and that its layout suits a star badly). Removed: the whole
"Star Multiplier is a livelock the horizon escapes" paragraph and the
`star Multiplier 722 / 455` callout row of `tab:heavyhex`.

**`tab:heavyhex` now has three columns** --- \dSABRE{}, \PORTER{} on its own
layout, \PORTER{} on \dSABRE{}'s `SabreLayout` candidates --- so the
fixed-layout control that carries V-E's layout claim is in the main table
instead of only the appendix:

| core graph | dSABRE | PORTER own | PORTER on dSABRE's |
|---|---|---|---|
| ring (9) | 85.2 | 86.1 | **82.9** |
| star (9) | 101.1 | 122.3 | **98.5** |

The control is the row minimum on both graphs, which is the point.

**Three downstream fixes the removal forced:**
- the **intro's** mechanism-to-experiment map tied horizon selection to "the
  scale-up series and the star-Multiplier livelock"; now the scale-up series
  alone;
- `verify_tex_tables`'s heavyhex parser assumed the callout row and a
  conditional row count keyed on whether \PORTER{} still failed the instance
  --- now a flat 2 rows, 4 columns, plus a check that the control column is
  the row minimum;
- the $455$/$722$ and widest-margin pins are no longer quoted; kept as
  regression guards that horizon selection still routes the instance.

**Sec VI keeps the livelock** as a limitation on the completion record
("only livelock was observed here, on heavy-hex star Multiplier at a fixed
horizon"). That is the right home for it --- it is a limitation, not a
result --- and it is self-contained, so V-E no longer has to set it up.

**V-E 460 -> 379 words; Section V 1,902; the paper dropped to 14 pages**
(references now start on 13), the first page the whole trimming round has
bought.

## V-A trimmed; Section V now under 2,000 words (2026-09-01)

**V-A 341 -> 264 prose words.** Cut: the "Table~II summarises the three
suites" opener; the two sentences explaining why block \emph{(a)} is the
\TeleSABRE{} basis and block \emph{(b)} the \dSABRE{} one (the caption says
both); the restatement of each protocol's route budget (`tab:budgets` says
it); and the raw pairs behind the 25q and 80q ratios ($43.1$/$45.8$,
$396.7$/$412.1$), which are table cells --- the ratios stay in prose. Every
figure the abstract, intro or conclusion cites is untouched.

**Section V across this round: ~2,800 -> 1,983 prose words** (V-A 264,
V-B 397, V-C 452, V-D 158, V-E 460, V-F 252), plus captions 899 -> 432 and
`tab:ablation` from 18 per-circuit rows to 7. Paper holds at 15 pages with
references starting on 14, so the space went into margin rather than
page count --- worth knowing before trimming further.

## V-B trimmed, pytket paragraph halved (2026-09-01)

**V-B 535 -> 397 prose words**; the pytket paragraph, which was $290$ of
them, is down to about $170$. Cut:

- **Four of the six statistics.** The argument needs the reversal
  ($+10.7\%$ / $+9.1\%$ on the eighteen), the per-instance record (worse on
  14 of 24) and the median ratio ($1.03$). The $38.8\%$/$36.8\%$ pair and
  the total-EPR figures ($+11.8\%$ / $+5.9\%$) made the same point a third
  and fourth time; their pins stay as regression guards, commented as
  unquoted.
- **The gmean-sensitivity explanation** ("costing one to two orders of
  magnitude fewer pairs ... moves an unweighted geometric mean as much as
  halving the dearest circuit"). It is in `tab:shared`'s caption, where a
  reader meets the two blocks.
- The 64q-QNN timing specifics and the "controlled probe" half of the
  opt-in sentence; the $0.6$--$650$\,s range and \appOptin{} carry both.
- The parenthetical spelling out pytket's permissive network ("every qubit
  available for data, unboundedly many live link qubits per core"), now just
  a citation --- \dSABRE{}'s paper is where that model is described.
- V-B's opening paragraph, which spelled out the \TeleSABRE{} exclusion in
  two sentences, is one.

**Section V is now 2,060 prose words** (V-A 341, V-B 397, V-C 452, V-D 158,
V-E 460, V-F 252), from roughly 2,800 before this round of trims. V-C and
V-E are now the longest; both are carrying findings rather than restatement.

## V-E and V-F trimmed (2026-09-01)

**V-E 512 -> 460 prose words, V-F 353 -> 252.** Cut, all of it either
restatement or implementation history:

- V-E's opening restated the *Question* line directly above it and described
  the topology assertion, which IV-C already covers ("read from the
  baselines' own device files, so every compiler sees identical physical
  qubit ids").
- The star-Multiplier livelock forensics ($3{,}226$ of $13{,}040$ retired,
  EPR frozen at $538$) --- the livelock-vs-deadlock *distinction* is what
  Sec VI's failure-mode claim needs, not the counters. Kept the mechanism,
  dropped the numbers.
- The $f_\mathrm{min}\in\{4,6\}$ parenthetical; the claim that a uniform
  bump does not repair the star survives without it.
- **V-F's "That property is what removed an earlier caveat"** --- a note
  about how *our own implementation* used to behave at a fixed horizon.
  IV-E-2 already states the property that matters (refining from the
  selected route is what makes +R contain \PORTER{}).
- V-F's per-iteration explanation of why \PORTER{} is dearer per route
  (plan enumeration, packet forward-simulation, two-tier capacity search).
  The $3.6\times$ figure carries the point.
- The separate \PORTER{}+S sentence folded into the trade sentence as one
  clause.

Nothing removed was pinned or cited elsewhere (checked both verifiers and
every `\ref`). **Section V is now 2,198 prose words** --- V-A 341, V-B 535,
V-C 452, V-D 158, V-E 460, V-F 252. Paper 15 pages, references start on 14.

## V-D reports, Sec VI interprets (2026-09-01)

**V-D's last two paragraphs are gone** (author's call: not directly helpful):
"The horizon, not the layout, accounts for the reversal" and "This separates
two deficits the smaller suites conflate" --- 167 words. V-D now answers RQ4
and stops: \PORTER{} wins all six, $0.72\times$, at $0.54\times$ the compile
cost. The horizon-vs-layout attribution is interpretation spanning V-B, V-D
and V-E, so it belongs in Sec VI, which already made it --- this is the
paper's own structural rule ("interpretation spanning several results goes in
VI, not in the results subsections").

**Two downstream claims had to be rescoped, both of which the removal
orphaned:**
- **Sec VI** said "Section V-D locates it elsewhere: ... the horizon moves
  \PORTER{} from $1.45\times$ behind to $0.72\times$ ahead", attributing to
  V-D a claim it no longer makes. VI now owns the interpretation and cites
  V-D only for the $0.72\times$ it does report.
- **V-E's closing** asserted "above $150$ the horizon takes over", supported
  only by the removed text. It now states its own $\le108$ bound and points
  at VI for the contrast.

**No longer quoted anywhere:** the $0.96\times$ dSABRE-layout scale-up ratio
and the $1{,}791$ figure for 360q QFT on dSABRE's layout. Their pins are kept
as regression guards, commented as unquoted. $1.45\times$ survives in Sec VI
and is its only occurrence --- note the removed text cited
Section~\ref{sec:horizon} for it, which never stated it.

**A real error found while reconciling VI with V-B:** both said the layout
spread is "three to five times" the routing spread. Measured over the six
column/block pairs it is **2.2x--3.6x**; no pairing supports three-to-five.
Corrected to "two to four times" in both, and pinned as a bounded range.
Sec VI also still said the routing loops are "within $2\%$" (true of block
(a) only) where V-B now says $3\%$; aligned.

## Table IV is 80q-only; V-C and every caption cut (2026-08-31)

**Author's call, and it REVERSES the 2026-08-31 decision recorded below**
("Ablation basis widened, then compacted"), which kept 25q/64q summary lines
to preserve two cross-scale findings. Those findings are now **dropped from
the paper entirely**, on the author's framing that *the purpose of a
mechanism ablation is to show why a mechanism is needed*, and a scale trend
does not speak to that:

- "the TeleData advantage is monotone in width" ($+1.3\%$ / $-1.6\%$ /
  $-21.4\%$) --- gone from V-C and from the conclusion, which now quotes the
  80q figure alone;
- "relief inverts with scale" --- gone; V-C says only that relief earns its
  place on *completion* (5 of 9 fail without it) and not on cost ($4.0\%$).

The ablation still **runs** on all three suites, and the 25q/64q checks stay
in `verify_paper_numbers` as a regression guard on the measurement, clearly
commented as no longer quoted. CLAUDE.md is where those trends now live.

**V-C is restructured around "does this mechanism earn its place":** packets
yes on EPR ($10.9\%$), \TeleGate{} yes on *completion* (strict removal fails
all but two rows), relief yes on *completion* and not on cost. The ordering
$\text{\TeleData{} only} < \text{Full} < \text{No packets}$ is now made on
**80q alone** --- it holds on 4 of the 5 rows where all three columns
complete, **QFT the exception**, which is also one of the two circuits
cheaper without packets. Pinned as a count plus the exception's identity.

**Sec VI was carrying the same stale qualifier** ("cheaper still on the
packet-heaviest 80-qubit circuits") and now says "on every 80-qubit circuit
it completes" --- at 80q there is no packet discrimination, it wins
everything it completes.

**`tab:ablation` now has no Suite column** (every row is 80q): 7 per-circuit
rows + 3 gmean lines, 7 columns. `gen_tables_selection.tab_ablation` and
`verify_tex_tables` were both rewritten for the shape --- the row regex
matches circuit names now, indices shift by one, and the summary regex is
`^\\textbf\{gmean\}`.

**A basis change silently invalidated a count.** V-C said "two instances are
cheaper without relief" --- true pooled over 24 (64q QNN, 80q Multiplier, 25q
Random) but at 80q it is **one** (Multiplier). Fixed, and `verify_paper_
numbers` now pins the 80q counts specifically: 5 relief failures, 1 cheaper
without relief, 2 cheaper without packets, and the QAOA/AE packet
percentages. **Whenever a table's basis narrows, re-derive every count in its
prose --- percentages usually survive, counts usually do not.**

**V-C prose 705 -> 426 words (-40%).** Not the full half: the remaining
material is load-bearing and has been cut-and-restored once already (the
"the next overturns that" bridge and the dSABRE-open-question link are both
asserted by the intro and conclusion, so V-C has to make them).

**Every main-paper caption cut, 899 -> 432 words (-52%):**
tab:ablation $-70\%$, tab:main $-51\%$, tab:scaleup $-47\%$,
tab:protocols $-44\%$, tab:heavyhex $-43\%$, tab:shared $-41\%$,
tab:budgets $-38\%$. Paper back to **15 pages**.

## Why pytket-dqc's partition is NOT PORTER's layout (2026-08-31)

**V-B used to say pytket-dqc's partition is "the best start for *both*
routers" ($-4.5\%$ / $-4.8\%$). That is a geometric-mean artefact of six
near-trivial rows.** Decomposed:

| basis | dSABRE own -> pytket | PORTER own -> pytket |
|---|---|---|
| gmean, all 24 | 171.9 -> 164.1 (**-4.5%**) | 174.9 -> 166.4 (**-4.8%**) |
| GHZ + Graphstate (6) | 9.4 -> 5.8 (-38.8%) | 9.3 -> 5.9 (-36.8%) |
| **the other 18** | 452.5 -> 501.1 (**+10.7%**) | 464.6 -> 506.7 (**+9.1%**) |
| total EPR (24) | +11.8% | +5.9% |
| win/loss | 10W/14L | 9W/14L/1T |
| median per-instance ratio | 1.031 | 1.032 |

GHZ/Graphstate cost 1-2 orders of magnitude fewer pairs than the rest, so a
proportional change there moves an unweighted gmean as much as halving the
dearest circuit in the suite. **Same inflation pattern as
[[porter-two-phase-layout-qap]]** --- check for it whenever a layout change
looks like a broad win.

**Independently confirmed by dSABRE's own harness.** `../dsabre/code/results/
results_pytket_layout.json` (2026-08-10) routes dSABRE from pytket KaHyPar
layouts. At **64q**, the one suite where our dSE column reproduces theirs
exactly: theirs 173.3 -> 181.2 (**+4.6%**, 3W/6L), ours 173.1 -> 179.7
(**+3.8%**, 4W/5L). (Their 25q rows are a *different device* --- B-grid,
2 ports/core --- so not comparable; do not cross-check 25q.)

**Cost, measured (best-of-3 KaHyPar vs `build_initial_layout` vs PORTER's
3-route protocol):**

| circuit | CX | partition | layout build | PORTER 3 routes |
|---|---|---|---|---|
| 80q graphstate | 80 | 0.55 s | 0.5 ms | 0.3 s |
| 25q ae | 558 | 3.2 s | 0.3 ms | 0.2 s |
| 64q ae | 1,962 | 14.2 s | 1.2 ms | 1.6 s |
| 64q qnn | 8,126 | 122.2 s | 3.1 ms | 4.8 s |
| **80q random** | 23,381 | **649.8 s** | 9.6 ms | 206.5 s |

3-5 orders of magnitude over the layout it would replace, and more than the
whole compile on 6 of 8. Scales worse than routing: 80x the CX buys 200x the
partition time. **Appendix C said 309 s for 80q Random; measured 650 s.**

**What dSABRE's paper says** (`../dsabre/paper/dsabre.tex`): as a *compiler*
it is "a cost-model study, not a like-for-like router comparison" --- pytket's
network is more permissive than the device (every qubit available for data,
unbounded live link qubits per core), so 4/6, 2/6 and >=6/9 of its
distributions are **provably unbuildable** (25q AE needs 20 simultaneous link
qubits where the device has 2), and its e-bits assume unbounded entanglement
lifetime (cap at 3 gates/pair and 64q flips from pytket +15.3% to dSABRE
-59.6%). As a *layout source* its Related Work explicitly endorses the use
--- "their output can supply an initial allocation" --- but reports no result
doing it. That permissiveness is the paper's stated reason the partition need
not suit a port-constrained router.

**Landed.** `tab:shared` is now **two blocks** --- (a) all 24, (b) the 18
without GHZ/Graphstate --- because the two disagree in *every column*: pytket
is the column minimum in (a) and the maximum in (b), where each router's own
layout is (near) best for it. What survives both bases: the routing loops are
within 3.0% across every row (max deviation exactly 3.00%, so pins must round
to 1 dp) while the column spread is 3-5x larger, i.e. **the layout is the
weaker component of both compilers**. What does not survive: which layout is
best, and "dSABRE ahead in all three rows" (it is ahead in 2 of 3 in block
(b); PORTER takes its own layout there).

V-B now states the two reasons for not adopting the partition --- **cost, and
confinement to the two structurally simplest families** --- and Appendix C was
rebuilt around them with a timing table (`tab:pytkettime`). Its stale figures
were: the "-16%" best-of-2 (now **-12.1%** over 24 and only **-1.8%** over the
18), "80q AE 490->352" (490 was the pre-selection single pass; now **299 own
vs 389 pytket, a loss**), "Graphstate 28->11" (28->10), and the 309 s.

**`gen_tables_selection.tab_shared` had to be taught the second block** --- it
silently spliced the old 3-row grid back over the new table *after* both
verifiers had passed. Same trap as 2026-08-31's first occurrence: **run the
generator BEFORE the verifiers, and test idempotence by diffing the file
across two runs, not against HEAD.** `verify_tex_tables` now pins 6 rows and
the column-minimum reversal; `verify_paper_numbers` adds ~20 pins covering
the decomposition, both bases, the totals, the win/loss counts, the median
ratio and Appendix C's two best-of-2 figures. 223 checks.

Paper is 16 pages (body ends on 15; p16 is 22 lines of references).

**Abstract/intro/conclusion re-audited after the +S removal --- one stale
number found.** Every headline figure was recomputed live: the three
TeleSABRE margins (59.6/41.6/68.2 at three routes, block (a) basis), 24-vs-17
completions and the seven non-convergences, 1.02x EPR / 0.91x time vs dSABRE,
0.72x and 6/6 on scale-up, 48 instances, the 23,381-CX circuit (80q Random),
and the factor-32 horizon span. **All correct, and none of them depended on
+S** --- the removal touched nothing in those three sections.

**The exception: the conclusion's negative-finding figure was wrong.** It said
TeleData-only "beats the full action set by $32.8\%$ on the packet-heaviest
circuits" at 80q, while V-C and `tab:ablation` say **-21.4%** (n=7). The
32.8% reproduces on exactly one basis --- the geometric mean over
{80q ae, qft, qnn} --- which the paper never defines, and **those three are
not the packet-heaviest**: at 80q the ranking is random 572 > qnn 448 >
qaoa 303 > ae 264 > qpeexact 239 > qft 209 > multiplier 192. It is a fossil
of the pre-widening common-6 ablation basis. **It was the only headline
percentage in the three sections with no pin**, which is how it survived
(the `-32.8` that greps in `verify_paper_numbers.py` and the appendix is an
unrelated coincidence --- 64q Multiplier's $\Delta_\mathrm{TS}$).

Fixed to the body's own basis, and the conclusion now states the **monotone
scale trend** that is the actual finding: +1.3% at 25q, -1.6% at 64q,
-21.4% at 80q, "never the more expensive of the two on any circuit it
completes" at 80q (verified: zero 80q circuits where TeleData-only is dearer).

**V-C's "the circuits it wins are the packet-heaviest" was also unscoped.**
It holds cleanly at **64q** --- ranked by packets, the completers go
`WWWLLLTT` (qaoa 331, qnn 240, qft 45 win; qpeexact 42, multiplier 34, ae 32
lose; ghz/graphstate tie at 0) --- and **fails at 80q**, where the ranking is
`WWWWWTT`: it wins every circuit it completes, and the two it cannot complete
are the packet-heaviest (random) and the packet-lightest (multiplier). The
sentence sat immediately after the 80q figure, so it read as explaining it.
Now scoped to 64q with the 80q behaviour stated separately. Both orderings
are pinned as strings, so either flipping fails.

**Route-count arithmetic checked, and one number was wrong.** \PORTER{}+R's
`routes = 7` is **correct** --- verified by counting `PorterRouter.compile`
calls: `run_refinement_passes(selection=True)` spends |H|=3 on horizon
selection, **pins `dag_extended_max_layers` to the winner**, and runs the
remaining P-1=4 passes at that horizon (live trace: `L per route =
[16,4,8,16,16,16,16]`). It is **not** 5x3=15; re-selecting per pass is
explicitly rejected in the code. With `selection=False` it is 5.

**But \PORTER{}+S's "10--17" was wrong under the paper's own definition of a
route** ("one invocation of the routing loop"). Two counts exist:

- **Actual invocations** = 5 (phase 1) + **7 per refinement seed**, since each
  seed runs the full `run_refinement_passes(selection=True)` = |H| + P - 1.
  So **12** when gamma=0.99 wins phase 1 (one seed) and **19** otherwise.
  Measured live: 25q ae 19, qft 12, graphstate 19.
- **`info["routes"]`**, what the harness records, discounts one route per seed
  --- `info["routes"] += (passes_run-1) + (horizon_routes-1)` charges each
  seed's pass 1 to phase 1, because that (layout, horizon) pair was already
  routed there. Gives 11 or 17, dropping to 10/13/15/16 where a per-pass
  guard cuts a pass short. **The code does not memoise: it really re-routes.**

Appendix J now states both and the derivation; the old text's
"$5+4=9$ / $5+4+4=13$ plus $|H|-1$ probes" was the second count with a wrong
derivation (it credits P-1=4 + 2 probes = 6 per seed, not 7). Pinned:
per-seed routes = |H|+P-1 = 7 against the live constants, |H|=3 for both
candidate sets, the counter's observed min/max (10/17), and that the
one-seed instances are exactly the three where gamma=0.99 wins.

**Gotcha for future appendix tables:** `verify_tex_tables.rows_of` and
`gmean_rows` match **one line at a time**, so a row wrapped across two source
lines is silently dropped or mis-indexed (it cost an `IndexError` here). Keep
every table row on a single line.

## V-B rebuilt as a layout x router grid; Section V compressed (2026-08-31)

**`tab:shared` in the main paper is no longer the \TeleSABRE{}-shared
table.** It is a 3x3 grid --- three initial-layout sources (dSABRE's
`SabreLayout`, PORTER's temporal locality-greedy, pytket-dqc's partition)
against three routing configurations (dSABRE, PORTER, PORTER+R) --- with
**every cell over all 24 instances**, no exclusions, because all three
layout sources place all 24 circuits. What it says:

| initial layout | dSABRE | PORTER | PORTER+R |
|---|---|---|---|
| dSABRE's `SabreLayout` | 171.9 | 175.2 | **166.3** |
| PORTER's temporal locality-greedy | 171.2 | 174.9 | 171.4 |
| pytket-dqc's partition | **164.1** | **166.4** | 166.5 |

- Across a row the two routing loops are within 2%, dSABRE ahead on all
  three. **This is the controlled test and PORTER loses it.**
- Down a column pytket's partition is the best start for *both* routers
  (4.5% better for dSABRE, 4.8% for PORTER), so the layout spread exceeds
  the routing spread and the initial layout is the weaker component of
  both compilers.
- **Dropping \TeleSABRE{}'s layout as the frame removes a PORTER-favourable
  result**: on it PORTER+R overtakes dSABRE outright (86.0 vs 100.9),
  which happens on *no* other layout source. The mechanism is that
  TeleSABRE's layout is much the worst start (dSABRE 100.9 on it vs 71.1
  on pytket's, same 17 instances) and refinement gains 20.2% from it
  against ~0% from pytket's. Refinement repairs a bad layout; it adds
  nothing to a good one. V-B keeps this as one sentence rather than the
  headline, and `verify_paper_numbers.py` pins all four figures.

**`tab:crosslayout` was deleted from the appendix.** Its cells were
pre-selection *and* pre-default-layout (PORTER own-layout 194.6 = the old
single pass; dSABRE 163.9 = the old best-of-six candidate set), so it
contradicted the new grid inside the same paper. `verify_tex_tables.py`
never parsed it and `verify_paper_numbers.py`'s three `crosslayout ...`
pins were computed live, so both passed while the table was wrong ---
they are renamed `grid ...` now. The appendix's per-circuit
TeleSABRE-shared table stays (V-B still cites it), with "single-shot"
struck from its caption: those legs run each compiler's own route budget.

**Run `gen_tables_selection.py --write` BEFORE the verifiers, never
after.** Its `tab_shared` generator still emitted the old
TeleSABRE-shared summary block and spliced six data rows into the grid's
four-column tabular, *after* both verifiers had passed on the correct
file. `tab_shared` now generates the grid (bold = column minimum, errors
out if any leg does not cover all 24), and `--released` is **no longer a
self-test** --- the released `*_results.json` are one protocol behind, so
it prints single-pass numbers by design.

**Two questions answered in the text (2026-08-31).** (i) *Why not
TeleSABRE's layout as a grid row*: it converges on 17 of 24 and emits a
layout only where it converges, so a row would rest on a
seventeen-instance basis missing 64q Random and six of nine 80q circuits
--- the scale where the compilers differ most. V-B says so before the
first finding; the missing set's identity is pinned. (ii) *Why PORTER+R
can be worse than PORTER*: **+R is not PORTER plus more effort.**
`run_refinement_passes` defaults `selection=False`, so all five passes
run at the configured `L_tp`, while PORTER spends its three routes on
three candidate horizons. Each schedule is safe only against the route
it *contains* (PORTER because the configured horizon competes and wins
ties; +R because the best forward pass is kept), and neither contains
the other's, so neither bounds it. Where the horizon binds, the
fixed-horizon penalty exceeds refinement's gain (80q, scale-up, star
Multiplier); where it does not, refinement's gain is small and can
vanish, because passes after the first start from a post-routing layout
that has lost the free-slot reservation. IV-E states the fixed horizon,
V-F the consequence.

**Residual error found while writing that**: `tab:budgets` still listed
**four** gammas and $|\mathcal{L}|{=}4$ for PORTER+S. The second review
caught this in the prose (2026-08-29) and the prose was fixed; the table
row was not. `DEFAULT_LAYOUT_GAMMAS` is five. Now corrected and pinned
against the live constant, along with `run_refinement_passes`'
`selection` default. The caption's "routes $=|\mathcal{L}|\cdot P$" was
also false for +S/+SR and now says so.

**Section V compressed 20%** (3,488 -> 2,806 prose words; V-A -20%,
V-B **-47%**, V-C -18%, V-D -7%, V-E -10%, V-F -9%), paper still 15 pages.
Cut: the GHZ chain-circuit aside, the per-suite gamma-search figures in
V-A (V-F carries them), the restatement of column definitions already in
`tab:ablation`'s caption, and the dSABRE-reproduces-its-published-numbers
sentence in V-E (its caption says it).

## The main paper is split by section (2026-08-29)

`paper/sfc.tex` is now a **driver only** --- preamble, title block, `\input`
lines, bibliography, biography. The body lives in `paper/sections/`, one file
per section (`00-abstract` .. `07-acknowledgments`); `sections/README.md`
carries the workflow. The split is output-preserving: `pdftotext` of the
rebuilt PDF is byte-identical to the pre-split one.

- **Macros stay in the driver**, so a section file is NOT independently
  compilable. Do not add a local `\newcommand` to a section.
- **All five data tables are in `04-evaluation.tex`.** Both verifiers were
  updated for this and must stay that way:
  `verify_tex_tables.py` concatenates `sfc.tex` with every `sections/*.tex`,
  and `gen_tables_selection.py` locates each table by `\label` instead of by
  filename, so tables may move between sections freely.
- `gen_tables_selection.py` is **idempotent** on current files --- running
  `--write` and getting no diff is a valid check that the tables are current.
  Two bugs were fixed to get there: the appendix generators were shadowing the
  main paper's for the two labels that exist in *both* documents
  (`tab:shared`, `tab:heavyhex` --- they name different tables, so the label
  search is scoped per document), and the star-Multiplier row hardcoded bold
  on the last column when the minimum had moved to `porter` (455, not 462).
- Appendix `sfc_appendix.tex` is **not** split; it is still one file.

## Paper proofread + restructure (2026-08-29) --- the protocol migration left prose fossils

Full audit of `sfc.tex` after horizon selection became the headline protocol.
**Both verifiers passed the whole time**: `verify_tex_tables.py` only checks
table *cells*, and `verify_paper_numbers.py` had already been updated to the
new values while its check *names* and the paper's *prose* still carried the
old ones. That is the failure mode to watch for --- a green verifier is not
evidence the prose is current.

**Sec IV-E (scale-up) was entirely stale and contradicted its own table.**
Every figure in it came from the pre-selection `scaleup_results.json`:
"dSABRE takes all six instances" (PORTER takes all six, 6W/0L), "refinement
helps on two ... 1.45 to 1.32" (it helps on **zero**), "the fixed-layout
control does not rescue it" (nothing to rescue), 1.35x/1.24x/3266-vs-2822,
and "PORTER remains 1.8-6.5x faster per attempt" (that is the *old single
pass*; the shipped three-route protocol is 0.61-1.53x one dSABRE attempt,
but 0.20x its **complete** cost, which is the paper's own convention).
The stale reading had propagated to Sec IV-D's forward pointer, Sec IV-F's
closing paragraph and the Conclusion. Corrected reading: **below ~108
physical qubits the initial layout binds (control it and the gap closes);
from 150 up the layout stops binding and the lookahead horizon does** ---
all six scale-up instances select L=128, and dSABRE's layout makes PORTER
*worse* there (0.94x vs 0.72x).

Other corrections, all now pinned (183 checks, was 158):

- "a single PORTER pass lowers ... 41.6% and 68.2%" (abstract, intro,
  Sec IV-D) --- those need **three** routes; single-pass is 35.8%/61.2%.
  Sec IV-C's protocol bullet and tab:shared's caption said "single-shot" too.
- "0.08x dSABRE's per-pass speed" compared dSABRE's *per-route* cost against
  PORTER's *three-route protocol*. True per-route gmean is **0.27x**.
- "selection gives the better route on ten ... search on fourteen" ---
  selection wins **4**, search 14, 6 tie.
- Cross-layout "8.7% for PORTER's" is the old single pass; it is **6.0%**
  for +R (the row tab:crosslayout actually shows), 4.7% for selection.
- Shared-layout prose quoted the old -39.6/-35.3; with selection it is
  -41.5/-37.7, **and dSABRE no longer leads at every scale** (PORTER takes
  64q). The inference survives and sharpens: three routes spent on horizons
  do not close the fixed-layout gap, five spent on f-b-f do.
- "ahead on both heavy-hex core graphs" (abstract/intro/conclusion) was
  unscoped --- true only under the fixed-layout control; under its own
  layout PORTER trails the star 122.3 vs 101.1.
- tab:heavyhex bolded 462 in the star-Multiplier row where 455 is lowest.
- `\author` said "Yongjian Xie", `\thanks` said "Y. Xing"; the
  acknowledgment said "the author" (singular) for four authors.
- Appendix header said "Appendices A--D"; it holds A--I.

**Determinism is now qualified, and it has to be.** The speculative horizons
share a *wall-clock* budget, so the protocol's output depends on machine
load: `horizon_results.json` has 360q/QPEexact falling back to L=16 at 2342
EPR (both speculative candidates hit `HorizonTimeout`), while
`scaleup_results_selection.json` has it at L=128 and **1224**. Sec IV-A now
says a single route is byte-identical and the *protocol* is reproducible
only up to that budget. Do not restore the unqualified claim.

**Still unreproducible from released data** (flagged, not fixed): Sec IV-G's
opening sweep over {4,...,1024}, the 17.2% oracle gap, Spearman -0.765 and
the 8.0% threshold-rule recovery. `bench_horizon.py` only routes the
best-of-3 candidates; no sweep harness or results file is released. Same
class as the deleted `tab:timedecomp` figures. The prose now says "in an
offline sweep" so the reader knows it is a separate measurement.

**Structure.** 14 -> 13 pages (body ends on 12; p13 is references), -686
prose words. Removed: the dSABRE corner-rule digression, the TeleSABRE
crash mechanism, the `DagFrontierSimulator` internals and the "4x against a
straightforward implementation" claim, the refinement free-slot-vector
diagnostic, the f_min in {4,6} sweep, the two paragraphs justifying why
both +R and +S are reported, and the star-row basis note. Deduplicated the
"differ in exactly one respect" thesis, the front-adjacency fact (stated
3x), the safe-but-not-complete guarantee (2x) and the AutoComm description
(2x); the Contributions block became a four-item list. Sec III-I
(complexity) moved to the appendix as **Appendix I**, and the five
supplementary tables that had been sitting unlabelled inside the action-mix
section got their own **Appendix H, "Supplementary Tables"** (the SWAP-count
section folded into it) --- which is what `\appTables` had always claimed to
point at. Appendix letters A--G are unchanged.

## Fixed-layout control extended to scale-up and heavy-hex (2026-08-28)

Both harnesses now run PORTER on **dSABRE's own SabreLayout candidates**,
one pass and refined (`sfc_on_dse_layout{,_refined}` in `bench_scaleup.py`;
`porter_on_dse{,_refined}` in `compare_heavyhex.py`). This is the control
that separates layout from routing, and it **splits by scale**:

| | dSABRE | PORTER+R own layout | PORTER+R on dSABRE's layout |
|---|---|---|---|
| heavy-hex ring (9) | 85.2 | 82.3 (0.97x) | **81.4 (0.96x)** |
| heavy-hex star (9) | 101.1 | fails 1 of 9 | **93.5 (0.93x)** |
| scale-up 100-360q (6) | 705.7 | 930.3 (1.32x) | 877.9 (**1.24x**) |

- **<= ~108 physical qubits the gap is the layout**: control it and match
  passes and PORTER+R wins both heavy-hex core graphs, including the star it
  cannot even complete under its own layout.
- **>= 150 physical qubits it is not**: 1.24x survives every control. On
  360q QFT dSABRE's layout is *worse* for PORTER than its own (3266 vs
  2822), so the mapping is not the binding constraint there. Untested
  hypothesis in the paper: the lookahead horizons
  (`teleport_lookahead_cx_count=50`, `dag_extended_max_layers=16`) are
  absolute and do not grow with core count K.
- Do NOT repeat the unqualified claim "the deficit is the layout, not the
  routing loop" — three places in `sfc.tex` now scope it by scale.

## Heavy-hex architectures (ring / star), added 2026-08-28 — in the paper as Sec. IV-I

`compare_heavyhex.py` -> `paper/heavyhex_results.json`. Four IBM 27-qubit
heavy-hex cores (108 physical) wired as a **ring** (4 links, all cores
degree 2) or a **star** (3 links, core 0 a hub every route crosses), on the
same nine-circuit 64q suite. This is dSABRE's own architecture-independence
experiment (`../dsabre/code/bench_heavyhex.py`).

`dsabre_architecture_to_porter_hardware()` derives PORTER's `Hardware`
**from dSABRE's native architecture object**, and `verify_topology_match`
asserts the two describe the identical device. dSABRE keeps routing on its
own object per the insertion-order rule below. **All 18 dSABRE values
reproduce its published `results_heavyhex{,_star}.json` exactly** — the
setup is validated, not merely plausible. All 17 completing PORTER streams
pass `verify_porter`.

| | dSABRE | PORTER | PORTER+R | PORTER on dSE layout |
|---|---|---|---|---|
| ring (n=9) | 85.2 | 96.0 (+12.7%) | **82.3 (-3.4%)** | 95.0 (+11.6%) |
| star (n=8 / 9) | 79.1 / 101.1 | 111.5 (+41.1%) | 89.8 (+13.6%) | 109.9 (+8.7%) |

- **The core graph matters far more than the core shape.** An irregular
  27-qubit tile (degree 1-3, diameter 12) costs PORTER nothing: on the ring
  PORTER+R *beats* dSABRE, 6W-2L-1T. The star is what hurts — PORTER+R
  goes 3W-4L-1T there.
- **PORTER does not complete star/multiplier** (1 of 18). It is a hard
  **local-SWAP livelock**, not a budget: gates retired freeze at 3226/13040
  and EPR freezes at 538 while SWAPs grow exactly 1 per step to 1M+
  iterations. Distinct from the teledata-only livelock, where EPR also grew.
- **The star deficit is the initial layout, not the router.** PORTER on
  *dSABRE's* layout completes all nine including multiplier, and does it at
  **462 against dSABRE's own 722**. `build_initial_layout` is core-graph
  blind: it reserves `f_min` uniformly, so on star/multiplier it starts at
  free=(2,2,13,27) — the hub pinned at the floor while a whole core sits
  empty.
- **A uniform reservation bump is NOT the fix** (tested, not shipped):
  `min_free_per_core` 2->4->6 on the star helps random (609->458), qnn
  (535->451) and qft (124->113) but hurts qaoa (473->605), qpeexact
  (162->199) and ghz (3->5), and multiplier still livelocks at every value.
  A fix would have to be hub-aware (reserve by core centrality/degree in the
  core graph), which is untested.

Landed in `sfc.tex` as `\subsection{Architecture Independence: Heavy-Hex
Cores}` (`sec:heavyhex`, `tab:heavyhex`), between the scale-up and
best-of-$\gamma$ subsections. Every number is pinned in
`paper/verify_paper_numbers.py` (including that the dSABRE column equals
dSABRE's published figures) and the table's LaTeX rows are re-parsed by
`paper/verify_tex_tables.py`. Three claims elsewhere in the paper were
reconciled with it: the failure-model section no longer calls pytket-dqc
"the one place the router" fails (it is the only *infeasibility* report;
the star livelock is stopped by `max_iterations`), the empirical-completeness
sentence now names the exception, and the abstract/intro "completes every
benchmark" is scoped to the three MQT-Bench suites.

## Keeping the dSABRE baseline current

`../dsabre/` is actively revised (TCAD-2026-0901). **Its router class was
renamed `dSABRE_BurstExt` -> `dSABRE_BFSExt` on 2026-08-07**; `dsabre_ext.py`
keeps `dSABRE_BurstExt` as a back-compatible alias to the same object, so the
old name still resolves. Our harness now imports the current name. Checked
2026-08-30: dSABRE HEAD is `cb5515b`, the revision our results were generated
from, with no commits since -- the baseline is current. Its code lives in
`code/` (moved from `paper/` in Aug 2026) and `bench_pytket_large.py` in
`code/investigations/` — both are on `compare_routers.py`'s `sys.path`.
Re-run `compare_routers.py` after any dSABRE change. The Aug-2026 rewrite
(shared extended set + safe mode) improved dSABRE on **all 18 instances**,
by up to 40% EPR and 97x time, and **flipped the own-protocol gmean at 64q
and 80q**. Never quote a dSABRE number from an older `compare_results.json`.

Two protocol rules the harness now encodes, both required for a fair
own-protocol comparison:

1. **Pass `deadlock_limit=max_backup_attempts=max_iterations=None`.** That is
   dSABRE's own convention; its only per-suite constant is
   `L_deadlock = 4*max(1,D_K)*(D_M+1)` (40 on arch A, 84 on H). In safe mode
   `max_backup_attempts` is overridden to `remaining+1`, so passing a number
   is inert; a *binding* `max_iterations` is the harmful one — it truncates
   the heuristic search and hands the remainder to `_safe_drain`, inflating
   EPR. The old hand-tuned 100/100/20000 came from the pre-safe-mode router.
2. **Net out pre-routing layout repair.** `compare_routers.dSE` subclasses
   `dSABRE_BurstExt` to record the first `_make_layout_safe` call per
   `route()` as `entry_repair_eprs`. That call runs in `route()`'s
   precondition block, before the clock starts and before any gate is
   considered, so it adjusts the *starting layout*, not the route — the same
   job PORTER's `_repair_full_cores` does for free. Later
   `_make_layout_safe` calls come from `_safe_route_gate` and are genuine
   routing cost, so only the first is excluded. Note it is nonzero even under
   own-protocol layouts, because `run_sabre_passes`' passes 2 and 3 start
   from whatever layout the previous pass left, and `tier1_floor=2` permits a
   core to end a pass at 1 free. dSABRE's own files are never modified.

## External-review packet, round 3 (2026-09-01)

`paper/review/` holds the artefacts for the Copilot/GPT-5.6 review round:
`paper_brief.md` (grounding), `resolved_findings.md` (what two prior rounds
already settled — the exclusion list), `prompt_A_technical.md`,
`prompt_B_editorial.md`, `prompt_C_delta.md`, and `README.md` with the loop
and the non-negotiable rules. Round boundary tagged `paper-round3-pre`.

**The protocol, in one line**: Copilot returns *structured findings*, never a
rewritten manuscript; Claude Code triages them against the verifiers before
touching a file, then patches in risk-ordered batches.

Three things about this repo shape the packet and are worth keeping:

1. **The claims ledger is already executable**, so the rubric tells the
   reviewer *not* to check arithmetic or table-to-text consistency — that is
   machine-verified — and to spend the attention on **whether a number
   supports the sentence built on it**. Triage rule that follows: a finding
   contradicting a pinned number is **presumptively wrong**; disproving a pin
   means showing the pin is wrong, not asserting a different value.
2. **This is round 3.** `responses_to_reviews.md` answers two rounds, so an
   unrestricted review re-surfaces answered items. `resolved_findings.md`
   lists the corrected errors, the narrowed claims, the structural decisions
   with their reasons, and the ten declared caveats — inviting the reviewer
   to argue a declaration is *inadequate* rather than undisclosed.
   **It is built from the current manuscript, not from
   `responses_to_reviews.md`, which is stale in places** (it still describes
   the Hop-wise ablation column and PORTER+S in IV-F3; both have since moved
   or been removed).
3. **Upload the PDFs, not the LaTeX** — a driver plus nine `\input`s gives
   unusable locations in the report. Compile `sfc.tex` before the appendix or
   its `xr` refs render as `??`.

Per-batch build chain, generator FIRST (see the trap noted above):
`gen_tables_selection.py --write` -> `verify_tex_tables.py` ->
`verify_paper_numbers.py` -> pdflatex both documents.

## The 360q QPEexact selected result sits ~0.5 s inside its budget (2026-09-01)

Found while confirming the round-3 `A06` re-run. **`tab:scaleup`'s $1{,}224$
for 360q QPEexact does not reproduce on this machine**; the protocol falls
back to the configured horizon and $2{,}342$, which turns the suite from
$0.72\times$/6-of-6 into $0.80\times$/5-of-6 -- and $0.72\times$ is in the
abstract, intro, V-D and the conclusion.

Diagnosed, not worked around. Each speculative candidate gets
`max(SPECULATIVE_MIN_SECONDS, ceil(SPECULATIVE_TIME_FACTOR * t_first))`
seconds, derived from the **first route's own wall time**. On this instance
that share is 14 s and the L=128 route -- which reaches exactly 1224, so the
released number is real -- costs 14.4-14.9 s. **It misses by under a second.**

**Note the perversity: a slower machine buys a larger share**, so the released
value is likelier to reproduce on slower hardware, not faster.

- Released `paper/probe_horizon_budget.py` measures all three quantities
  (default-horizon route, derived share, L=128 route), following the
  `probe_front_limit.py` precedent. IV-C names the instance and cites it.
- **Do not raise `SPECULATIVE_TIME_FACTOR` to "fix" this** -- it would change
  every selected route in the paper and require re-running all three suites.
- The **fixed-horizon** leg of `scaleup_results.json` reproduces *exactly*
  (all six values, gmean 1026.5), so the V-D fixed-vs-selected comparison
  (1026.5/1.45x/0-of-6 against 507.7/0.72x/6-of-6) is solid on both ends.

**Protocol audit passed alongside** (2026-09-01): every PORTER leg in all
three released selection files follows `tab:budgets`. 179 recorded
`chosen_horizon` values -- `sfc`, `sfc_shared`, `sfc_pytket`,
`sfc_on_dse_layout`, `porter`, `porter_on_dse` and every `*_refined` /
`*_search` leg -- are each a member of the 3-element set `select_horizons`
derives from that circuit's own density, and $|H|=3$ on all 48 instances.
`run_sfc_sabre_layout` loops 3 candidate layouts x 3 horizons = the 9 routes
`tab:budgets` claims. Script: scratchpad `audit_horizons.py`; worth
re-running after any change to the horizon constants.


## `dag_front_limit` removed (2026-09-01)

The front cap (96 gates) is **deleted from `RouterConfig` and from
`_current_dag_front`**, and from Algorithm 1, III-D and the appendix
parameter table. `paper/probe_front_limit.py` is deleted; the
`dag_front_limit` pin is out of `verify_paper_numbers.py`.

**It never changed a routing decision.** Measured capped vs uncapped at a
fixed horizon on all six scale-up instances: EPR, SWAPs, depth,
intercore depth and `seeded_tie_break_count` identical everywhere. On the
three QFT instances the op stream is **byte-identical** (max front 8). On
the three QPEexact instances, where the front reaches $n$, the stream is a
**permutation**: same multiset of ops, first divergence at index exactly
96, and every differing op a **single-qubit gate**. Both arms pass
`verify_porter`. Cost of removal: **1.03x wall clock**.

**No released number changed.** Re-verified after the removal: all 24
main-suite and all 6 scale-up single-pass EPRs reproduce exactly, 60/60
fuzz trials pass. The released `*_results*.json` are untouched and still
correct.

**Watch out: `_current_dag_front` still sorts by gid**, and that sort is
now the only thing making the front order canonical -- it is what keeps
the emitted stream deterministic, not a leftover of the truncation. Do
not "optimise" it into a raw set iteration.

**Found alongside, and NOT fixed: a second instance sits inside a second
of its speculative budget.** IV-C discloses only 360q QPEexact. Measured
slack (budget $-$ the $L{=}128$ route's own time):

| instance | t(L=16) | budget | t(L=128) | slack |
|---|---|---|---|---|
| **200q QFT** | 1.6 s | 7 s | 6.6 s | **+0.4 s** |
| 200q QPEexact | 2.2 s | 9 s | 5.4 s | +3.6 s |
| 360q QFT | 3.9 s | 16 s | 12.7 s | +3.3 s |
| 360q QPEexact | 4.2 s | 17 s | 14.8 s | +2.2 s |

200q QFT flips $579 \leftrightarrow 1128$ across repeats (2 of 3 trials
gave 579), so `tab:scaleup`'s $579$ is as fragile as the $1{,}224$ IV-C
flags. **This is unrelated to the cap** -- the cap never bound there (max
front 8) and its timings are identical in both arms.

**`paper/responses_to_reviews.md` s1.1 is now stale**: it tells the
reviewer that `probe_front_limit.py` was released. The cap's removal
supersedes that answer.


## The last component of the selection key is vestigial, and its sign is wrong (2026-09-01)

`_remote_plan_selection_key` (router.py:1293) is
`(-total, not ready, prep, rank(kind), cap, -lookahead_gain, stable_id)`.
Instrumented over **2,714 plan rankings** on 7 circuits (25q ae/random,
64q ae/qft/qaoa/qpeexact, 80q qft), counting the first index at which the
winner and runner-up differ:

| deciding component | count | share |
|---|---|---|
| `-total` | 1,995 | 73.5% |
| `prep` | 377 | 13.9% |
| `not ready` | 96 | 3.5% |
| `rank` | 78 | 2.9% |
| `cap` | 19 | 0.7% |
| **`-lookahead`** | **1** | **0.04%** |
| `stable_id` | 148 | 5.5% |

- **Neutralising `-lookahead` changes the selected plan in 0 of 2,714
  rankings** -- including the one it decides, where the tie fell through
  to `stable_id`, which picked the same plan. The arbitrary identifier
  does **148x** the work of the component the paper describes as a design
  choice.
- **The cause is structural**: `total = direct_gain + lookahead_gain`
  (router.py:1326), so lookahead is a *summand of* component 0. Any
  difference in it moves `total` first and the comparison ends at index 0.
  It is not degenerate -- `lookahead_gain` varies across candidates in
  2,336 of 2,714 rankings (86%) -- it just never gets to matter. Reaching
  index 5 needs direct and latent gain to trade in exactly compensating
  amounts *and* a tie on readiness, prep, kind and capacity.
- **The sign is backwards** (author's observation, 2026-09-01). At equal
  `total`, preferring the larger `lookahead_gain` is preferring the
  *smaller* `direct_gain` -- deferring certain progress in favour of
  discounted progress. To break the tie toward surer progress it should
  sort on `-direct_gain`. Noted as future work in VI-A alongside the
  comparator-currency item, which is the same mismatch; **not changed in
  the code**, since touching the key means re-deriving every released
  number (the front-cap removal is the template for that).
- **III-E still presents the six components as equally load-bearing**
  ("The order is the design, so we take the components in turn"). Softening
  the last one's billing was offered and not taken; if a reviewer asks why
  the key has a component that never fires, this is the answer.

Script: scratchpad `key_components.py`. **Trap it hit first time**: the
probe re-wrapped `PorterRouter._choose_best_remote_plan` once per circuit
without restoring, so wrappers nested and early circuits' counters kept
incrementing during later circuits -- pooled totals came out 4.6x too
high (12,599 vs 2,714). Restore the pristine method before each wrap.


## Lookahead horizon: the walk bound landed, the gate budget did not (2026-09-02)

Two changes were tried against `_collect_teleport_post_latent_lookahead_gates`
(router.py:1559). **The first shipped, the second is refuted.**

### What the collector actually does -- read this before touching it

It peels **whole DAG layers** and re-sorts the entire frontier each layer, so
cost is `O(L x |frontier| log|frontier|)` **whether or not the moving qubit
has anything left to find**. A qubit has at most one front gate at a time, so
`|out| <= L`.

**The discount floors at layer 7.** `layer_weight = max(0.5, 0.9 * 0.9^(L-1))`
hits the `teleport_lookahead_weight_floor=0.5` at layer 7 and stays there, so
a gate found at layer 8 and one at layer 128 contribute **identically**.
Past layer 7 the horizon does not discount at all.

Measured (`selection=False`, single pass):

| | mean gates found | walks finding nothing | found beyond layer 16 |
|---|---|---|---|
| 64q QFT, L=16 | 2.41 | 28% | 0% |
| 64q QFT, L=128 | **34.69** | 7% | **92%** |
| 200q QFT, L=16 | 2.18 | 58% | 0% |
| 200q QFT, L=128 | **23.74** | 25% | **92%** |

Also: at 64q QFT, L=128 makes **434,417** collector calls against 3,830 at
L=16 (113x) because the deeper horizon changes the *trajectory* into far more
router iterations; at 200q QFT it goes the other way (10,468 vs 16,744). That
asymmetry -- not per-call cost -- is why L=128 times out on some circuits and
runs fast on others.

### SHIPPED: bound the walk by the moving qubit's remaining CXs

`RouterState.active_cx_by_qubit` is a per-qubit count of active CXs, built in
`_initialize_dag` and decremented at the **single** retirement point
`_remove_gate_ids`. The collector now uses
`cap = min(max_cx, active_cx_by_qubit[moving_qubit])`, which returns
immediately for a finished qubit line and stops peeling layers that provably
cannot yield another gate.

**Output-preserving by construction** -- only active CXs of the moving qubit
are collectable and there are exactly that many. Verified: op-stream SHA,
`seeded_tie_break_count`, EPR, SWAPs, depth and op count **identical on 12
routes** (including L=128); 60/60 fuzz; all 24 main + 6 scale-up single-pass
EPRs reproduce exactly; **0 desyncs in 6,259 in-flight counter checks** against
a fresh scan of `dag_active`, draining to zero at the end.

Payoff is **1.11x** overall, 1.26x on 200q QFT at L=128. It does **NOT** buy
back timed-out horizons: `max_cx = teleport_lookahead_cx_count = 50` was
already the binding cap on dense circuits, so 0 of 9 probed timeouts were
recovered before the run was stopped. Do not claim otherwise.

### REFUTED: replacing the layer budget with a per-qubit gate budget

**No code needed to test this** -- `teleport_lookahead_cx_count` *is* the gate
budget, merely dominated by `dag_extended_max_layers`. Setting
`RouterConfig(teleport_lookahead_cx_count=k, dag_extended_max_layers=512)`
gives a per-qubit horizon directly. (The shipped walk bound is what makes it
affordable; without it an exhausted qubit walks 512 layers.)

Swept k in {16,24,32,48,64} on the six 80q/200q/360q instances:

| configuration | routes | gmean | vs best-L | completes |
|---|---|---|---|---|
| fixed L=16 | 1 | 1152.9 | +95% | 6/6 |
| **shipped best-of-3 L** | 3 | **618.8** | **+5%** | 6/6 |
| gate budget k=16 | 1 | 925.6 | +56% | 6/6 |
| gate budget k=24 | 1 | 856.4 | +45% | 6/6 |
| best k per instance (oracle) | 5 | 650.5 | +10% | 6/6 |
| best L per instance (oracle) | 8 | 592.0 | -- | 6/6 |

The best k **loses to the best L on all six** (+1% to +24%), an *oracle* over
k is beaten by the shipped 3-route protocol, and k >= 32 times out on half the
instances. Also worse at 25q AE (75 vs 65) and 64q QFT (268 vs 262).

**Why, and this is the durable lesson: the layer bound is a *relevance
window*, not just a counter.** The flat weight past layer 7 makes it look like
pure counting, but L also *excludes* gates beyond it outright. A gate budget
deletes that window and counts the first k gates however distant -- at 360q a
qubit's 48th future CX can be 900 layers out, and scoring it at half weight is
a claim about a layout that will be unrecognisable by then. **`N_tp` inert and
`L_tp` live is the correct assignment, not an accident** -- if a reviewer asks
why the paper has a second lookahead parameter that never binds, this is the
answer.

Scripts: scratchpad `determinism.py` (SHA + tie-count harness, reusable for any
refactor), `phase2.py`, `recover.py`.


## ADOPTED: one fixed four-value horizon set; the density branch is retired (2026-09-03)

`PORTER_HORIZONS = (4, 8, 16, 128)`, applied to every circuit.
`PORTER_HORIZONS_DENSE` and `DENSE_INTERACTION_THRESHOLD` are **deleted**;
`select_horizons` still returns `(horizons, density)` but the density is
recorded as a diagnostic and selects nothing, and
`circuit_interaction_density` is kept because IV-E still discusses it.

**Nothing moved on the main suite.** All 24 instances re-run on all three
protocols: `sfc`, `sfc_refined` and `sfc_search` are **EPR-identical**, 175.0 /
163.1 / 160.1. Only time moved: 165 -> 247 s, 386 -> 475 s, 796 -> 921 s
(1.50x / 1.23x / 1.16x). Scale-up is unchanged in EPR too.

**Five heavy-hex star cells moved** (`porter` random 547->510, qaoa 405->401;
`porter_on_dse` qft 108->98, random 478->466, qaoa 245->243), so the star
own-protocol gmean is **121.2** (was 122.3) and on dSABRE's layouts **97.1**
(was 98.5). Ring is unchanged.

**The wall-clock guard now YIELDS to the work budget.** Both were active, so
the protocol was still machine-dependent and IV-C's determinism sentence was
false. `run_horizon_selection` passes the clock only when
`SPECULATIVE_WORK_FACTOR = 0`. Cost of that fix: 64q QFT's
`sfc_on_dse_layout` 238 -> 253, a candidate the clock admitted and the
deterministic budget rejects. **Do not re-enable both at once.**

**V-B's row-spread bound moved again**: block (b)'s widest row is now
$3.47\%$, so prose and pin say $3.5\%$ (was 3.2%, was 3%). That bound has
caught every one of these re-runs -- keep it.

**Highlighting is round 5**, baselined at `ffa9b25`, and
`paper/remark_highlights.py` now refuses to mark **any line carrying an
unescaped `&`**. The previous rule only skipped rows ending in `\\`, so a row
continued across source lines got wrapped and broke the build with
`Missing } inserted`. Marks are prose-only by the manuscript's own convention,
and `verify_tex_tables.py` parses table rows with regexes a wrapper would break.

## The density branch can be replaced by ONE four-value set (2026-09-03)

The author's objection: selecting three horizons by $\rho$ is a fitted rule with
no justification beyond the corpus. Measured every horizon in
{4,8,16,32,48,64,128} at the shipped schedule on all 48 instances
(`paper/horizon_sweep/hz_four.py` -> `four_horizon_cells.jsonl`), then every
4-subset containing 16, each candidate budgeted the way the protocol budgets it.

**Three routes are not enough; four are.** The best three-set is `+0.3%` against
the branch at 1.31x its time. Every one of the top four 4-sets matches or beats
it:

| four-value set | main 24 | vs branch | all 48 | time (main) |
|---|---|---|---|---|
| {4,16,48,128} | 173.3 | -0.9% | 159.1 (-0.7%) | 2.12x |
| {4,16,64,128} | 173.9 | -0.6% | 158.6 (**-1.0%**) | 2.52x |
| {4,16,32,128} | 174.8 | -0.1% | 158.9 (-0.8%) | 1.95x |
| **{4,8,16,128}** | **175.0 (parity)** | **0.0%** | 159.9 (-0.2%) | **1.58x** |

- **{4,8,16,128} is the union of the two sets the branch chooses between**, so
  adopting it introduces NO horizon value the paper does not already use, no
  threshold and no new fitted quantity. The sets that beat it on EPR do so by
  adding 32/48/64, each a new fitted value -- the same objection one level down.
- **Under +R it is identical to the shipped protocol on all 24 instances**
  (0 better, 0 worse, 24 tied, 163.1 either way) at 1.29x the time: refinement
  washes the horizon choice out entirely. {4,16,64,128} trades two wins for two
  losses for 0.6 EPR at 1.7x.
- Price of removing $\rho$: **1.58x compile time single-pass, 1.29x for +R**.
  PORTER would go 0.90x -> ~1.4x dSABRE, so V-F's compile-time claim becomes
  four routes against nine rather than a wall-clock advantage.
- **NOT LANDED.** Constants, re-runs and IV-E's rewrite await the author's call.

**The (schedule, horizon) portfolio is appendix-only, by the author's decision**
("I will not adopt the 3x2"). Kept for the record in
`report_schedule_portfolio.md` / `portfolio_refined.jsonl`: as a single pass the
six-pair set is -0.9% on the main suite for 3.74x but **-10.8% on heavy-hex
star and -6.8% on scale-up with no regressions**; as +R's base it reaches 157.4
and turns 64q from 1.07x into **1.00x** dSABRE, at 7.9x dSABRE's time.

## The refined and search legs were stale too; re-run (2026-09-03)

**`rerun_porter_legs.py` skips every `*_refined` leg on a rationale that does
not cover the selection key.** Its docstring says refinement keeps its own
unselected horizon, which is true of the 2026-08-29 horizon change and false of
a change to the key, which every route uses. Checked: 25q Random's
`sfc_refined` read 383 and produced 389 live. `sfc_search` was stale the same
way. **Do not accept that rationale for any future router change.**

Re-run `sfc_refined`, `sfc_on_dse_layout_refined`, `sfc_search` and
`sfc_selection_and_search` for the 24 main instances and overlaid.

| protocol | routes | EPR (24) | time |
|---|---|---|---|
| dSABRE | 9 | 171.9 | 182 s |
| PORTER | 3 | 175.0 | 165 s |
| PORTER+R | 7 | 163.0 -> **163.1** | 1468 s -> **386 s** |
| PORTER+S | 12 | 159.1 -> **160.1** | 4267 s -> **796 s** |

- **The stall guard is what collapsed those times.** PORTER+R's released 8.9x
  over PORTER was one instance: 80q QPEexact took **908.7 s of the 1468**, one
  refinement pass oscillating until the 900 s per-pass guard fired. With the
  stall guard it is **13.9 s**, and +R is now **2.3x** PORTER, matching 7/3 on
  routes. Excluding the top three instances the released figure was already
  2.2x, so the 8.9x was never the protocol.
- EPR moved on five +R cells (25q Random 383->389, 64q Random 737->732,
  80q AE 299->277, 80q Random 11040->11013, 80q Multiplier 2132->2313) and the
  +R record against dSABRE went **11W/11L/2T -> 11W/10L/3T**.
- **Appendix J changed materially**: +S improves on **6** instances now, not
  ten, ties on 18, and costs **2.1x** +R rather than 2.9x. 80q AE's 62x
  becomes 4x and returns nothing, since +R already reaches 277.
- **STILL STALE, AND THE ONE OUTSTANDING ITEM IN THE REPO: `sfc_shared`,
  `sfc_pytket` and their `_refined` variants.** They are now stale for TWO
  reasons -- the three-term selection key (`df034da`) and the four-value horizon
  set (`abb845b`) -- and cannot be rebuilt from the released files, because they
  need TeleSABRE's and pytket-dqc's layouts and only the EPR counts are stored,
  not the layouts. Closing this needs a full `compare_routers.py` run, which
  also re-runs the external baselines. **`tab:shared` (Table III) and
  Appendix C read these legs**, so until that run happens Table III's PORTER
  columns describe a protocol the code no longer implements. Every other leg in
  every released file reproduces from HEAD.

## The four cost optimisations, measured on one basis (2026-09-03)

All four toggled independently, 48 instances, shipped 3-route protocol, one
process, so the times compare with each other rather than with numbers taken
under different load (`paper/horizon_sweep/hz_ablate_opt.py` ->
`optimisation_ablation.jsonl`, `report_optimisations.md`). **Every
configuration emits the identical op stream on 48/48**, so EPR is constant at
163.7 (365.6 over the 38 non-trivial) and only time moves.

| configuration | time | vs shipped |
|---|---|---|
| shipped (all four) | 293.5 s | 1.00x |
| no walk bound (per route) | 299.1 s | 1.02x |
| no work budget (protocol) | 302.2 s | 1.03x |
| no frontier-scan fix (per route) | 309.5 s | 1.05x |
| **no stall guard (protocol)** | **451.7 s** | **1.54x** |
| none of the four | 501.1 s | 1.71x |

- **The stall guard is almost the whole win**; the other three are 2-5% each.
  Together they take 41% off the protocol.
- The two *per-route* optimisations are the walk bound and the frontier scan.
  Both are output-preserving; neither is worth more than 5% on its own, because
  the collector's cost is the layer peeling, not the scan.
- **Do not quote the isolated figures measured earlier** (walk bound 1.11x,
  frontier scan 1.09x): those came from selected fixed-horizon routes under
  different load. On the shipped protocol over all 48 they are 1.02x and 1.05x.

## The speculative budget is deterministic now; the portfolio is priced (2026-09-03)

**SHIPPED: `SPECULATIVE_WORK_FACTOR = 7.0` in `compile_porter.py`.** A
speculative horizon is bounded by the DAG layers its lookahead walk may peel --
at most 7x the count the configured horizon's route produced -- instead of a
share of wall-clock time. New: `RouterConfig.max_lookahead_layers` (0 = off) and
`RouterStats.lookahead_layers_peeled`, incremented once per peeled layer in the
collector. **Validated on all 48 instances: op-stream SHA, EPR, SWAPs, depth,
tie count AND selected horizon identical 48/48, protocol wall time 0.88x.**
Both paper verifiers pass and the released numbers still reproduce.

- **Why a work counter and not an iteration cap**: the iteration cap is already
  refuted here (a deep peel makes each iteration ~400x costlier). Peeled layers
  rise with the horizon as the run time does, so the same factor transfers.
- **The factor is load-bearing and was calibrated twice.** Against the SHIPPED
  counter, every candidate that *wins* its instance costs at most **6.47x**
  (64q Multiplier 6.05, 360q QPEexact 6.24, 80q Multiplier 6.47) while the
  cheapest candidate that wins nothing costs **7.95x** -- a real gap, and 7
  sits in it. **6x is too tight** and drops all three winners (360q QPEexact by
  91%). Fitted on this corpus; too low costs EPR, not correctness, since the
  configured horizon runs unguarded and wins ties.
- **TRAP that cost a wrong calibration.** The offline probe counted
  `DagFrontierSimulator.remove_gate_ids` globally, which includes the
  latent-direct closure; the shipped counter counts only the post-latent
  lookahead walk. The closure does not scale with L, so the probe's ratios are
  **damped** and its 6x looked safe when it was not. Live validation caught it.
  **Calibrate against the counter you ship, not a probe's superset.**
- IV-C's reproducibility sentence now states the work bound; the wall-clock
  caveat is gone.

**The 3x3 portfolio is priced, and it is dearer than the frozen grid implied.**
Measured head to head against HEAD's router, same process, 38 non-trivial
instances, each portfolio budgeted by the same 4x rule the protocol uses:

| portfolio | routes | gmean | vs shipped | budgeted time |
|---|---|---|---|---|
| shipped density branch | 3 | 365.6 | --- | 1.00x |
| `{4,16,128}` at w=0.5 (single horizon set) | 3 | 366.7 | **+0.3%** | **1.31x** |
| `{16,128}` x `{.5,.25}` | 4 | 351.8 | -3.8% | 2.71x |
| `{4,16,128}` x `{.5,.25}` | 6 | 345.4 | -5.5% | 3.08x |
| `{16,128}` x `{.5,.25,0}` | 6 | 344.9 | -5.7% | 4.07x |
| **full 3x3** | 9 | 341.4 | **-6.6%** | **4.61x** |

- **This REVISES the earlier advice to replace the rho branch with one horizon
  set.** On the frozen grid `{4,16,128}` looked like parity EPR with tighter
  tails; measured head to head with budgets and the stall guard it is
  **+0.3% EPR for 1.31x the time**. The density branch is doing real work --
  **as a compile-time optimisation**, avoiding L=128 on dense circuits -- not as
  an EPR mechanism. Removing rho is not free.
- The earlier "1.98x" for the 3x3 was an artefact of comparing grid-summed times
  where the baseline still contained 300 s timeouts the stall guard now avoids.
  The guard made the *baseline* much cheaper, which raises the relative price of
  any larger portfolio.

## Released results re-run against HEAD's router (2026-09-03)

The three-term selection key (`df034da`) and the stall guard (`01b8be8`) left
the released `*_results*.json` disagreeing with the code. Closed by re-running
**only PORTER's legs** and overlaying them on the released files, so every
non-PORTER leg is byte-identical.

**`rerun_porter_legs.py` has two traps that cost a wasted run:**
1. **Its main section silently skips everything.** It prints `[key] cached` and
   carries the old values whenever `compare_results_selection.json` already has
   all three PORTER legs -- which it always does. The first full re-run
   therefore left the main suite untouched, and the diff looked reassuringly
   small for the wrong reason.
2. **Its main section uses the RETIRED layout family.** Line 281 calls
   `cr.sabre_two_corner_layout`; the 2026-08-31 decision moved dSABRE to its own
   `cr.dsabre_layout_candidates`, which the scaleup section (line 75) already
   uses. Re-running main through the script as written would regress
   `sfc_on_dse_layout` to a family the paper no longer reports.
3. **Its scaleup/heavyhex sections read the PRE-selection file as their base**,
   so they revert any later leg. The run reverted dSABRE's scale-up time from
   the current $15.4$ s to the pre-2026-08-31 $41.1$ s. Always overlay PORTER's
   legs onto the released file rather than adopting the script's output whole.

**What actually moved: 16 leg values, and heavy-hex not at all.**

| | released | re-run |
|---|---|---|
| 25q Random `sfc` | 401 | **393** |
| 80q Multiplier `sfc` | 2411 | **2486** |
| 360q QFT `sfc` | 1156 | **1170** |
| main-24 `sfc` gmean | 174.9 | **175.0** |
| scale-up `sfc` gmean | 507.7 | **508.7** |
| scale-up `sfc_on_dse_layout` gmean | 678.9 | **611.9** (ratio $0.96\to0.87$) |
| scale-up complete cost | 8.4 s, $0.54\times$ | **6.9 s, $0.45\times$** |
| heavy-hex ring / star | 86.1 / 122.3 | **unchanged** |

`sfc_selection_and_search` is now populated on the six scale-up rows (it was
`None`); no table reads it, and the paper still reports no scale-up $+$S leg.

**One qualitative claim flipped.** V-B's "the two land within $3\%$ on every
row" is false after the re-run: block \emph{(b)}'s dSABRE-layout row is now
$3.12\%$. Prose and pin both say $3.2\%$. **The `within 3%` pin was the only
thing that caught it** -- every other consequence was a number, this one was a
bound.

37 pins moved in `verify_paper_numbers.py`; both verifiers pass, the generator
is idempotent, and both documents build at 15 and 8 pages with zero errors.

## Adaptive-horizon programme evaluated; weight floor is load-bearing (2026-09-03)

The vault's `porter_adaptive_horizon_experiment_instructions.md` (a 7-phase
programme: sweep validation, portfolio search, architecture-aware selection,
incremental collector + plan-level traces, progressive stopping, calibrated
stopping, weight-floor factorial) was evaluated and the affordable phases
run. Full write-up: vault `porter_adaptive_horizon_experiment_evaluation.md`.
Data: **`paper/horizon_sweep/`** (uncommitted) -- 1,248 single forward passes
(`selection=False`, own layout, 300 s guard, all replay-verified): 48 instances
x {4,8,16,32,64,128} x four weight schedules, plus {48,256} for the shipped
one; `README.md`, `MANIFEST.txt`, scripts and three generated reports.
Nothing in it is read by the verifiers; released numbers are untouched.

- **`teleport_lookahead_weight_floor=0.5` is load-bearing.** `w_min=0` costs
  **+14.9%** EPR under the 3-route rule and **+62% on the scale-up series
  (0W/6L)** -- with a true decay the weight at layer 30 is 0.04, so L=128
  collapses to ~L=32 and the deep-horizon wins vanish. Flat weight (no
  decay, `w_min=0.9`) costs +7.8%. `w_min=0.25` is parity overall
  (wins heavy-hex/scale-up 3-6%, loses 25q +14.5%, 80q +8.1%). **Keep
  0.5 / gamma 0.9.** Also: `w_min=0` halves horizon spread and cuts timeouts
  15 -> 2 and *still* loses -- a smoother score is a worse route, and deep-L
  non-convergence is a property of the score, not collector cost.
- **A single global set {4,16,128} matches the density rule**: 363.1 vs 365.4
  in-sample, parity leave-one-suite-out, p90 regret 11% vs 21%. The density
  split's whole net effect is 80q QNN (wins at L=4) against heavy-hex star QNN
  (loses, wants 128), which cancel; the sparse set alone scores exactly 365.4.
  Adopting it would retire the in-sample-fitted rule IV-E declares, but moves
  8/48 selected results (star QNN -29%, 64q QAOA +10%) -> author's call,
  needs every selected leg re-run. 4th candidate (64): -2.1% for +33% routes.
- **K/D scaling rules fail** (`L=clip(round(c*K))` etc.: median held-out
  regret 19-35%, worse than fixed 16). Ring and star share K=4, D=2 and
  differ in best L on 5/7 shared circuits; only one star family exists, so
  hub-aware rules are unvalidatable here. Refitting even the 3-parameter
  density form out-of-sample (375.8) is worse than a fixed global set (366.5).
- **Phases 3-5 (progressive / plan-level lookahead) not built, by evidence**:
  their "deep reference winner" is the optimum on 9/38 instances (median
  regret 20.7%, max 111%); L=256 vs 128 is 1 better / 8 worse / 5 tied.
- Sweep bookkeeping fixed: 348 routes (30x8 + 18x6), not 288; fixed-16
  statistics are over 37 because star/Multiplier livelocks at L=16.
  Best-of-assigned-set from the sweep reproduces the released protocol exactly
  (174.9 / 507.7 / 86.1 / 122.3).
- **Test 1 (same day): slow decay with no floor is REFUTED as a way to remove
  the horizon parameter, but the weight schedule is a richer portfolio axis
  than the horizon.** Three arms `w_min=0` x gamma {0.95,0.97,0.99} over
  {4..256}, 1,008 routes. No single slow route matches the shipped 3-route
  rule (best that completes all 38: `slow95@L64`, **+20.3%**); EPR does **not**
  go flat in L (spread 1.43/1.46/1.71 vs base 1.64 -- gamma=0.99 is *worse*);
  a portfolio is still needed inside each slow arm. Only gamma=0.99 recovers
  scale-up (+2.9%), and that is the arm that most resembles a floor -- **the
  sharp inclusion boundary is the mechanism, not a stand-in for one**.
  - **The actionable result: a 4th route at a DIFFERENT SCHEDULE beats a 4th or
    5th HORIZON.** Oracle over 7 schedules x 7 horizons is **-11.0%** against
    the shipped rule where a horizon oracle is only -3.5%, and **all seven
    schedules win somewhere** (base 10, slow99 8, floor25 6, floor0 4,
    slow95 4, flat 3, slow97 3). Adding one route at **`w_min=0.25, L=128`**
    gives **-4.8%, 12W/0L** (losses impossible: it is a portfolio) for 1.39x
    the wall time, against -2.1% for a 4th horizon and -3.1% for a 5th.
    **Held out**: leave-one-family-out -4.8% (all 7 folds pick the same route),
    leave-one-suite-out -3.7% (5 of 6 folds; scale-up picks `slow99@L256`).
  - Against dSABRE under each own protocol it lands where PORTER is weakest:
    main-24 1.02x -> **1.01x**, heavy-hex ring 1.01x -> **0.96x (a flip)**,
    star 1.21x -> **1.11x**, scale-up 0.72x -> **0.67x**. Twelve instances
    improve: star QPEexact -27.2%, ring QPEexact -28.6%, star AE -20.8%,
    200q QFT -22.8%, 80q QFT -14.6%.
  - **Not shipped.** Every figure is a single forward pass at a fixed
    (schedule, horizon); shipping means extending the speculative time budget
    to a second axis and re-running every released leg, and the interaction
    with backward refinement is untested. Next step is a joint
    (schedule, horizon) portfolio study at budgets 3/4/5, not more schedule
    search -- the axes are clearly not independent.
- **Replacing the rho branch with a single set (asked 2026-09-03).** A
  horizon-only single set is not enough: {4,16,128} is -0.6% in-sample but
  **+0.3%/+1.0% held out**, and even {4,16,32,64,128} (5 routes) only reaches
  -1.0%/-2.0%. Crossing the two axes works. **Recommended: the full 3x3
  crossing {4,16,128} x w_min {0.5,0.25,0}, 9 routes** -- `-8.1%` gmean,
  **21 better / 0 worse over all 48** (it strictly dominates the branch),
  1.98x the 3-route wall time, and vs dSABRE main-24 **0.99x**, scale-up
  **0.67x**, ring **0.93x**, star **1.04x** (from 1.21x). Nine routes is
  **exactly dSABRE's budget**, which buys a matched-budget framing the paper
  cannot currently make. Nothing in the shape is postselected -- only the axis
  ranges, and {4,16,128} was independently the best global 3-set.
  - The 6-route subsets are NOT loss-free: dropping the zero-floor row costs
    64q QAOA +10.2%, dropping L=4 costs 80q QNN +14.5%. `{4,16,128} x
    {0.5,0.25}` (6 routes) is the fallback: -6.4%, 16W/2L, worst +10.2%, 1.65x.
  - Caveat: figures are single fixed-pair forward passes under a flat 300 s
    guard, so 1.98x is idealised -- at 9 routes the speculative wall-clock
    budget needs redesigning, not scaling, and compile time would go from
    0.91x dSABRE to ~1.8x. Interaction with +R untested.
  - Search: `paper/horizon_sweep/hz_joint.py` -> `report_single_set.md`.
- **Five questions settled before the portfolio decision (2026-09-03).** Probes
  released as `paper/horizon_sweep/hz_probe.py`, `hz_timeout.py`, `hz_stall.py`;
  reports `report_mechanism.md`, `report_earlyexit.md`, `report_gamma.md`,
  `report_timeout.md`, `report_stall.md`.
  - **(Q1) III-D's plan tuple under-determines 15.6% of plans.** Instrumented:
    7,710 plans -> only 6,507 distinct `(pi, G(p), dir, c_src, c_dst, Pi(p))`
    keys; **1,203 collisions, all TeleData**. Cause: `G(p)` is EMPTY for a
    TeleData, so the tuple names no gate, and `dir` is defined relative to the
    seed gate it therefore does not identify -- two teleports moving different
    qubits between the same core pair are identical tuples. Also **`dir` is
    never read** (write-only metadata) and **`Pi(p)` is a function of
    (c_src,c_dst)** since `Core.ports` has one port per neighbour. Suggested
    tuple: `(pi, g, G(p), q_move, c_src, c_dst, mode)` = `plan_id()`; `mode`
    matters because `router.py` branches on it in three places.
  - **(Q2) gamma is a weak knob; keep 0.90.** At the shipped floor gamma only
    sets WHERE the floor bites (layer 5/7/14/59 for 0.85/0.90/0.95/0.99).
    3 arms x 288 cells: vs 0.90 the 3-route rule gives **+0.8% / +2.8% / +2.7%**
    for 0.85/0.95/0.99 and the horizon oracle **-0.1% / +2.4% / +2.9%**. No
    setting beats 0.90; only 0.85 ties it (13W/13L). **An order of magnitude
    weaker than the floor** (3.4% max vs 62%). Sign flips with horizon: at L=16
    faster decay wins monotonically (401.6/415.8/426.3/429.0), at L=128 0.90 is
    best. 0.95 helps only completion at L=128 (30/38 vs 27/38). At L=4 three
    arms give IDENTICAL gmeans -- ranking is insensitive to the weight profile
    at shallow horizons.
  - **(Q3) exact early exit exists but prunes little; the cost is the walk.**
    A route that never stops on the LAYER BUDGET proves every deeper horizon is
    byte-identical (`cap` and `dag`, the other two stop reasons, cannot be
    relieved by a larger L). Fires on **all 5 graphstate instances (0%
    budget-bound)** and nothing else; **GHZ is not caught** (10-25%
    budget-bound though horizon-invariant), so it is sound but not complete.
    Corpus median 88% budget-bound. **The collector is 68% of route time at
    L=128.** Two wins: (i) the inner loop's `sorted(dag.frontier)` is
    unnecessary -- a qubit has at most one frontier gate, so the sort cannot
    change what is found; dropping it is **1.09x, byte-identical on 7
    instances**; (ii) 12-14 walks run per decision and **48% re-walk a qubit
    already walked in that decision**, so within-decision sharing caps at
    ~1.5x, ~1.6x combined (untested).
  - **(Q4) timeouts are FROZEN routes, not slow ones.** 7 timed-out cells
    re-run at 900s (3x): **7/7 froze, 0 completed**. Gate retirement stops after
    a median of **6 s** and the router spins for the remaining ~99% of the
    guard with EPR/SWAPs still climbing. More time never helps, so the grid's
    timeout cells are genuine failures.
  - **(Q4 consequence) a DETERMINISTIC stall guard.** Over **all 96 routes**
    (48 instances x L=16,128) the longest run of iterations retiring no gate is
    **max 17 (median 10) on the 84 that complete** and **min 5,084 (max
    165,762) on the 12 that do not** -- a **299x gap with nothing in between**.
    A guard at 1,000 iterations is 59x above healthy, 5x below stuck, and
    classifies all 96 correctly: it **never fired** on 10 healthy routes
    (streams byte-identical) and abandoned 6 frozen routes in **4-73 s instead
    of 300 s**. Being an iteration count it is **machine-independent**, so
    *abandonment* is now reproducible, and it catches star/Multiplier
    deterministically instead of burning `max_iterations`.
    **CORRECTION (same day): it does NOT fix the speculative wall-clock
    share.** An earlier note here claimed it removed the reason IV-C discloses
    the load-dependent 360q QPEexact / 200q QFT results. It does not: those are
    *healthy* routes racing their time share (both complete with a
    no-retirement gap of 12-13), so the guard never fires on them. It shortens
    360q QPEexact's protocol time 32.6 -> 20.3 s only by abandoning that
    instance's frozen L=8 candidate, and the share for L=128 is derived from
    the FIRST route, so the 1,224-vs-2,342 flip is untouched. Making the
    *budget* deterministic is still open.
    - **SHIPPED (2026-09-03): `RouterConfig.max_iterations_without_progress`
    = 1_000.** `compile()` tracks a watermark on `len(state.dag_active)` (which
    only shrinks) and raises `RuntimeError('Router retired no gate in N
    iterations; abandoning as stalled')` once that many iterations pass with no
    gate retired. **Validated on all 48 instances under the shipped protocol**
    (`paper/horizon_sweep/hz_guard_validate.py` ->
    `guard_validation.jsonl`): op-stream SHA, EPR, SWAPs, depth,
    `seeded_tie_break_count` AND the selected horizon are **identical 48/48**,
    and the same 13 candidate horizons are abandoned during selection either
    way -- so it changes only how long a doomed route runs. Protocol wall time
    over the 48 falls **509.8 s -> 323.1 s (1.58x)**, concentrated in
    80q Random (236 -> 71 s), 360q QPEexact (33 -> 20 s) and star/Multiplier
    (14.5 -> 4.7 s). 60/60 fuzz, both paper verifiers pass, and the
    single-pass stream is byte-identical on 25q AE, 64q AE/QFT/Multiplier and
    80q QPEexact. **Do not raise the limit without re-deriving the separation**
    -- it rests on max healthy gap 17 vs min stuck gap 5,084.
- **(Q5) you cannot cut earlier -- and the deep term is a PENALTY.** At L=128
    on scale-up, layers 65-128 carry **53%** of the total |gain| and 90% is only
    reached at **layer 108** (95% at 117, 99% at 126). Truncating at 64 discards
    half the signal. Why: **every core graph in the corpus is bipartite**
    (grids, the 4-cycle ring, the star tree), so for adjacent src/dst the two
    distances differ in parity and **|Delta| = 1 on 100% of collected gates**
    (verified on 4 instances). Past layer 7 the lookahead term is therefore
    exactly `0.5 * (#closer - #farther)`, a signed count -- and at scale it is
    overwhelmingly negative (100q QFT: 10,605 closer vs 60,548 farther; 80q
    QPEexact 21,442 vs 70,263). **Deep lookahead discourages moving a qubit
    away from its future partners.** This explains the floor result and both
    earlier refutations: the gate budget and the slow decay each discard the
    distant penalties.
- **Backward refinement at a FIXED horizon (measured 2026-09-02, recovered from
  a session that could not commit).** `+R` with `selection=False`, 5 passes, the
  isolation of what refinement contributes without horizon selection under it:
  main-24 gmean **171.4**, heavy-hex ring **82.3** (9), star **89.8** (8 of 9 --
  star/Multiplier fails), scale-up **773.4** (5 of 6 -- 360q QPEexact exceeds
  the 900 s per-pass guard). Read against dSABRE (171.9 / 85.2 / 101.1 / 705.7)
  refinement alone **leads below ~108 physical qubits** (ring 82.3 vs 85.2) and
  **collapses above 150** (773.4 vs selection's 507.7). Data:
  `paper/horizon_sweep/refine_fixed_horizon_{main,rest}.json`.
  This is the fixed-horizon `+R`, NOT the shipped one (which selects the horizon
  on pass 1); do not quote it against `tab:protocols`.
- `paper/horizon_sweep/gate_budget_sweep.json` is the refuted per-qubit gate
  budget (`teleport_lookahead_cx_count` k in {16..64} at `dag_extended_max_layers`
  512), the evidence base `horizon_open_question.md` cites as `phase2.json`.
- Grid was routed from a snapshot carrying the **uncommitted three-term
  selection key**; the shipped schedule was re-run as the control arm, so all
  comparisons are same-key. vs the old-key sweep, 24/271 fixed-horizon cells
  differ, 3 at the protocol (25q Random 401->393, 80q Multiplier 2411->2486,
  360q QFT 1156->1170).

## dSABRE's intra-core routing strategy: ported, measured, REFUTED (2026-09-03)

Full write-up and data: `paper/local_routing/` (README, `ablate_local.py` ->
`local_routing_ablation.jsonl`, `report_local.py`, two probes). 768 routes,
every completing stream replay-verified.

**The three differences, which are the complete set** (dSABRE has no
SABRE-style recently-used-qubit decay): dSABRE applies the best SWAP of
**every** active core per iteration where PORTER applies one chip-wide; it
scores against core `c`'s own front and its own slice of `E`, normalised by
those counts, where PORTER sums and normalises chip-wide; and it discounts an
extended gate by `decay^depth` where PORTER weights the local set flat.  Each
was implemented as a `RouterConfig` flag defaulting to PORTER's choice ---
`local_per_core_parallel`, `local_score_per_core`, `local_ext_decay` --- and
all three defaults left the shipped stream **byte-identical** (SHA256 +
`seeded_tie_break_count`, 6 circuits).

**The flags are REVERTED (author's call): PORTER's local stage stands as it
was, with no ablation knob for it.** They exist only in commit `3dee83e`;
`git checkout 3dee83e -- porter/` to re-run `ablate_local.py`. The two probes
instrument the shipped router and still run against HEAD. After the revert the
same six stream SHAs reproduce and 60/60 fuzz passes, so `porter/` is
bit-for-bit its pre-experiment self --- do NOT re-add the knobs to "keep the
ablation runnable".

**ANSWER: it does not help.** Under the shipped best-of-4-horizon protocol,
all 48 completing, the faithful full port is **+1.3%** EPR (17W/20L/11T) and
**+2.6%** on the paper's main-24 basis (179.6 vs 175.0). The per-core score
alone is +0.4% / +0.9%. The control arm reproduces the released `sfc` main-24
gmean of **175.0 exactly**, so the harness is measuring the real protocol.

**The trap: at a FIXED horizon the per-core score looks like a 5% win.**
Single pass, 44-instance common basis: per-core score **147.2 vs 154.9
(-5.0%)**, 17W/8L/20T. It does not survive the portfolio --- per-instance the
change is large in *both* directions (80q QFT 446->321, 64q QAOA 775->652
against star/Multiplier 455->721, 80q Multiplier 2486->3222) and nets to
nothing. **Same pattern as every other lookahead-scoring axis measured here:
the four-horizon portfolio already collects that spread.** Do not report a
fixed-horizon local-scoring result without re-running it under selection.

**The per-core *unit* has nothing to work with in PORTER.** Measured
(`probe_cores.py`): **92-99% of local-stage calls have exactly ONE active
core**, mean local front 1.03-1.18 gates, because the locality-first loop
drains local work every iteration. dSABRE's parallelism is a real speedup in
dSABRE and a no-op here by construction. Added on top of the per-core score it
*costs* 3.7 points (-5.0% -> -1.3%).

**The per-core score is a REWEIGHTING, not a structure.** A local SWAP in core
`c` cannot change a distance outside `c`, so PORTER's out-of-core terms are
constant and cancel in the ranking; what changes is the normaliser, `|E_c|`
instead of `|E|`, measured at **1.02-2.22x** (`probe_ext.py`). Confirmed
directly: raising the chip-wide weight alone recovers most of the gain
(40-instance basis, `w_e` 0.8/1.2/1.6/2.4 -> 135.5/132.5/133.3/132.7 against
per-core 130.9), and **per-core at `w_e=1.6` is back to baseline (135.3)**, so
`w_e=0.8` is already near that axis's optimum. dSABRE's own `weight_extended=0.25`
is *worse* under per-core normalisation (156.0, +0.8%).

**The axis trades fixed-horizon EPR for robustness.** Single-pass completions
of 48 fall to 46 (per-core), 44 (`w_e=1.6`), 41 (`w_e=2.4`); PORTER's 0.8
loses only star/Multiplier. Every arm recovers to 48/48 under the portfolio.

**NOT a compile-time win either, and an early 2x reading was an artefact** of
summing wall time over each arm's *own* completing set --- PORTER completes two
expensive instances (80q Random, 360q QFT) that per-core does not. Common
basis: **1.03x**; under the protocol 608 s vs 611 s. dSABRE's per-core
traversal is a real saving *in dSABRE*, whose intra-core stage is `Theta(N_r)`
per call; PORTER's local stage is only 9-33% of route time and already peels a
bounded number of layers.

## The horizon sets sampling AND weight; that is both the depth question and the timeouts (2026-09-03)

Full write-up and data: `paper/horizon_sweep/report_lookahead_scale.md`,
`scale_cells.jsonl` (336 routes), `freeze_modes.jsonl` (all 32 failures
classified), `revisit_cells.jsonl`, `domination.jsonl`, `depth_features.json`.
Scripts: `hz_scale.py`, `hz_freeze.py`, `hz_revisit.py`, `hz_ratio.py`,
`hz_depth.py`, `report_scale.py`.

**`total = direct_gain + lookahead_gain` mixes two units.** `direct_gain`
counts front/latent-direct gates, O(1). `lookahead_gain` is a SUM over up to
`min(L, N_tp=50)` collected gates, each ±w(layer) with w floored at 0.5. So
`dag_extended_max_layers` widens the view AND multiplies the future's weight.
Measured mean |lookahead|/|direct|: **0.2-1.8 at L=16, 1.4-28.5 at L=128**;
the lookahead reverses the direct-only ranking on 1.7-40% of decisions at
L=16 and **33-99%** at L=128.

- **The "53% of magnitude beyond layer 65" figure is not special to scale-up.**
  The floor makes a layer-8 gate and a layer-128 gate count the same, so any
  circuit whose walks reach deep carries most of its magnitude there. What
  differs is whether the magnitude is information or pressure.

**THERE IS NO RULE FOR WHEN TO GO DEEPER, and the search is now exhausted.**
- Identical circuits pick different horizons on different machines (64q QFT:
  L=16 on H, L=256 on both heavy-hex graphs), so no circuit-only feature can work.
- Partner novelty is flat (~0.51) across every family -- refuted.
- Best static signal is circuit ASAP depth (Spearman **+0.68** with deep-gain;
  rho **-0.60**, K +0.04, diameter +0.04), but `L*/D` spans **420x**.
- **No feature gate beats not gating**: exhaustive single-threshold search over
  {depth, rho, CX, n, cx-depth, physical} in both directions reaches 373.3,
  exactly the ungated `{16,128}` score. Held out: 373.3 / 378.5.
- **Runtime features fail too**: domination ratio at L=16 vs deep-gain is
  Spearman **+0.02** (flip rate -0.11, gates collected -0.41). A 7-instance
  eyeball looked promising; on 38 it is noise.
- **Nothing left to win**: shipped best-of-4 = 361.6, oracle over 8 horizons
  = 350.4 -- a perfect predictor is worth **3.1%**.

**Every timeout is one pathology.** All 32 non-completing cells classified:
**28 teleport shuttles**, 2 local-SWAP cycles (ring/star Multiplier -- the
known intra-core livelock, no teleport in the window), 2 other. All 28
shuttles span **exactly 2 cores** with one qubit making >=99.5% of the
teleports. 10 of 11 failures at L=128 and 14 of 14 at L=256.
- Mechanism, traced on `main/64/qft`@128: period-3 cycle (local SWAP,
  teleport, nothing retired) x 38,741. `q45 2->5` scores direct -1.0 /
  lookahead **-11.16**; `q45 5->2` scores +1.0 / **+11.16**. The lookahead is
  **exactly antisymmetric** under reversing a move -- same collected set, same
  weights, and local SWAPs do not change any qubit's core. The remote stage
  has **no null action**, so at core 2 where every plan is negative it takes
  the least negative, which is the undo. From core 5 the return is positive
  outright.
- Independent confirmation from released data: failure rate is monotone in
  horizon (**0% at L=4 -> 23% at 128 -> 29% at 256**) and by weight schedule
  tracks lookahead MAGNITUDE, not circuit mix: `floor0` (true decay, sum
  saturates) **1.0%** vs shipped `base` **8.3%**.
- **`main/80/random`@64 is not a failure**: re-run it completes in 145 s. The
  grid's 300 s wall-clock guard cut off a slow route. Wall clock cannot tell
  slow from stuck -- which is why the iteration-based stall guard exists.
- Portfolio margin: of 48 instances, 35 complete on all four shipped
  candidates, 12 on three, and **80q Random on only two** (L=4, L=16).

**Two default-off `RouterConfig` flags added; both leave the shipped stream
byte-identical** (SHA256 + tie count + SWAPs + depth on 8 routes over 4
horizons; 60/60 fuzz; both paper verifiers pass; released JSONs untouched).

1. `teleport_lookahead_scaling` = `sum` (shipped) | `mean` | `sqrt`, with
   `teleport_lookahead_coefficient`. Divides the sum by the weight it
   accumulated (or its square root) so the horizon sets sampling only. Swept
   all 48 x 7 horizons (`scale_cells.jsonl`, 336 routes, all replay-verified):
   **non-completions 31 -> 5**, L=128 completions 27 -> 36, L=256 24 -> 37 --
   but portfolio EPR **+2.8%** (17 better / 20 worse), main-24 175.0 -> 183.0,
   scale-up 508.7 -> 518.0, ring 86.1 -> **84.2**. **A completion fix that
   costs EPR, not an EPR win.** It does NOT flatten the horizon (best-of-2
   395.3, best-of-4 371.6, best-of-7 356.8), so it buys no smaller portfolio,
   and it adds one NEW failure (`scaleup/360/qft`@16). `mean` is too weak;
   `sqrt` at coefficient 4-8 fails again -- 1-2 is the only stable region.
2. `teleport_revisit_block` (+`_strict`): drop a teleport returning a qubit to
   a core it has occupied since the last retirement; record clears on every
   retirement, so between retirements each qubit enters each core at most once
   (bound: `n x K` teleports). Rescues **19 of the 32** failing cells --
   **18 of 28 shuttles**, 0 of 2 local-SWAP cycles (correctly: no teleport in
   their windows). **The rescued routes are bad**: only **1 of 19** beats its
   instance's shipped-protocol result (ring/qaoa@128 completes at 1015 against
   a portfolio best of 244), so it buys completion, never EPR -- and since the
   stall guard already abandons a failed candidate cheaply, it costs time.
   The 13 it misses are the widest instances (7 of them 80q): `n x K` is up to
   480 teleports at 80q and each costs several iterations, so the bound
   exceeds the stall guard's 1,000-iteration window before it bites.
   **Free on healthy routes: 47/47 instances routed at the configured horizon
   emit a byte-identical op stream.** The strict variant (no soft fallback)
   rescues one more of four probed and leaves ten controls byte-identical too.

**REFINES A PAPER CLAIM.** Sec VI says the guarantee "needs a progress
argument for the intra-core stage, not a stronger capacity transaction",
citing star/Multiplier as "the one failure we observe". True of the
configurations the paper reports -- but over the horizon grid the dominant
failure is a **remote-stage shuttle, 28 cells to 2**. The remote stage has its
own livelock; unlike the intra-core one it now has an identified cause
(antisymmetric lookahead + forced move) and a bound.

**Recommendation: change nothing in the shipped protocol.** The portfolio is
within 3.1% of an eight-horizon oracle; the stall guard already makes a failed
candidate cost a median 36.9 s; and both fixes buy completion at an EPR cost.
Adopt the revisit block only if the completeness story is wanted for its own
sake. Do NOT spend more routes on horizon search.

**Waiter trap, second variant (hit again 2026-09-03).** The recorded fix for
the self-matching waiter is the `[h]z_scale.py` bracket trick, and it works ---
until the waiter *also contains the command it is waiting for*:

```bash
until ! ps aux | grep -q "[h]z_rev""isit.py"; do sleep 20; done
python3 paper/horizon_sweep/hz_revisit.py --cells completed ...   # <- self-match
```

The second line puts the literal `hz_revisit.py` in the waiter's own command
line, so the bracket trick on line 1 matches it and the loop never exits. It
sat idle ~25 min. **Wait on a PID, not a pattern**:
`while kill -0 <pid> 2>/dev/null; do sleep 30; done`.
