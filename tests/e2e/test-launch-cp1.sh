#!/usr/bin/env bash
# CP1 e2e: launch directory model — init / link / info / find().
# Verifies LaunchDir API + the three CLI commands behave per the plan,
# critically that `link` does not clobber existing files.

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
# Use absolute path to the venv binary so subshells that `cd` into temp
# dirs don't lose uv's project context (which made `uv run gtm` fall
# through to a non-project gtm and report `No such command 'launch'`).
GTM="$REPO/.venv/bin/gtm"

TMP="$(mktemp -d -t gtm-launch-cp1.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

echo "── CP1: launch directory model ──"
echo "Tmp: $TMP"

echo "[1] Module imports"
check "gtm.launch imports cleanly" \
    "$PYRUN -c 'from gtm.launch import LaunchDir, LAUNCH_MARKER, LaunchDirError'"

check "gtm.launch.dir scaffold helpers import" \
    "$PYRUN -c 'from gtm.launch.dir import build_default_config, scaffold_layout, SCHEMA_VERSION'"

echo "[2] LaunchDir.find() walk-up + None case"
EMPTY="$TMP/empty"
mkdir -p "$EMPTY/a/b/c"
check "find() returns None when no marker anywhere up the tree" \
    "GTM_LAUNCH_DIR= $PYRUN -c '
import os
os.environ.pop(\"GTM_LAUNCH_DIR\", None)
from pathlib import Path
from gtm.launch import LaunchDir
out = LaunchDir.find(Path(\"$EMPTY/a/b/c\"))
assert out is None, out
'"

echo "[3] gtm launch init scaffolds full layout"
INIT_DIR="$TMP/myllaunch"
mkdir -p "$INIT_DIR"
# Feed prompts: 2 products, 1 direction, blank cloudflare project
INIT_INPUT='alpha
Alpha
the alpha tagline
active
beta
Beta
beta tag
next

doc-drift
solve doc drifts

'
echo "$INIT_INPUT" | $GTM launch init "$INIT_DIR" >"$TMP/init.out" 2>&1 || {
    echo "init failed:"; cat "$TMP/init.out"; bad "launch init ran"; exit 1
}
ok "launch init ran"

check "marker .gtm-launch.yaml exists" "[ -f '$INIT_DIR/.gtm-launch.yaml' ]"
check "README.md scaffolded" "[ -f '$INIT_DIR/README.md' ]"
check "ROADMAP.md scaffolded" "[ -f '$INIT_DIR/ROADMAP.md' ]"
check "dist/ scaffolded" "[ -d '$INIT_DIR/dist' ]"
check ".gitignore mentions dist/" "grep -q '^dist/$' '$INIT_DIR/.gitignore'"
check "alpha/posts/ scaffolded" "[ -d '$INIT_DIR/alpha/posts' ]"
check "alpha/posts/assets/ scaffolded" "[ -d '$INIT_DIR/alpha/posts/assets' ]"
check "alpha/ROADMAP.md scaffolded" "[ -f '$INIT_DIR/alpha/ROADMAP.md' ]"
check "beta/posts/ scaffolded" "[ -d '$INIT_DIR/beta/posts' ]"

echo "[4] .gtm-launch.yaml is well-formed"
check "yaml loads + has expected top-level keys" \
    "$PYRUN -c '
import yaml
from pathlib import Path
data = yaml.safe_load(Path(\"$INIT_DIR/.gtm-launch.yaml\").read_text())
for k in (\"version\", \"products\", \"directions\", \"default_identity_by_platform\", \"dashboard\"):
    assert k in data, (k, data)
assert data[\"version\"] == 1
assert len(data[\"products\"]) == 2
assert data[\"products\"][0][\"key\"] == \"alpha\"
assert data[\"products\"][1][\"key\"] == \"beta\"
assert len(data[\"directions\"]) == 1
assert data[\"directions\"][0][\"key\"] == \"doc-drift\"
'"

echo "[5] LaunchDir.find() walks up from a nested cwd"
mkdir -p "$INIT_DIR/alpha/posts/deep/nested"
INIT_DIR_REAL="$(cd "$INIT_DIR" && pwd -P)"
check "find() locates marker from a deep subdir" \
    "$PYRUN -c '
import os
os.environ.pop(\"GTM_LAUNCH_DIR\", None)
from pathlib import Path
from gtm.launch import LaunchDir
ld = LaunchDir.find(Path(\"$INIT_DIR/alpha/posts/deep/nested\"))
assert ld is not None
assert str(ld.path) == \"$INIT_DIR_REAL\", (ld.path, \"$INIT_DIR_REAL\")
assert len(ld.products) == 2
'"

echo "[6] gtm launch info reads via --launch <path>"
$GTM launch info --launch "$INIT_DIR" >"$TMP/info.out" 2>&1 || bad "info --launch ran"
check "info --launch shows alpha product" "grep -q 'alpha' '$TMP/info.out'"
check "info --launch shows beta product" "grep -q 'beta' '$TMP/info.out'"
check "info --launch shows doc-drift direction" "grep -q 'doc-drift' '$TMP/info.out'"

echo "[7] gtm launch info reads via cwd walk-up"
(cd "$INIT_DIR/alpha/posts/deep/nested" && $GTM launch info >"$TMP/info_walkup.out" 2>&1) \
    && ok "info ran from nested cwd" \
    || bad "info ran from nested cwd"
check "walk-up info found launch dir path" \
    "grep -q '$INIT_DIR' '$TMP/info_walkup.out'"

echo "[8] gtm launch link does NOT clobber existing files (Q1=a)"
LINK_DIR="$TMP/existing"
mkdir -p "$LINK_DIR/myproduct/posts"
echo "ORIGINAL DASHBOARD" > "$LINK_DIR/dashboard.html"
echo "ORIGINAL README" > "$LINK_DIR/README.md"
echo "EXISTING POST" > "$LINK_DIR/myproduct/posts/d1.md"
DASH_HASH_BEFORE=$(shasum "$LINK_DIR/dashboard.html" | cut -d' ' -f1)
README_HASH_BEFORE=$(shasum "$LINK_DIR/README.md" | cut -d' ' -f1)
POST_HASH_BEFORE=$(shasum "$LINK_DIR/myproduct/posts/d1.md" | cut -d' ' -f1)

# link prompts: confirm inferred products (y), no directions, no cloudflare
LINK_INPUT='y

'
echo "$LINK_INPUT" | $GTM launch link "$LINK_DIR" >"$TMP/link.out" 2>&1 || {
    echo "link failed:"; cat "$TMP/link.out"; bad "launch link ran"; exit 1
}
ok "launch link ran"

check "link wrote .gtm-launch.yaml" "[ -f '$LINK_DIR/.gtm-launch.yaml' ]"

DASH_HASH_AFTER=$(shasum "$LINK_DIR/dashboard.html" | cut -d' ' -f1)
README_HASH_AFTER=$(shasum "$LINK_DIR/README.md" | cut -d' ' -f1)
POST_HASH_AFTER=$(shasum "$LINK_DIR/myproduct/posts/d1.md" | cut -d' ' -f1)

check "dashboard.html UNCHANGED after link" "[ '$DASH_HASH_BEFORE' = '$DASH_HASH_AFTER' ]"
check "README.md UNCHANGED after link" "[ '$README_HASH_BEFORE' = '$README_HASH_AFTER' ]"
check "existing post UNCHANGED after link" "[ '$POST_HASH_BEFORE' = '$POST_HASH_AFTER' ]"

check "link inferred 'myproduct' from existing posts/ subdir" \
    "$PYRUN -c '
import yaml
data = yaml.safe_load(open(\"$LINK_DIR/.gtm-launch.yaml\").read())
keys = [p[\"key\"] for p in data[\"products\"]]
assert \"myproduct\" in keys, keys
'"

echo "[9] link refuses to clobber an existing marker"
echo "$LINK_INPUT" | $GTM launch link "$LINK_DIR" >"$TMP/link2.out" 2>&1 \
    && bad "link should fail when marker exists" \
    || ok "link refused to overwrite existing marker"

echo "[10] init refuses on existing marker"
echo "$INIT_INPUT" | $GTM launch init "$INIT_DIR" >"$TMP/init2.out" 2>&1 \
    && bad "init should fail when marker exists" \
    || ok "init refused to overwrite existing marker"

echo "[11] info errors gracefully when no launch dir found"
NOLAUNCH="$TMP/nolaunch"
mkdir -p "$NOLAUNCH"
(cd "$NOLAUNCH" && GTM_LAUNCH_DIR= $GTM launch info >"$TMP/info_none.out" 2>&1) \
    && bad "info should fail with no launch dir" \
    || ok "info exits non-zero when no launch dir found"

echo
echo "── CP1 result: $PASS passed, $FAIL failed ──"
[ "$FAIL" -eq 0 ]
