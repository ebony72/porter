# Patched TeleSABRE binary

`compare_routers.py` uses the `telesabre` binary in this directory instead of
the stock `../../other/telesabre/telesabre`.

## Why

The stock binary segfaults on architecture A (2x2 cores of 3x3, 9 slots per
core): `initial_layout_hungarian()` in `src/layout.c` only assigns a qubit to
a core whose free capacity exceeds `init_layout_hun_min_free_qubit` (default
4). When no core qualifies — which happens with 9-slot cores — the qubit's
`virt_to_core[q]` stays `-1` and is then used as a negative array index
(out-of-bounds write / segfault).

## The patch

`layout.c.patch` adds a fallback branch: if a qubit is left unassigned, put it
on the core with the most remaining free capacity (erroring out cleanly only
if every core is completely full). Nothing else is changed; results on
circuits that don't hit the fallback are identical to the stock binary.

## Rebuilding

```bash
./build.sh
```

This copies the upstream `src/` from `../../other/telesabre` into a temp dir,
applies `layout.c.patch`, and compiles with the upstream build command
(`gcc -O3 -flto -I src src/*.c -o telesabre`). The upstream tree is never
modified. If the patch fails to apply, upstream `layout.c` has changed —
re-derive the patch against the new source.
