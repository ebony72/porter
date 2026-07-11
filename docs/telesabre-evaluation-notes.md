# TeleSABRE evaluation notes

Supplementary material for the PORTER paper (`paper/sfc.tex`). These two
issues were discovered while building the three-way PORTER / TeleSABRE /
dSABRE comparison. The paper's Setup section summarises the first in two
sentences and cites this document for the details; the second was a bug in
our own harness and is recorded here for transparency and reproducibility.
All TeleSABRE numbers in the paper reflect both fixes.

## 1. The TeleSABRE reference-implementation bug (out-of-bounds write)

Running TeleSABRE's compiled C binary against architecture A (four
3×3 = 9-qubit cores) with its default hungarian initial-layout configuration
segfaults deterministically on every circuit we tried. We traced this with
source-level instrumentation (macOS's `lldb` could not attach headlessly in
our environment) to `initial_layout_hungarian` in `src/layout.c`: its second
assignment pass places a logical qubit `q` into the first core whose
remaining capacity exceeds `init_layout_hun_min_free_qubit` (4 in the
reference config), but if *every* core's remaining capacity is at or below
that threshold — which routinely happens once a 9-slot core has already
absorbed 5 of its share of a 25-logical-qubit circuit — `virt_to_core[q]` is
left at its sentinel `-1` and is then used, unchecked, as a negative array
index a few lines later.

This is a latent bug in the reference implementation, not an artefact of our
harness: it reproduces with the project's own `configs/default.json` and
device file, invoked exactly per the project's README. It is specific to
core capacities materially smaller than the 4×4 = 16 cores TeleSABRE was
originally evaluated on; we did not observe it on architecture H.

We built a minimal, behaviour-preserving patch — fall back to the
least-loaded core rather than leaving the qubit unassigned — against a
separate copy of the source tree and used the resulting binary for every
TeleSABRE number in the paper; the upstream repository is untouched.
Results on circuits that never hit the fallback are identical to the stock
binary. The patch (`layout.c.patch`), the rebuild script, and usage notes
live in [`patched_telesabre/`](../patched_telesabre/README.md).

## 2. The filename-handling bug in our comparison harness

Our comparison harness originally invoked TeleSABRE with the 64-qubit QNN
circuit file's on-disk name, `qnn_OLD_DEEP….qasm.bak` (the deeper of two QNN
variants present in the upstream repository, selected because its CX count
exactly matches dSABRE's own published QNN table). TeleSABRE's `main.c`
infers file type from the *last* dot in the filename, so this double
extension is parsed as `.bak` and rejected outright (`"does not have a .json
or .qasm extension"`) before any routing is attempted — a harness bug, not a
genuine TeleSABRE non-convergence, though an earlier version of the
evaluation had recorded it as one.

We fixed this by always handing the binary a temporary copy with a clean
`.qasm` suffix (see `compare_routers.py`). Once fixed, TeleSABRE completes
this circuit in 21.7 s at exactly the EPR and SWAP counts dSABRE's own
evaluation reports — confirming the fix and giving an independent
cross-check of our harness's fidelity to TeleSABRE's actual behaviour.
