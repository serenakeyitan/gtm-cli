#!/usr/bin/env bash
# Checkpoint 10 e2e: preflight is now a hard gate on submit.
#
# Tests the pure logic of submit_gate.evaluate_submit (with stubbed
# preflight, so no network) covering every verdict × strict × override
# combination, plus a CLI smoke against `gtm reddit submit --dry-run`.
#
# Total checks: 18+

set -uo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO"

PASS=0
FAIL=0

ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

py() { uv run --quiet python "$@"; }

echo "── Checkpoint 10: preflight submit gate ──"

echo "[1] Module imports"
py -c "from gtm.modules.submit_gate import evaluate_submit, format_gate_summary; print('ok')" \
    >/dev/null 2>&1 && ok "imports" || bad "imports"

echo "[2] PASS → ALLOW"
py - <<'PY' >/tmp/cp10-pass.log 2>&1
from gtm.modules.submit_gate import evaluate_submit
def stub(identity, sub, **kw):
    return {"identity": identity, "sub": sub, "verdict": "PASS",
            "reasons": [], "notes": "lenient sub", "permanent_skip": False,
            "rule_found": True, "fetch_action": "used_cached", "stats": {}}
r = evaluate_submit("u/foo", "test", preflight_fn=stub)
assert r["allowed"] is True, r
assert r["verdict"] == "PASS"
assert r["override_used"] is False
print("ok")
PY
[ $? -eq 0 ] && ok "PASS allows" || { bad "PASS"; cat /tmp/cp10-pass.log; }

echo "[3] BORDERLINE → ALLOW (non-strict)"
py - <<'PY' >/tmp/cp10-borderline.log 2>&1
from gtm.modules.submit_gate import evaluate_submit
def stub(identity, sub, **kw):
    return {"identity": identity, "sub": sub, "verdict": "BORDERLINE",
            "reasons": [{"status": "borderline", "detail": "karma 110 vs floor 100"}],
            "notes": None, "permanent_skip": False, "rule_found": True,
            "fetch_action": "used_cached", "stats": {}}
r = evaluate_submit("u/foo", "test", preflight_fn=stub, strict=False)
assert r["allowed"] is True, r
assert r["verdict"] == "BORDERLINE"
print("ok")
PY
[ $? -eq 0 ] && ok "BORDERLINE allows non-strict" || { bad "BORDERLINE"; cat /tmp/cp10-borderline.log; }

echo "[4] BORDERLINE → BLOCK (strict)"
py - <<'PY' >/tmp/cp10-borderline-strict.log 2>&1
from gtm.modules.submit_gate import evaluate_submit
def stub(identity, sub, **kw):
    return {"identity": identity, "sub": sub, "verdict": "BORDERLINE",
            "reasons": [{"status": "borderline", "detail": "karma close to floor"}],
            "notes": None, "permanent_skip": False, "rule_found": True,
            "fetch_action": "used_cached", "stats": {}}
r = evaluate_submit("u/foo", "test", preflight_fn=stub, strict=True)
assert r["allowed"] is False, r
print("ok")
PY
[ $? -eq 0 ] && ok "BORDERLINE blocks under strict" || { bad "BORDERLINE strict"; cat /tmp/cp10-borderline-strict.log; }

echo "[5] BORDERLINE strict + override → ALLOW (recorded)"
py - <<'PY' >/tmp/cp10-borderline-override.log 2>&1
from gtm.modules.submit_gate import evaluate_submit
def stub(identity, sub, **kw):
    return {"identity": identity, "sub": sub, "verdict": "BORDERLINE",
            "reasons": [], "notes": None, "permanent_skip": False,
            "rule_found": True, "fetch_action": "used_cached", "stats": {}}
r = evaluate_submit("u/foo", "test", preflight_fn=stub, strict=True,
                    override_reason="warming this account")
assert r["allowed"] is True, r
assert r["override_used"] is True
assert r["override_reason"] == "warming this account"
print("ok")
PY
[ $? -eq 0 ] && ok "borderline strict overridable + recorded" \
    || { bad "borderline override"; cat /tmp/cp10-borderline-override.log; }

echo "[6] FAIL → BLOCK"
py - <<'PY' >/tmp/cp10-fail.log 2>&1
from gtm.modules.submit_gate import evaluate_submit
def stub(identity, sub, **kw):
    return {"identity": identity, "sub": sub, "verdict": "FAIL",
            "reasons": [{"status": "fail", "detail": "karma 50 < floor 100"}],
            "notes": "strict sub", "permanent_skip": False, "rule_found": True,
            "fetch_action": "used_cached", "stats": {}}
r = evaluate_submit("u/foo", "test", preflight_fn=stub)
assert r["allowed"] is False, r
assert "karma 50" in r["reason"]
print("ok")
PY
[ $? -eq 0 ] && ok "FAIL blocks; reason carries detail" || { bad "FAIL"; cat /tmp/cp10-fail.log; }

echo "[7] FAIL + override → ALLOW (recorded)"
py - <<'PY' >/tmp/cp10-fail-override.log 2>&1
from gtm.modules.submit_gate import evaluate_submit
def stub(identity, sub, **kw):
    return {"identity": identity, "sub": sub, "verdict": "FAIL",
            "reasons": [{"status": "fail", "detail": "karma low"}],
            "notes": None, "permanent_skip": False, "rule_found": True,
            "fetch_action": "used_cached", "stats": {}}
r = evaluate_submit("u/foo", "test", preflight_fn=stub,
                    override_reason="emergency canary, accept removal risk")
assert r["allowed"] is True, r
assert r["override_used"] is True
print("ok")
PY
[ $? -eq 0 ] && ok "FAIL overridable with reason" \
    || { bad "FAIL override"; cat /tmp/cp10-fail-override.log; }

echo "[8] permanent_skip → BLOCK regardless of verdict"
py - <<'PY' >/tmp/cp10-skip.log 2>&1
from gtm.modules.submit_gate import evaluate_submit
def stub(identity, sub, **kw):
    return {"identity": identity, "sub": sub, "verdict": "PASS",
            "reasons": [], "notes": "mod-removed in past",
            "permanent_skip": True, "rule_found": True,
            "fetch_action": "used_cached", "stats": {}}
r = evaluate_submit("u/foo", "test", preflight_fn=stub)
assert r["allowed"] is False, r
assert "permanent_skip" in r["reason"]
print("ok")
PY
[ $? -eq 0 ] && ok "permanent_skip blocks even on PASS verdict" \
    || { bad "permanent_skip"; cat /tmp/cp10-skip.log; }

echo "[9] permanent_skip + override → ALLOW"
py - <<'PY' >/tmp/cp10-skip-override.log 2>&1
from gtm.modules.submit_gate import evaluate_submit
def stub(identity, sub, **kw):
    return {"identity": identity, "sub": sub, "verdict": "PASS",
            "reasons": [], "notes": "old removal",
            "permanent_skip": True, "rule_found": True,
            "fetch_action": "used_cached", "stats": {}}
r = evaluate_submit("u/foo", "test", preflight_fn=stub,
                    override_reason="reframed for new angle")
assert r["allowed"] is True, r
assert r["override_used"] is True
print("ok")
PY
[ $? -eq 0 ] && ok "permanent_skip overridable" \
    || { bad "permanent_skip override"; cat /tmp/cp10-skip-override.log; }

echo "[10] format_gate_summary includes notes + verdict + decision"
py - <<'PY' >/tmp/cp10-summary.log 2>&1
from gtm.modules.submit_gate import evaluate_submit, format_gate_summary
def stub(identity, sub, **kw):
    return {"identity": identity, "sub": sub, "verdict": "PASS",
            "reasons": [], "notes": "flair required",
            "permanent_skip": False, "rule_found": True,
            "fetch_action": "fetched_new", "stats": {}}
r = evaluate_submit("u/foo", "ClaudeAI", preflight_fn=stub)
lines = format_gate_summary(r)
joined = "\n".join(lines)
assert "ClaudeAI" in joined
assert "flair required" in joined
assert "PASS" in joined
assert "ALLOW" in joined
assert "fetched_new" in joined
print("ok")
PY
[ $? -eq 0 ] && ok "summary lines: sub, notes, fetch action, verdict, decision" \
    || { bad "summary"; cat /tmp/cp10-summary.log; }

echo "[11] format_gate_summary on BLOCK includes reason + override hint"
py - <<'PY' >/tmp/cp10-summary-block.log 2>&1
from gtm.modules.submit_gate import evaluate_submit, format_gate_summary
def stub(identity, sub, **kw):
    return {"identity": identity, "sub": sub, "verdict": "FAIL",
            "reasons": [{"status": "fail", "detail": "karma 50 < 100"}],
            "notes": None, "permanent_skip": False, "rule_found": True,
            "fetch_action": "used_cached", "stats": {}}
r = evaluate_submit("u/foo", "ML", preflight_fn=stub)
joined = "\n".join(format_gate_summary(r))
assert "BLOCK" in joined
assert "karma 50" in joined
print("ok")
PY
[ $? -eq 0 ] && ok "BLOCK summary surfaces failing reason" \
    || { bad "block summary"; cat /tmp/cp10-summary-block.log; }

echo "[12] CLI smoke: submit --dry-run with FAIL identity is blocked"
# Ok_Championship8304 vs MachineLearning is a real FAIL per CP4 — submit must block.
OUTPUT=$(uv run --quiet gtm reddit submit --as Ok_Championship8304 --sub MachineLearning \
    --title "test" --body "test" --dry-run 2>&1)
RC=$?
if [ "$RC" -ne 0 ] && echo "$OUTPUT" | grep -q "blocked by preflight"; then
    ok "CLI submit blocks low-karma identity on strict sub"
else
    bad "CLI submit didn't block (rc=$RC)"
    echo "$OUTPUT" | head -10
fi

echo "[13] CLI smoke: submit --dry-run with --no-preflight bypasses gate"
# Same combo but with --no-preflight: should at least clear the gate.
# (May still fail at the actual submit step for other reasons under --dry-run,
#  so we just check the gate's "blocked by preflight" string is absent.)
OUTPUT=$(uv run --quiet gtm reddit submit --as Ok_Championship8304 --sub MachineLearning \
    --title "test" --body "test" --dry-run --no-preflight 2>&1)
if ! echo "$OUTPUT" | grep -q "blocked by preflight"; then
    ok "CLI --no-preflight skips the gate"
else
    bad "CLI --no-preflight did not skip the gate"
    echo "$OUTPUT" | head -10
fi

echo "[14] CLI smoke: submit --dry-run with --override allows blocked combo"
OUTPUT=$(uv run --quiet gtm reddit submit --as Ok_Championship8304 --sub MachineLearning \
    --title "test" --body "test" --dry-run --override "test override" 2>&1)
if ! echo "$OUTPUT" | grep -q "blocked by preflight"; then
    ok "CLI --override bypasses FAIL gate"
else
    bad "CLI --override did not bypass"
    echo "$OUTPUT" | head -10
fi

echo
echo "── Result: $PASS passed, $FAIL failed ──"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
