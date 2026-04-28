#!/usr/bin/env bash
# CP2 e2e: Post frontmatter parser + `gtm post list` / `gtm post status`.
# Validates schema enforcement, sort order, round-trip save, CLI filters,
# and graceful empty against a real launch dir (atf-launch).

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
GTM="uv run --quiet gtm"

TMP="$(mktemp -d -t gtm-launch-cp2.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

echo "── CP2: Post frontmatter parser + post list/status ──"
echo "Tmp: $TMP"

# ── Build a synthetic launch dir with 3 products, 3 posts ────────────
LAUNCH="$TMP/launch"
mkdir -p "$LAUNCH/first-tree/posts" "$LAUNCH/repo-gardener/posts" "$LAUNCH/empty-prod/posts"

cat > "$LAUNCH/.gtm-launch.yaml" <<'YAML'
version: 1
products:
  - key: first-tree
    name: first-tree
    tagline: Shared Context for Agent Teams
    status: active
  - key: repo-gardener
    name: repo-gardener
    tagline: Gardener
    status: active
  - key: empty-prod
    name: empty-prod
    tagline: ""
    status: future
directions:
  - key: doc-drift
    label: solve doc drifts
  - key: llm-wiki
    label: llm-wiki
default_identity_by_platform:
  reddit: Pale_Stand5217
dashboard: {}
YAML

# Post 1: live, oldest
cat > "$LAUNCH/first-tree/posts/d1.md" <<'POST'
---
id: d1
product: first-tree
direction: doc-drift
channel: reddit r/AI_Agents
identity: Pale_Stand5217
kind: self
status: live
url: https://reddit.com/r/AI_Agents/comments/abc
live_id: abc
posted_at: 2026-04-20T10:00:00+00:00
metrics:
  score: 12
  comments: 5
  comments_real: 3
  last_checked: 2026-04-25T00:00:00+00:00
note:
---

This is the body of d1. It has multiple lines.

Second paragraph.
POST

# Post 2: live, newer
cat > "$LAUNCH/first-tree/posts/d2.md" <<'POST'
---
id: d2
product: first-tree
direction: llm-wiki
channel: reddit r/LangChain
identity: Pale_Stand5217
kind: image
image: posts/assets/llm-wiki.png
status: live
url: https://reddit.com/r/LangChain/comments/xyz
live_id: xyz
posted_at: 2026-04-25T18:00:00+00:00
metrics:
  score: 42
  comments: 11
  comments_real: 9
  last_checked: 2026-04-26T00:00:00+00:00
note:
---

LLM-wiki body content here.
POST

# Post 3: drafting, no posted_at, optional fields null
cat > "$LAUNCH/repo-gardener/posts/g1.md" <<'POST'
---
id: g1
product: repo-gardener
direction:
channel: reddit r/devops
identity:
kind:
status: drafting
url:
live_id:
posted_at:
metrics:
  score: 0
  comments: 0
note:
---

Draft body.
POST

# ── [1] Module imports ─────────────────────────────────────────────
echo "[1] Module imports"
check "gtm.launch.post imports cleanly" \
    "$PYRUN -c 'from gtm.launch.post import Post, PostError, REQUIRED_FIELDS, STATUS_ENUM, KIND_ENUM'"
check "Post + PostError re-exported from gtm.launch" \
    "$PYRUN -c 'from gtm.launch import Post, PostError'"

# ── [2] Post.load happy path ───────────────────────────────────────
echo "[2] Post.load on a synthetic .md → fields parse correctly"
check "Post.load parses all required + optional fields" \
    "$PYRUN -c '
from pathlib import Path
from gtm.launch import Post
p = Post.load(Path(\"$LAUNCH/first-tree/posts/d1.md\"))
assert p.id == \"d1\", p.id
assert p.product == \"first-tree\", p.product
assert p.channel == \"reddit r/AI_Agents\", p.channel
assert p.status == \"live\", p.status
assert p.kind == \"self\", p.kind
assert p.direction == \"doc-drift\", p.direction
assert p.identity == \"Pale_Stand5217\", p.identity
assert p.score == 12, p.score
assert p.comments == 5, p.comments
assert \"body of d1\" in p.body, p.body[:60]
'"

# ── [3] Optional fields = null parses cleanly ──────────────────────
echo "[3] Post.load with null optional fields parses cleanly"
check "drafting post with null kind/identity/posted_at parses" \
    "$PYRUN -c '
from pathlib import Path
from gtm.launch import Post
p = Post.load(Path(\"$LAUNCH/repo-gardener/posts/g1.md\"))
assert p.id == \"g1\"
assert p.status == \"drafting\"
assert p.kind is None, p.kind
assert p.identity is None, p.identity
assert p.posted_at is None, p.posted_at
assert p.direction is None, p.direction
'"

# ── [4] Missing required field → clear error ───────────────────────
echo "[4] Missing required field raises clear error"
BAD_MISSING="$LAUNCH/first-tree/posts/bad_missing.md"
cat > "$BAD_MISSING" <<'POST'
---
id: bm
product: first-tree
channel: reddit r/foo
---

body
POST
check "load() raises PostError when status is missing" \
    "$PYRUN -c '
from pathlib import Path
from gtm.launch import Post, PostError
try:
    Post.load(Path(\"$BAD_MISSING\"))
except PostError as e:
    assert \"status\" in str(e).lower(), str(e)
else:
    raise SystemExit(\"expected PostError\")
'"
rm -f "$BAD_MISSING"

# ── [5] Bad enum (status=foo) → clear error ────────────────────────
echo "[5] Bad status enum raises clear error"
BAD_STATUS="$LAUNCH/first-tree/posts/bad_status.md"
cat > "$BAD_STATUS" <<'POST'
---
id: bs
product: first-tree
channel: reddit r/foo
status: foo
---

body
POST
check "load() raises PostError on status=foo" \
    "$PYRUN -c '
from pathlib import Path
from gtm.launch import Post, PostError
try:
    Post.load(Path(\"$BAD_STATUS\"))
except PostError as e:
    assert \"status\" in str(e).lower(), str(e)
    assert \"foo\" in str(e), str(e)
else:
    raise SystemExit(\"expected PostError\")
'"
rm -f "$BAD_STATUS"

# ── [5b] Bad kind enum → clear error ───────────────────────────────
BAD_KIND="$LAUNCH/first-tree/posts/bad_kind.md"
cat > "$BAD_KIND" <<'POST'
---
id: bk
product: first-tree
channel: reddit r/foo
status: drafting
kind: video
---

body
POST
check "load() raises PostError on kind=video (not in enum)" \
    "$PYRUN -c '
from pathlib import Path
from gtm.launch import Post, PostError
try:
    Post.load(Path(\"$BAD_KIND\"))
except PostError as e:
    assert \"kind\" in str(e).lower(), str(e)
else:
    raise SystemExit(\"expected PostError\")
'"
rm -f "$BAD_KIND"

# ── [6] Post.find_all returns posts sorted newest first ────────────
echo "[6] find_all sort order: newest posted_at first, drafts last"
check "find_all sorts d2 (newer) before d1 (older); g1 (draft) last" \
    "$PYRUN -c '
from pathlib import Path
from gtm.launch import LaunchDir, Post
ld = LaunchDir.load(Path(\"$LAUNCH\"))
posts = Post.find_all(ld)
ids = [p.id for p in posts]
assert ids == [\"d2\", \"d1\", \"g1\"], ids
'"

# ── [7] Post.save round-trip ───────────────────────────────────────
echo "[7] Post.save round-trips"
ROUND="$TMP/round.md"
check "load → save → load produces identical fields" \
    "$PYRUN -c '
import shutil
from pathlib import Path
from gtm.launch import Post
shutil.copy(\"$LAUNCH/first-tree/posts/d1.md\", \"$ROUND\")
p1 = Post.load(Path(\"$ROUND\"))
p1.save()
p2 = Post.load(Path(\"$ROUND\"))
assert p1.frontmatter == p2.frontmatter, (p1.frontmatter, p2.frontmatter)
assert p1.body.strip() == p2.body.strip(), (p1.body, p2.body)
'"

# ── [8] gtm post list ──────────────────────────────────────────────
echo "[8] gtm post list against synthetic launch"
$GTM post list --launch "$LAUNCH" >"$TMP/list.out" 2>&1 || bad "post list ran"
check "list shows d1" "grep -q ' d1 ' '$TMP/list.out' || grep -q '│ d1' '$TMP/list.out' || grep -q 'd1' '$TMP/list.out'"
check "list shows d2" "grep -q 'd2' '$TMP/list.out'"
check "list shows g1" "grep -q 'g1' '$TMP/list.out'"
check "list footer says 3 posts" "grep -q '3 posts' '$TMP/list.out'"

# ── [9] gtm post list --status filter ──────────────────────────────
echo "[9] gtm post list --status drafting filters"
$GTM post list --launch "$LAUNCH" --status drafting >"$TMP/list_draft.out" 2>&1
check "drafting filter shows g1" "grep -q 'g1' '$TMP/list_draft.out'"
check "drafting filter hides d1" "! grep -q ' d1 ' '$TMP/list_draft.out' && ! grep -q '│ d1' '$TMP/list_draft.out'"
check "drafting filter footer says 1 post" "grep -q '1 post' '$TMP/list_draft.out'"

# ── [10] gtm post list --product filter ────────────────────────────
echo "[10] gtm post list --product first-tree filters"
$GTM post list --launch "$LAUNCH" --product first-tree >"$TMP/list_ft.out" 2>&1
check "product=first-tree shows d1" "grep -q 'd1' '$TMP/list_ft.out'"
check "product=first-tree shows d2" "grep -q 'd2' '$TMP/list_ft.out'"
check "product=first-tree hides g1" "! grep -q 'g1' '$TMP/list_ft.out'"

# ── [11] gtm post list --direction filter ──────────────────────────
echo "[11] gtm post list --direction llm-wiki filters"
$GTM post list --launch "$LAUNCH" --direction llm-wiki >"$TMP/list_dir.out" 2>&1
check "direction=llm-wiki shows d2" "grep -q 'd2' '$TMP/list_dir.out'"
check "direction=llm-wiki hides d1" "! grep -q ' d1 ' '$TMP/list_dir.out' && ! grep -q '│ d1' '$TMP/list_dir.out'"

# ── [12] gtm post status <slug> ────────────────────────────────────
echo "[12] gtm post status <slug> prints metadata"
$GTM post status d1 --launch "$LAUNCH" >"$TMP/status.out" 2>&1
check "status output mentions slug d1" "grep -q 'd1' '$TMP/status.out'"
check "status output shows channel" "grep -q 'reddit r/AI_Agents' '$TMP/status.out'"
check "status output shows score 12" "grep -q '12' '$TMP/status.out'"
check "status output shows body length" "grep -q 'Body length' '$TMP/status.out'"

# ── [13] gtm post status <missing> errors with hint ────────────────
echo "[13] gtm post status <missing-slug> errors with hint"
$GTM post status nonexistent --launch "$LAUNCH" >"$TMP/status_miss.out" 2>&1 \
    && bad "status should fail on missing slug" \
    || ok "status exits non-zero on missing slug"
check "missing-slug error mentions 'Hint'" "grep -qi 'hint' '$TMP/status_miss.out'"

# ── [14] atf-launch graceful empty ─────────────────────────────────
echo "[14] atf-launch (no .md posts yet) prints '0 posts' gracefully"
if [ -f "/Users/keyitan/atf-launch/.gtm-launch.yaml" ]; then
    $GTM post list --launch /Users/keyitan/atf-launch >"$TMP/atf.out" 2>&1
    EXIT=$?
    if [ $EXIT -eq 0 ]; then
        ok "atf-launch post list exited 0 (no crash)"
    else
        bad "atf-launch post list crashed (exit $EXIT)"
        cat "$TMP/atf.out"
    fi
    check "atf-launch output says '0 posts'" "grep -q '0 posts' '$TMP/atf.out'"
else
    echo "  ⚠ skip — atf-launch not linked, no .gtm-launch.yaml"
fi

echo
echo "── CP2 result: $PASS passed, $FAIL failed ──"
[ "$FAIL" -eq 0 ]
