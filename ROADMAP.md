# growth-cli Roadmap

> Single source of truth for all phases, milestones, and status.

**Design Specs:**
- [v0.1 Full Spec](./docs/design-spec-v01.md) — architecture, identity, safety, onboarding
- [v0.2 Module System Spec](./docs/design-spec-v02-modules.md) — composability, DAG runner, module registry

**Codex Review Log:** [CODEX_REVIEWS.md](./CODEX_REVIEWS.md)

---

## v0.1 — "Marketing from your terminal" ✅ DONE

> Single user, own accounts, CLI works, built-in strategies.

| Feature | Status | Commit |
|---------|--------|--------|
| Project scaffold (pyproject.toml, CLI) | ✅ | `701e98d` |
| Twitter adapter (search, user, post, like, reply, retweet) | ✅ | `701e98d` |
| Reddit adapter (search, submit) | ✅ | `d14ead3` |
| HN adapter (search, top, submit) | ✅ | `d14ead3` |
| Cookie-Editor auth flow (all 3 platforms) | ✅ | `eefe30a` |
| Rate limiter (always on, conservative defaults) | ✅ | `701e98d` |
| Identity manager (add, list, status, health) | ✅ | `701e98d` |
| Strategy YAML loader + sequential runner | ✅ | `cca2ca1` |
| 3 example strategies (twitter-scout, hn-trending, cross-search) | ✅ | `cca2ca1` |
| Route 1 (GitHub Growth) + Route 2 (HN Submit) migrated | ✅ | `7d3b78c` |
| All 6 agents migrated (scout, novelty, builder, tester, promoter, hn_promoter) | ✅ | `7d3b78c` |
| Output git logger (auto-commit every action) | ✅ | `cca2ca1` |
| Traction tracker (live engagement from all platforms) | ✅ | `2b533c9` |
| Migration from openclaw pipeline | ✅ | `cca2ca1` |
| SKILL.md for Claude Code integration | ✅ | `a35d944` |
| README | ✅ | `66f838a` |
| Security: 0700/0600 perms, no password in CLI args | ✅ | `f7020a7` |
| Expired cookie detection + re-auth instructions | ✅ | `0c2c750` |
| `--dry-run` on all posting commands | ✅ | `701e98d` |
| `--json` output on all commands | ✅ | `701e98d` |
| Codex auto-review on every commit | ✅ | `701e98d` |

---

## v0.2 — "Composable Module System" 🔧 IN PROGRESS

> Every piece is a Lego block. Same blocks, different arrangement.
> Full spec: [growth-cli-design-spec-v02-modules.md](../growth-cli-design-spec-v02-modules.md)

### Phase 1: Foundation ✅ DONE

| Feature | Status | Commit |
|---------|--------|--------|
| Module base class (Module ABC + ModuleResult contract) | ✅ | `4dfbfd7` |
| Module registry (register, discover, list, search) | ✅ | `4dfbfd7` |
| 5 source modules (twitter/search, twitter/user, reddit/search, hn/search, hn/top) | ✅ | `4dfbfd7` |
| 4 filter modules (engagement, keyword, deduplicate, limit) | ✅ | `4dfbfd7` |
| 5 action modules (twitter/post, twitter/like, twitter/retweet, reddit/submit, hn/submit) | ✅ | `4dfbfd7` |
| 1 monitor module (track/engagement) | ✅ | `4dfbfd7` |
| `growth modules list` CLI command | ✅ | `4dfbfd7` |
| `growth modules info <name>` CLI command | ✅ | `4dfbfd7` |
| Codex reviewed + all findings fixed (3 rounds) | ✅ | `178b10c` |

### Phase 2: Transforms ⬜ NEXT

| Feature | Status |
|---------|--------|
| transform/rewrite — LLM rewrite for platform tone | ⬜ |
| transform/extract_url — find original source URL from tweets | ⬜ |
| transform/platform_adapt — format content for platform requirements | ⬜ |
| transform/summarize — condense for character limits | ⬜ |

### Phase 3: DAG Runner ⬜

| Feature | Status |
|---------|--------|
| Parse module DAG from YAML (infer order from `input` field) | ⬜ |
| Topological sort for execution order | ⬜ |
| Parallel execution (modules with no shared dependencies) | ⬜ |
| control/delay — fixed wait between modules | ⬜ |
| control/jitter — random wait within range (human-like) | ⬜ |
| control/for_each — run a module per item | ⬜ |
| control/condition — if/then/else based on data | ⬜ |

### Phase 4: Strategy-as-Module ⬜

| Feature | Status |
|---------|--------|
| Reference a strategy as a module in another strategy | ⬜ |
| `growth modules create` scaffold tool | ⬜ |
| Strategy composability test (nested 3 levels) | ⬜ |

### Phase 5: Multi-Account ⬜

| Feature | Status |
|---------|--------|
| Multiple identities per platform | ⬜ |
| Identity roles (brand, organic, supporter, scout) | ⬜ |
| `--as` supports roles: `--as supporter` (picks from pool) | ⬜ |
| BYOP proxy support (SOCKS5/HTTP per identity) | ⬜ |
| Rate Limit Coordinator (5 layers) | ⬜ |
| Ban detection + identity status (healthy/warning/suspended) | ⬜ |
| Auto-rotate to backup identity on failure | ⬜ |

---

## v0.3 — "Intelligence" ⬜

| Feature | Status |
|---------|--------|
| Chat TUI mode (`growth chat`) | ⬜ |
| NL → strategy planning (describe campaign, agent builds YAML) | ⬜ |
| Content generation (`--generate` flag) | ⬜ |
| Platform-native tone adaptation | ⬜ |
| Social listening (continuous monitoring) | ⬜ |
| Traction alerts (webhook/CLI notification) | ⬜ |
| Traction-triggered strategies ("score > 50 → amplify") | ⬜ |
| Agent modules (agent/scout, agent/promoter as composable modules) | ⬜ |

---

## v0.4 — "Growth Cloud" ⬜

| Feature | Status |
|---------|--------|
| Supabase backend (users, inventory, payments) | ⬜ |
| `growth cloud shop` (browse accounts/IPs) | ⬜ |
| `growth cloud buy` (Stripe checkout) | ⬜ |
| `growth cloud redeem` (download + auto-configure) | ⬜ |
| Account tiers: Fresh / Warmed / Aged / Premium | ⬜ |
| One-time purchase model (not rental) | ⬜ |

---

## v0.5 — "GitHub Integration" ⬜

| Feature | Status |
|---------|--------|
| Optional GitHub PR workflow for content review | ⬜ |
| Safety checks as GitHub Actions CI | ⬜ |
| Team review via GitHub UI | ⬜ |
| Merge = auto-post webhook | ⬜ |

---

## v1.0 — "Public Launch" ⬜

| Feature | Status |
|---------|--------|
| Documentation polish | ⬜ |
| Video demo / walkthrough | ⬜ |
| Landing page + pricing | ⬜ |
| Launch campaign (dogfooding growth-cli) | ⬜ |
| Apache 2.0 license setup | ⬜ |

---

## v2.0 — "Ecosystem" ⬜

| Feature | Status |
|---------|--------|
| Plugin system for new platforms (LinkedIn, Instagram, TikTok...) | ⬜ |
| Strategy marketplace (share/fork strategies) | ⬜ |
| Team features (shared identity pools, RBAC) | ⬜ |
| Web analytics dashboard | ⬜ |
| Scheduled/cron strategies | ⬜ |
| Event-driven triggers | ⬜ |
| Account warming automation | ⬜ |

---

## v3.0 — "Autonomous Growth Agent" ⬜

| Feature | Status |
|---------|--------|
| Self-optimizing strategies (A/B test content) | ⬜ |
| LLM memory integration (learn what works across runs) | ⬜ |
| Continuous monitoring + autonomous response | ⬜ |
| Agency mode (multi-client) | ⬜ |

---

## Stats

| Metric | Value |
|--------|-------|
| Total commits | 21 |
| Lines of Python | ~8,000 |
| Modules | 15 |
| Platforms | 3 (Twitter, Reddit, HN) |
| Agents | 6 (scout, novelty, builder, tester, promoter, hn_promoter) |
| Strategies | 5 (3 examples + 2 local routes) |
| Codex reviews | 14 commits reviewed |
| Codex findings fixed | 17 total across all reviews |
