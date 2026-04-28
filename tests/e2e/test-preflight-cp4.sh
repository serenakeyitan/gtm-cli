#!/usr/bin/env bash
# Checkpoint 4 e2e: full integration smoke.
# Re-runs CP1+CP2+CP3, plus an end-to-end real-data check confirming
# u/Pale_Stand5217 vs r/MachineLearning lands on BORDERLINE.

set -uo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO"

PASS=0
FAIL=0

ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

run_prior() {
    local name="$1"; local script="$2"
    if "$script" >/tmp/preflight-$name.log 2>&1; then
        local n
        n=$(grep -oE '[0-9]+ passed' /tmp/preflight-$name.log | head -1 | grep -oE '[0-9]+')
        ok "$name suite: $n passed"
    else
        bad "$name suite (see /tmp/preflight-$name.log)"
    fi
}

echo "── Checkpoint 4: full integration smoke ──"

echo "[1] Re-run prior checkpoints"
run_prior "CP1" "$REPO/tests/e2e/test-preflight-cp1.sh"
run_prior "CP2" "$REPO/tests/e2e/test-preflight-cp2.sh"
run_prior "CP3" "$REPO/tests/e2e/test-preflight-cp3.sh"

echo "[2] End-to-end real-data verdict"
JSON_OUT="$(uv run --quiet gtm reddit preflight MachineLearning --identity Pale_Stand5217 --json 2>&1)"
RC=$?
VERDICT="$(echo "$JSON_OUT" | uv run --quiet python -c 'import json,sys; print(json.load(sys.stdin)["verdict"])')"
[ "$VERDICT" = "BORDERLINE" ] && ok "Pale_Stand5217 vs MachineLearning → BORDERLINE (real data)" \
    || bad "Pale_Stand5217 vs MachineLearning expected BORDERLINE, got $VERDICT"
[ "$RC" -eq 0 ] && ok "BORDERLINE exit code 0" || bad "BORDERLINE exit code 0 — got $RC"

echo "[3] End-to-end real-data: low-karma account vs strict sub → FAIL"
uv run --quiet gtm reddit preflight MachineLearning --identity Ok_Championship8304 --json >/dev/null 2>&1
RC=$?
[ "$RC" -eq 1 ] && ok "Ok_Championship8304 vs MachineLearning → FAIL (exit 1)" \
    || bad "Ok_Championship8304 vs MachineLearning expected FAIL — got exit $RC"

echo "[4] End-to-end real-data: lenient sub → PASS"
uv run --quiet gtm reddit preflight ClaudeAI --identity Ok_Championship8304 --json >/dev/null 2>&1
RC=$?
[ "$RC" -eq 0 ] && ok "Ok_Championship8304 vs ClaudeAI → PASS (no rules)" \
    || bad "Ok_Championship8304 vs ClaudeAI expected PASS — got exit $RC"

echo "[5] Memory file written"
MEMFILE="$HOME/.claude/projects/-Users-keyitan/memory/feedback_preflight_before_post.md"
[ -f "$MEMFILE" ] && ok "memory file exists at $MEMFILE" \
    || bad "memory file missing at $MEMFILE"
[ -f "$MEMFILE" ] && grep -q '\*\*Why:\*\*' "$MEMFILE" && ok "memory file has Why: section" \
    || bad "memory file missing Why: section"
[ -f "$MEMFILE" ] && grep -q '\*\*How to apply:\*\*' "$MEMFILE" && ok "memory file has How to apply: section" \
    || bad "memory file missing How to apply: section"

echo
echo "── Checkpoint 4 result: $PASS passed, $FAIL failed ──"
[ "$FAIL" -eq 0 ]
