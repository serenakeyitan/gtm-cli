# gtm-cli

> Claude Code gave developers a terminal for everything.  
> **gtm-cli gives marketers the same.**

One terminal. Every platform. No more switching between Twitter, Reddit, and HN dashboards.

```bash
$ gtm twitter user karpathy --count 3
  @karpathy — latest 3 tweets:
  LLM Knowledge Bases...                    ❤️ 11,025  🔁 1,124
  New supply chain attack for npm axios...  ❤️ 10,444  🔁 1,121

$ gtm hn top --count 3
  1. [1586] LinkedIn is searching your browser extensions
  2. [1207] Google releases Gemma 4 open models

$ gtm run combined-routes -p query="AI open source" -p min_likes=10
  ✅ scout          twitter/search (16 items)
  ✅ filter_hot     filter/engagement (8 items)
  ✅ r1_keywords    filter/keyword (5 items)       ─┐ Route 1 → Reddit
  ✅ r1_adapt       transform/platform_adapt (5)    ─┘
  ✅ r2_extract     transform/extract_url (8 items) ─┐ Route 2 → HN
  ✅ r2_adapt       transform/platform_adapt (4)    ─┘
  ✅ summary        filter/limit (6 items)
  Status: completed
```

## Install

```bash
pip install -e .
gtm init
gtm auth twitter    # paste Cookie-Editor export
gtm auth reddit
gtm auth hn
```

### Inside Claude Code

```
Install gtm-cli: run `pip install -e /path/to/gtm-cli && gtm init`
then help me connect my social media accounts.
```

## 30 Composable Modules

Every piece is a Lego block. Compose them into any strategy.

```bash
$ gtm modules list
  SOURCES (5)     twitter/search, twitter/user_tweets, reddit/search, hn/search, hn/top_stories
  FILTERS (4)     filter/engagement, filter/keyword, filter/deduplicate, filter/limit
  TRANSFORMS (4)  transform/rewrite, transform/extract_url, transform/platform_adapt, transform/summarize
  ACTIONS (5)     twitter/post, twitter/like, twitter/retweet, reddit/submit, hn/submit_link
  CONTROL (4)     control/delay, control/jitter, control/for_each, control/condition
  AGENTS (7)      agent/scout, agent/novelty_check, agent/build, agent/test,
                  agent/promote_reddit, agent/promote_hn, agent/synthesize
  MONITORS (1)    track/engagement
  STRATEGIES (8+) Any strategy YAML is also a composable module
```

### Cross-Platform Pipelines

```yaml
# hn-to-reddit.yaml — scrape HN, filter, adapt, post to Reddit
modules:
  scrape:    { use: hn/top_stories, params: { count: 10 } }
  hot:       { use: filter/engagement, input: scrape, params: { min_score: 300 } }
  adapt:     { use: transform/platform_adapt, input: hot, params: { platform: reddit } }
```

```yaml
# twitter-to-hn.yaml — scrape Twitter, extract URLs, submit to HN
modules:
  scout:     { use: twitter/search, params: { query: "AI tools" } }
  urls:      { use: transform/extract_url, input: scout }
  clean:     { use: transform/platform_adapt, input: urls, params: { platform: hn } }
```

### Parallel Execution

Modules with no mutual dependencies run simultaneously:

```yaml
modules:
  twitter: { use: twitter/search, params: { query: "AI" } }    # ─┐
  reddit:  { use: reddit/search, params: { query: "AI" } }     # ─┤ PARALLEL
  hn:      { use: hn/search, params: { query: "AI" } }         # ─┘
  merge:   { use: filter/limit, input: [twitter, reddit, hn] } # waits for all 3
```

### Strategies Compose Into Bigger Strategies

```yaml
# full-launch.yaml
modules:
  hn_launch:     { use: strategy/hn-scout-and-filter, params: { ... } }
  reddit_launch: { use: strategy/reddit-to-twitter, params: { ... } }
  combined:      { use: filter/limit, input: [hn_launch, reddit_launch] }
```

## Direct Commands

```bash
# Search
gtm twitter search "AI agents" --count 10
gtm twitter user karpathy --count 5
gtm reddit search "launch strategy" --sub startups
gtm hn search "Show HN"
gtm hn top --count 15

# Post (rate-limited, safe)
gtm twitter post "Just shipped v2! 🚀" --dry-run
gtm reddit submit --sub SaaS --title "..." --body "..." --dry-run
gtm hn submit --title "Show HN: ..." --url "..." --dry-run

# Strategies
gtm run --list                          # see all + execution mode
gtm run combined-routes -p query="AI"   # run a strategy
gtm run cross-platform-scout --dry-run  # preview
gtm modules create my-strategy          # scaffold new YAML

# Track
gtm traction                            # live engagement metrics
gtm traction --json                     # for agent analysis
gtm status                              # connected accounts
gtm log                                 # recent activity
```

## Architecture: Direct API First, LLM Last

**Default to direct API calls.** Only use LLM when a task genuinely requires reasoning.

| Approach | API Calls | Speed | Cost | When |
|----------|-----------|-------|------|------|
| Module DAG (default) | 0 Claude calls | 30 sec | $0.00 | Scrape, filter, transform, post |
| Hybrid | 1 Claude call | 60 sec | $0.01 | Need intelligent selection |
| Full LLM Agent (legacy) | ~175 Claude calls | 30 min | $1.00 | Need creative writing, code generation |

If LLM fails (rate limit, API down), deterministic fallback always produces output.

See [docs/architecture-principles.md](./docs/architecture-principles.md) for details.

## Account Safety

Rate limits are always on. `--force` exists but prints a warning and requires confirmation.

```
Twitter:  2 posts/hr, 6/day, 5min cooldown
Reddit:   1 post/hr, 3/day, 10min cooldown
HN:       1 submit/hr, 2/day, 30min cooldown
```

⚠️ Use burner accounts, not your personal ones.

## Strategy Locations

```
~/.config/gtm/strategies/    Your strategies (local, private, never on GitHub)
strategies/examples/            Sample strategies (shipped with repo, 8 examples)
```

## Project Structure

```
gtm/
├── cli.py              CLI entry point
├── config.py            XDG config (~/.config/gtm/)
├── modules/             30 composable modules
│   ├── sources/         Scrape platforms (5)
│   ├── filters/         Process data (4)
│   ├── transforms/      Adapt content (4)
│   ├── actions/         Post/engage (5)
│   ├── control/         Flow logic (4)
│   ├── agents/          LLM-powered (7 + strategy wrapper)
│   └── monitors/        Track results (1)
├── platforms/           Twitter, Reddit, HN adapters
├── engine/              DAG runner + legacy runner
├── identity/            Account management
├── safety/              Rate limiter
└── output/              Git-backed logger + traction

prompts/                 Style guides + agent prompts (7 files)
strategies/examples/     Sample strategies (8 YAML files)
```

## Roadmap

See [ROADMAP.md](./ROADMAP.md) for full phase-by-phase progress with showcases.

## License

Apache 2.0 — See [LICENSE](./LICENSE).
