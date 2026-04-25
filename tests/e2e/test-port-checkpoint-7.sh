#!/usr/bin/env bash
# Checkpoint 7 e2e: promoter agent uses identity-routed tools in Phase C.

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

echo "── Checkpoint 7: promoter Phase C identity routing ──"

echo "[1] promoter imports identity routing tools"
check "promoter imports reddit_pick_identity_for_sub etc" \
    "$PYRUN -c '
import inspect
from gtm.agents import promoter
src = inspect.getsource(promoter)
for name in [\"reddit_list_identities\", \"reddit_identity_affinity\", \"reddit_pick_identity_for_sub\", \"reddit_cross_post_lint\"]:
    assert name in src, name
'"

echo "[2] Phase C prompt mentions identity tools"
check "prompt text includes Phase C identity instructions" \
    "$PYRUN -c '
import inspect
from gtm.agents import promoter
src = inspect.getsource(promoter)
assert \"reddit_list_identities\" in src
assert \"reddit_pick_identity_for_sub\" in src
assert \"identity\" in src.lower()
'"

echo "[3] Output schema includes identity per post"
check "JSON output schema references identity" \
    "$PYRUN -c '
import inspect
from gtm.agents import promoter
src = inspect.getsource(promoter)
assert \"subreddit, identity\" in src or \"subreddit,identity\" in src.replace(\" \", \"\"), src[2200:2600]
'"

echo "[4] Promoter still imports cleanly"
check "promoter agent module imports" \
    "$PYRUN -c 'from gtm.agents.promoter import run_promoter'"

echo
echo "── Checkpoint 7 result: $PASS passed, $FAIL failed ──"
[ "$FAIL" -eq 0 ]
