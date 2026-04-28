#!/usr/bin/env bash
# CP3 e2e: `gtm post draft` interactive create.
# Uses --noninteractive everywhere so the editor never opens. The interactive
# path (Click prompts + click.edit) is human-tested.

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

TMP="$(mktemp -d -t gtm-launch-cp3.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

echo "── CP3: gtm post draft ──"
echo "Tmp: $TMP"

# ── Build a synthetic launch dir with 1 product, 1 direction ─────────
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
  reddit: reddit_default_user
  twitter: twitter_default_user
  hn: hn_default_user
dashboard: {}
YAML

# Reusable body file
BODY_FILE="$TMP/body.md"
cat > "$BODY_FILE" <<'BODY'
this is a real post body written by the user. lowercase ftw.
BODY

# ── [1] Module imports + helpers ─────────────────────────────────────
echo "[1] Module imports"
check "gtm.launch.draft imports cleanly" \
    "$PYRUN -c 'from gtm.launch.draft import build_slug, infer_platform, strip_template_comment, build_frontmatter, copy_image_into_assets, find_unique_slug, BODY_TEMPLATE'"
check "gtm.launch re-exports draft module" \
    "$PYRUN -c 'from gtm.launch import draft; assert hasattr(draft, \"build_slug\")'"

# ── [2] Pure helpers ─────────────────────────────────────────────────
echo "[2] Slug / platform / template helpers behave"
check "infer_platform('reddit r/foo') == 'reddit'" \
    "$PYRUN -c 'from gtm.launch.draft import infer_platform; assert infer_platform(\"reddit r/foo\") == \"reddit\"'"
check "infer_platform('twitter') == 'twitter'" \
    "$PYRUN -c 'from gtm.launch.draft import infer_platform; assert infer_platform(\"twitter\") == \"twitter\"'"
check "infer_platform('hn') == 'hn'" \
    "$PYRUN -c 'from gtm.launch.draft import infer_platform; assert infer_platform(\"hn\") == \"hn\"'"
check "build_slug includes date+channel+title pieces" \
    "$PYRUN -c '
from datetime import date
from gtm.launch.draft import build_slug
s = build_slug(\"reddit r/AI_Agents\", \"my First Post!\", day=date(2026,4,26))
assert s.startswith(\"2026-04-26-\"), s
assert \"reddit\" in s, s
assert \"my\" in s and \"first\" in s and \"post\" in s, s
assert len(s) <= 60, len(s)
'"
check "build_slug truncates to <=60 chars at hyphen boundary" \
    "$PYRUN -c '
from datetime import date
from gtm.launch.draft import build_slug
s = build_slug(\"reddit r/SomeReallyLongSubredditName\", \"this is a very long title that should be cut down quite a bit indeed\", day=date(2026,4,26))
assert len(s) <= 60, (s, len(s))
assert not s.endswith(\"-\"), s
'"
check "strip_template_comment removes the leading <!-- block -->" \
    "$PYRUN -c '
from gtm.launch.draft import strip_template_comment, BODY_TEMPLATE
out = strip_template_comment(BODY_TEMPLATE + \"hello world\\n\")
assert \"Karpathy\" not in out, out
assert \"hello world\" in out, out
'"

# ── [3] noninteractive draft creates a .md ───────────────────────────
echo "[3] noninteractive draft creates a file"
$GTM post draft my-product \
    --launch "$LAUNCH" \
    --channel "reddit r/test" \
    --noninteractive \
    --title "hello world test" \
    --body-file "$BODY_FILE" \
    >"$TMP/draft1.out" 2>&1 || { bad "post draft exited 0"; cat "$TMP/draft1.out"; }
ok "post draft exited 0"
check "exactly one .md created under my-product/posts/" \
    "[ \"\$(ls $LAUNCH/my-product/posts/*.md 2>/dev/null | wc -l | tr -d ' ')\" = 1 ]"

DRAFT1="$(ls "$LAUNCH/my-product/posts/"*.md | head -1)"
SLUG1="$(basename "$DRAFT1" .md)"
echo "  → draft path: $DRAFT1"
echo "  → slug:       $SLUG1"

# ── [4] Slug pattern: <YYYY-MM-DD>-<channel>-<title> ─────────────────
echo "[4] slug pattern check"
TODAY="$(date -u +%Y-%m-%d)"
check "slug starts with today's date" \
    "echo '$SLUG1' | grep -q '^${TODAY}-'"
check "slug contains 'reddit'" \
    "echo '$SLUG1' | grep -q 'reddit'"
check "slug contains words from title (hello/world/test)" \
    "echo '$SLUG1' | grep -qE 'hello|world|test'"
check "slug is lowercase + hyphens only" \
    "echo '$SLUG1' | grep -qE '^[a-z0-9-]+\$'"

# ── [5] Frontmatter has all required keys + defaults ─────────────────
echo "[5] Frontmatter sanity"
check "frontmatter has status: drafting" \
    "grep -q '^status: drafting' '$DRAFT1'"
check "frontmatter has identity defaulted from config (reddit_default_user)" \
    "grep -q '^identity: reddit_default_user' '$DRAFT1'"
check "frontmatter has product: my-product" \
    "grep -q '^product: my-product' '$DRAFT1'"
check "frontmatter has channel: reddit r/test" \
    "grep -q '^channel: reddit r/test' '$DRAFT1'"
check "frontmatter has kind: self (default)" \
    "grep -q '^kind: self' '$DRAFT1'"
check "frontmatter has metrics block" \
    "grep -q '^metrics:' '$DRAFT1'"

# ── [6] Body is the user-supplied text, NOT the template comment ─────
echo "[6] Body content"
check "body contains user-supplied text" \
    "grep -q 'real post body written by the user' '$DRAFT1'"
check "body does NOT contain Karpathy voice rules comment" \
    "! grep -q 'Karpathy voice rules' '$DRAFT1'"
check "body does NOT contain '<!--' block from template" \
    "! grep -q '<!-- ' '$DRAFT1'"

# ── [7] Title >75 chars triggers warning (but allowed) ───────────────
echo "[7] Long title warning (still writes)"
LONG_TITLE="$(printf 'x%.0s' {1..80})"
$GTM post draft my-product \
    --launch "$LAUNCH" \
    --channel "reddit r/longtitletest" \
    --noninteractive \
    --title "$LONG_TITLE" \
    --body-file "$BODY_FILE" \
    >"$TMP/long.out" 2>&1
EXIT_LONG=$?
check "long-title draft exits 0" "[ $EXIT_LONG -eq 0 ]"
check "long-title prints warning about >75 chars" \
    "grep -qi 'warning' '$TMP/long.out' && grep -q '75' '$TMP/long.out'"

# ── [8] Direction not in config → refused ────────────────────────────
echo "[8] Unknown direction is refused"
$GTM post draft my-product \
    --launch "$LAUNCH" \
    --channel "reddit r/test" \
    --direction unknown-direction \
    --noninteractive \
    --title "another title" \
    --body-file "$BODY_FILE" \
    >"$TMP/baddir.out" 2>&1 \
    && bad "draft should fail on unknown direction" \
    || ok "draft exits non-zero on unknown direction"
check "unknown-direction error mentions the direction key" \
    "grep -q 'unknown-direction' '$TMP/baddir.out'"
check "unknown-direction error lists known directions" \
    "grep -q 'doc-drift' '$TMP/baddir.out'"

# ── [9] Product not in config → refused ──────────────────────────────
echo "[9] Unknown product is refused"
$GTM post draft no-such-product \
    --launch "$LAUNCH" \
    --channel "reddit r/test" \
    --noninteractive \
    --title "another title" \
    --body-file "$BODY_FILE" \
    >"$TMP/badprod.out" 2>&1 \
    && bad "draft should fail on unknown product" \
    || ok "draft exits non-zero on unknown product"
check "unknown-product error mentions the product key" \
    "grep -q 'no-such-product' '$TMP/badprod.out'"

# ── [10] Slug collision → refused with suffix suggestion ─────────────
echo "[10] Slug collision is refused with suggestion"
# Re-run the same command from [3] — should collide
$GTM post draft my-product \
    --launch "$LAUNCH" \
    --channel "reddit r/test" \
    --noninteractive \
    --title "hello world test" \
    --body-file "$BODY_FILE" \
    >"$TMP/collide.out" 2>&1 \
    && bad "draft should fail on slug collision" \
    || ok "draft exits non-zero on slug collision"
check "collision error mentions 'already exists'" \
    "grep -qi 'already exists' '$TMP/collide.out'"
check "collision error suggests a -2 suffix" \
    "grep -q -- '-2' '$TMP/collide.out'"

# ── [11] --kind image copies image into assets/ + sets frontmatter ──
echo "[11] image kind copies asset + sets frontmatter"
IMG_SRC="$TMP/foo.png"
printf '\x89PNG\r\n\x1a\n' > "$IMG_SRC"  # minimal PNG-ish bytes
$GTM post draft my-product \
    --launch "$LAUNCH" \
    --channel "reddit r/imgtest" \
    --noninteractive \
    --kind image \
    --image "$IMG_SRC" \
    --title "image post hello" \
    --body-file "$BODY_FILE" \
    >"$TMP/img.out" 2>&1 || { bad "image draft exited 0"; cat "$TMP/img.out"; }
ok "image draft exited 0"
check "image was copied into <product>/posts/assets/foo.png" \
    "[ -f '$LAUNCH/my-product/posts/assets/foo.png' ]"
IMG_DRAFT="$(ls "$LAUNCH/my-product/posts/"*imgtest*.md | head -1)"
check "image draft frontmatter has image: posts/assets/foo.png" \
    "grep -q 'image: posts/assets/foo.png' '$IMG_DRAFT'"
check "image draft frontmatter has kind: image" \
    "grep -q '^kind: image' '$IMG_DRAFT'"

# ── [12] Inferred identity from channel: reddit ──────────────────────
echo "[12] reddit channel → reddit default identity"
# Already covered by [5] but assert independently for clarity.
check "draft from [3] used reddit_default_user" \
    "grep -q 'identity: reddit_default_user' '$DRAFT1'"

# ── [13] Inferred identity from channel: twitter ─────────────────────
echo "[13] twitter channel → twitter default identity"
$GTM post draft my-product \
    --launch "$LAUNCH" \
    --channel "twitter" \
    --noninteractive \
    --title "twitter draft please" \
    --body-file "$BODY_FILE" \
    >"$TMP/tw.out" 2>&1 || { bad "twitter draft exit 0"; cat "$TMP/tw.out"; }
TW_DRAFT="$(ls "$LAUNCH/my-product/posts/"*twitter*.md | head -1)"
check "twitter draft used twitter_default_user" \
    "grep -q 'identity: twitter_default_user' '$TW_DRAFT'"

# ── [14] Round-trip with CP2: post list shows the drafts ─────────────
echo "[14] gtm post list (CP2) sees the new drafts"
COLUMNS=400 $GTM post list --launch "$LAUNCH" --status drafting >"$TMP/list.out" 2>&1
check "post list shows the slug from [3] (or its channel)" \
    "grep -q '${SLUG1}' '$TMP/list.out' || grep -q 'reddit r/test' '$TMP/list.out' || grep -q 'r/test' '$TMP/list.out'"
check "post list footer counts >= 4 drafts" \
    "grep -qE '[4-9] post' '$TMP/list.out' || grep -qE '[1-9][0-9]+ post' '$TMP/list.out'"

# ── [15] Direction valid → accepted + recorded ───────────────────────
echo "[15] Valid direction is accepted"
$GTM post draft my-product \
    --launch "$LAUNCH" \
    --channel "reddit r/dirtest" \
    --direction doc-drift \
    --noninteractive \
    --title "valid direction draft" \
    --body-file "$BODY_FILE" \
    >"$TMP/dirok.out" 2>&1 || { bad "valid-direction draft exit 0"; cat "$TMP/dirok.out"; }
DIR_DRAFT="$(ls "$LAUNCH/my-product/posts/"*dirtest*.md | head -1)"
check "frontmatter has direction: doc-drift" \
    "grep -q '^direction: doc-drift' '$DIR_DRAFT'"

echo
echo "── CP3 result: $PASS passed, $FAIL failed ──"
[ "$FAIL" -eq 0 ]
