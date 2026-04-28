#!/usr/bin/env bash
# Checkpoint 2 e2e: `gtm reddit preflight` CLI command.
# Verifies command is registered, JSON output parseable, exit codes correct.

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

GTM="uv run --quiet gtm"

echo "── Checkpoint 2: gtm reddit preflight CLI ──"

echo "[1] Command registered + help text"
HELP_REDDIT="$($GTM reddit --help 2>&1)"
check "preflight subcommand appears in 'gtm reddit --help'" \
    "echo \"\$HELP_REDDIT\" | grep -q preflight"
HELP_PRE="$($GTM reddit preflight --help 2>&1)"
check "preflight --help mentions identity option" \
    "echo \"\$HELP_PRE\" | grep -q -- '--identity'"

echo "[2] JSON output is parseable"
JSON_OUT="$($GTM reddit preflight ClaudeAI --identity Pale_Stand5217 --json 2>&1)"
JSON_RC=$?
check "JSON output parses + has verdict field" \
    "echo \"\$JSON_OUT\" | uv run --quiet python -c 'import json, sys; d = json.load(sys.stdin); assert d[\"verdict\"] in (\"PASS\",\"BORDERLINE\",\"FAIL\"), d; assert d[\"identity\"] == \"Pale_Stand5217\"'"

echo "[3] Exit code: PASS / BORDERLINE → 0"
$GTM reddit preflight ClaudeAI --identity Pale_Stand5217 --json >/dev/null 2>&1
RC=$?
[ "$RC" -eq 0 ] && ok "ClaudeAI exit code 0 (PASS)" || bad "ClaudeAI exit code 0 (PASS) — got $RC"

$GTM reddit preflight MachineLearning --identity Pale_Stand5217 --json >/dev/null 2>&1
RC=$?
[ "$RC" -eq 0 ] && ok "MachineLearning + Pale_Stand5217 exit 0 (BORDERLINE)" || bad "MachineLearning + Pale_Stand5217 exit 0 — got $RC"

echo "[4] Exit code: FAIL → 1"
$GTM reddit preflight LocalLLaMA --identity Pale_Stand5217 --json >/dev/null 2>&1
RC=$?
[ "$RC" -eq 1 ] && ok "LocalLLaMA (permanent_skip) exit 1 (FAIL)" || bad "LocalLLaMA exit 1 — got $RC"

# Ok_Championship8304 has 7 comment karma, 100 floor → FAIL → exit 1
$GTM reddit preflight MachineLearning --identity Ok_Championship8304 --json >/dev/null 2>&1
RC=$?
[ "$RC" -eq 1 ] && ok "MachineLearning + Ok_Championship8304 exit 1 (FAIL: comment karma 7<100)" || bad "MachineLearning + Ok_Championship8304 expected FAIL — got $RC"

echo "[5] Human-readable output"
HUMAN_OUT="$($GTM reddit preflight ClaudeAI --identity Pale_Stand5217 2>&1)"
check "human output contains 'verdict:' line" \
    "echo \"\$HUMAN_OUT\" | grep -q 'verdict:'"
check "human output contains 'karma:' line" \
    "echo \"\$HUMAN_OUT\" | grep -q 'karma:'"
check "human output contains 'sub: r/' line" \
    "echo \"\$HUMAN_OUT\" | grep -q 'sub: r/'"

echo "[6] Bogus user → exit 2"
$GTM reddit preflight ClaudeAI --identity this_user_definitely_does_not_exist_zzz_999_aaa --json >/dev/null 2>&1
RC=$?
[ "$RC" -eq 2 ] && ok "bogus user exits 2 (PreflightError path)" || bad "bogus user exit 2 — got $RC"

echo
echo "── Checkpoint 2 result: $PASS passed, $FAIL failed ──"
[ "$FAIL" -eq 0 ]
