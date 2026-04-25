#!/usr/bin/env bash
# Checkpoint 6 e2e: warmup module + CLI subgroup, engagement CLI command.

set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO"

PASS=0
FAIL=0

ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

check() {
    local label="$1"; shift
    if eval "$@" >/dev/null 2>&1; then ok "$label"; else bad "$label"; fi
}

PYRUN="uv run --quiet python"

echo "── Checkpoint 6: warmup module + CLI ──"

# Use a temp config dir so we don't pollute ~/.config/gtm
export GTM_CONFIG_DIR="$(mktemp -d)/gtm"

echo "[1] warmup module imports + roundtrip"
check "warmup add/list/remove roundtrip works" \
    "$PYRUN -c '
import importlib
# Re-import config to pick up GTM_CONFIG_DIR override
import gtm.config; importlib.reload(gtm.config)
import gtm.modules.warmup as wm; importlib.reload(wm)
wm.add(\"first-tree\", \"alice\", \"twitter\", \"agreed via DM\")
wm.add(\"first-tree\", \"bob\", \"reddit\")
entries = wm.list_for_launch(\"first-tree\")
assert len(entries) == 2, entries
assert any(e[\"handle\"] == \"alice\" for e in entries)
assert wm.remove(\"first-tree\", \"alice\", \"twitter\") is True
assert len(wm.list_for_launch(\"first-tree\")) == 1
assert wm.remove(\"first-tree\", \"ghost\", \"twitter\") is False
'"

echo "[2] CLI: warmup group registered"
check "gtm warmup --help works" \
    "uv run --quiet gtm warmup --help"
check "gtm warmup add --help works" \
    "uv run --quiet gtm warmup add --help"
check "gtm warmup list --help works" \
    "uv run --quiet gtm warmup list --help"
check "gtm warmup remove --help works" \
    "uv run --quiet gtm warmup remove --help"

echo "[3] CLI: warmup add/list/remove roundtrip"
check "warmup add via CLI" \
    "uv run --quiet gtm warmup add carol --launch demo --platform twitter --notes hello"
check "warmup list shows entry" \
    "uv run --quiet gtm warmup list --launch demo | grep -q twitter:carol"
check "warmup remove succeeds" \
    "uv run --quiet gtm warmup remove carol --launch demo --platform twitter"

echo "[4] CLI: engagement command registered + accepts posts file"
check "gtm engagement --help works" \
    "uv run --quiet gtm engagement --help"
# Don't actually run the agent — just verify the command parses required flag
check "missing --posts-file errors out" \
    "! uv run --quiet gtm engagement 2>/dev/null"

# cleanup
rm -rf "$GTM_CONFIG_DIR"

echo
echo "── Checkpoint 6 result: $PASS passed, $FAIL failed ──"
[ "$FAIL" -eq 0 ]
