#!/usr/bin/env bash
# CP4 e2e: `gtm post submit` — preflight + Playwright submit + frontmatter writeback.
# All Playwright + preflight network calls are mocked. No real Reddit submissions.

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

TMP="$(mktemp -d -t gtm-launch-cp4.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

echo "── CP4: gtm post submit ──"
echo "Tmp: $TMP"

# ── Build a synthetic launch dir with 2 drafting posts (text + image) ──
LAUNCH="$TMP/launch"
mkdir -p "$LAUNCH/my-product/posts/assets"

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
  reddit: testuser
dashboard: {}
YAML

# Text-kind drafting post
cat > "$LAUNCH/my-product/posts/2026-04-26-reddit-r-test-text-post.md" <<'POST'
---
id: d1
product: my-product
direction: doc-drift
channel: reddit r/test
identity: testuser
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
this is the body text of the draft post.
POST

# Image-kind drafting post
echo "fakeimagedata" > "$LAUNCH/my-product/posts/assets/cover.png"
cat > "$LAUNCH/my-product/posts/2026-04-26-reddit-r-test-image-post.md" <<'POST'
---
id: d2
product: my-product
direction: doc-drift
channel: reddit r/test
identity: testuser
kind: image
image: posts/assets/cover.png
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
optional caption body for image post.
POST

# Already-live post
cat > "$LAUNCH/my-product/posts/2026-04-25-reddit-r-test-already-live.md" <<'POST'
---
id: d3
product: my-product
direction: doc-drift
channel: reddit r/test
identity: testuser
kind: self
status: live
url: https://reddit.com/r/test/comments/old123/already/
live_id: old123
posted_at: 2026-04-25T10:00:00Z
metrics:
  score: 5
  comments: 2
  comments_real: 1
  last_checked: 2026-04-25T11:00:00Z
note: null
---
already published.
POST

# Twitter-channel drafting post (should be refused)
cat > "$LAUNCH/my-product/posts/2026-04-26-twitter-tweet.md" <<'POST'
---
id: d4
product: my-product
direction: doc-drift
channel: twitter
identity: testuser
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
just a tweet draft.
POST

TEXT_SLUG="2026-04-26-reddit-r-test-text-post"
IMAGE_SLUG="2026-04-26-reddit-r-test-image-post"
LIVE_SLUG="2026-04-25-reddit-r-test-already-live"
TWEET_SLUG="2026-04-26-twitter-tweet"

# ── [1] Module imports ───────────────────────────────────────────────
echo "[1] Module imports"
check "gtm.launch.submit imports cleanly" \
    "$PYRUN -c 'from gtm.launch.submit import parse_reddit_channel, channel_platform, extract_live_id, mark_post_live, mark_post_failed'"
check "gtm.launch re-exports submit module" \
    "$PYRUN -c 'from gtm.launch import submit; assert hasattr(submit, \"parse_reddit_channel\")'"

# ── [2] Pure helpers ─────────────────────────────────────────────────
echo "[2] Pure helpers"
check "parse_reddit_channel('reddit r/AI_Agents') == 'AI_Agents'" \
    "$PYRUN -c 'from gtm.launch.submit import parse_reddit_channel; assert parse_reddit_channel(\"reddit r/AI_Agents\") == \"AI_Agents\"'"
check "parse_reddit_channel('twitter') is None" \
    "$PYRUN -c 'from gtm.launch.submit import parse_reddit_channel; assert parse_reddit_channel(\"twitter\") is None'"
check "channel_platform('hn') == 'hn'" \
    "$PYRUN -c 'from gtm.launch.submit import channel_platform; assert channel_platform(\"hn\") == \"hn\"'"
check "extract_live_id picks abc123 out of /comments/abc123/" \
    "$PYRUN -c 'from gtm.launch.submit import extract_live_id; assert extract_live_id(\"https://reddit.com/r/x/comments/abc123/title\") == \"abc123\"'"
check "mark_post_live sets status=live + live_id + posted_at" \
    "$PYRUN -c '
from gtm.launch.submit import mark_post_live
out = mark_post_live({\"status\": \"drafting\"}, url=\"https://reddit.com/r/x/comments/xyz789/\", live_id=None)
assert out[\"status\"] == \"live\"
assert out[\"live_id\"] == \"xyz789\"
assert out[\"posted_at\"].endswith(\"Z\")
'"
check "mark_post_failed writes note='submit failed: ...' and keeps status" \
    "$PYRUN -c '
from gtm.launch.submit import mark_post_failed
out = mark_post_failed({\"status\": \"drafting\"}, \"timeout\")
assert out[\"note\"] == \"submit failed: timeout\"
assert out[\"status\"] == \"drafting\"
'"

# ── [3] Refuses unknown slug ─────────────────────────────────────────
echo "[3] Unknown slug → error with hint"
$PYRUN -c "
from click.testing import CliRunner
from gtm.cli import main
r = CliRunner().invoke(main, ['post', 'submit', 'bogus-slug', '--launch', '$LAUNCH'])
assert r.exit_code == 1, (r.exit_code, r.output)
assert 'No post found' in r.output, r.output
assert 'gtm post list' in r.output, r.output
" >/dev/null 2>&1 && ok "unknown slug refuses with hint" || bad "unknown slug refuses with hint"

# ── [4] Refuses already-live post ────────────────────────────────────
echo "[4] Already-live post → refuses"
$PYRUN -c "
from click.testing import CliRunner
from gtm.cli import main
r = CliRunner().invoke(main, ['post', 'submit', '$LIVE_SLUG', '--launch', '$LAUNCH', '--yes'])
assert r.exit_code == 1, (r.exit_code, r.output)
assert 'not' in r.output.lower() and 'drafting' in r.output.lower(), r.output
" >/dev/null 2>&1 && ok "already-live post refuses" || bad "already-live post refuses"

# ── [5] Refuses non-reddit (twitter) channel ─────────────────────────
echo "[5] Twitter channel → refuses with TODO message"
$PYRUN -c "
from click.testing import CliRunner
from gtm.cli import main
r = CliRunner().invoke(main, ['post', 'submit', '$TWEET_SLUG', '--launch', '$LAUNCH', '--yes'])
assert r.exit_code == 1, (r.exit_code, r.output)
assert 'twitter' in r.output.lower(), r.output
assert 'TODO' in r.output or 'follow-up' in r.output.lower() or 'punt' in r.output.lower(), r.output
" >/dev/null 2>&1 && ok "twitter channel refuses with TODO" || bad "twitter channel refuses with TODO"

# ── [6] Preflight FAIL → aborts, no playwright launch ────────────────
echo "[6] Preflight FAIL → aborts without invoking Playwright"
$PYRUN -c "
from unittest.mock import patch, AsyncMock
from click.testing import CliRunner
from gtm.cli import main
with patch('gtm.modules.preflight.preflight') as mp, \
     patch('gtm.platforms.reddit.client.PlaywrightRedditClient.submit_post', new_callable=AsyncMock) as ms:
    mp.return_value = {
        'verdict': 'FAIL',
        'reasons': [{'status': 'fail', 'detail': 'too low karma'}],
        'notes': '', 'permanent_skip': False,
    }
    r = CliRunner().invoke(main, ['post', 'submit', '$TEXT_SLUG', '--launch', '$LAUNCH', '--yes'])
    assert r.exit_code == 1, (r.exit_code, r.output)
    assert 'FAIL' in r.output, r.output
    ms.assert_not_called()
" >/dev/null 2>&1 && ok "preflight FAIL aborts + no submit call" || bad "preflight FAIL aborts + no submit call"

# ── [7] Preflight BORDERLINE without --yes → aborts ──────────────────
echo "[7] Preflight BORDERLINE without --yes → aborts"
$PYRUN -c "
from unittest.mock import patch, AsyncMock
from click.testing import CliRunner
from gtm.cli import main
with patch('gtm.modules.preflight.preflight') as mp, \
     patch('gtm.platforms.reddit.client.PlaywrightRedditClient.submit_post', new_callable=AsyncMock) as ms:
    mp.return_value = {
        'verdict': 'BORDERLINE',
        'reasons': [{'status': 'borderline', 'detail': 'only 10% over floor'}],
        'notes': '', 'permanent_skip': False,
    }
    r = CliRunner().invoke(main, ['post', 'submit', '$TEXT_SLUG', '--launch', '$LAUNCH'], input='n\n')
    assert r.exit_code == 1, (r.exit_code, r.output)
    assert 'BORDERLINE' in r.output, r.output
    assert '--yes' in r.output, r.output
    ms.assert_not_called()
" >/dev/null 2>&1 && ok "BORDERLINE w/o --yes aborts + requires --yes" || bad "BORDERLINE w/o --yes aborts + requires --yes"

# ── [8] Dry-run with --yes → preflight runs, no submit, no mutation ──
echo "[8] --dry-run --yes runs preflight, skips submit, no mutation"
$PYRUN -c "
from unittest.mock import patch, AsyncMock
from click.testing import CliRunner
from gtm.cli import main
from gtm.launch import Post
from pathlib import Path
target = Path('$LAUNCH/my-product/posts/$TEXT_SLUG.md')
before = target.read_text()
with patch('gtm.modules.preflight.preflight') as mp, \
     patch('gtm.platforms.reddit.client.PlaywrightRedditClient.submit_post', new_callable=AsyncMock) as ms, \
     patch('gtm.platforms.reddit.client.PlaywrightRedditClient.submit_image_post', new_callable=AsyncMock) as msi:
    mp.return_value = {
        'verdict': 'PASS', 'reasons': [{'status': 'pass', 'detail': 'all good'}],
        'notes': '', 'permanent_skip': False,
    }
    r = CliRunner().invoke(main, ['post', 'submit', '$TEXT_SLUG', '--launch', '$LAUNCH', '--dry-run', '--yes'])
    assert r.exit_code == 0, (r.exit_code, r.output)
    assert 'DRY RUN' in r.output, r.output
    ms.assert_not_called()
    msi.assert_not_called()
    mp.assert_called_once()
after = target.read_text()
p = Post.load(target)
assert p.status == 'drafting', p.status
assert before == after, 'file should be unchanged after dry-run'
" >/dev/null 2>&1 && ok "dry-run runs preflight, skips submit, leaves file untouched" || bad "dry-run runs preflight, skips submit, leaves file untouched"

# ── [9] BORDERLINE + --yes proceeds ─────────────────────────────────
echo "[9] BORDERLINE + --yes proceeds to submit"
$PYRUN -c "
from unittest.mock import patch, AsyncMock
from click.testing import CliRunner
from gtm.cli import main
with patch('gtm.modules.preflight.preflight') as mp, \
     patch('gtm.identity.session.session_dir_for_identity') as msd, \
     patch('gtm.platforms.reddit.client.PlaywrightRedditClient.submit_post', new_callable=AsyncMock) as ms:
    mp.return_value = {
        'verdict': 'BORDERLINE', 'reasons': [{'status': 'borderline', 'detail': 'tight'}],
        'notes': '', 'permanent_skip': False,
    }
    msd.return_value = '/tmp/fake-session'
    ms.return_value = {
        'url': 'https://reddit.com/r/test/comments/border1/title/',
        'post_id': 'border1', 'subreddit': 'test', 'title': 't', 'success': True,
    }
    r = CliRunner().invoke(main, ['post', 'submit', '$TEXT_SLUG', '--launch', '$LAUNCH', '--dry-run', '--yes'])
    assert r.exit_code == 0, (r.exit_code, r.output)
    assert 'BORDERLINE' in r.output, r.output
    assert 'DRY RUN' in r.output, r.output
" >/dev/null 2>&1 && ok "BORDERLINE + --yes proceeds (dry-run path)" || bad "BORDERLINE + --yes proceeds (dry-run path)"

# ── [10] Successful submit → frontmatter updated ─────────────────────
echo "[10] Mocked successful submit → frontmatter updated to live"
# Reset the text post (in case prior tests mutated it — they shouldn't have)
cat > "$LAUNCH/my-product/posts/$TEXT_SLUG.md" <<'POST'
---
id: d1
product: my-product
direction: doc-drift
channel: reddit r/test
identity: testuser
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
this is the body text of the draft post.
POST

$PYRUN -c "
from unittest.mock import patch, AsyncMock
from click.testing import CliRunner
from gtm.cli import main
from gtm.launch import Post
from pathlib import Path
with patch('gtm.modules.preflight.preflight') as mp, \
     patch('gtm.identity.session.session_dir_for_identity') as msd, \
     patch('gtm.platforms.reddit.client.PlaywrightRedditClient.submit_post', new_callable=AsyncMock) as ms:
    mp.return_value = {'verdict': 'PASS', 'reasons': [], 'notes': '', 'permanent_skip': False}
    msd.return_value = '/tmp/fake-session'
    ms.return_value = {
        'url': 'https://reddit.com/r/test/comments/abc999/some-title/',
        'post_id': 'abc999', 'subreddit': 'test', 'title': 't', 'success': True,
    }
    r = CliRunner().invoke(main, ['post', 'submit', '$TEXT_SLUG', '--launch', '$LAUNCH', '--yes'])
    assert r.exit_code == 0, (r.exit_code, r.output)
    ms.assert_called_once()
    args, _ = ms.call_args
    assert args[0] == 'test', args
p = Post.load(Path('$LAUNCH/my-product/posts/$TEXT_SLUG.md'))
assert p.status == 'live', p.status
assert p.frontmatter['live_id'] == 'abc999', p.frontmatter
assert 'abc999' in (p.frontmatter['url'] or ''), p.frontmatter
assert p.posted_at and p.posted_at.endswith('Z'), p.posted_at
" >/dev/null 2>&1 && ok "successful submit writes live_url/live_id/posted_at + status=live" || bad "successful submit writes live_url/live_id/posted_at + status=live"

# ── [11] Submit failure → status stays drafting + note appended ──────
echo "[11] Mocked submit raise → status=drafting + note='submit failed: ...'"
# Reset the post first
cat > "$LAUNCH/my-product/posts/$TEXT_SLUG.md" <<'POST'
---
id: d1
product: my-product
direction: doc-drift
channel: reddit r/test
identity: testuser
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
this is the body text of the draft post.
POST

$PYRUN -c "
from unittest.mock import patch, AsyncMock
from click.testing import CliRunner
from gtm.cli import main
from gtm.launch import Post
from pathlib import Path
with patch('gtm.modules.preflight.preflight') as mp, \
     patch('gtm.identity.session.session_dir_for_identity') as msd, \
     patch('gtm.platforms.reddit.client.PlaywrightRedditClient.submit_post', new_callable=AsyncMock) as ms:
    mp.return_value = {'verdict': 'PASS', 'reasons': [], 'notes': '', 'permanent_skip': False}
    msd.return_value = '/tmp/fake-session'
    ms.side_effect = RuntimeError('captcha demanded')
    r = CliRunner().invoke(main, ['post', 'submit', '$TEXT_SLUG', '--launch', '$LAUNCH', '--yes'])
    assert r.exit_code == 1, (r.exit_code, r.output)
    assert 'failed' in r.output.lower(), r.output
p = Post.load(Path('$LAUNCH/my-product/posts/$TEXT_SLUG.md'))
assert p.status == 'drafting', p.status
note = p.frontmatter.get('note') or ''
assert note.startswith('submit failed:'), note
assert 'captcha' in note, note
" >/dev/null 2>&1 && ok "failure leaves status=drafting + note appended" || bad "failure leaves status=drafting + note appended"

# ── [12] Image kind → submit_image_post called with image path ───────
echo "[12] kind=image dispatches submit_image_post with image path"
# Reset the image post first (in case)
cat > "$LAUNCH/my-product/posts/$IMAGE_SLUG.md" <<'POST'
---
id: d2
product: my-product
direction: doc-drift
channel: reddit r/test
identity: testuser
kind: image
image: posts/assets/cover.png
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
optional caption body for image post.
POST

$PYRUN -c "
from unittest.mock import patch, AsyncMock
from click.testing import CliRunner
from gtm.cli import main
from gtm.launch import Post
from pathlib import Path
with patch('gtm.modules.preflight.preflight') as mp, \
     patch('gtm.identity.session.session_dir_for_identity') as msd, \
     patch('gtm.platforms.reddit.client.PlaywrightRedditClient.submit_image_post', new_callable=AsyncMock) as msi:
    mp.return_value = {'verdict': 'PASS', 'reasons': [], 'notes': '', 'permanent_skip': False}
    msd.return_value = '/tmp/fake-session'
    msi.return_value = {
        'url': 'https://reddit.com/r/test/comments/img555/cover/',
        'post_id': 'img555', 'subreddit': 'test', 'title': 't', 'kind': 'image', 'success': True,
    }
    r = CliRunner().invoke(main, ['post', 'submit', '$IMAGE_SLUG', '--launch', '$LAUNCH', '--yes'])
    assert r.exit_code == 0, (r.exit_code, r.output)
    msi.assert_called_once()
    args, _ = msi.call_args
    # signature: (sub, title, body, image_path)
    assert args[0] == 'test', args
    img_path = args[3]
    assert img_path.endswith('cover.png'), img_path
    assert '/my-product/posts/assets/cover.png' in img_path, img_path
p = Post.load(Path('$LAUNCH/my-product/posts/$IMAGE_SLUG.md'))
assert p.status == 'live', p.status
assert p.frontmatter['live_id'] == 'img555', p.frontmatter
" >/dev/null 2>&1 && ok "image kind dispatches submit_image_post with absolute image path" || bad "image kind dispatches submit_image_post with absolute image path"

# ── [13] PlaywrightRedditClient has submit_image_post ────────────────
echo "[13] submit_image_post exists on PlaywrightRedditClient"
check "PlaywrightRedditClient.submit_image_post is callable" \
    "$PYRUN -c '
from gtm.platforms.reddit.client import PlaywrightRedditClient
import inspect
m = getattr(PlaywrightRedditClient, \"submit_image_post\", None)
assert m is not None and inspect.iscoroutinefunction(m), m
sig = inspect.signature(m)
params = list(sig.parameters)
assert params == [\"self\", \"subreddit\", \"title\", \"body\", \"image_path\"], params
'"

echo
echo "──────────────────────────────────────────"
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
