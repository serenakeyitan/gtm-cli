#!/usr/bin/env bash
# E2e: gtm identity migrate-from-openclaw handles per-account session dirs
# (reddit_session_pale, reddit_session_ok, etc), and writes storage_state.json
# directly under identity_dir (not session/ subdir) so the gtm Reddit client
# can find it.

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

echo "── migrate: multi-account openclaw → gtm identities ──"

# Synthetic openclaw layout in a tmp dir + tmp gtm config
TMP="$(mktemp -d)"
export GTM_CONFIG_DIR="$TMP/gtm"
SECRETS="$TMP/openclaw"
mkdir -p "$SECRETS/reddit_session_pale" "$SECRETS/reddit_session_ok" "$SECRETS/reddit_session"
echo '{"cookies":[],"origins":[]}' > "$SECRETS/reddit_session_pale/storage_state.json"
echo '{"cookies":[],"origins":[]}' > "$SECRETS/reddit_session_ok/storage_state.json"
echo '{"cookies":[],"origins":[]}' > "$SECRETS/reddit_session/storage_state.json"

echo "[1] Migrate discovers all 3 reddit session dirs"
check "migrate returns 3 reddit identities" \
    "$PYRUN -c '
import importlib, gtm.config
gtm.config = importlib.reload(gtm.config)
from pathlib import Path
import gtm.identity.migrate as m
m.OLD_SECRETS_DIR = Path(\"$SECRETS\")
import gtm.identity.manager as mgr
mgr.IDENTITIES_DIR = gtm.config.IDENTITIES_DIR
m.IDENTITIES_DIR = gtm.config.IDENTITIES_DIR
got = m.migrate_from_openclaw()
assert sorted(got) == sorted([\"reddit:openclaw_migrated\", \"reddit:ok\", \"reddit:pale\"]), got
'"

echo "[2] storage_state.json lives directly under identity_dir (not session/)"
check "Pale identity has storage_state.json at the correct level" \
    "test -f \"$TMP/gtm/identities/reddit/pale/storage_state.json\" && ! test -f \"$TMP/gtm/identities/reddit/pale/session/storage_state.json\""
check "Ok identity has storage_state.json at the correct level" \
    "test -f \"$TMP/gtm/identities/reddit/ok/storage_state.json\""

echo "[3] identity.yaml is well-formed"
check "Pale identity.yaml has username + browser auth_method" \
    "$PYRUN -c '
import yaml
d = yaml.safe_load(open(\"$TMP/gtm/identities/reddit/pale/identity.yaml\"))
assert d[\"username\"] == \"pale\", d
assert d[\"platform\"] == \"reddit\", d
assert d[\"auth_method\"] == \"browser\", d
'"

echo "[4] Re-running migrate is idempotent (no error, no duplication)"
check "second run returns same 3 names without crashing" \
    "$PYRUN -c '
import importlib, gtm.config
gtm.config = importlib.reload(gtm.config)
from pathlib import Path
import gtm.identity.migrate as m
m.OLD_SECRETS_DIR = Path(\"$SECRETS\")
import gtm.identity.manager as mgr
mgr.IDENTITIES_DIR = gtm.config.IDENTITIES_DIR
m.IDENTITIES_DIR = gtm.config.IDENTITIES_DIR
got = m.migrate_from_openclaw()
assert sorted(got) == sorted([\"reddit:openclaw_migrated\", \"reddit:ok\", \"reddit:pale\"]), got
'"

echo "[5] Reddit client resolves migrated identity to correct session"
check "session_dir_for_identity('pale', 'reddit') points to dir with storage_state.json" \
    "$PYRUN -c '
import importlib, gtm.config
gtm.config = importlib.reload(gtm.config)
import gtm.identity.manager as mgr; importlib.reload(mgr)
import gtm.identity.session as s; importlib.reload(s)
from pathlib import Path
d = s.session_dir_for_name(\"pale\")
assert (Path(d) / \"storage_state.json\").exists(), d
'"

rm -rf "$TMP"

echo
echo "── migrate result: $PASS passed, $FAIL failed ──"
[ "$FAIL" -eq 0 ]
