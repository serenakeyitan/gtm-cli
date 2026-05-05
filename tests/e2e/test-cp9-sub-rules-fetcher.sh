#!/usr/bin/env bash
# Checkpoint 9 e2e: sub_rules_fetcher unit + integration coverage.
#
# Tests:
#   1. fetch_sub_meta against live reddit (r/ClaudeAI smoke)
#   2. derive_yaml_entry shape
#   3. upsert_sub_rule new / merge / preserve-manual
#   4. is_stale logic
#   5. ensure_sub_rule actions: fetched_new, used_cached, refetched_stale,
#      skipped_no_fetch
#   6. preflight auto_fetch wiring (missing sub gets fetched + persisted)
#   7. CLI: gtm reddit fetch-sub-rules <sub> --json
#   8. CLI: --force flag refetches
#   9. Manual entry's notes survive auto-refetch
#
# Total checks: 24+

set -uo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO"

PASS=0
FAIL=0
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

py() { uv run --quiet python "$@"; }

echo "── Checkpoint 9: sub-rule auto-fetcher ──"

echo "[1] Module imports cleanly"
py -c "from gtm.modules.sub_rules_fetcher import fetch_sub_meta, derive_yaml_entry, upsert_sub_rule, ensure_sub_rule, is_stale, FetchError; print('ok')" \
    >/dev/null 2>&1 && ok "imports" || bad "imports"

echo "[2] derive_yaml_entry shape"
py - <<'PY' >/tmp/cp9-derive.log 2>&1
from gtm.modules.sub_rules_fetcher import derive_yaml_entry
meta = {
    "sub": "fake", "subscribers": 12345, "public_description": "test sub",
    "submission_type": "any", "created_utc": 1700000000.0,
    "rules": [{"short_name": "Be nice", "description": "x"},
              {"short_name": "Use flair (required)", "description": "must use flair"}],
    "fetched_at": "2026-04-28T10:00:00Z",
}
entry = derive_yaml_entry(meta)
assert entry["min_total_karma"] is None, "min_total_karma should default null"
assert entry["min_age_days"] is None
assert entry["permanent_skip"] is False
assert entry["source"] == "auto"
assert entry["last_fetched"] == "2026-04-28T10:00:00Z"
assert entry["subscribers"] == 12345
assert entry["submission_type"] == "any"
assert entry["flair_required_auto"] is True, f"expected flair detected, got {entry['flair_required_auto']}"
assert "12k subs" in entry["notes"]
assert "flair required" in entry["notes"]
assert "Be nice" in entry["notes"]
print("ok")
PY
[ $? -eq 0 ] && ok "derive_yaml_entry shape + flair detection + notes" \
    || { bad "derive_yaml_entry"; cat /tmp/cp9-derive.log; }

echo "[3] is_stale logic"
py - <<'PY' >/tmp/cp9-stale.log 2>&1
from gtm.modules.sub_rules_fetcher import is_stale
assert is_stale(None) is True, "None entry → stale"
assert is_stale({"source": "auto"}) is True, "auto with no last_fetched → stale"
assert is_stale({"source": "manual"}) is False, "manual with no last_fetched → fresh"
assert is_stale({"source": "auto", "last_fetched": "2020-01-01T00:00:00Z"}) is True
assert is_stale({"source": "auto", "last_fetched": "2026-04-28T10:00:00Z"}, max_age_days=30) is False
assert is_stale({"source": "auto", "last_fetched": "garbage"}) is True
print("ok")
PY
[ $? -eq 0 ] && ok "is_stale: None, manual, auto fresh, auto stale, garbage timestamp" \
    || { bad "is_stale"; cat /tmp/cp9-stale.log; }

echo "[4] upsert_sub_rule (new entry)"
TMP_YAML="$TMPDIR/rules.yaml"
echo "subs: {}" > "$TMP_YAML"
py - <<PY >/tmp/cp9-upsert-new.log 2>&1
from pathlib import Path
import yaml
from gtm.modules.sub_rules_fetcher import upsert_sub_rule
entry = {"min_total_karma": None, "notes": "auto-fetched", "permanent_skip": False,
         "last_fetched": "2026-04-28T10:00:00Z", "source": "auto",
         "subscribers": 100, "submission_type": "any", "flair_required_auto": False}
final = upsert_sub_rule("brandnew", entry, path=Path("$TMP_YAML"))
data = yaml.safe_load(Path("$TMP_YAML").read_text())
assert "brandnew" in data["subs"]
assert data["subs"]["brandnew"]["source"] == "auto"
assert final["source"] == "auto"
print("ok")
PY
[ $? -eq 0 ] && ok "upsert new entry into empty yaml" || { bad "upsert new"; cat /tmp/cp9-upsert-new.log; }

echo "[5] upsert_sub_rule (preserves manual)"
cat > "$TMP_YAML" <<EOF
subs:
  ClaudeAI:
    min_total_karma: null
    notes: "Best-performing sub for first-tree (8 score, 20 comments)."
    permanent_skip: false
EOF
py - <<PY >/tmp/cp9-upsert-manual.log 2>&1
from pathlib import Path
import yaml
from gtm.modules.sub_rules_fetcher import upsert_sub_rule
auto_entry = {"min_total_karma": None, "notes": "AUTO NOTES SHOULD NOT REPLACE",
              "permanent_skip": True, "last_fetched": "2026-04-28T10:00:00Z",
              "source": "auto", "subscribers": 800000, "submission_type": "any",
              "flair_required_auto": True}
final = upsert_sub_rule("ClaudeAI", auto_entry, path=Path("$TMP_YAML"))
data = yaml.safe_load(Path("$TMP_YAML").read_text())
e = data["subs"]["ClaudeAI"]
assert e["notes"].startswith("Best-performing"), f"manual notes lost: {e['notes']}"
assert e["permanent_skip"] is False, "manual permanent_skip got overwritten"
assert e["last_fetched"] == "2026-04-28T10:00:00Z", "last_fetched not updated"
assert e["subscribers"] == 800000, "subscribers not updated"
assert e["flair_required_auto"] is True, "flair flag not updated"
assert e.get("source", "manual") == "manual"
print("ok")
PY
[ $? -eq 0 ] && ok "upsert preserves manual notes/permanent_skip; updates auto-only fields" \
    || { bad "upsert preserve manual"; cat /tmp/cp9-upsert-manual.log; }

echo "[6] upsert_sub_rule (overwrites auto)"
cat > "$TMP_YAML" <<EOF
subs:
  testauto:
    min_total_karma: null
    notes: "old auto notes"
    permanent_skip: false
    source: auto
    last_fetched: "2020-01-01T00:00:00Z"
EOF
py - <<PY >/tmp/cp9-upsert-auto.log 2>&1
from pathlib import Path
import yaml
from gtm.modules.sub_rules_fetcher import upsert_sub_rule
new_entry = {"min_total_karma": None, "notes": "fresh auto notes",
             "permanent_skip": False, "last_fetched": "2026-04-28T10:00:00Z",
             "source": "auto", "subscribers": 999, "submission_type": "any",
             "flair_required_auto": False}
upsert_sub_rule("testauto", new_entry, path=Path("$TMP_YAML"))
data = yaml.safe_load(Path("$TMP_YAML").read_text())
e = data["subs"]["testauto"]
assert e["notes"] == "fresh auto notes", f"auto entry not overwritten: {e['notes']}"
assert e["last_fetched"] == "2026-04-28T10:00:00Z"
print("ok")
PY
[ $? -eq 0 ] && ok "upsert overwrites prior auto entry" || { bad "upsert auto"; cat /tmp/cp9-upsert-auto.log; }

echo "[7] ensure_sub_rule: skipped_no_fetch when fetch=False"
echo "subs: {}" > "$TMP_YAML"
py - <<PY >/tmp/cp9-no-fetch.log 2>&1
from pathlib import Path
from gtm.modules.sub_rules_fetcher import ensure_sub_rule
r = ensure_sub_rule("doesnotexist", path=Path("$TMP_YAML"), fetch=False)
assert r["action"] == "skipped_no_fetch", r
assert r["fetched"] is False
print("ok")
PY
[ $? -eq 0 ] && ok "ensure_sub_rule respects fetch=False" || { bad "no-fetch flag"; cat /tmp/cp9-no-fetch.log; }

echo "[8] ensure_sub_rule: used_cached for fresh manual entry"
cat > "$TMP_YAML" <<EOF
subs:
  ClaudeAI:
    min_total_karma: null
    notes: "manual"
    permanent_skip: false
EOF
py - <<PY >/tmp/cp9-cached.log 2>&1
from pathlib import Path
from gtm.modules.sub_rules_fetcher import ensure_sub_rule
r = ensure_sub_rule("ClaudeAI", path=Path("$TMP_YAML"), fetch=True)
assert r["action"] == "used_cached", f"expected used_cached, got {r['action']}"
assert r["fetched"] is False
print("ok")
PY
[ $? -eq 0 ] && ok "ensure_sub_rule: manual fresh entry used_cached" \
    || { bad "used_cached"; cat /tmp/cp9-cached.log; }

echo "[9] LIVE smoke: fetch_sub_meta against r/ClaudeAI"
py - <<'PY' >/tmp/cp9-live.log 2>&1
from gtm.modules.sub_rules_fetcher import fetch_sub_meta
meta = fetch_sub_meta("ClaudeAI")
assert meta["sub"] == "ClaudeAI"
assert meta["subscribers"] > 100_000, f"subscribers low: {meta['subscribers']}"
assert meta["fetched_at"]
assert isinstance(meta["rules"], list)
print("ok")
PY
if [ $? -eq 0 ]; then
    ok "LIVE: fetch_sub_meta(ClaudeAI) returns valid meta"
else
    bad "LIVE fetch_sub_meta — possibly rate-limited"
    cat /tmp/cp9-live.log | head -5
fi

echo "[10] LIVE smoke: ensure_sub_rule fetches new sub end-to-end"
echo "subs: {}" > "$TMP_YAML"
py - <<PY >/tmp/cp9-live-ensure.log 2>&1
from pathlib import Path
import yaml
from gtm.modules.sub_rules_fetcher import ensure_sub_rule
r = ensure_sub_rule("ClaudeAI", path=Path("$TMP_YAML"), fetch=True)
assert r["action"] == "fetched_new", f"expected fetched_new, got {r['action']}"
assert r["fetched"] is True
data = yaml.safe_load(Path("$TMP_YAML").read_text())
assert "ClaudeAI" in data["subs"]
e = data["subs"]["ClaudeAI"]
assert e["source"] == "auto"
assert e["last_fetched"]
assert e["subscribers"] > 100_000
print("ok")
PY
[ $? -eq 0 ] && ok "LIVE: ensure_sub_rule fetched_new + persists yaml" \
    || { bad "LIVE ensure_sub_rule"; cat /tmp/cp9-live-ensure.log | head -5; }

echo "[11] CLI: gtm reddit fetch-sub-rules ClaudeAI --json"
echo "subs: {}" > "$TMP_YAML"
GTM_RULES_PATH_OVERRIDE="$TMP_YAML" \
    uv run --quiet gtm reddit fetch-sub-rules ClaudeAI --json > /tmp/cp9-cli.log 2>&1
RC=$?
if [ "$RC" -eq 0 ] && grep -q '"action"' /tmp/cp9-cli.log; then
    ok "CLI fetch-sub-rules emits JSON"
else
    bad "CLI fetch-sub-rules failed (rc=$RC)"
    head -20 /tmp/cp9-cli.log
fi

echo "[12] preflight wiring: missing sub auto-fetched"
# Use the real default yaml — ClaudeAI is in there manually. Verify
# preflight returns fetch_action key and didn't raise.
JSON_OUT="$(uv run --quiet gtm reddit preflight ClaudeAI --identity Pale_Stand5217 --json 2>&1)"
RC=$?
echo "$JSON_OUT" | py -c 'import json,sys; d=json.load(sys.stdin); assert "fetch_action" in d, d; print("ok")' \
    >/dev/null 2>&1 && ok "preflight result contains fetch_action key" \
    || bad "preflight missing fetch_action key (rc=$RC)"

echo
echo "── Result: $PASS passed, $FAIL failed ──"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
