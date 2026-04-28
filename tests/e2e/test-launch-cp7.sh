#!/usr/bin/env bash
# CP7 e2e: `gtm dashboard serve` + `gtm dashboard deploy`.
# Mocks wrangler/vercel via stub scripts on PATH.

set -uo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO"

PASS=0
FAIL=0

ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

PYRUN="uv run --quiet python"

TMP="$(mktemp -d -t gtm-launch-cp7.XXXXXX)"
trap 'rm -rf "$TMP"; pkill -P $$ 2>/dev/null || true' EXIT

echo "── CP7: gtm dashboard serve / deploy ──"
echo "Tmp: $TMP"

# ── Mock wrangler / vercel on PATH ───────────────────────────────────
MOCKBIN="$TMP/mockbin"
mkdir -p "$MOCKBIN"

cat > "$MOCKBIN/wrangler" <<'STUB'
#!/usr/bin/env bash
echo "wrangler-mock invoked: $*"
echo "✨ Deployment complete! Take a peek over at https://abc123.atf-launch.pages.dev"
exit 0
STUB
chmod +x "$MOCKBIN/wrangler"

cat > "$MOCKBIN/vercel" <<'STUB'
#!/usr/bin/env bash
echo "vercel-mock invoked: $*"
echo "✅  Production: https://my-launch.vercel.app"
exit 0
STUB
chmod +x "$MOCKBIN/vercel"

export PATH="$MOCKBIN:$PATH"

# ── Synthetic launch dir ─────────────────────────────────────────────
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
dashboard:
  cloudflare_project: my-test-project
  vercel_project: my-vercel-project
  provider: cloudflare
YAML

cat > "$LAUNCH/my-product/posts/2026-04-25-alpha.md" <<'POST'
---
id: p1
product: my-product
direction: doc-drift
channel: reddit r/test
identity: Pale_Stand5217
kind: self
status: live
url: https://reddit.com/r/test/comments/abc111/alpha/
live_id: abc111
posted_at: 2026-04-25T10:00:00Z
metrics:
  score: 1
  comments: 0
---
body
POST

# ── [1] Module imports ───────────────────────────────────────────────
echo "[1] module imports"
$PYRUN -c "from gtm.launch.deploy import build_plan, stage_dashboard, parse_deploy_url, resolve_provider, DeployConfigError, PROVIDERS, DEFAULT_PROVIDER" \
    >/dev/null 2>&1 && ok "gtm.launch.deploy imports" || bad "gtm.launch.deploy imports"

$PYRUN -c "from gtm.launch import deploy; assert hasattr(deploy, 'build_plan')" \
    >/dev/null 2>&1 && ok "gtm.launch re-exports deploy" || bad "gtm.launch re-exports deploy"

# ── [2] Help text mentions both new commands ─────────────────────────
echo "[2] help text mentions serve + deploy"
HELP="$(uv run --quiet gtm dashboard --help 2>&1)"
echo "$HELP" | grep -q "serve" && ok "dashboard --help mentions serve" || bad "dashboard --help mentions serve"
echo "$HELP" | grep -q "deploy" && ok "dashboard --help mentions deploy" || bad "dashboard --help mentions deploy"

# ── [3] dry-run cloudflare prints expected wrangler command ──────────
echo "[3] deploy --dry-run (cloudflare)"
DRY_OUT="$(uv run --quiet gtm dashboard deploy --launch "$LAUNCH" --dry-run 2>&1)"
RC=$?
if [ $RC -eq 0 ]; then
    echo "$DRY_OUT" | grep -q "wrangler pages deploy" \
        && ok "dry-run prints wrangler pages deploy" || bad "dry-run prints wrangler pages deploy: $DRY_OUT"
    echo "$DRY_OUT" | grep -q -- "--project-name=my-test-project" \
        && ok "dry-run includes --project-name" || bad "dry-run includes --project-name"
    echo "$DRY_OUT" | grep -q "dry-run: not executing" \
        && ok "dry-run banner present" || bad "dry-run banner present"
    echo "$DRY_OUT" | grep -q "$LAUNCH/dist" \
        && ok "dry-run shows dist path" || bad "dry-run shows dist path"
else
    bad "dry-run exited $RC: $DRY_OUT"
fi

# ── [4] dry-run staged the dashboard to dist/index.html ──────────────
echo "[4] dry-run staged dist/index.html"
[ -f "$LAUNCH/dist/index.html" ] && ok "dist/index.html exists after dry-run" \
    || bad "dist/index.html exists after dry-run"

# ── [5] real deploy with mocked wrangler succeeds + parses URL ───────
echo "[5] deploy --provider cloudflare (mocked)"
DEPLOY_OUT="$(uv run --quiet gtm dashboard deploy --launch "$LAUNCH" --provider cloudflare 2>&1)"
RC=$?
if [ $RC -eq 0 ]; then
    echo "$DEPLOY_OUT" | grep -q "wrangler-mock invoked" \
        && ok "wrangler stub was invoked" || bad "wrangler stub was invoked: $DEPLOY_OUT"
    echo "$DEPLOY_OUT" | grep -q "deployed: https://abc123.atf-launch.pages.dev" \
        && ok "deploy URL parsed + printed" || bad "deploy URL parsed + printed"
else
    bad "deploy --provider cloudflare exited $RC: $DEPLOY_OUT"
fi

# ── [6] missing cloudflare_project → clear error ─────────────────────
echo "[6] missing cloudflare_project"
BADL="$TMP/bad-launch"
mkdir -p "$BADL/p/posts"
cat > "$BADL/.gtm-launch.yaml" <<'YAML'
version: 1
products:
  - key: p
    name: p
    status: active
directions: []
default_identity_by_platform: {}
dashboard: {}
YAML
ERR_OUT="$(uv run --quiet gtm dashboard deploy --launch "$BADL" --provider cloudflare --dry-run 2>&1)"
RC=$?
[ $RC -ne 0 ] && echo "$ERR_OUT" | grep -q "cloudflare_project" \
    && ok "missing cloudflare_project errors clearly" || bad "missing cloudflare_project errors clearly (rc=$RC, out=$ERR_OUT)"

# ── [7] vercel dry-run prints expected vercel command ────────────────
echo "[7] deploy --provider vercel --dry-run"
VOUT="$(uv run --quiet gtm dashboard deploy --launch "$LAUNCH" --provider vercel --dry-run 2>&1)"
RC=$?
if [ $RC -eq 0 ]; then
    echo "$VOUT" | grep -q "vercel deploy" \
        && ok "vercel dry-run prints vercel deploy" || bad "vercel dry-run prints vercel deploy: $VOUT"
    echo "$VOUT" | grep -q -- "--yes" \
        && ok "vercel command includes --yes" || bad "vercel command includes --yes"
else
    bad "vercel dry-run exited $RC: $VOUT"
fi

# ── [8] build is fresh on each deploy (yaml tweak reflected) ─────────
echo "[8] build is fresh on each deploy"
# tweak: change product name in yaml, run dry-run, confirm dashboard reflects it
sed -i.bak 's/tagline: Test product/tagline: TWEAKED-XYZ/' "$LAUNCH/.gtm-launch.yaml"
uv run --quiet gtm dashboard deploy --launch "$LAUNCH" --dry-run >/dev/null 2>&1
grep -q "TWEAKED-XYZ" "$LAUNCH/dashboard.html" \
    && ok "deploy rebuilds dashboard.html (tweak visible)" || bad "deploy rebuilds dashboard.html"
grep -q "TWEAKED-XYZ" "$LAUNCH/dist/index.html" \
    && ok "dist/index.html reflects fresh build" || bad "dist/index.html reflects fresh build"

# ── [9] idempotent: deploy twice, both succeed ───────────────────────
echo "[9] deploy idempotency"
uv run --quiet gtm dashboard deploy --launch "$LAUNCH" --provider cloudflare >/dev/null 2>&1
RC1=$?
uv run --quiet gtm dashboard deploy --launch "$LAUNCH" --provider cloudflare >/dev/null 2>&1
RC2=$?
[ $RC1 -eq 0 ] && [ $RC2 -eq 0 ] && ok "deploy → deploy both succeed" \
    || bad "deploy → deploy both succeed (rc1=$RC1 rc2=$RC2)"

# ── [10] serve --port 0 starts and is reachable ──────────────────────
echo "[10] serve --port 0 reachable"
SERVE_LOG="$TMP/serve.log"
uv run --quiet gtm dashboard serve --launch "$LAUNCH" --port 0 >"$SERVE_LOG" 2>&1 &
SERVE_PID=$!
# wait for the "serving at" line
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
    [ "$STATUS" = "200" ] && ok "GET dashboard.html returns 200" \
        || bad "GET dashboard.html returns 200 (got: $STATUS)"
else
    bad "serve printed URL"
    bad "GET dashboard.html returns 200 (no URL to test)"
fi
kill $SERVE_PID 2>/dev/null
wait $SERVE_PID 2>/dev/null

# ── [11] --launch flag works for serve too (no walk-up needed) ───────
echo "[11] --launch flag on serve"
SERVE_LOG2="$TMP/serve2.log"
( cd /tmp && uv run --quiet gtm dashboard serve --launch "$LAUNCH" --port 0 >"$SERVE_LOG2" 2>&1 ) &
SP2=$!
for i in 1 2 3 4 5 6 7 8 9 10; do
    if grep -q "serving at" "$SERVE_LOG2" 2>/dev/null; then break; fi
    sleep 0.5
done
grep -q "serving at" "$SERVE_LOG2" && ok "--launch works from foreign cwd" \
    || bad "--launch works from foreign cwd"
kill $SP2 2>/dev/null
wait $SP2 2>/dev/null

# ── [12] DeployConfigError on bogus provider override ────────────────
echo "[12] bogus provider rejected by click"
BOGUS="$(uv run --quiet gtm dashboard deploy --launch "$LAUNCH" --provider bogus --dry-run 2>&1)"
RC=$?
[ $RC -ne 0 ] && echo "$BOGUS" | grep -q -i "invalid" \
    && ok "click rejects --provider bogus" || bad "click rejects --provider bogus"

# ── [13] parse_deploy_url unit (vercel.app + pages.dev) ──────────────
echo "[13] parse_deploy_url unit"
$PYRUN -c "
from gtm.launch.deploy import parse_deploy_url
assert parse_deploy_url('hello https://x.atf-launch.pages.dev cool') == 'https://x.atf-launch.pages.dev'
assert parse_deploy_url('Production: https://foo.vercel.app') == 'https://foo.vercel.app'
assert parse_deploy_url('') is None
assert parse_deploy_url('no urls here') is None
" >/dev/null 2>&1 && ok "parse_deploy_url handles known formats" || bad "parse_deploy_url handles known formats"

# ── Summary ──────────────────────────────────────────────────────────
echo
echo "── Results: $PASS pass / $FAIL fail ──"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
