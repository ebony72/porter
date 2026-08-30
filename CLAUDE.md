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
  not by 96, and 1Q gates are not excluded. The cap **binds on all three
  QPEexact scale-up instances** (front reaches 100/200/360). It is
  output-neutral there (truncation is by ascending gate index and executable
  gates drain first), verified by re-routing uncapped. New released probe
  `paper/probe_front_limit.py` reproduces both figures; max front elsewhere
  is 47 (64q random).
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
