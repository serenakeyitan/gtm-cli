# Port Plan: openclaw-growth-pipeline → gtm-cli

**Date:** 2026-04-24
**Source:** `serenakeyitan/growth-sop-pipeline` branch `wip/multi-account-engagement-pre-archive` (already pushed, safety snapshot)
**Target:** this repo (`serenakeyitan/gtm-cli`)
**End state:** all today's work lives in gtm-cli; openclaw repo gets archived (read-only, not deleted).

---

## What today's openclaw work added

11 net-new files + 5 modified, totalling ~600 lines of code + a 33-test e2e suite.

| File (in openclaw) | Purpose | Lines |
|---|---|---|
| `accounts.py` | Multi-account registry at `~/.openclaw-growth-pipeline/accounts.json` | ~80 |
| `account_affinity.py` | Learn which account scores best on which sub from run history | ~120 |
| `warmup.py` | Per-launch handle list for sock-puppet warm comments | ~70 |
| `utils/playwright_twitter_client.py` | Browser-based Twitter client (post/thread/reply/check) | ~280 |
| `tools/twitter_browser_tools.py` | MCP tool wrappers for the above | ~110 |
| `agents/twitter_promoter.py` | Twitter promoter agent shim | ~100 |
| `prompts/twitter_promoter.md` | Voice rules: lowercase, no em dashes, ICP statement | ~60 |
| `agents/engagement_loop.py` | Comment-triage daily digest agent | ~95 |
| `prompts/engagement_loop.md` | 5-bucket triage framework + draft_only mode | ~50 |
| `tests/e2e/test-multi-account-pipeline.sh` | 33 checks across 8 sections | ~280 |
| `utils/playwright_reddit_client.py` (M) | Per-dir client cache + `get_reddit_browser_client_for_account` | +30 |
| `tools/reddit_tools.py` (M) | `account` param on submit + 3 new tools + extended opener archetypes | +140 |
| `agents/promoter.py` (M) | Phase C uses `reddit_pick_account_for_sub` per sub | +20 |
| `prompts/promoter.md` (M) | Documents the new account-selection step | +15 |
| `cli.py` (M) | New subgroups: `reddit`, `twitter`, `warmup`, `engagement` | +180 |

---

## What gtm-cli already has that overlaps

| Concept | gtm-cli location | Today's openclaw equivalent | Decision |
|---|---|---|---|
| Identity / account registry | `gtm/identity/manager.py` (richer: roles, rate_profile, status, health.json, 0700/0600 perms) | `accounts.py` (simpler) | **Use gtm-cli's IdentityManager. Drop accounts.py.** |
| Reddit Playwright client | `gtm/platforms/reddit/client.py` | `utils/playwright_reddit_client.py` | gtm-cli's. **Add per-identity caching** (today's change). |
| Reddit MCP tools | `gtm/platforms/reddit/tools.py` (no `account` param) | `tools/reddit_tools.py` (with `account`) | gtm-cli's. **Add `identity` param** (renamed from `account`). |
| HN Playwright client | `gtm/platforms/hn/client.py` | `tools/hn_tools.py` (lighter) | gtm-cli's. No port needed. |
| Twitter API client | `gtm/platforms/twitter/client.py` (twikit-based, **API only**) | n/a | Keep both: API for read, browser for write. |
| Agents (promoter/builder/scout/etc) | `gtm/agents/*` | `openclaw/agents/*` (parent) | gtm-cli's are descendants. **Modify gtm's promoter.py** to use account selection. |
| `agent_wrapper`, `activity_log`, `state_tools`, `RunState` | All present in gtm-cli with same/compatible signatures | Same names in openclaw | Drop-in for new agents. |
| CLI shape | `gtm` (auth, identity, run, modules, traction) | `openclaw-growth-pipeline` (custom subgroups) | gtm-cli's. **Add new subgroups under gtm's style.** |

---

## The 6 design decisions

These are the calls I'd otherwise guess. Confirm or override.

### D1. `accounts.py` → drop, use IdentityManager

Today's `accounts.py` stores `{name, service, session_dir, notes}` at `~/.openclaw-growth-pipeline/accounts.json`. gtm-cli's `IdentityManager` stores far more (`role`, `rate_profile`, `status`, `health`, `proxy`) at `~/.config/gtm/identities/<platform>/<username>/`.

**Recommendation:** Drop `accounts.py`. Wire the new MCP tools to read identity via `IdentityManager().get(name)`. Cookies/session lives at `<identity_dir>/storage_state.json`.

**Tradeoff:** Today's e2e test uses `accounts.json` directly. Test rewrite adds ~30 lines.

### D2. MCP tool param: `account` vs `identity`

Today's openclaw uses `account="myhandle"`. gtm-cli's vocabulary is `identity` everywhere.

**Recommendation:** Rename to `identity` for consistency. Format: `"twitter:myhandle"` or just `"myhandle"` (auto-resolve if unambiguous, matching `IdentityManager.get()` behavior).

### D3. `account_affinity.py` → new module under `gtm/modules/filters/`

Today it's a standalone Python module read by reddit_tools. In gtm-cli's architecture, it should be a discoverable Module so it shows up in `gtm modules list` and can be used in YAML strategies.

**Recommendation:**
- New module: `gtm/modules/filters/identity_affinity.py` (renamed for consistency).
- Reads run history from gtm-cli's output dir (not openclaw's `runs/`).
- Also keep an `agents/`-callable function so the promoter agent can call it directly without going through the module DAG.

**Tradeoff:** Slight duplication (module + function) but matches gtm's two-layer pattern (modules for strategies, helpers for agents).

### D4. `warmup.py` → standalone CLI subgroup OR identity metadata

Two reasonable homes:
- **Option A:** Stays standalone at `gtm/launch/warmup.py` with `gtm warmup add/list/remove` CLI. Per-launch JSON at `~/.config/gtm/warmup.json`.
- **Option B:** Add a `warmup_for: [launch_id, ...]` field to Identity; query via `IdentityManager.list_warmup(launch_id)`.

**Recommendation:** Option A. Warmup is launch-scoped, not identity-scoped (one identity may warm 5 launches; one launch needs 5 identities). Keeping it separate avoids muddying the identity schema.

### D5. CLI surface

Today's openclaw CLI has 4 new subgroups. Mapping into gtm:

| Openclaw command | gtm-cli equivalent | Status |
|---|---|---|
| `openclaw reddit add-account` | `gtm auth reddit` | **Already exists in gtm. Drop today's command.** |
| `openclaw reddit list-accounts` | `gtm identity list --platform reddit` | Already exists. Drop. |
| `openclaw reddit verify-account` | `gtm identity health <name>` | Already exists. Drop. |
| `openclaw reddit affinity` | **NEW: `gtm identity affinity`** | Show learned affinity table |
| `openclaw twitter add/list/verify-account` | Same as reddit (use existing `gtm auth/identity`) | Drop today's commands. |
| `openclaw warmup add/list/remove` | **NEW: `gtm warmup` subgroup** | Add to gtm |
| `openclaw engagement --posts-file --auto` | **NEW: `gtm engagement` command** | Add to gtm |

**Recommendation:** Only add 3 new commands (`identity affinity`, `warmup`, `engagement`). The 6 redundant account-management commands disappear because gtm-cli already has them.

### D6. Twitter browser client: where it lives

gtm-cli convention: each platform has `client.py` (the API/programmatic client). Browser clients are unusual.

**Recommendation:** New file `gtm/platforms/twitter/browser_client.py` (parallel to `reddit/client.py` which is itself a Playwright client — so this matches the pattern). Tools at `gtm/platforms/twitter/browser_tools.py`. Keep twikit `client.py` for read operations.

---

## Execution order (after you approve D1-D6)

1. **Branch:** `git checkout -b port/multi-account-engagement` (in gtm-cli).
2. **Identity migration shim (10 min):** wire `IdentityManager.get()` into a tiny `get_identity_session_dir(name)` helper that the new MCP tools will call.
3. **Reddit tools update (20 min):** add `identity` param to `reddit_browser_submit`, port the 3 new tools (`reddit_list_identities`, `reddit_identity_affinity`, `reddit_pick_identity_for_sub`), extend opener archetypes.
4. **Reddit Playwright client cache (10 min):** port the per-dir cache pattern from today's `playwright_reddit_client.py`.
5. **Twitter browser client (30 min):** new `browser_client.py` adapted from today's `playwright_twitter_client.py`. Use gtm's `IDENTITIES_DIR` for storage.
6. **Twitter browser tools (15 min):** new `browser_tools.py` with `identity` param.
7. **Twitter promoter agent + prompt (20 min):** port `agents/twitter_promoter.py` + `prompts/twitter_promoter.md`. Adapt imports.
8. **Engagement loop agent + prompt (20 min):** port `agents/engagement_loop.py` + `prompts/engagement_loop.md`. Adapt imports.
9. **Cross-post lint module (20 min):** new `gtm/modules/filters/cross_post_lint.py`. Also expose as `reddit_cross_post_lint` MCP tool for the promoter agent.
10. **Identity affinity module + helper (30 min):** new `gtm/modules/filters/identity_affinity.py` + agent-callable function. Reads from gtm's run-output dir.
11. **Warmup module + CLI (20 min):** new `gtm/launch/warmup.py` + `gtm warmup` subgroup.
12. **Promoter agent update (15 min):** modify `gtm/agents/promoter.py` Phase C to call `pick_identity_for_sub`.
13. **Engagement CLI command (10 min):** new `gtm engagement` command.
14. **E2E test port (45 min):** rewrite `tests/e2e/test-multi-account-pipeline.sh` against gtm CLI surface. Aim for 33+ checks still passing.
15. **Smoke test (15 min):** `gtm modules list`, `gtm identity list`, `gtm run --list`, dry-run a strategy.
16. **PR (5 min):** push branch, open PR with this plan as the PR description.

**Total estimate:** ~5 hours of focused work. Not "today done in 30 minutes."

---

## Step 5 — Archive openclaw (only after the gtm-cli PR is merged)

1. **Update openclaw README** to point to gtm-cli ("This project moved to https://github.com/serenakeyitan/gtm-cli. This repo is archived for history.").
2. Push README change to `main`.
3. **GitHub: Settings → Archive this repository.** Read-only, can't push, can't open issues. Stays accessible forever.
4. Local dir `~/growth-sop-pipeline-serena/` — leave alone or rename to `_archive_openclaw/`.

**Will NOT delete** the GitHub repo or local files.

---

## What I need from you

Confirm or override D1-D6. If you approve all defaults, I just need a "go" and I run steps 1-16 in one session, with progress updates after each step.

If you want to change anything, tell me which D# and what you'd prefer. The most consequential calls are D1 (drop accounts.py), D3 (affinity as a module), and D5 (drop redundant CLI subgroups in favor of existing `gtm auth`/`gtm identity`).
