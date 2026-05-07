#!/usr/bin/env bash
# Checkpoint 3 e2e: promoter agent integration.
# Verifies reddit_preflight tool is registered, prompt mentions preflight in
# Phase C, and the helper drops FAIL identities.

set -uo pipefail

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

echo "── Checkpoint 3: promoter agent integration ──"

echo "[1] reddit_preflight MCP tool exposed"
check "reddit_preflight imports from gtm.platforms.reddit.tools" \
    "$PYRUN -c 'from gtm.platforms.reddit.tools import reddit_preflight'"

echo "[2] reddit_preflight tool runs end-to-end (with injected stats path)"
check "reddit_preflight tool returns BORDERLINE for Pale_Stand5217 vs MachineLearning" \
    "$PYRUN -c '
import asyncio, json
from gtm.platforms.reddit.tools import reddit_preflight
result = asyncio.run(reddit_preflight.handler({\"identity\": \"Pale_Stand5217\", \"sub\": \"MachineLearning\"}))
data = json.loads(result[\"content\"][0][\"text\"])
assert data[\"verdict\"] == \"BORDERLINE\", data
'"

check "reddit_preflight tool errors out on bogus identity" \
    "$PYRUN -c '
import asyncio
from gtm.platforms.reddit.tools import reddit_preflight
result = asyncio.run(reddit_preflight.handler({\"identity\": \"this_user_definitely_does_not_exist_zzz_999_aaa\", \"sub\": \"ClaudeAI\"}))
assert result.get(\"isError\") is True, result
'"

echo "[3] filter_identities_by_preflight helper drops FAIL identities"
check "filter drops identity below karma floor (mocked rules)" \
    "$PYRUN -c '
from gtm.platforms.reddit.tools import filter_identities_by_preflight
from gtm.modules import preflight as pf

# Monkey-patch fetch to avoid network — return synthetic stats per user.
def fake_fetch(name):
    return {
        \"alice\": {\"username\":\"alice\",\"total_karma\":50,\"link_karma\":25,\"comment_karma\":25,\"age_days\":10,\"verified\":False},
        \"bob\":   {\"username\":\"bob\",  \"total_karma\":5000,\"link_karma\":2500,\"comment_karma\":2500,\"age_days\":1000,\"verified\":False},
    }[name]
pf.fetch_reddit_user = fake_fetch

# Force-fail rule: comment_karma >= 1000.
rules = {\"subs\": {\"strict\": {\"min_comment_karma\": 1000, \"min_age_days\": 365}}}

safe, log = filter_identities_by_preflight(\"strict\", [\"alice\", \"bob\"], rules=rules)
assert safe == [\"bob\"], safe
verdicts = {entry[\"identity\"]: entry[\"verdict\"] for entry in log}
assert verdicts[\"alice\"] == \"FAIL\", verdicts
assert verdicts[\"bob\"] == \"PASS\", verdicts
'"

check "filter keeps identity on PreflightError (transient)" \
    "$PYRUN -c '
from gtm.platforms.reddit.tools import filter_identities_by_preflight
from gtm.modules import preflight as pf

def fail_fetch(name):
    raise pf.PreflightError(\"simulated 429\")
pf.fetch_reddit_user = fail_fetch

rules = {\"subs\": {\"strict\": {\"min_comment_karma\": 100}}}
safe, log = filter_identities_by_preflight(\"strict\", [\"alice\"], rules=rules)
assert safe == [\"alice\"], safe
assert log[0][\"verdict\"] == \"ERROR\", log
'"

# Sections [4] and [5] tested gtm.agents.promoter source — the agent was
# deleted in the OSS cleanup pass (skills/workflows/reddit-organic-seed.md
# replaces its behavior). The reddit_preflight tool itself is verified by
# checks above.

echo
echo "── Checkpoint 3 result: $PASS passed, $FAIL failed ──"
[ "$FAIL" -eq 0 ]
