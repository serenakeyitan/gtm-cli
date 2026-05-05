#!/usr/bin/env bash
# CP6 e2e: `gtm dashboard build` — render dashboard.html from frontmatter.
# Builds against synthetic launch dirs and verifies POSTS_JSON shape +
# template substitution.

set -uo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO"

PASS=0
FAIL=0

ok()  { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

PYRUN="uv run --quiet python"

TMP="$(mktemp -d -t gtm-launch-cp6.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

echo "── CP6: gtm dashboard build ──"
echo "Tmp: $TMP"

# ── Synthetic launch dir with 2 posts (1 live, 1 removed) ────────────
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
  - key: llm-wiki
    label: llm-wiki
default_identity_by_platform:
  reddit: Pale_Stand5217
dashboard: {}
YAML

cat > "$LAUNCH/my-product/posts/2026-04-25-alpha.md" <<'POST'
---
id: p1
product: my-product
direction: doc-drift
channel: reddit r/test
identity: Pale_Stand5217
kind: image
image: my-product/posts/assets/foo.png
status: live
url: https://reddit.com/r/test/comments/abc111/alpha_title/
live_id: abc111
posted_at: 2026-04-25T10:00:00Z
metrics:
  score: 8
  comments: 6
  comments_real: 4
  last_checked: 2026-04-25T11:00:00Z
note: alpha title note
---
body alpha
POST

cat > "$LAUNCH/my-product/posts/2026-04-26-beta.md" <<'POST'
---
id: p2
product: my-product
direction: llm-wiki
channel: reddit r/test
identity: Pale_Stand5217
kind: self
status: removed
url: https://reddit.com/r/test/comments/def222/beta_title/
live_id: def222
posted_at: 2026-04-26T10:00:00Z
metrics:
  score: 0
  comments: 0
note: removed by mods (self-promo)
---
body beta
POST

OUT="$LAUNCH/dashboard.html"

# ── [1] Module imports ───────────────────────────────────────────────
echo "[1] Module imports"
$PYRUN -c "from gtm.launch.dashboard import build_dashboard, write_dashboard, TEMPLATE_PATH" \
    >/dev/null 2>&1 && ok "gtm.launch.dashboard imports cleanly" || bad "gtm.launch.dashboard imports cleanly"

$PYRUN -c "from gtm.launch import dashboard; assert hasattr(dashboard, 'build_dashboard')" \
    >/dev/null 2>&1 && ok "gtm.launch re-exports dashboard module" || bad "gtm.launch re-exports dashboard module"

# ── [2] Template file exists + has all four placeholders ─────────────
echo "[2] Template placeholders present"
$PYRUN -c "
from gtm.launch.dashboard import TEMPLATE_PATH
t = TEMPLATE_PATH.read_text()
for ph in ['{{TODAY}}','{{DIRECTIONS_JSON}}','{{PRODUCTS_JSON}}','{{POSTS_JSON}}']:
    assert ph in t, ph
" >/dev/null 2>&1 && ok "template has all 4 placeholders" || bad "template has all 4 placeholders"

# ── [3] CLI default path writes to <launch>/dashboard.html ───────────
echo "[3] gtm dashboard build (default --out)"
rm -f "$OUT"
uv run --quiet gtm dashboard build --launch "$LAUNCH" >/tmp/cp6_stdout 2>&1
RC=$?
[ $RC -eq 0 ] && [ -f "$OUT" ] && ok "default build writes <launch>/dashboard.html" \
    || bad "default build writes <launch>/dashboard.html (rc=$RC)"

# ── [4] stdout reports byte count + path ─────────────────────────────
echo "[4] stdout banner"
grep -q "wrote .* bytes to .*dashboard.html" /tmp/cp6_stdout \
    && ok "stdout has 'wrote N bytes to <path>'" || bad "stdout has 'wrote N bytes to <path>'"

# ── [5] --out overrides output path ──────────────────────────────────
echo "[5] --out override"
ALT="$TMP/alt.html"
uv run --quiet gtm dashboard build --launch "$LAUNCH" --out "$ALT" >/dev/null 2>&1
[ -f "$ALT" ] && ok "--out writes to override path" || bad "--out writes to override path"

# ── [6] No unsubstituted placeholders ────────────────────────────────
echo "[6] All placeholders substituted"
$PYRUN -c "
t = open('$OUT').read()
for ph in ['{{TODAY}}','{{DIRECTIONS_JSON}}','{{PRODUCTS_JSON}}','{{POSTS_JSON}}']:
    assert ph not in t, f'{ph} still present'
" >/dev/null 2>&1 && ok "no {{...}} placeholders remain" || bad "no {{...}} placeholders remain"

# ── [7] POSTS_JSON parses as valid JSON when extracted ───────────────
echo "[7] POSTS_JSON parses cleanly"
$PYRUN -c "
import re, json
t = open('$OUT').read()
m = re.search(r'const POSTS = (\[.*?\]);', t, re.DOTALL)
assert m, 'POSTS array not found'
posts = json.loads(m.group(1))
assert isinstance(posts, list)
assert len(posts) == 2, len(posts)
" >/dev/null 2>&1 && ok "POSTS_JSON is valid JSON, 2 entries" || bad "POSTS_JSON is valid JSON, 2 entries"

# ── [8] Both post titles/ids appear in rendered POSTS ────────────────
echo "[8] Both posts present in JSON"
$PYRUN -c "
import re, json
t = open('$OUT').read()
m = re.search(r'const POSTS = (\[.*?\]);', t, re.DOTALL)
posts = json.loads(m.group(1))
ids = {p['id'] for p in posts}
assert ids == {'p1','p2'}, ids
" >/dev/null 2>&1 && ok "both ids p1, p2 present" || bad "both ids p1, p2 present"

# ── [9] image field renders for image-kind post ──────────────────────
echo "[9] image field passthrough"
$PYRUN -c "
import re, json
t = open('$OUT').read()
m = re.search(r'const POSTS = (\[.*?\]);', t, re.DOTALL)
posts = {p['id']: p for p in json.loads(m.group(1))}
assert posts['p1'].get('image') == 'my-product/posts/assets/foo.png', posts['p1']
" >/dev/null 2>&1 && ok "image field passes through" || bad "image field passes through"

# ── [10] comments_real flat at top-level (not under metrics) ─────────
echo "[10] metrics hoisted to top-level"
$PYRUN -c "
import re, json
t = open('$OUT').read()
m = re.search(r'const POSTS = (\[.*?\]);', t, re.DOTALL)
posts = {p['id']: p for p in json.loads(m.group(1))}
p1 = posts['p1']
assert p1.get('score') == 8, p1
assert p1.get('comments') == 6, p1
assert p1.get('comments_real') == 4, p1
assert p1.get('last_checked', '').startswith('2026-04-25'), p1
assert 'metrics' not in p1, 'metrics should be flattened, not nested'
" >/dev/null 2>&1 && ok "score/comments/comments_real/last_checked hoisted; no nested metrics" \
                || bad "score/comments/comments_real/last_checked hoisted; no nested metrics"

# ── [11] removed post has reason field ───────────────────────────────
echo "[11] removed post → reason"
$PYRUN -c "
import re, json
t = open('$OUT').read()
m = re.search(r'const POSTS = (\[.*?\]);', t, re.DOTALL)
posts = {p['id']: p for p in json.loads(m.group(1))}
p2 = posts['p2']
assert p2['status'] == 'removed', p2
assert p2.get('reason'), 'reason should be populated for removed posts'
" >/dev/null 2>&1 && ok "removed post has reason" || bad "removed post has reason"

# ── [12] DIRECTIONS_JSON sourced from .gtm-launch.yaml ───────────────
echo "[12] DIRECTIONS_JSON from yaml"
$PYRUN -c "
import re, json
t = open('$OUT').read()
m = re.search(r'const DIRECTIONS = (\[.*?\]);', t, re.DOTALL)
dirs = json.loads(m.group(1))
keys = {d['key'] for d in dirs}
assert keys == {'doc-drift','llm-wiki'}, keys
" >/dev/null 2>&1 && ok "DIRECTIONS pulled from yaml" || bad "DIRECTIONS pulled from yaml"

# ── [13] PRODUCTS_JSON sourced from yaml ─────────────────────────────
echo "[13] PRODUCTS_JSON from yaml"
$PYRUN -c "
import re, json
t = open('$OUT').read()
m = re.search(r'const PRODUCTS = (\[.*?\]);', t, re.DOTALL)
prods = json.loads(m.group(1))
keys = {p['key'] for p in prods}
assert keys == {'my-product'}, keys
" >/dev/null 2>&1 && ok "PRODUCTS pulled from yaml" || bad "PRODUCTS pulled from yaml"

# ── [14] date derived from posted_at ─────────────────────────────────
echo "[14] date derived from posted_at"
$PYRUN -c "
import re, json
t = open('$OUT').read()
m = re.search(r'const POSTS = (\[.*?\]);', t, re.DOTALL)
posts = {p['id']: p for p in json.loads(m.group(1))}
assert posts['p1']['date'] == '2026-04-25', posts['p1']
assert posts['p2']['date'] == '2026-04-26', posts['p2']
" >/dev/null 2>&1 && ok "date YYYY-MM-DD prefix from posted_at" \
                || bad "date YYYY-MM-DD prefix from posted_at"

# ── [15] account synthesized as u/<identity> ─────────────────────────
echo "[15] account synth"
$PYRUN -c "
import re, json
t = open('$OUT').read()
m = re.search(r'const POSTS = (\[.*?\]);', t, re.DOTALL)
posts = {p['id']: p for p in json.loads(m.group(1))}
assert posts['p1']['account'] == 'u/Pale_Stand5217', posts['p1']
" >/dev/null 2>&1 && ok "account = u/<identity>" || bad "account = u/<identity>"

# ── [16] Output ends with </html> ────────────────────────────────────
echo "[16] file ends with </html>"
$PYRUN -c "
t = open('$OUT').read().rstrip()
assert t.endswith('</html>'), repr(t[-40:])
" >/dev/null 2>&1 && ok "file ends with </html>" || bad "file ends with </html>"

# ── [17] Idempotent: build twice → identical bytes ───────────────────
echo "[17] idempotent build (today fixed)"
$PYRUN -c "
from gtm.launch.dashboard import build_dashboard
from gtm.launch import LaunchDir
ld = LaunchDir.load('$LAUNCH')
a = build_dashboard(ld, today='2026-04-30')
b = build_dashboard(ld, today='2026-04-30')
assert a == b, 'build is not idempotent'
" >/dev/null 2>&1 && ok "build is idempotent for fixed today" \
                || bad "build is idempotent for fixed today"

# ── [18] TODAY substituted with given value ──────────────────────────
echo "[18] TODAY substituted"
$PYRUN -c "
from gtm.launch.dashboard import build_dashboard
from gtm.launch import LaunchDir
ld = LaunchDir.load('$LAUNCH')
html = build_dashboard(ld, today='2026-04-30')
assert \"const TODAY = '2026-04-30';\" in html, 'TODAY not substituted'
" >/dev/null 2>&1 && ok "TODAY literal substituted" || bad "TODAY literal substituted"

# ── [19] Empty launch (no posts) doesn't crash, POSTS=[] ─────────────
echo "[19] empty launch dir"
EMPTY="$TMP/empty"
mkdir -p "$EMPTY/p1/posts"
cat > "$EMPTY/.gtm-launch.yaml" <<'YAML'
version: 1
products:
  - key: p1
    name: p1
    tagline: solo
    status: active
directions: []
default_identity_by_platform: {}
dashboard: {}
YAML
uv run --quiet gtm dashboard build --launch "$EMPTY" >/dev/null 2>&1
[ -f "$EMPTY/dashboard.html" ] && $PYRUN -c "
import re, json
t = open('$EMPTY/dashboard.html').read()
m = re.search(r'const POSTS = (\[.*?\]);', t, re.DOTALL)
assert json.loads(m.group(1)) == [], 'POSTS should be empty array'
m2 = re.search(r'const DIRECTIONS = (\[.*?\]);', t, re.DOTALL)
assert json.loads(m2.group(1)) == [], 'DIRECTIONS should be empty array'
" >/dev/null 2>&1 && ok "empty launch builds, POSTS=[]" || bad "empty launch builds, POSTS=[]"

# ── [20] Build against atf-launch (real) → no crash ──────────────────
echo "[20] build against /Users/keyitan/atf-launch (real, no crash)"
ATF_OUT="$TMP/atf-built.html"
if [ -f "/Users/keyitan/atf-launch/.gtm-launch.yaml" ]; then
    uv run --quiet gtm dashboard build --launch /Users/keyitan/atf-launch --out "$ATF_OUT" >/dev/null 2>&1
    if [ -f "$ATF_OUT" ]; then
        $PYRUN -c "
t = open('$ATF_OUT').read()
assert t.rstrip().endswith('</html>')
import re, json
m = re.search(r'const POSTS = (\[.*?\]);', t, re.DOTALL)
posts = json.loads(m.group(1))
print('atf posts:', len(posts))
" >/dev/null 2>&1 && ok "atf-launch builds without crash" || bad "atf-launch builds without crash"
    else
        bad "atf-launch builds without crash (no output)"
    fi
else
    ok "atf-launch builds without crash (skipped — no marker yet)"
fi

# ── Summary ──────────────────────────────────────────────────────────
echo
echo "── Results: $PASS pass / $FAIL fail ──"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
