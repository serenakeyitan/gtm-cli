#!/usr/bin/env bash
# Checkpoint 1 e2e: preflight module — fetch, load rules, evaluate, top-level preflight.
# Verifies imports, synthetic PASS/BORDERLINE/FAIL evaluation, real fetch
# against u/Pale_Stand5217 and u/Ok_Championship8304.

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

echo "── Checkpoint 1: preflight module ──"

echo "[1] Module imports"
check "gtm.modules.preflight imports" \
    "$PYRUN -c 'from gtm.modules.preflight import fetch_reddit_user, load_sub_rules, evaluate, preflight, PreflightError'"

echo "[2] Rules loading"
check "load_sub_rules returns subs dict with MachineLearning" \
    "$PYRUN -c '
from gtm.modules.preflight import load_sub_rules
r = load_sub_rules()
assert \"subs\" in r
assert \"MachineLearning\" in r[\"subs\"]
assert r[\"subs\"][\"MachineLearning\"][\"min_comment_karma\"] == 100
'"

echo "[3] Synthetic evaluate logic"
check "PASS: stats far above all floors" \
    "$PYRUN -c '
from gtm.modules.preflight import evaluate
rule = {\"min_total_karma\": 100, \"min_comment_karma\": 100, \"min_age_days\": 60}
stats = {\"total_karma\": 5000, \"comment_karma\": 5000, \"age_days\": 1000, \"link_karma\": 0}
out = evaluate(stats, rule)
assert out[\"verdict\"] == \"PASS\", out
'"

check "BORDERLINE: comment karma 103 vs floor 100 (3% margin)" \
    "$PYRUN -c '
from gtm.modules.preflight import evaluate
rule = {\"min_comment_karma\": 100, \"min_total_karma\": 100, \"min_age_days\": 60}
stats = {\"total_karma\": 1796, \"comment_karma\": 103, \"link_karma\": 1693, \"age_days\": 945}
out = evaluate(stats, rule)
assert out[\"verdict\"] == \"BORDERLINE\", out
'"

check "FAIL: comment karma 50 below floor 100" \
    "$PYRUN -c '
from gtm.modules.preflight import evaluate
rule = {\"min_comment_karma\": 100, \"min_total_karma\": 100, \"min_age_days\": 60}
stats = {\"total_karma\": 200, \"comment_karma\": 50, \"link_karma\": 150, \"age_days\": 200}
out = evaluate(stats, rule)
assert out[\"verdict\"] == \"FAIL\", out
assert any(r[\"status\"] == \"fail\" for r in out[\"reasons\"]), out
'"

check "Empty rule → PASS" \
    "$PYRUN -c '
from gtm.modules.preflight import evaluate
out = evaluate({\"total_karma\": 0}, {})
assert out[\"verdict\"] == \"PASS\", out
'"

echo "[4] preflight() with injected stats (no network)"
check "preflight returns BORDERLINE for Pale_Stand5217-like stats vs MachineLearning" \
    "$PYRUN -c '
from gtm.modules.preflight import preflight, load_sub_rules
rules = load_sub_rules()
stats = {\"total_karma\": 1796, \"comment_karma\": 103, \"link_karma\": 1693, \"age_days\": 945, \"username\": \"Pale_Stand5217\"}
out = preflight(\"Pale_Stand5217\", \"MachineLearning\", rules=rules, stats=stats)
assert out[\"verdict\"] == \"BORDERLINE\", out
assert out[\"rule_found\"] is True
assert out[\"notes\"] is not None
'"

check "preflight returns FAIL when rule has permanent_skip" \
    "$PYRUN -c '
from gtm.modules.preflight import preflight, load_sub_rules
rules = load_sub_rules()
stats = {\"total_karma\": 5000, \"comment_karma\": 5000, \"link_karma\": 5000, \"age_days\": 9999, \"username\": \"x\"}
out = preflight(\"x\", \"LocalLLaMA\", rules=rules, stats=stats)
assert out[\"verdict\"] == \"FAIL\", out
assert out[\"permanent_skip\"] is True
'"

check "preflight returns PASS for unknown sub (no rule)" \
    "$PYRUN -c '
from gtm.modules.preflight import preflight, load_sub_rules
rules = load_sub_rules()
stats = {\"total_karma\": 100, \"comment_karma\": 50, \"link_karma\": 50, \"age_days\": 30, \"username\": \"x\"}
out = preflight(\"x\", \"some_random_unmapped_sub\", rules=rules, stats=stats)
assert out[\"verdict\"] == \"PASS\", out
assert out[\"rule_found\"] is False
'"

echo "[5] Live fetch against real accounts"
check "fetch_reddit_user(Pale_Stand5217) returns plausible karma" \
    "$PYRUN -c '
from gtm.modules.preflight import fetch_reddit_user
s = fetch_reddit_user(\"Pale_Stand5217\")
assert s[\"total_karma\"] > 100, s
assert s[\"age_days\"] > 30, s
'"

check "fetch_reddit_user(Ok_Championship8304) returns plausible karma" \
    "$PYRUN -c '
from gtm.modules.preflight import fetch_reddit_user
s = fetch_reddit_user(\"Ok_Championship8304\")
assert s[\"total_karma\"] >= 1, s
assert s[\"age_days\"] >= 1, s
'"

check "fetch_reddit_user raises PreflightError on bogus user" \
    "$PYRUN -c '
from gtm.modules.preflight import fetch_reddit_user, PreflightError
try:
    fetch_reddit_user(\"this_user_definitely_does_not_exist_zzz_999_aaa\")
    raise AssertionError(\"expected PreflightError\")
except PreflightError:
    pass
'"

echo
echo "── Checkpoint 1 result: $PASS passed, $FAIL failed ──"
[ "$FAIL" -eq 0 ]
