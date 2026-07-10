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
was `DistributedRouter`, kept as an alias of `PorterRouter`; the
initial-layout heuristic was called "try15", now `build_initial_layout` /
`porter.balanced_first_layer`.)

## Files

| File | Description |
|------|-------------|
| `porter/` | The router package: `PorterRouter(hw, cfg).compile(circuit, layout) -> RouterState` |
| `porter/hardware.py` | `Core`, `Hardware` (cores, ports, cached distances), `bfs_distances`, `canonical_edge` |
| `porter/layout.py` | `Layout` (logical↔physical map with O(1) occupancy cache) |
| `porter/model.py` | `Gate`, `CompiledOp`, `RouterState/Stats/Config`, `Action`, `RemotePlan`, `assign_gate_ids` |
| `porter/router.py` | `PorterRouter`, `DagFrontierSimulator`, `CapacityReliefPlanner` |
| `compile_porter.py` | CLI: QASM parsing, A/H grid hardware, initial layout (`hardware_for_name`, `build_initial_layout`), JSON/CSV outputs |
| `verify_porter.py` | Independent replay verifier + fuzz suite (see below) |
| `compare_routers.py` | Head-to-head benchmark vs TeleSABRE / dSABRE / pytket-dqc |
| `patched_telesabre/` | Patched TeleSABRE binary used by `compare_routers.py` — the stock `../other/telesabre/telesabre` segfaults on architecture A. Rebuild with `build.sh`; see its README |

## CLI shapes

```bash
# Compile one circuit (architecture A = 2x2 cores of 3x3, H = 3x2 cores of 4x4):
python compile_porter.py <file.qasm> -a A --seed 0 --out-dir compile_outputs

# Verify one circuit end-to-end (compile + independent replay check):
python verify_porter.py --qasm <file.qasm> -a A --seed 0

# Fuzz: random circuits on A/H, compile + verify each:
python verify_porter.py --trials 60
```

Benchmark QASM circuits live in `../other/telesabre/circuits/` (`qasm_25/` fits
architecture A, `qasm_64/` fits H; only basis `id, rz, sx, x, cx` is supported).

## Key invariants

- **Determinism**: for a fixed `(circuit, hardware, RouterConfig.random_seed)`
  the emitted op stream is byte-identical across runs. Any refactor must
  preserve this — compare SHA256 of the serialized `compiled_ops` JSON and the
  `seeded_tie_break_count` stat (identical RNG consumption) before/after.
  (Last verified 2026-07-10 after the porter package split: 6 circuits × A/H
  byte-identical, tie counts unchanged, 60/60 fuzz trials pass.)
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
lookahead-scored SWAP heuristic. The load-bearing differences:

- **Action vocabulary**: dSABRE's only inter-core action is teleportation
  (TeleData); TeleSABRE adds telegate. PORTER additionally batches
  same-control remote CXs into telegate packets.
- **Decision structure**: dSABRE and TeleSABRE score a flat pool of candidate
  moves each iteration. PORTER is staged (inter-core actions are never
  considered while front-local work exists) and plan-committed (one
  `RemotePlan` is selected before any of its preparation SWAPs are generated,
  instead of mixing every remote gate's prep moves into one pool).
- **Capacity handling**: PORTER enforces `f_min` free slots before teleports
  and proactively routes qubits toward reservoir cores (BFS capacity relief);
  dSABRE reacts with forced evictions (`_force_make_room`), TeleSABRE with
  its Hungarian initial layout plus deadlock counting/recovery.
- **Failure model**: dSABRE recovers from deadlock via checkpoint rollback
  and stochastic "backup plans"; PORTER is deterministic-greedy with a
  decision-state cycle check and raises on genuine deadlock.
