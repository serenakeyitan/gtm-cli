#!/usr/bin/env bash
# Checkpoint 8 e2e: full ported surface integration smoke test.
# This is the final sweep — re-runs every prior checkpoint and adds CLI smoke checks.

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

echo "── Checkpoint 8: full integration smoke ──"

echo "[1] Re-run all earlier checkpoints"
# checkpoint-3 was removed in Phase 5 along with gtm.agents.twitter_promoter
# (the prompt-wrapping legacy agent it validated). See PLAN-claude-code-shape.md.
for cp in 1 2 4 5 6 7; do
    if tests/e2e/test-port-checkpoint-$cp.sh >/dev/null 2>&1; then
        ok "checkpoint-$cp passes"
    else
        bad "checkpoint-$cp FAILED"
    fi
done

echo "[2] Top-level CLI surface intact"
check "gtm --help works" \
    "uv run --quiet gtm --help"
check "gtm modules list works" \
    "uv run --quiet gtm modules list"
check "gtm warmup is registered" \
    "uv run --quiet gtm --help | grep -q warmup"
check "gtm engagement is registered" \
    "uv run --quiet gtm --help | grep -q engagement"

echo "[3] All ported agents importable together"
# twitter_promoter was deleted in Phase 5 (its prompt was unused after the
# legacy step-based runner became dead code). engagement_loop is still live
# (used by `gtm engagement`).
check "all agents import without conflicts" \
    "$PYRUN -c '
from gtm.agents.promoter import run_promoter
from gtm.agents.engagement_loop import run_engagement_loop
from gtm.agents.scout import run_twitter_scout
from gtm.agents.builder import run_builder
'"

echo "[4] All ported platforms importable together"
check "twitter + reddit browser tools coexist" \
    "$PYRUN -c '
from gtm.platforms.twitter.browser_tools import twitter_browser_post
from gtm.platforms.reddit.tools import reddit_browser_submit
from gtm.platforms.twitter.browser_client import get_twitter_browser_client_for_identity
from gtm.platforms.reddit.client import get_reddit_browser_client_for_identity
'"

echo "[5] Identity vocabulary consistent — no leftover openclaw imports"
check "no openclaw_growth_pipeline imports remain in ported code" \
    "! grep -rn 'openclaw_growth_pipeline' gtm/ 2>/dev/null"

echo "[6] Identity affinity wired through the stack"
check "promoter imports same affinity module the tools call" \
    "$PYRUN -c '
import inspect
from gtm.agents import promoter
from gtm.platforms.reddit import tools as rt
# Both reference identity-routing names
assert \"reddit_pick_identity_for_sub\" in inspect.getsource(promoter)
assert hasattr(rt, \"reddit_pick_identity_for_sub\")
'"

echo "[7] Warmup module persists data through CLI roundtrip"
TMP_GTM="$(mktemp -d)/gtm"
export GTM_CONFIG_DIR="$TMP_GTM"
check "CLI add+list+remove roundtrip persists to disk" \
    "uv run --quiet gtm warmup add testuser --launch ck8 --platform twitter --notes smoke && \
     uv run --quiet gtm warmup list --launch ck8 | grep -q twitter:testuser && \
     uv run --quiet gtm warmup remove testuser --launch ck8 --platform twitter"
unset GTM_CONFIG_DIR
rm -rf "$TMP_GTM"

echo
echo "── Checkpoint 8 result: $PASS passed, $FAIL failed ──"
[ "$FAIL" -eq 0 ]
