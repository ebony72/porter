#!/bin/sh
# Rebuild the patched TeleSABRE binary used by compare_routers.py.
#
# Copies the upstream source tree from ../../other/telesabre, applies
# layout.c.patch (fallback-to-least-full-core in initial_layout_hungarian,
# see README.md), and compiles with the upstream README's build command.
# The upstream tree is never modified.
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
UPSTREAM="$HERE/../../other/telesabre"
BUILD=$(mktemp -d)
trap 'rm -rf "$BUILD"' EXIT

cp -R "$UPSTREAM/src" "$BUILD/src"
patch -d "$BUILD" -p1 < "$HERE/layout.c.patch"
gcc -O3 -flto -I "$BUILD/src" "$BUILD/src"/*.c -o "$HERE/telesabre"
echo "Built $HERE/telesabre"
