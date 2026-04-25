#!/usr/bin/env bash
# Checkpoint 5 e2e: identity affinity full implementation.
# Verifies: scans real run state, aggregates per (identity, sub), respects removals.

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

echo "── Checkpoint 5: identity affinity full impl ──"

# Set up a tmp runs/ dir with synthetic state.json
TMP="$(mktemp -d)"
mkdir -p "$TMP/run_001" "$TMP/run_002"
cat > "$TMP/run_001/state.json" <<JSON
{
  "completed_at": "2026-04-20T10:00:00Z",
  "promote_results": [
    {"posts": [
      {"identity": "alice", "subreddit": "r/AI", "score": 50, "deleted": false},
      {"identity": "alice", "subreddit": "r/AI", "score": 30, "deleted": false},
      {"identity": "bob",   "subreddit": "r/AI", "score": 5,  "deleted": true}
    ]}
  ]
}
JSON
cat > "$TMP/run_002/state.json" <<JSON
{
  "completed_at": "2026-04-22T10:00:00Z",
  "promote_results": [
    {"posts": [
      {"identity": "carol", "subreddit": "r/python", "score": 100, "deleted": false}
    ]}
  ]
}
JSON

echo "[1] compute_affinity scans runs/ and aggregates"
check "alice has 2 posts in r/AI with avg_score=40" \
    "$PYRUN -c '
from gtm.modules.filters.identity_affinity import compute_affinity
t = compute_affinity(\"$TMP\")
a = t[\"alice\"][\"r/ai\"]
assert a[\"posts\"] == 2, a
assert a[\"avg_score\"] == 40.0, a
assert a[\"any_removed\"] is False
'"

check "bob has any_removed=True in r/AI" \
    "$PYRUN -c '
from gtm.modules.filters.identity_affinity import compute_affinity
t = compute_affinity(\"$TMP\")
assert t[\"bob\"][\"r/ai\"][\"any_removed\"] is True
'"

check "carol picked up from second run dir" \
    "$PYRUN -c '
from gtm.modules.filters.identity_affinity import compute_affinity
t = compute_affinity(\"$TMP\")
assert t[\"carol\"][\"r/python\"][\"posts\"] == 1
'"

echo "[2] best_identity_for_sub respects removals + scores"
check "best for r/AI from [alice, bob] → alice (bob removed)" \
    "$PYRUN -c '
from gtm.modules.filters.identity_affinity import compute_affinity, best_identity_for_sub
t = compute_affinity(\"$TMP\")
assert best_identity_for_sub(\"r/AI\", [\"alice\", \"bob\"], t) == \"alice\"
'"

check "best for r/unknown_sub falls back to first candidate" \
    "$PYRUN -c '
from gtm.modules.filters.identity_affinity import compute_affinity, best_identity_for_sub
t = compute_affinity(\"$TMP\")
assert best_identity_for_sub(\"r/unknown\", [\"dave\", \"eve\"], t) == \"dave\"
'"

check "empty candidates → None" \
    "$PYRUN -c '
from gtm.modules.filters.identity_affinity import best_identity_for_sub
assert best_identity_for_sub(\"r/x\", [], {}) is None
'"

echo "[3] Legacy 'account' field still works (back-compat)"
mkdir -p "$TMP/run_003"
cat > "$TMP/run_003/state.json" <<JSON
{
  "completed_at": "2026-04-23T10:00:00Z",
  "promote_results": [
    {"posts": [
      {"account": "legacy_user", "subreddit": "r/old", "score": 7, "deleted": false}
    ]}
  ]
}
JSON
check "legacy account field is read as identity" \
    "$PYRUN -c '
from gtm.modules.filters.identity_affinity import compute_affinity
t = compute_affinity(\"$TMP\")
assert \"legacy_user\" in t, list(t.keys())
assert t[\"legacy_user\"][\"r/old\"][\"posts\"] == 1
'"

echo "[4] Missing runs_dir returns empty table (no crash)"
check "nonexistent runs dir returns {}" \
    "$PYRUN -c '
from gtm.modules.filters.identity_affinity import compute_affinity
assert compute_affinity(\"/tmp/nonexistent_runs_xyz_abc\") == {}
'"

# cleanup
rm -rf "$TMP"

echo
echo "── Checkpoint 5 result: $PASS passed, $FAIL failed ──"
[ "$FAIL" -eq 0 ]
