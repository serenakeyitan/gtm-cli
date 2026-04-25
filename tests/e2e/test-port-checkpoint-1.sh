#!/usr/bin/env bash
# Checkpoint 1 e2e: identity session helper + reddit tools updated.
# Verifies imports resolve, opener archetypes catch "i built", lint runs,
# per-identity client cache works, identity helper resolves correctly.

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

echo "── Checkpoint 1: identity helper + reddit tools ──"

echo "[1] Module imports"
check "gtm.identity.session imports" \
    "$PYRUN -c 'from gtm.identity.session import session_dir_for_identity, session_dir_for_name'"
check "gtm.platforms.reddit.tools imports all new tools" \
    "$PYRUN -c 'from gtm.platforms.reddit.tools import reddit_browser_submit, reddit_cross_post_lint, reddit_list_identities, reddit_identity_affinity, reddit_pick_identity_for_sub'"
check "gtm.platforms.reddit.client cache helpers import" \
    "$PYRUN -c 'from gtm.platforms.reddit.client import get_reddit_browser_client, get_reddit_browser_client_for_identity, reset_reddit_browser_client'"
check "gtm.modules.filters.identity_affinity (stub) imports" \
    "$PYRUN -c 'from gtm.modules.filters.identity_affinity import compute_affinity, best_identity_for_sub'"

echo "[2] Per-identity client cache"
check "two distinct session dirs → two distinct cached clients" \
    "$PYRUN -c '
from gtm.platforms.reddit.client import get_reddit_browser_client, reset_reddit_browser_client
reset_reddit_browser_client()
a = get_reddit_browser_client(\"/tmp/sess_a\")
b = get_reddit_browser_client(\"/tmp/sess_b\")
a2 = get_reddit_browser_client(\"/tmp/sess_a\")
assert a is a2, \"same key should return cached\"
assert a is not b, \"different keys should return different clients\"
'"

echo "[3] Opener archetype regression"
check "'I built X' triggers announcement archetype" \
    "$PYRUN -c '
from gtm.platforms.reddit.tools import _classify_opener
assert _classify_opener(\"I built a tool that does X\") == \"announcement\", _classify_opener(\"I built a tool\")
'"
check "'I made Y' triggers announcement archetype" \
    "$PYRUN -c '
from gtm.platforms.reddit.tools import _classify_opener
assert _classify_opener(\"I made a thing\") == \"announcement\"
'"
check "'I open-sourced Z' triggers announcement archetype" \
    "$PYRUN -c '
from gtm.platforms.reddit.tools import _classify_opener
assert _classify_opener(\"I open-sourced this today\") == \"announcement\"
'"
check "Pure question opener does NOT trigger announcement" \
    "$PYRUN -c '
from gtm.platforms.reddit.tools import _classify_opener
assert _classify_opener(\"anyone else hitting this?\") == \"question\"
'"

echo "[4] Cross-post lint catches duplicate archetypes"
check "two posts both starting with 'I built' fail lint" \
    "$PYRUN -c '
import asyncio, json
from gtm.platforms.reddit.tools import reddit_cross_post_lint
result = asyncio.run(reddit_cross_post_lint.handler({
    \"posts\": [
        {\"subreddit\": \"a\", \"title\": \"t1\", \"body\": \"i built a tool that helps with X\"},
        {\"subreddit\": \"b\", \"title\": \"t2\", \"body\": \"i made something for Y\"},
    ]
}))
data = json.loads(result[\"content\"][0][\"text\"])
assert data[\"pass\"] is False, data
assert any(v[\"kind\"] == \"duplicate_opener_archetype\" for v in data[\"violations\"]), data
'"
check "single post passes lint trivially" \
    "$PYRUN -c '
import asyncio, json
from gtm.platforms.reddit.tools import reddit_cross_post_lint
result = asyncio.run(reddit_cross_post_lint.handler({
    \"posts\": [{\"subreddit\": \"a\", \"title\": \"t\", \"body\": \"i built x\"}]
}))
assert json.loads(result[\"content\"][0][\"text\"])[\"pass\"] is True
'"

echo "[5] Identity affinity stub"
check "best_identity_for_sub falls back to first candidate when no history" \
    "$PYRUN -c '
from gtm.modules.filters.identity_affinity import best_identity_for_sub
assert best_identity_for_sub(\"r/test\", [\"alice\", \"bob\"], {}) == \"alice\"
'"
check "best_identity_for_sub returns None for empty candidates" \
    "$PYRUN -c '
from gtm.modules.filters.identity_affinity import best_identity_for_sub
assert best_identity_for_sub(\"r/test\", [], {}) is None
'"

echo
echo "── Checkpoint 1 result: $PASS passed, $FAIL failed ──"
[ "$FAIL" -eq 0 ]
