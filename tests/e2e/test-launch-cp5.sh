#!/usr/bin/env bash
# CP5 e2e: `gtm post sync` — engagement refresh + bot/OP filtering.
# All Reddit JSON fetches are mocked via patching urllib.request.urlopen.

set -uo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO"

PASS=0
FAIL=0

ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

PYRUN="uv run --quiet python"

TMP="$(mktemp -d -t gtm-launch-cp5.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

echo "── CP5: gtm post sync ──"
echo "Tmp: $TMP"

# ── Build a synthetic launch dir with mixed posts ────────────────────
LAUNCH="$TMP/launch"
mkdir -p "$LAUNCH/my-product/posts"

cat > "$LAUNCH/.gtm-launch.yaml" <<'YAML'
version: 1
products:
  - key: my-product
    name: my-product
    tagline: Test product
    status: active
directions:
  - key: doc-drift
    label: solve doc drifts
default_identity_by_platform:
  reddit: Pale_Stand5217
dashboard: {}
YAML

# Live post #1 — has live_id, prior metrics to check delta
cat > "$LAUNCH/my-product/posts/2026-04-25-live-one.md" <<'POST'
---
id: p1
product: my-product
direction: doc-drift
channel: reddit r/test
identity: Pale_Stand5217
kind: self
status: live
url: https://reddit.com/r/test/comments/abc111/title/
live_id: abc111
posted_at: 2026-04-25T10:00:00Z
metrics:
  score: 2
  comments: 1
  comments_real: 0
  last_checked: 2026-04-25T11:00:00Z
note: null
---
body of live post one.
POST

# Live post #2 — no comments_real field at all (backfill check)
cat > "$LAUNCH/my-product/posts/2026-04-25-live-two.md" <<'POST'
---
id: p2
product: my-product
direction: doc-drift
channel: reddit r/test
identity: Pale_Stand5217
kind: self
status: live
url: https://reddit.com/r/test/comments/def222/title/
live_id: def222
posted_at: 2026-04-25T10:00:00Z
metrics:
  score: 0
  comments: 0
note: null
---
body two.
POST

# Drafting post — should be skipped on bulk sync
cat > "$LAUNCH/my-product/posts/2026-04-26-draft.md" <<'POST'
---
id: p3
product: my-product
direction: doc-drift
channel: reddit r/test
identity: Pale_Stand5217
kind: self
status: drafting
url: null
live_id: null
posted_at: null
metrics:
  score: 0
  comments: 0
  comments_real: 0
  last_checked: null
note: null
---
not yet posted.
POST

# Live post — no live_id, no url either (graceful failure)
cat > "$LAUNCH/my-product/posts/2026-04-25-live-no-id.md" <<'POST'
---
id: p4
product: my-product
direction: doc-drift
channel: reddit r/test
identity: Pale_Stand5217
kind: self
status: live
url: null
live_id: null
posted_at: 2026-04-25T10:00:00Z
metrics:
  score: 0
  comments: 0
  comments_real: 0
  last_checked: null
note: null
---
broken state.
POST

# Live post — for testing 'removed' transition
cat > "$LAUNCH/my-product/posts/2026-04-25-live-will-remove.md" <<'POST'
---
id: p5
product: my-product
direction: doc-drift
channel: reddit r/test
identity: Pale_Stand5217
kind: self
status: live
url: https://reddit.com/r/test/comments/rem555/title/
live_id: rem555
posted_at: 2026-04-25T10:00:00Z
metrics:
  score: 1
  comments: 0
  comments_real: 0
  last_checked: null
note: null
---
will be removed.
POST


# ── [1] Module imports ───────────────────────────────────────────────
echo "[1] Module imports"
$PYRUN -c "from gtm.launch.sync import fetch_comments_json, parse_listing, apply_sync_to_frontmatter, resolve_live_id, SyncFetchError, SyncResult, now_iso_utc" \
    >/dev/null 2>&1 && ok "gtm.launch.sync imports cleanly" || bad "gtm.launch.sync imports cleanly"

$PYRUN -c "from gtm.launch import sync; assert hasattr(sync, 'parse_listing')" \
    >/dev/null 2>&1 && ok "gtm.launch re-exports sync module" || bad "gtm.launch re-exports sync module"

# ── [2] resolve_live_id prefers live_id, falls back to url ───────────
echo "[2] resolve_live_id"
$PYRUN -c "
from gtm.launch.sync import resolve_live_id
assert resolve_live_id({'live_id': 'abc'}) == 'abc'
assert resolve_live_id({'url': 'https://reddit.com/r/x/comments/zzz999/t/'}) == 'zzz999'
assert resolve_live_id({'live_url': 'https://reddit.com/r/x/comments/yyy888/t/'}) == 'yyy888'
assert resolve_live_id({}) is None
" >/dev/null 2>&1 && ok "resolve_live_id handles live_id, url, live_url, missing" || bad "resolve_live_id handles live_id, url, live_url, missing"

# ── [3] parse_listing excludes AutoModerator, OP, [deleted] ──────────
echo "[3] parse_listing exclusion rules"
$PYRUN -c "
from gtm.launch.sync import parse_listing
payload = [
  {'data': {'children': [{'data': {'score': 8, 'num_comments': 6, 'subreddit': 'ClaudeAI', 'removed_by_category': None}}]}},
  {'data': {'children': [
    {'kind': 't1', 'data': {'author': 'real_user_a'}},
    {'kind': 't1', 'data': {'author': 'real_user_b'}},
    {'kind': 't1', 'data': {'author': 'AutoModerator'}},
    {'kind': 't1', 'data': {'author': 'Pale_Stand5217'}},
    {'kind': 't1', 'data': {'author': '[deleted]'}},
    {'kind': 'more', 'data': {'author': 'should_not_count'}},
  ]}},
]
r = parse_listing(payload, op_identity='Pale_Stand5217')
assert r.score == 8, r.score
assert r.comments == 6, r.comments
assert r.comments_real == 2, r.comments_real
assert r.subreddit == 'ClaudeAI', r.subreddit
assert r.removed_by_category is None
" >/dev/null 2>&1 && ok "parse_listing excludes AutoModerator/OP/[deleted]/more" \
                 || bad "parse_listing excludes AutoModerator/OP/[deleted]/more"

# ── [4] parse_listing surfaces removed_by_category ───────────────────
echo "[4] parse_listing reports removed_by_category"
$PYRUN -c "
from gtm.launch.sync import parse_listing
payload = [
  {'data': {'children': [{'data': {'score': 0, 'num_comments': 0, 'subreddit': 'x', 'removed_by_category': 'moderator'}}]}},
  {'data': {'children': []}},
]
r = parse_listing(payload, op_identity=None)
assert r.removed_by_category == 'moderator', r.removed_by_category
" >/dev/null 2>&1 && ok "parse_listing reports removed_by_category" \
                 || bad "parse_listing reports removed_by_category"

# ── [5] apply_sync_to_frontmatter writes metrics + last_checked ──────
echo "[5] apply_sync_to_frontmatter"
$PYRUN -c "
from gtm.launch.sync import apply_sync_to_frontmatter, SyncResult, now_iso_utc
from datetime import datetime, timezone
fm = {'status': 'live', 'metrics': {'score': 1, 'comments': 0}}
r = SyncResult(live_id='x', score=8, comments=6, comments_real=2, subreddit='x', removed_by_category=None)
out = apply_sync_to_frontmatter(fm, r)
assert out['metrics']['score'] == 8
assert out['metrics']['comments'] == 6
assert out['metrics']['comments_real'] == 2
assert out['metrics']['last_checked'].endswith('Z')
assert out['status'] == 'live'  # unchanged
# Removed → status flip
r2 = SyncResult(live_id='x', score=0, comments=0, comments_real=0, subreddit='x', removed_by_category='moderator')
out2 = apply_sync_to_frontmatter(fm, r2)
assert out2['status'] == 'removed'
assert 'moderator' in out2['note']
# Within 5s of now
ts = out['metrics']['last_checked'].replace('Z','+00:00')
delta = (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds()
assert abs(delta) < 5, delta
" >/dev/null 2>&1 && ok "apply_sync_to_frontmatter mutates metrics + ISO last_checked, flips removed" \
                 || bad "apply_sync_to_frontmatter mutates metrics + ISO last_checked, flips removed"

# ── [6] Sync one post by --slug → frontmatter updates ────────────────
echo "[6] gtm post sync --slug → frontmatter has new score/comments/comments_real"
$PYRUN -c "
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from gtm.cli import main
from gtm.launch import Post
from pathlib import Path

target = Path('$LAUNCH/my-product/posts/2026-04-25-live-one.md')

fake_resp = MagicMock()
fake_resp.read.return_value = b'[{\"data\": {\"children\": [{\"data\": {\"score\": 8, \"num_comments\": 6, \"subreddit\": \"test\", \"removed_by_category\": null}}]}}, {\"data\": {\"children\": [{\"kind\": \"t1\", \"data\": {\"author\": \"real_user\"}}, {\"kind\": \"t1\", \"data\": {\"author\": \"AutoModerator\"}}, {\"kind\": \"t1\", \"data\": {\"author\": \"Pale_Stand5217\"}}]}}]'

with patch('urllib.request.urlopen', return_value=fake_resp):
    r = CliRunner().invoke(main, ['post', 'sync', '--slug', 'p1', '--launch', '$LAUNCH'])
    assert r.exit_code == 0, (r.exit_code, r.output)

p = Post.load(target)
assert p.score == 8, p.score
assert p.comments == 6, p.comments
assert p.metrics['comments_real'] == 1, p.metrics
assert p.metrics['last_checked'].endswith('Z'), p.metrics
" >/dev/null 2>&1 && ok "sync by --slug updates score/comments/comments_real" \
                 || bad "sync by --slug updates score/comments/comments_real"

# ── [7] comments_real correctly excludes AutoModerator/OP/[deleted] ──
echo "[7] comments_real exclusion (end-to-end via CLI)"
$PYRUN -c "
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from gtm.cli import main
from gtm.launch import Post
from pathlib import Path

target = Path('$LAUNCH/my-product/posts/2026-04-25-live-two.md')
fake_resp = MagicMock()
fake_resp.read.return_value = b'[{\"data\": {\"children\": [{\"data\": {\"score\": 10, \"num_comments\": 5, \"subreddit\": \"test\", \"removed_by_category\": null}}]}}, {\"data\": {\"children\": [{\"kind\": \"t1\", \"data\": {\"author\": \"alice\"}}, {\"kind\": \"t1\", \"data\": {\"author\": \"bob\"}}, {\"kind\": \"t1\", \"data\": {\"author\": \"AutoModerator\"}}, {\"kind\": \"t1\", \"data\": {\"author\": \"Pale_Stand5217\"}}, {\"kind\": \"t1\", \"data\": {\"author\": \"[deleted]\"}}]}}]'

with patch('urllib.request.urlopen', return_value=fake_resp):
    r = CliRunner().invoke(main, ['post', 'sync', '--slug', 'p2', '--launch', '$LAUNCH'])
    assert r.exit_code == 0, (r.exit_code, r.output)

p = Post.load(target)
assert p.metrics['comments_real'] == 2, ('should be 2 (alice+bob), got', p.metrics['comments_real'])
" >/dev/null 2>&1 && ok "CLI excludes AutoModerator + OP + [deleted]" \
                 || bad "CLI excludes AutoModerator + OP + [deleted]"

# ── [8] comments_real backfill on post that lacked the field ─────────
echo "[8] backfill: post with no comments_real field gets one"
$PYRUN -c "
from gtm.launch import Post
from pathlib import Path
p = Post.load(Path('$LAUNCH/my-product/posts/2026-04-25-live-two.md'))
assert 'comments_real' in p.metrics, p.metrics
" >/dev/null 2>&1 && ok "comments_real field is backfilled" \
                 || bad "comments_real field is backfilled"

# ── [9] Bulk sync: only live posts touched, drafts skipped ───────────
echo "[9] gtm post sync (no slug) → only live posts touched"
$PYRUN -c "
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from gtm.cli import main
from gtm.launch import Post
from pathlib import Path

draft_path = Path('$LAUNCH/my-product/posts/2026-04-26-draft.md')
draft_before = draft_path.read_text()

# Need to handle 3 live posts — p1, p2, p5 (p4 has no live_id, fails before fetch)
fake_resp = MagicMock()
fake_resp.read.return_value = b'[{\"data\": {\"children\": [{\"data\": {\"score\": 3, \"num_comments\": 1, \"subreddit\": \"test\", \"removed_by_category\": null}}]}}, {\"data\": {\"children\": [{\"kind\": \"t1\", \"data\": {\"author\": \"alice\"}}]}}]'

with patch('urllib.request.urlopen', return_value=fake_resp):
    r = CliRunner().invoke(main, ['post', 'sync', '--launch', '$LAUNCH'])
    # exit 0 even with per-post failure (p4)
    assert r.exit_code == 0, (r.exit_code, r.output)

# Draft must be untouched
assert draft_path.read_text() == draft_before, 'drafting post was mutated!'
draft = Post.load(draft_path)
assert draft.status == 'drafting'
assert draft.metrics.get('last_checked') is None, draft.metrics
" >/dev/null 2>&1 && ok "bulk sync skips drafts, exits 0 on per-post failure" \
                 || bad "bulk sync skips drafts, exits 0 on per-post failure"

# ── [10] removed_by_category set → status flips to removed + note ────
echo "[10] removed post → status=removed + note"
$PYRUN -c "
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from gtm.cli import main
from gtm.launch import Post
from pathlib import Path

target = Path('$LAUNCH/my-product/posts/2026-04-25-live-will-remove.md')
fake_resp = MagicMock()
fake_resp.read.return_value = b'[{\"data\": {\"children\": [{\"data\": {\"score\": 0, \"num_comments\": 0, \"subreddit\": \"test\", \"removed_by_category\": \"moderator\"}}]}}, {\"data\": {\"children\": []}}]'

with patch('urllib.request.urlopen', return_value=fake_resp):
    r = CliRunner().invoke(main, ['post', 'sync', '--slug', 'p5', '--launch', '$LAUNCH'])
    assert r.exit_code == 0, (r.exit_code, r.output)

p = Post.load(target)
assert p.status == 'removed', p.status
assert p.frontmatter.get('note') and 'moderator' in p.frontmatter['note'], p.frontmatter
" >/dev/null 2>&1 && ok "removed post flipped to status=removed with note" \
                 || bad "removed post flipped to status=removed with note"

# ── [11] Network error → graceful note, doesn't crash ────────────────
echo "[11] network 404/timeout → note written, no crash"
$PYRUN -c "
import urllib.error
from unittest.mock import patch
from click.testing import CliRunner
from gtm.cli import main
from gtm.launch import Post
from pathlib import Path

target = Path('$LAUNCH/my-product/posts/2026-04-25-live-one.md')

def boom(*a, **kw):
    raise urllib.error.HTTPError('http://x', 404, 'Not Found', {}, None)

with patch('urllib.request.urlopen', side_effect=boom):
    r = CliRunner().invoke(main, ['post', 'sync', '--slug', 'p1', '--launch', '$LAUNCH'])
    # exit 0 — per-post failure isn't a run failure
    assert r.exit_code == 0, (r.exit_code, r.output)

p = Post.load(target)
assert p.frontmatter.get('note') and 'sync failed' in p.frontmatter['note'], p.frontmatter
" >/dev/null 2>&1 && ok "404 → graceful note, exit 0" || bad "404 → graceful note, exit 0"

# ── [12] Missing live_id → graceful error per-post ───────────────────
echo "[12] missing live_id → graceful skip with note"
$PYRUN -c "
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from gtm.cli import main
from gtm.launch import Post
from pathlib import Path

target = Path('$LAUNCH/my-product/posts/2026-04-25-live-no-id.md')
# urlopen shouldn't even be called; but patch it to make sure
with patch('urllib.request.urlopen', return_value=MagicMock()):
    r = CliRunner().invoke(main, ['post', 'sync', '--slug', 'p4', '--launch', '$LAUNCH'])
    assert r.exit_code == 0, (r.exit_code, r.output)

p = Post.load(target)
assert p.frontmatter.get('note') and 'live_id' in p.frontmatter['note'], p.frontmatter
" >/dev/null 2>&1 && ok "missing live_id → graceful skip with note" \
                 || bad "missing live_id → graceful skip with note"

# ── [13] --slug nonexistent → error with hint ────────────────────────
echo "[13] --slug nonexistent → error with hint"
$PYRUN -c "
from click.testing import CliRunner
from gtm.cli import main
r = CliRunner().invoke(main, ['post', 'sync', '--slug', 'no-such-slug', '--launch', '$LAUNCH'])
assert r.exit_code == 1, (r.exit_code, r.output)
assert 'No post found' in r.output, r.output
assert 'gtm post list' in r.output, r.output
" >/dev/null 2>&1 && ok "nonexistent slug → exit 1 with hint" || bad "nonexistent slug → exit 1 with hint"

# ── [14] Score delta computed correctly + table summary printed ──────
echo "[14] table summary printed with correct delta"
$PYRUN -c "
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from gtm.cli import main

# Reset live-one to known starting score=2
import yaml
from pathlib import Path
target = Path('$LAUNCH/my-product/posts/2026-04-25-live-one.md')
text = target.read_text()
# Re-write with score=2 to make delta predictable (it may have been set higher by earlier tests)
new_text = '''---
id: p1
product: my-product
direction: doc-drift
channel: reddit r/test
identity: Pale_Stand5217
kind: self
status: live
url: https://reddit.com/r/test/comments/abc111/title/
live_id: abc111
posted_at: 2026-04-25T10:00:00Z
metrics:
  score: 2
  comments: 1
  comments_real: 0
  last_checked: 2026-04-25T11:00:00Z
note: null
---
body of live post one.
'''
target.write_text(new_text)

fake_resp = MagicMock()
fake_resp.read.return_value = b'[{\"data\": {\"children\": [{\"data\": {\"score\": 8, \"num_comments\": 6, \"subreddit\": \"test\", \"removed_by_category\": null}}]}}, {\"data\": {\"children\": [{\"kind\": \"t1\", \"data\": {\"author\": \"a\"}}]}}]'

with patch('urllib.request.urlopen', return_value=fake_resp):
    r = CliRunner().invoke(main, ['post', 'sync', '--slug', 'p1', '--launch', '$LAUNCH'])
    assert r.exit_code == 0, (r.exit_code, r.output)

# Output should contain the table title and a delta of +6 (8 - 2) and +5 (6 - 1)
assert 'Sync summary' in r.output, r.output
assert '+6' in r.output, r.output
assert '+5' in r.output, r.output
" >/dev/null 2>&1 && ok "table summary with +delta printed" || bad "table summary with +delta printed"

# ── [15] last_checked is ISO8601 UTC and within 5s of now ────────────
echo "[15] last_checked timestamp shape + freshness"
$PYRUN -c "
from datetime import datetime, timezone
from gtm.launch import Post
from pathlib import Path
p = Post.load(Path('$LAUNCH/my-product/posts/2026-04-25-live-one.md'))
ts = p.metrics['last_checked']
assert ts.endswith('Z'), ts
parsed = datetime.fromisoformat(ts.replace('Z','+00:00'))
assert parsed.tzinfo is not None
delta = (datetime.now(timezone.utc) - parsed).total_seconds()
assert 0 <= delta < 30, delta
" >/dev/null 2>&1 && ok "last_checked is ISO8601 UTC, within 30s" \
                 || bad "last_checked is ISO8601 UTC, within 30s"

# ── Summary ──────────────────────────────────────────────────────────
echo
echo "── Results: $PASS pass / $FAIL fail ──"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
