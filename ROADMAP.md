# gtm-cli Roadmap

> Single source of truth for all phases, milestones, and status.

**Architecture:** [docs/architecture-principles.md](./docs/architecture-principles.md)  
**Agent Instructions:** [AGENTS.md](./AGENTS.md)  
**Codex Reviews:** `.codex-reviews/` (auto-generated per commit)

---

## Progress Summary

| Phase | Status | Features | Done |
|---|---|---|---|
| v0.1 | ✅ Done | CLI, 3 platforms, auth, rate limiter, strategies, traction | 21/21 |
| v0.2 Phase 1 | ✅ Done | Module system foundation (15 modules) | 8/8 |
| v0.2 Phase 2 | ✅ Done | Transform modules | 4/4 |
| v0.2 Phase 3 | ✅ Done | DAG runner | 7/7 |
| v0.2 Phase 4 | ✅ Done | Strategy-as-module | 3/3 |
| v0.2 Phase 5 | ✅ Done | Multi-account | 0/7 |
| v0.3 | 🔧 | Intelligence (skill, generation, listening) | 2/7 |
| v0.4 | ⬜ | Growth Cloud (managed accounts/IPs) | 0/6 |
| v0.5 | ⬜ | GitHub integration | 0/4 |
| v1.0 | ⬜ | Public launch | 0/5 |
| v2.0 | ⬜ | Ecosystem (plugins, marketplace, teams) | 0/7 |
| v3.0 | ⬜ | Autonomous growth agent | 0/4 |

---

## v0.1 — "Marketing from your terminal" ✅ DONE

> Single user, own accounts, CLI works, built-in strategies.

<details>
<summary>✅ 21/21 features completed (click to expand)</summary>

- [x] Project scaffold (pyproject.toml, CLI entry point) — `701e98d`
- [x] Twitter adapter (search, user, post, like, reply, retweet) — `701e98d`
- [x] Reddit adapter (search, submit) — `d14ead3`
- [x] HN adapter (search, top, submit) — `d14ead3`
- [x] Cookie-Editor auth flow (all 3 platforms) — `eefe30a`
- [x] Rate limiter (always on, conservative defaults) — `701e98d`
- [x] Identity manager (add, list, status, health) — `701e98d`
- [x] Strategy YAML loader + sequential runner — `cca2ca1`
- [x] Example strategies (replaced by DAG versions in v0.2) — `cca2ca1`
- [x] Route 1 (GitHub Growth) + Route 2 (HN Submit) migrated — `7d3b78c`
- [x] All 6 agents migrated (scout, novelty, builder, tester, promoter, hn_promoter) — `7d3b78c`
- [x] Output git logger (auto-commit every action) — `cca2ca1`
- [x] Traction tracker (live engagement from all platforms) — `2b533c9`
- [x] Migration from openclaw pipeline — `cca2ca1`
- [x] Content style guide (Reddit organic, HN technical, Twitter engagement) — `f384a07`
- [x] SKILL.md for Claude Code integration — `a35d944`
- [x] README — `66f838a`
- [x] Security: 0700/0600 perms, no password in CLI args — `f7020a7`
- [x] Expired cookie detection + re-auth instructions — `0c2c750`
- [x] `--dry-run` on all posting commands — `701e98d`
- [x] `--json` output on all commands — `701e98d`

</details>

### 🎬 v0.1 Showcase: "Everything from your terminal"

**Before gtm-cli:** You open Twitter in one tab, Reddit in another, HN in a third. You copy-paste your announcement across all three, manually adjusting tone. You check back every hour across 3 tabs to see engagement. You forget which account you're posting from.

**After gtm-cli:**

```bash
# Connect accounts once (30 seconds)
$ gtm auth twitter     # paste Cookie-Editor export
$ gtm auth reddit
$ gtm auth hn

# Search all platforms from one terminal
$ gtm twitter user karpathy --count 3
  @karpathy — latest 3 tweets:
  LLM Knowledge Bases...                    ❤️ 11,025  🔁 1,124
  New supply chain attack for npm axios...  ❤️ 10,444  🔁 1,121

$ gtm hn top --count 3
  1. [1586] LinkedIn is searching your browser extensions
  2. [1207] Google releases Gemma 4 open models

$ gtm reddit search "AI agents" --sub SaaS --count 2
  [267] Salesforce cut support staff by 4,000 using AI agents
  [12]  Has anyone actually automated sales with AI agents?

# Post across platforms (rate-limited, safe)
$ gtm twitter post "Just shipped v2!" --dry-run    # preview first
$ gtm reddit submit --sub SaaS --title "..." --dry-run

# Check engagement across ALL platforms in one command
$ gtm traction
  🐦 twitter  "Just shipped v2!"         ❤️ 142  🔁 23  👁 8,401
  🤖 reddit   "Show r/SaaS: gtm-cli"  ⬆️ 38   💬 7   📊 0.92
  🟠 hn       "Show HN: gtm-cli"      ▲ 23    💬 4
```

**The key insight:** You never leave the terminal. No UI switching. No copy-pasting. Rate limits protect your accounts automatically.

---

## v0.2 — "Composable Module System" 🔧 IN PROGRESS

> Every piece is a Lego block. Same blocks, different arrangement.
> See [docs/architecture-principles.md](./docs/architecture-principles.md) for design details.

### Phase 1: Foundation ✅ DONE

<details>
<summary>✅ 8/8 features completed</summary>

- [x] Module base class (Module ABC + ModuleResult contract) — `4dfbfd7`
- [x] Module registry (register, discover, list, search) — `4dfbfd7`
- [x] 5 source modules (twitter/search, twitter/user, reddit/search, hn/search, hn/top) — `4dfbfd7`
- [x] 4 filter modules (engagement, keyword, deduplicate, limit) — `4dfbfd7`
- [x] 5 action modules (twitter/post, twitter/like, twitter/retweet, reddit/submit, hn/submit) — `4dfbfd7`
- [x] 1 monitor module (track/engagement) — `4dfbfd7`
- [x] `gtm modules list` CLI command — `4dfbfd7`
- [x] `gtm modules info <name>` CLI command — `4dfbfd7`

</details>

#### 🎬 Phase 1 Showcase: "Discover and inspect your Lego blocks"

**Before:** Tools are buried in platform code. You don't know what's available or how to use it. Building a strategy means reading source code.

**After:**

```bash
$ gtm modules list
  SOURCES (Eyes)     — 5 modules
    twitter/search          Search tweets by query 🔑
    hn/top_stories          Get current HN front page stories
    reddit/search           Search Reddit posts
    ...

  FILTERS (Brain)    — 4 modules
    filter/engagement       Keep items above engagement thresholds
    filter/keyword          Keep or exclude items matching keywords
    ...

  ACTIONS (Hands)    — 5 modules
    twitter/post            Post a tweet 🔑
    reddit/submit           Submit to subreddit 🔑
    ...

  23 modules total

$ gtm modules info filter/engagement
  Name: filter/engagement
  Category: filter
  Description: Keep items above engagement thresholds
  Parameters:
    min_likes: int (default: 0)
    min_score: int (default: 0)
    min_retweets: int (default: 0)
```

**The key insight:** Every module is discoverable. You know exactly what Lego blocks exist, what they take as input, what they produce. No guessing.

---

### Phase 2: Transforms ✅ DONE

<details>
<summary>✅ 4/4 features completed</summary>

- [x] `transform/rewrite` — LLM rewrite for platform tone (uses style_guide.md) — `4d07bee`
- [x] `transform/extract_url` — find original source URL from tweets — `4d07bee`
- [x] `transform/platform_adapt` — format content for platform requirements — `4d07bee`
- [x] `transform/summarize` — condense for character limits — `4d07bee`

</details>

#### 🎬 Phase 2 Showcase: "Same content, different voice per platform"

**Before:** You manually rewrite your announcement 3 times — casual lowercase for Reddit, clean technical for HN, engagement-optimized for Twitter. Every time.

**After:** One piece of content flows through transform modules:

```yaml
# In your strategy:
modules:
  scout:
    use: twitter/search
    params: { query: "AI agents" }

  for_reddit:
    use: transform/rewrite
    input: scout
    params: { platform: reddit, tone: organic }
    # → "found this useful tool for anyone working with ai agents.
    #    no fancy setup. just works." (all lowercase, no self-promo)

  for_hn:
    use: transform/platform_adapt
    input: scout
    params: { platform: hn }
    # → Strips "!!!", fixes ALL CAPS, adds [video] suffix for YouTube links

  for_twitter:
    use: transform/summarize
    input: scout
    params: { max_length: 280 }
    # → Smart truncation at sentence boundary, keeps URL
```

**The key insight:** Content adapts to each platform automatically. The style guide (battle-tested from real posts that got removed vs worked) ensures Reddit posts don't get flagged for self-promotion, HN titles follow guidelines, Twitter stays within 280 chars.

---

### Phase 3: DAG Runner ✅ DONE

<details>
<summary>✅ 7/7 features completed</summary>

- [x] Parse module DAG from YAML (infer execution order from `input` field)
- [x] Topological sort for execution order
- [x] Parallel execution (modules with no shared dependencies)
- [x] `control/delay` — fixed wait between modules
- [x] `control/jitter` — random wait within range (human-like timing)
- [x] `control/for_each` — run a module per item in the list
- [x] `control/condition` — if/then/else based on data

</details>

#### 🎬 Phase 3 Showcase: "Parallel multi-platform campaigns"

**Before:** You run one step at a time. Search Twitter, wait. Search Reddit, wait. Search HN, wait. Post to Reddit, wait 10 minutes, post to HN. Everything sequential.

**After:**

```bash
$ gtm run cross-platform-scout -p query="growth hacking" -p count=3

  Running strategy: Cross-Platform Scout (Parallel)

  ✅ reddit  reddit/search (3 items): success     ─┐
  ✅ hn      hn/search (3 items): success          ├─ These 3 ran in PARALLEL
  ✅ twitter twitter/search (3 items): success     ─┘
  ✅ merged_filter filter/limit (9 items): success ← Waits for all 3, then merges

  Status: completed
```

The DAG runner figures out: "twitter, reddit, and hn have no mutual dependencies → run them at the same time." Then merged_filter depends on all 3 → waits for them to finish.

**With human-like timing:**

```yaml
modules:
  post_reddit:
    use: reddit/submit
    params: { subreddit: SaaS, title: "..." }

  wait:
    use: control/jitter
    input: post_reddit
    params: { min_seconds: 1800, max_seconds: 7200 }  # 30min-2hr random wait

  post_hn:
    use: hn/submit_link
    input: wait    # posts to HN 30min-2hr AFTER Reddit (looks human)
    params: { title: "...", url: "..." }
```

**The key insight:** Strategies express WHAT to do, the DAG runner figures out the optimal HOW (parallel where safe, sequential where needed, human-like timing between actions).

---

### Phase 4: Strategy-as-Module ✅ DONE

- [x] Reference a strategy as a module — `b1a8e52` in another strategy
- [x] `gtm modules create` scaffold tool — `b1a8e52`
- [x] Strategy composability test (nested 3 levels) — `f57fe3b`

#### 🎬 Phase 4 Showcase: "Strategies compose into bigger strategies"

**The vision:** Your "Show HN Launch" strategy and "Reddit Organic Seed" strategy are both tested and working. Now you want a "Full Launch Campaign" that runs both, plus a Twitter announcement after.

```yaml
name: "Full Launch Campaign"
modules:
  hn_launch:
    use: strategy/show-hn-launch           # ← a whole strategy as one module
    params: { topic: "gtm-cli" }

  reddit_launch:
    use: strategy/reddit-organic-seed      # ← another strategy as a module
    params: { topic: "gtm-cli", subreddits: [SaaS, startups] }

  # HN + Reddit run in PARALLEL (separate platforms)

  twitter_announce:
    use: twitter/post
    input: [hn_launch, reddit_launch]      # waits for both
    params: { text: "Just launched on HN and Reddit! 🧵" }
```

**Like quant trading:** Individual strategies are backtested. Then you compose them into a portfolio. Each strategy is a module. Modules compose infinitely.

---

### Phase 5: Multi-Account ✅ DONE

- [x] Multiple identities per platform — `dd290e0`
- [x] Identity roles (brand, organic, supporter, scout) — `dd290e0`
- [x] `--as` supports roles: `--as supporter` (picks from pool)
- [x] BYOP proxy support (SOCKS5/HTTP per identity)
- [x] Rate Limit Coordinator (5 layers)
- [x] Ban detection + identity status
- [x] Auto-rotate to backup identity on failure — `dd290e0`

#### 🎬 Phase 5 Showcase: "Coordinated multi-account campaigns"

**The vision:** Your brand account announces on Twitter. Then 3 "supporter" accounts like and retweet at staggered intervals. An "organic" Reddit account posts to r/SaaS. Each account has its own IP, its own rate limits, its own health status.

```yaml
identities:
  brand: { platform: twitter, role: brand }
  supporters: { platform: twitter, role: supporter, count: 3 }
  reddit_organic: { platform: reddit, role: organic }

modules:
  announce:
    use: twitter/post
    as: $brand
    params: { text: "Just shipped gtm-cli v1.0 🚀" }

  amplify:
    use: control/for_each
    input: announce
    as: $supporters       # picks 3 different supporter accounts
    params:
      use: twitter/like   # each supporter likes the announcement
      delay: { min: 300, max: 1800 }   # 5-30min stagger per account

  reddit_seed:
    use: reddit/submit
    as: $reddit_organic    # different account, different IP
    params: { subreddit: SaaS, title: "..." }
```

```bash
$ gtm status
  PLATFORM  IDENTITY           ROLE       PROXY         STATUS
  twitter   @brand_main        brand      us-west-1     ✅ OK
  twitter   @organic_sarah     supporter  us-east-2     ✅ OK
  twitter   @tech_mike         supporter  eu-west-1     ✅ OK
  twitter   @dev_community     supporter  ap-south-1    ⚠️ Cooldown 4m
  reddit    @r_organic_1       organic    us-central-1  ✅ OK
```

**The key insight:** The `--as` flag with roles means strategies are portable across users. Someone with 2 supporters runs the same strategy as someone with 10. The system picks from the pool, respects per-account rate limits, auto-rotates on failure.

---

## v0.3 — "Intelligence" ⬜

- [ ] Enhanced `/gtm` skill for Claude Code / Codex (the agent IS the UI — no TUI needed)
- [ ] NL → strategy planning (describe campaign, agent builds YAML)
- [ ] Content generation (`--generate` flag)
- [ ] Platform-native tone adaptation via transform/rewrite
- [ ] Social listening (continuous monitoring)
- [ ] Traction alerts (webhook/CLI notification)
- [ ] Traction-triggered strategies ("score > 50 → amplify")

#### 🎬 v0.3 Showcase: "Your agent IS the growth UI"

**Why no TUI?** Your target user is already inside Claude Code. Building a separate `gtm chat` is building a worse Claude Code. Instead, the `/gtm` skill makes Claude Code understand growth workflows natively.

```
# Inside Claude Code — just talk naturally:

You: launch my new feature on HN, Twitter, and Reddit.
     product is "gtm-cli", url is gtm-cli.dev
     use organic tone on reddit

Claude: I'll plan a launch campaign using gtm-cli.

> gtm run combined-routes --json -p query="gtm-cli" -p min_likes=50

  ✅ scout (16 tweets) → filter (8 viral) → 
  Route 1: 3 Reddit candidates
  Route 2: 3 HN candidates

Here are the top candidates:
1. [HN] "Show HN: gtm-cli — Terminal-native GTM automation" 
2. [Reddit] r/SaaS post adapted with organic tone
3. ...

Want me to post these? I'll stagger them over 2 hours.
```

**The key insight:** Claude Code + SKILL.md = better than any TUI we could build. The agent reads `--json` output, reasons about it, and suggests actions. We just need a smarter skill file.

---

## v0.4 — "Growth Cloud" ⬜

- [ ] Supabase backend
- [ ] `gtm cloud shop`
- [ ] `gtm cloud buy`
- [ ] `gtm cloud redeem`
- [ ] Account tiers
- [ ] One-time purchase

#### 🎬 v0.4 Showcase: "Buy accounts, plug them in, go"

```bash
$ gtm cloud shop
  TWITTER
  ├── Warmed (1-3 months)        $35
  └── Aged (6+ months, 500+ followers)  $65

  REDDIT
  ├── Warmed (100+ karma)        $30
  └── Aged (1000+ karma)         $55

$ gtm cloud buy twitter-warmed --count 3
  → Payment: https://gtm.cloud/checkout/xxx
  → After payment: gtm cloud redeem <code>

$ gtm cloud redeem abc123
  → Downloaded 3 identities
  → twitter:gc_organic_1, twitter:gc_organic_2, twitter:gc_organic_3
  → All configured with dedicated proxies
  → Ready to use in any strategy
```

**The key insight:** Zero friction. Buy accounts, they auto-configure. No manual cookie grabbing, no proxy setup. Plug into any strategy with `as: $supporters`.

---

## v0.5 — "GitHub Integration" ⬜

- [ ] Optional GitHub PR workflow for content review
- [ ] Safety checks as GitHub Actions CI
- [ ] Team review via GitHub UI
- [ ] Merge = auto-post webhook

#### 🎬 v0.5 Showcase: "PRs for content, not just code"

```bash
$ gtm draft "Announce our Series A"
  → Branch: content/series-a-2026-04
  → PR #42 opened for review

# On GitHub:
  PR #42: "Content: Series A announcement"
  ├── twitter_announcement.md     ✅ Safety: pass
  ├── reddit_saas_post.md         ✅ Safety: pass
  └── hn_submission.md            ⚠️ Safety: duplicate detected

  Reviews: @cofounder approved, @marketing approved

# Merge PR → content auto-posted to all platforms
```

**The key insight:** Same workflow as code review. Draft → CI checks → team review → merge = publish. History, rollback, audit trail — all on GitHub.

---

## v1.0 — "Public Launch" ⬜

- [ ] Documentation polish
- [ ] Video demo / walkthrough
- [ ] Landing page + pricing
- [ ] Launch campaign (dogfooding gtm-cli)
- [ ] Apache 2.0 license ✅ (done early)

#### 🎬 v1.0 Showcase: "Launching gtm-cli using gtm-cli"

```bash
$ gtm run launch-campaign -p product="gtm-cli" -p url="github.com/serenakeyitan/gtm-cli"

  ✅ hn_submit: Show HN: gtm-cli — Terminal-native growth automation
  ✅ twitter_thread: 5-tweet thread posted
  ✅ reddit_saas: Posted to r/SaaS (organic tone)
  ✅ reddit_startups: Posted to r/startups (30min stagger)
  ✅ monitor: Watching for 24h...

  # 2 hours later:
  🟠 HN alert: Score hit 87! Engage in comments now.
  🤖 Reddit alert: r/SaaS post at 42 upvotes, 8 comments. Trending.
```

---

## v2.0 — "Ecosystem" ⬜

- [ ] Plugin system for new platforms (LinkedIn, Instagram, TikTok...)
- [ ] Strategy marketplace (share/fork strategies)
- [ ] Team features (shared identity pools, RBAC)
- [ ] Web analytics dashboard
- [ ] Scheduled/cron strategies
- [ ] Event-driven triggers
- [ ] Account warming automation

#### 🎬 v2.0 Showcase: "A marketplace of growth playbooks"

```bash
$ gtm marketplace search "product-hunt-launch"
  📦 ph-blitz (by @growthguru) — 847 installs
     Coordinated PH + Twitter + Reddit launch
  📦 ph-slow-burn (by @indiehacker) — 312 installs
     Week-long warmup campaign

$ gtm marketplace install ph-blitz
  → Strategy saved to ~/.config/gtm/strategies/ph-blitz.yaml

$ gtm run ph-blitz -p product="my-saas"
```

---

## v3.0 — "Autonomous Growth Agent" ⬜

- [ ] Self-optimizing strategies (A/B test content)
- [ ] LLM memory integration (learn what works across runs)
- [ ] Continuous monitoring + autonomous response
- [ ] Agency mode (multi-client)

#### 🎬 v3.0 Showcase: "Set it and forget it"

```bash
$ gtm auto --strategy continuous-gtm --budget 50-posts/week
  Agent running... monitoring all platforms.

  Week 1 report:
    Posted: 47 items across 3 platforms
    Best performer: "AI agents replacing junior devs" on r/SaaS (892 upvotes)
    Learned: Technical posts outperform listicles on HN by 3x
    Learned: Posting at 9am PST gets 2x more Reddit engagement
    Adjusted: Shifted HN posting to technical-only, Reddit to 9am window

  Week 2 report:
    Average engagement up 40% vs Week 1
    Auto-amplified 3 posts that crossed 100 upvote threshold
    ...
```

**The key insight:** The agent remembers what worked. It A/B tests tones, timing, platforms. It learns YOUR audience. Over time, it gets better at growth than you are — because it never forgets and never sleeps.

---

## Stats

| Metric | Value |
|---|---|
| Commits | 33 |
| Lines of Python | ~12,000 |
| Composable modules | 23 |
| Platforms | 3 (Twitter, Reddit, HN) |
| Agents | 6 (scout, novelty, builder, tester, promoter, hn_promoter) |
| Strategies | 7 (5 examples + 2 local routes) |
| Prompts | 7 (6 agent prompts + 1 style guide) |
| Codex reviews | 33 commits reviewed |
| Codex findings fixed | 42 total |
