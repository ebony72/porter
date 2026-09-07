# PORTER — a plan-committed router for multi-core distributed quantum computers

PORTER compiles a quantum circuit onto a **distributed** machine: several
small cores joined by entanglement-distribution links. A two-qubit gate whose
operands sit in different cores needs inter-core communication, which consumes
EPR pairs — the resource PORTER minimises.

Its distinguishing idea is to decide *what remote action to take* before
working out *how to set it up*. Each candidate is a **plan** — a communication
primitive, the gates it can discharge, and its readiness conditions, but no
SWAP sequence. PORTER ranks plans by the progress they deliver, uses
preparation cost only to break ties, commits to one, and only then generates
the local SWAPs that make it executable.

This repository holds the implementation, the evaluation harness, an
independent replay verifier, the raw per-circuit results, and the manuscript.

- **Paper:** [`paper/sfc.pdf`](paper/sfc.pdf)
- **Supplement:** [`paper/sfc_appendix.pdf`](paper/sfc_appendix.pdf)

## Results at a glance

Measured over 48 circuit–architecture instances: 24 main-suite (MQT-Bench at
25, 64 and 80 logical qubits), 6 scale-up (100–360 qubits), 18 heavy-hex.

| Comparison | EPR pairs | Completion | Compile time |
|---|---|---|---|
| vs. TeleSABRE (25 / 64 / 80 qubits) | **−59.7% / −44.9% / −68.8%** | 24/24 vs. 17/24 | — |
| vs. dSABRE, main suite | 0.99× | 24/24 both | 1.20× |
| vs. dSABRE, main suite, PORTER+R | **0.91×** | 24/24 | 2.15× |
| vs. dSABRE, 100–360-qubit scale-up | **0.69×** (6 of 6) | 6/6 both | **0.52×** |

TeleSABRE figures are geometric means over the instances both compilers
complete; EPR aggregates are unweighted geometric means. PORTER is
*competitive with* dSABRE rather than uniformly superior — it wins 11
instances, loses 10 and ties 3. Taking the better of the two per instance
gives 12.5% below dSABRE alone, which is why the two designs are worth having
side by side.

## Quick start

The router, the compiler CLI and the verifier are **pure standard library** —
no dependencies to install.

```bash
python compile_porter.py circuit.qasm -a A --out-dir compile_outputs
```

Architecture `A` is a 2×2 array of 3×3 cores (36 physical qubits); `H` is a
2×3 array of 4×4 cores (96). Input circuits must use the basis
`id, rz, sx, x, cx`.

Verify a compiled circuit end to end — the verifier replays the emitted
operation stream against its own copy of the layout and shares no routing,
scoring or layout code with the router:

```bash
python verify_porter.py --qasm circuit.qasm -a A --seed 0
```

Run the built-in fuzz suite (random circuits on both architectures, compiled
and verified):

```bash
python verify_porter.py --trials 60
```

Check the verifier itself, by mutating streams that pass and asserting every
mutant is rejected:

```bash
python verify_fault_injection.py
```

Route with backward refinement (PORTER+R); `--passes` must be odd, and 1
reproduces the default protocol byte-for-byte:

```bash
python compile_porter.py circuit.qasm -a H --passes 5 --out-dir compile_outputs
```

## Using the router directly

```python
import pathlib, porter, compile_porter

_, hw = compile_porter.hardware_for_name("A")
circuit, n = compile_porter.parse_qasm2(pathlib.Path("circuit.qasm"))
cfg = porter.RouterConfig(random_seed=0)
layout = compile_porter.build_initial_layout(
    circuit, hw, n, min_free_per_core=cfg.min_free_before_teleport)
state = porter.PorterRouter(hw, cfg).compile(circuit, layout)
print(state.stats.epr, state.stats.local_swap_count, state.stats.depth)
```

`compile_porter.route(hw, cfg, circuit, layout)` is the entry point that runs
the shipped protocol: one route at each of four lookahead horizons
(`L_tp ∈ {4, 8, 16, 128}`), keeping the lowest-EPR result.

## What is in here

| Path | Contents |
|---|---|
| `porter/` | The router package. `PorterRouter(hw, cfg).compile(circuit, layout) -> RouterState` |
| `compile_porter.py` | CLI, QASM parsing, hardware construction, initial layout, operating protocols |
| `verify_porter.py` | Independent replay verifier and fuzz suite |
| `verify_fault_injection.py` | Verifier-of-the-verifier: ten corruption classes, every mutant must be rejected |
| `compare_routers.py` | Head-to-head harness against TeleSABRE, dSABRE and pytket-dqc |
| `compare_heavyhex.py` | The two heavy-hex core graphs (ring and star) |
| `ablation_mechanisms.py`, `bench_*.py`, `rerun_*.py` | The harnesses behind each released results file |
| `patched_telesabre/` | Patched TeleSABRE binary used by the comparison; see its README |
| `paper/` | Manuscript sources, both PDFs, and every released results file |
| `paper/horizon_sweep/` | The lookahead-horizon study: a 3,120-route sweep grid (every completing route replay-verified), plus scripts and reports |
| `paper/local_routing/` | The intra-core routing-strategy ablation |

## Reproducing the paper's numbers

Every quantitative claim in the manuscript is machine-checked. From `paper/`:

```bash
python gen_tables_selection.py --write
python verify_tex_tables.py
python verify_paper_numbers.py
python verify_horizon_claims.py
```

`gen_tables_selection.py` regenerates the data tables from the released JSON
and is idempotent — a no-op diff means the tables are current.
`verify_tex_tables.py` parses the LaTeX rows and checks every cell against the
results files; `verify_paper_numbers.py` re-derives the figures quoted in the
prose; `verify_horizon_claims.py` checks Section IV-E against
`paper/horizon_sweep/`.

To rebuild the documents, compile the main paper **first** so that `sfc.aux`
exists — the supplement resolves its cross-references through it:

```bash
cd paper && pdflatex sfc && bibtex sfc && pdflatex sfc && pdflatex sfc
pdflatex sfc_appendix && bibtex sfc_appendix && pdflatex sfc_appendix && pdflatex sfc_appendix
```

## Reproducing the comparisons

`compare_routers.py` and `compare_heavyhex.py` additionally need `networkx`,
`qiskit`, and sibling checkouts of the two baselines (`../dsabre/` and
`../other/telesabre/`) together with their benchmark circuits. The released
`paper/*_results*.json` files record every leg, so the tables can be checked
without re-running the baselines.

## Determinism

For a fixed circuit, hardware, `RouterConfig.random_seed` and protocol, the
emitted operation stream is byte-identical across runs. The speculative
horizons are bounded by a deterministic work budget rather than wall-clock
time, so the selected route does not depend on machine load.

## Licence

MIT — see [`LICENSE`](LICENSE).

Two things the licence does not cover. `patched_telesabre/layout.c.patch` is a
small diff against the upstream TeleSABRE sources, which are not vendored here
and carry their own licence; `build.sh` applies the patch to a copy of an
upstream checkout you supply. The manuscript, its figures and the PDFs in
`paper/` are the authors' work and are not released under the MIT licence.

## Citing

The manuscript is under review; please cite the PDF in `paper/` until a
published reference is available.
