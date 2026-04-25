#!/usr/bin/env bash
# Checkpoint 4 e2e: engagement loop agent + prompt.

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

echo "── Checkpoint 4: engagement loop agent + prompt ──"

echo "[1] Module imports"
check "engagement_loop agent imports" \
    "$PYRUN -c 'from gtm.agents.engagement_loop import run_engagement_loop'"

echo "[2] Prompt loads"
check "load_prompt(\"engagement_loop\") returns content with 5 buckets" \
    "$PYRUN -c '
from gtm.agents.base import load_prompt
text = load_prompt(\"engagement_loop\")
for bucket in [\"constructive_critique\", \"scale_dismissal\", \"ai_generated\", \"edge_case\", \"buy_signal\"]:
    assert bucket in text, bucket
'"

echo "[3] Identity vocabulary used (not openclaw account)"
check "prompt uses identity, agent imports gtm.platforms" \
    "$PYRUN -c '
from gtm.agents.base import load_prompt
text = load_prompt(\"engagement_loop\")
assert \"identity\" in text.lower()
import inspect
from gtm.agents import engagement_loop
src = inspect.getsource(engagement_loop)
assert \"gtm.platforms.twitter.browser_tools\" in src
assert \"gtm.platforms.reddit.tools\" in src
assert \"openclaw_growth_pipeline\" not in src
'"

echo "[4] Models config has engagement_loop slot"
check "runner.py declares engagement_loop model" \
    "$PYRUN -c 'import inspect, gtm.engine.runner as r; assert \"engagement_loop\" in inspect.getsource(r)'"

echo "[5] draft_only defaults to True"
check "run_engagement_loop has draft_only=True default" \
    "$PYRUN -c '
import inspect
from gtm.agents.engagement_loop import run_engagement_loop
sig = inspect.signature(run_engagement_loop)
assert sig.parameters[\"draft_only\"].default is True
'"

echo
echo "── Checkpoint 4 result: $PASS passed, $FAIL failed ──"
[ "$FAIL" -eq 0 ]
