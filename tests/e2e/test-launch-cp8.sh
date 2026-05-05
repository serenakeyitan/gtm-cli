#!/usr/bin/env bash
# CP8 e2e: full integration story across CP1-CP7.
#
# Walks one tmp launch dir through every public command in the launch surface,
# serving as both regression test AND the canonical example for
# docs/LAUNCH-ONBOARDING.md.
#
# No real network: `gtm post submit` is exercised via --dry-run, sync mocks
# urllib.request.urlopen, and dashboard deploy uses --dry-run.

set -uo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO"

PASS=0
FAIL=0

ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

PYRUN="uv run --quiet python"
GTM="uv run --quiet gtm"

TMP="$(mktemp -d -t gtm-launch-cp8.XXXXXX)"
trap 'rm -rf "$TMP"; pkill -P $$ 2>/dev/null || true' EXIT

echo "── CP8: end-to-end integration (CP1→CP7) ──"
echo "Tmp: $TMP"

LAUNCH="$TMP/my-launches"
SLUG="2026-04-26-reddit-r-test-cp8-end-to-end-flow"
BODY_FILE="$TMP/body.md"
cat > "$BODY_FILE" <<'BODY'
this is the cp8 e2e body. lowercase voice. no em dashes.
written by a real user, for the integration story.
BODY

# ── [1] launch init scaffolds the dir ────────────────────────────────
echo "[1] gtm launch init"
INIT_INPUT='cp8-product
cp8 product
cp8 e2e tagline
active

doc-drift
solve doc drifts


'
echo "$INIT_INPUT" | $GTM launch init "$LAUNCH" >"$TMP/init.out" 2>&1
RC=$?
[ $RC -eq 0 ] && [ -f "$LAUNCH/.gtm-launch.yaml" ] \
    && ok "init scaffolded $LAUNCH with marker" \
    || { bad "init scaffolded $LAUNCH"; cat "$TMP/init.out"; }

[ -d "$LAUNCH/cp8-product/posts" ] \
    && ok "init created cp8-product/posts/" \
    || bad "init created cp8-product/posts/"

# ── [2] launch link is idempotent (refuses, doesn't clobber) ─────────
echo "[2] gtm launch link refuses on existing marker (idempotent)"
echo "$INIT_INPUT" | $GTM launch link "$LAUNCH" >"$TMP/link.out" 2>&1
RC=$?
[ $RC -ne 0 ] && grep -qi "exists\|marker" "$TMP/link.out" \
    && ok "link refuses to clobber existing .gtm-launch.yaml" \
    || bad "link refuses to clobber existing .gtm-launch.yaml (rc=$RC)"

# ── [3] launch info prints products + directions ─────────────────────
echo "[3] gtm launch info"
$GTM launch info --launch "$LAUNCH" >"$TMP/info.out" 2>&1
grep -q "cp8-product" "$TMP/info.out" \
    && ok "info shows cp8-product" || bad "info shows cp8-product"
grep -q "doc-drift" "$TMP/info.out" \
    && ok "info shows doc-drift direction" || bad "info shows doc-drift direction"

# ── [3.5] patch in default reddit identity (init prompt left it blank) ──
$PYRUN -c "
import yaml
from pathlib import Path
p = Path('$LAUNCH/.gtm-launch.yaml')
d = yaml.safe_load(p.read_text())
d.setdefault('default_identity_by_platform', {})['reddit'] = 'cp8_testuser'
p.write_text(yaml.safe_dump(d, sort_keys=False))
" >/dev/null 2>&1

# ── [4] post draft creates a .md ─────────────────────────────────────
echo "[4] gtm post draft (noninteractive)"
$GTM post draft cp8-product \
    --launch "$LAUNCH" \
    --channel "reddit r/test" \
    --noninteractive \
    --title "cp8 end to end flow" \
    --body-file "$BODY_FILE" \
    >"$TMP/draft.out" 2>&1
RC=$?
[ $RC -eq 0 ] && ok "post draft exited 0" \
    || { bad "post draft exited 0"; cat "$TMP/draft.out"; }

DRAFT="$(ls "$LAUNCH/cp8-product/posts/"*.md 2>/dev/null | head -1)"
[ -n "$DRAFT" ] && [ -f "$DRAFT" ] \
    && ok "draft .md was created" || bad "draft .md was created"
ACTUAL_SLUG="$(basename "$DRAFT" .md)"
echo "  → slug: $ACTUAL_SLUG"

# ── [5] post list shows the draft ────────────────────────────────────
echo "[5] gtm post list"
COLUMNS=400 $GTM post list --launch "$LAUNCH" >"$TMP/list.out" 2>&1
grep -q "cp8-product" "$TMP/list.out" \
    && ok "post list shows cp8-product post" || bad "post list shows cp8-product post"
grep -q "drafting" "$TMP/list.out" \
    && ok "post list shows status=drafting" || bad "post list shows status=drafting"

# ── [6] post status prints metadata ──────────────────────────────────
echo "[6] gtm post status"
$GTM post status "$ACTUAL_SLUG" --launch "$LAUNCH" >"$TMP/status.out" 2>&1
RC=$?
[ $RC -eq 0 ] && ok "post status exited 0" || bad "post status exited 0 (rc=$RC)"
grep -q "cp8-product" "$TMP/status.out" \
    && ok "post status shows product" || bad "post status shows product"
grep -q "drafting" "$TMP/status.out" \
    && ok "post status shows status=drafting" || bad "post status shows status=drafting"

# ── [7] post submit --dry-run: preflight runs, no mutation ───────────
echo "[7] gtm post submit --dry-run --yes (preflight only, no submission)"
BEFORE_HASH="$(shasum "$DRAFT" | cut -d' ' -f1)"
$PYRUN -c "
from unittest.mock import patch, AsyncMock
from click.testing import CliRunner
from gtm.cli import main
with patch('gtm.modules.preflight.preflight') as mp, \
     patch('gtm.platforms.reddit.client.PlaywrightRedditClient.submit_post', new_callable=AsyncMock) as ms, \
     patch('gtm.platforms.reddit.client.PlaywrightRedditClient.submit_image_post', new_callable=AsyncMock) as msi:
    mp.return_value = {'verdict': 'PASS', 'reasons': [], 'notes': '', 'permanent_skip': False}
    r = CliRunner().invoke(main, ['post', 'submit', '$ACTUAL_SLUG', '--launch', '$LAUNCH', '--dry-run', '--yes'])
    assert r.exit_code == 0, (r.exit_code, r.output)
    assert 'DRY RUN' in r.output, r.output
    mp.assert_called_once()
    ms.assert_not_called()
    msi.assert_not_called()
" >/dev/null 2>&1 && ok "dry-run runs preflight + skips real submit" \
                || bad "dry-run runs preflight + skips real submit"

AFTER_HASH="$(shasum "$DRAFT" | cut -d' ' -f1)"
[ "$BEFORE_HASH" = "$AFTER_HASH" ] \
    && ok "dry-run did NOT mutate the post .md" \
    || bad "dry-run did NOT mutate the post .md"

# ── [8] Post still drafting after dry-run ────────────────────────────
echo "[8] post status still drafting"
grep -q "^status: drafting" "$DRAFT" \
    && ok "status still drafting after dry-run" \
    || bad "status still drafting after dry-run"

# ── [9] Manually flip status to live + add live_id/url for sync test ──
echo "[9] manual flip → status=live (sim'd successful submit)"
$PYRUN -c "
from gtm.launch import Post
from pathlib import Path
p = Post.load(Path('$DRAFT'))
p.frontmatter['status'] = 'live'
p.frontmatter['live_id'] = 'cp8fake'
p.frontmatter['url'] = 'https://reddit.com/r/test/comments/cp8fake/cp8-end-to-end/'
p.frontmatter['posted_at'] = '2026-04-26T10:00:00Z'
p.save(Path('$DRAFT'))
" >/dev/null 2>&1 && ok "manually flipped to status=live with live_id" \
                || bad "manually flipped to status=live with live_id"

# ── [10] post sync --slug: mocked network, metrics updated ───────────
echo "[10] gtm post sync --slug (mocked urlopen)"
$PYRUN -c "
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from gtm.cli import main
from gtm.launch import Post
from pathlib import Path

fake_resp = MagicMock()
fake_resp.read.return_value = b'[{\"data\": {\"children\": [{\"data\": {\"score\": 12, \"num_comments\": 7, \"subreddit\": \"test\", \"removed_by_category\": null}}]}}, {\"data\": {\"children\": [{\"kind\": \"t1\", \"data\": {\"author\": \"alice\"}}, {\"kind\": \"t1\", \"data\": {\"author\": \"bob\"}}, {\"kind\": \"t1\", \"data\": {\"author\": \"AutoModerator\"}}]}}]'

with patch('urllib.request.urlopen', return_value=fake_resp):
    r = CliRunner().invoke(main, ['post', 'sync', '--slug', '$ACTUAL_SLUG', '--launch', '$LAUNCH'])
    assert r.exit_code == 0, (r.exit_code, r.output)

p = Post.load(Path('$DRAFT'))
assert p.score == 12, p.score
assert p.comments == 7, p.comments
assert p.metrics['comments_real'] == 2, p.metrics
assert p.metrics['last_checked'].endswith('Z'), p.metrics
" >/dev/null 2>&1 && ok "sync updated score/comments/comments_real from mocked Reddit JSON" \
                || bad "sync updated score/comments/comments_real from mocked Reddit JSON"

# ── [11] dashboard build produces dashboard.html with the post ───────
echo "[11] gtm dashboard build"
$GTM dashboard build --launch "$LAUNCH" >"$TMP/build.out" 2>&1
RC=$?
[ $RC -eq 0 ] && [ -f "$LAUNCH/dashboard.html" ] \
    && ok "dashboard build produced dashboard.html" \
    || bad "dashboard build produced dashboard.html (rc=$RC)"

grep -q "cp8fake" "$LAUNCH/dashboard.html" \
    && ok "dashboard.html embeds the post live_id" \
    || bad "dashboard.html embeds the post live_id"

# Verify the metrics that sync wrote also made it into the dashboard
$PYRUN -c "
import re, json
t = open('$LAUNCH/dashboard.html').read()
m = re.search(r'const POSTS = (\[.*?\]);', t, re.DOTALL)
posts = json.loads(m.group(1))
assert len(posts) == 1, len(posts)
p = posts[0]
assert p['score'] == 12, p
assert p['comments'] == 7, p
assert p['comments_real'] == 2, p
" >/dev/null 2>&1 && ok "dashboard reflects synced metrics (score=12, comments=7, real=2)" \
                || bad "dashboard reflects synced metrics"

# ── [12] dashboard serve --port 0 reachable on localhost ─────────────
echo "[12] gtm dashboard serve --port 0 (subprocess, briefly)"
SERVE_LOG="$TMP/serve.log"
$GTM dashboard serve --launch "$LAUNCH" --port 0 >"$SERVE_LOG" 2>&1 &
SERVE_PID=$!
for i in 1 2 3 4 5 6 7 8 9 10; do
    if grep -q "serving at" "$SERVE_LOG" 2>/dev/null; then break; fi
    sleep 0.5
done
URL="$(grep -o 'http://localhost:[0-9]*/dashboard.html' "$SERVE_LOG" | head -1)"
if [ -n "$URL" ]; then
    ok "serve printed URL: $URL"
    STATUS="$($PYRUN -c "
import urllib.request
try:
    r = urllib.request.urlopen('$URL', timeout=3)
    print(r.status)
except Exception as e:
    print('ERR', e)
" 2>&1)"
    [ "$STATUS" = "200" ] && ok "GET dashboard.html on serve URL returns 200" \
        || bad "GET dashboard.html on serve URL returns 200 (got: $STATUS)"
else
    bad "serve printed a localhost URL"
    bad "GET dashboard.html on serve URL returns 200 (no URL)"
fi
kill $SERVE_PID 2>/dev/null
wait $SERVE_PID 2>/dev/null

# ── [13] dashboard deploy --dry-run prints expected wrangler command ──
echo "[13] gtm dashboard deploy --dry-run (cloudflare)"
# Need cloudflare_project for the dry-run to succeed
$PYRUN -c "
import yaml
from pathlib import Path
p = Path('$LAUNCH/.gtm-launch.yaml')
data = yaml.safe_load(p.read_text())
data['dashboard'] = {'cloudflare_project': 'cp8-test-project', 'provider': 'cloudflare'}
p.write_text(yaml.safe_dump(data, sort_keys=False))
" >/dev/null 2>&1 && ok "patched yaml with cloudflare_project" \
                || bad "patched yaml with cloudflare_project"

DEPLOY_OUT="$($GTM dashboard deploy --launch "$LAUNCH" --dry-run 2>&1)"
RC=$?
if [ $RC -eq 0 ]; then
    echo "$DEPLOY_OUT" | grep -q "wrangler pages deploy" \
        && ok "deploy --dry-run prints wrangler pages deploy" \
        || bad "deploy --dry-run prints wrangler pages deploy: $DEPLOY_OUT"
    echo "$DEPLOY_OUT" | grep -q -- "--project-name=cp8-test-project" \
        && ok "deploy --dry-run includes --project-name from yaml" \
        || bad "deploy --dry-run includes --project-name"
    echo "$DEPLOY_OUT" | grep -qi "dry-run" \
        && ok "deploy --dry-run banner present" || bad "deploy --dry-run banner present"
else
    bad "deploy --dry-run exited 0 (got $RC: $DEPLOY_OUT)"
    bad "deploy --dry-run includes --project-name"
    bad "deploy --dry-run banner present"
fi

# ── [14] integration story end-to-end: every artifact in place ───────
echo "[14] integration artifacts on disk"
[ -f "$LAUNCH/.gtm-launch.yaml" ] && ok "marker .gtm-launch.yaml exists" \
    || bad "marker .gtm-launch.yaml exists"
[ -f "$DRAFT" ] && ok "post .md exists" || bad "post .md exists"
[ -f "$LAUNCH/dashboard.html" ] && ok "dashboard.html exists" \
    || bad "dashboard.html exists"
[ -f "$LAUNCH/dist/index.html" ] && ok "dist/index.html staged by dry-run deploy" \
    || bad "dist/index.html staged by dry-run deploy"

# ── [15] onboarding doc exists ───────────────────────────────────────
echo "[15] onboarding doc shipped"
[ -f "$REPO/docs/LAUNCH-ONBOARDING.md" ] \
    && ok "docs/LAUNCH-ONBOARDING.md exists" \
    || bad "docs/LAUNCH-ONBOARDING.md exists"

# ── [16] onboarding doc covers the user journey ──────────────────────
echo "[16] onboarding doc covers all 10 journey commands"
DOC="$REPO/docs/LAUNCH-ONBOARDING.md"
if [ -f "$DOC" ]; then
    for cmd in "gtm auth reddit" "gtm launch init" "gtm launch link" \
               "gtm post draft" "gtm post submit" "gtm dashboard build" \
               "gtm dashboard serve" "gtm dashboard deploy" "gtm post sync"; do
        grep -q "$cmd" "$DOC" \
            && ok "onboarding doc mentions: $cmd" \
            || bad "onboarding doc mentions: $cmd"
    done
    grep -q "PLAN-launch-workflow.md" "$DOC" \
        && ok "onboarding doc links to PLAN-launch-workflow.md" \
        || bad "onboarding doc links to PLAN-launch-workflow.md"
    grep -q -i "atf-launch" "$DOC" \
        && ok "onboarding doc references atf-launch as reference impl" \
        || bad "onboarding doc references atf-launch"
    grep -q "default_identity_by_platform" "$DOC" \
        && ok "onboarding doc covers default_identity_by_platform gotcha" \
        || bad "onboarding doc covers default_identity_by_platform gotcha"
else
    bad "onboarding doc cannot be checked — file missing"
fi

# ── Summary ──────────────────────────────────────────────────────────
echo
echo "── Results: $PASS pass / $FAIL fail ──"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
