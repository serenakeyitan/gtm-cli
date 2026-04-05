# growth-cli Roadmap

> Single source of truth for all phases, milestones, and status.

**Design Specs:**

- [v0.1 Full Spec](./docs/design-spec-v01.md) — architecture, identity, safety, onboarding
- [v0.2 Module System Spec](./docs/design-spec-v02-modules.md) — composability, DAG runner, module registry

**Codex Review Log:** [CODEX_REVIEWS.md](./CODEX_REVIEWS.md)

---

## Progress Summary


| Phase        | Status | Features                                                   | Done  |
| ------------ | ------ | ---------------------------------------------------------- | ----- |
| v0.1         | ✅ Done | CLI, 3 platforms, auth, rate limiter, strategies, traction | 21/21 |
| v0.2 Phase 1 | ✅ Done | Module system foundation (15 modules)                      | 8/8   |
| v0.2 Phase 2 | ✅ Done | Transform modules                                          | 4/4   |
| v0.2 Phase 3 | ⬜      | DAG runner                                                 | 0/7   |
| v0.2 Phase 4 | ⬜      | Strategy-as-module                                         | 0/3   |
| v0.2 Phase 5 | ⬜      | Multi-account                                              | 0/7   |
| v0.3         | ⬜      | Intelligence (chat, generation, listening)                 | 0/8   |
| v0.4         | ⬜      | Growth Cloud (managed accounts/IPs)                        | 0/6   |
| v0.5         | ⬜      | GitHub integration                                         | 0/4   |
| v1.0         | ⬜      | Public launch                                              | 0/5   |
| v2.0         | ⬜      | Ecosystem (plugins, marketplace, teams)                    | 0/7   |
| v3.0         | ⬜      | Autonomous growth agent                                    | 0/4   |


---

## v0.1 — "Marketing from your terminal" ✅ DONE

> Single user, own accounts, CLI works, built-in strategies.

- Project scaffold (pyproject.toml, CLI entry point) — `701e98d`
- Twitter adapter (search, user, post, like, reply, retweet) — `701e98d`
- Reddit adapter (search, submit) — `d14ead3`
- HN adapter (search, top, submit) — `d14ead3`
- Cookie-Editor auth flow (all 3 platforms) — `eefe30a`
- Rate limiter (always on, conservative defaults) — `701e98d`
- Identity manager (add, list, status, health) — `701e98d`
- Strategy YAML loader + sequential runner — `cca2ca1`
- 3 example strategies (twitter-scout, hn-trending, cross-search) — `cca2ca1`
- Route 1 (GitHub Growth) + Route 2 (HN Submit) migrated — `7d3b78c`
- All 6 agents migrated (scout, novelty, builder, tester, promoter, hn_promoter) — `7d3b78c`
- Output git logger (auto-commit every action) — `cca2ca1`
- Traction tracker (live engagement from all platforms) — `2b533c9`
- Migration from openclaw pipeline — `cca2ca1`
- Content style guide (Reddit organic, HN technical, Twitter engagement) — `f384a07`
- SKILL.md for Claude Code integration — `a35d944`
- README — `66f838a`
- Security: 0700/0600 perms, no password in CLI args — `f7020a7`
- Expired cookie detection + re-auth instructions — `0c2c750`
- `--dry-run` on all posting commands — `701e98d`
- `--json` output on all commands — `701e98d`

---

## v0.2 — "Composable Module System" 🔧 IN PROGRESS

> Every piece is a Lego block. Same blocks, different arrangement.
> Full spec: [design-spec-v02-modules.md](./docs/design-spec-v02-modules.md)

### Phase 1: Foundation ✅ DONE

- Module base class (Module ABC + ModuleResult contract) — `4dfbfd7`
- Module registry (register, discover, list, search) — `4dfbfd7`
- 5 source modules (twitter/search, twitter/user, reddit/search, hn/search, hn/top) — `4dfbfd7`
- 4 filter modules (engagement, keyword, deduplicate, limit) — `4dfbfd7`
- 5 action modules (twitter/post, twitter/like, twitter/retweet, reddit/submit, hn/submit) — `4dfbfd7`
- 1 monitor module (track/engagement) — `4dfbfd7`
- `growth modules list` CLI command — `4dfbfd7`
- `growth modules info <name>` CLI command — `4dfbfd7`

### Phase 2: Transforms ✅ DONE

- [x] `transform/rewrite` — LLM rewrite for platform tone (uses style_guide.md) — `4d07bee`
- [x] `transform/extract_url` — find original source URL from tweets — `4d07bee`
- [x] `transform/platform_adapt` — format content for platform requirements — `4d07bee`
- [x] `transform/summarize` — condense for character limits — `4d07bee`

### Phase 3: DAG Runner ⬜ NEXT

- Parse module DAG from YAML (infer execution order from `input` field)
- Topological sort for execution order
- Parallel execution (modules with no shared dependencies)
- `control/delay` — fixed wait between modules
- `control/jitter` — random wait within range (human-like timing)
- `control/for_each` — run a module per item in the list
- `control/condition` — if/then/else based on data

### Phase 4: Strategy-as-Module ⬜

- Reference a strategy as a module in another strategy
- `growth modules create` scaffold tool
- Strategy composability test (nested 3 levels)

### Phase 5: Multi-Account ⬜

- Multiple identities per platform
- Identity roles (brand, organic, supporter, scout)
- `--as` supports roles: `--as supporter` (picks from pool)
- BYOP proxy support (SOCKS5/HTTP per identity)
- Rate Limit Coordinator (5 layers: per-account, per-IP, per-platform, behavioral, cross-platform)
- Ban detection + identity status (healthy/warning/suspended)
- Auto-rotate to backup identity on failure

---

## v0.3 — "Intelligence" ⬜

- Chat TUI mode (`growth chat`)
- NL → strategy planning (describe campaign, agent builds YAML)
- Content generation (`--generate` flag)
- Platform-native tone adaptation
- Social listening (continuous monitoring)
- Traction alerts (webhook/CLI notification)
- Traction-triggered strategies ("score > 50 → amplify")
- Agent modules (agent/scout, agent/promoter as composable modules)

---

## v0.4 — "Growth Cloud" ⬜

- Supabase backend (users, inventory, payments)
- `growth cloud shop` (browse accounts/IPs)
- `growth cloud buy` (Stripe checkout)
- `growth cloud redeem` (download + auto-configure)
- Account tiers: Fresh / Warmed / Aged / Premium
- One-time purchase model (not rental)

---

## v0.5 — "GitHub Integration" ⬜

- Optional GitHub PR workflow for content review
- Safety checks as GitHub Actions CI
- Team review via GitHub UI
- Merge = auto-post webhook

---

## v1.0 — "Public Launch" ⬜

- Documentation polish
- Video demo / walkthrough
- Landing page + pricing
- Launch campaign (dogfooding growth-cli)
- Apache 2.0 license ✅ (done early)

---

## v2.0 — "Ecosystem" ⬜

- Plugin system for new platforms (LinkedIn, Instagram, TikTok...)
- Strategy marketplace (share/fork strategies)
- Team features (shared identity pools, RBAC)
- Web analytics dashboard
- Scheduled/cron strategies
- Event-driven triggers
- Account warming automation

---

## v3.0 — "Autonomous Growth Agent" ⬜

- Self-optimizing strategies (A/B test content)
- LLM memory integration (learn what works across runs)
- Continuous monitoring + autonomous response
- Agency mode (multi-client)

---

## Stats


| Metric               | Value                                                      |
| -------------------- | ---------------------------------------------------------- |
| Commits              | 27                                                         |
| Lines of Python      | ~10,000                                                     |
| Composable modules   | 19                                                         |
| Platforms            | 3 (Twitter, Reddit, HN)                                    |
| Agents               | 6 (scout, novelty, builder, tester, promoter, hn_promoter) |
| Strategies           | 5 (3 examples + 2 local routes)                            |
| Prompts              | 7 (6 agent prompts + 1 style guide)                        |
| Codex reviews        | 27 commits reviewed                                        |
| Codex findings fixed | 23 total                                                   |


