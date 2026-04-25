#!/usr/bin/env bash
# Checkpoint 3 e2e: twitter promoter agent + prompt.
# Verifies imports, prompt loads, identity vocabulary used.

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

echo "── Checkpoint 3: twitter promoter agent + prompt ──"

echo "[1] Module imports"
check "twitter_promoter agent imports" \
    "$PYRUN -c 'from gtm.agents.twitter_promoter import run_twitter_promoter'"

echo "[2] Prompt loads via load_prompt"
check "load_prompt(\"twitter_promoter\") returns non-empty content" \
    "$PYRUN -c '
from gtm.agents.base import load_prompt
text = load_prompt(\"twitter_promoter\")
assert len(text) > 200, len(text)
assert \"twitter\" in text.lower()
assert \"identity\" in text.lower()
'"

echo "[3] Prompt uses identity vocabulary, not account"
check "prompt references identity (not openclaw account vocabulary)" \
    "$PYRUN -c '
from gtm.agents.base import load_prompt
text = load_prompt(\"twitter_promoter\").lower()
# Must mention identity for routing
assert \"identity\" in text
# Must NOT reference openclaw-growth-pipeline CLI command
assert \"openclaw-growth-pipeline\" not in text, text
'"

echo "[4] Models config has twitter_promoter slot"
check "runner.py declares twitter_promoter model" \
    "$PYRUN -c 'import inspect, gtm.engine.runner as r; assert \"twitter_promoter\" in inspect.getsource(r)'"

echo "[5] Agent module references identity-routed tools"
check "twitter_promoter imports browser_tools (not openclaw)" \
    "$PYRUN -c '
import inspect
from gtm.agents import twitter_promoter
src = inspect.getsource(twitter_promoter)
assert \"gtm.platforms.twitter.browser_tools\" in src
assert \"openclaw_growth_pipeline\" not in src
'"

echo
echo "── Checkpoint 3 result: $PASS passed, $FAIL failed ──"
[ "$FAIL" -eq 0 ]
