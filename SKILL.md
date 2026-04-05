---
name: growth-cli
description: |
  Terminal-native marketing automation. Post to Twitter, Reddit, and HN.
  Scout trends, draft content, run multi-platform strategies.
  Use when asked to help with social media, content marketing,
  go-to-market, or growth engineering tasks.
allowed-tools:
  - Bash
  - Read
  - Write
---

## CRITICAL: Direct API vs LLM — Read This First

**Default to direct API calls. Only use LLM when a task genuinely requires reasoning.**

| Task | Use | Why |
|------|-----|-----|
| Fetch tweets from accounts | `growth twitter user <name>` (direct API) | No reasoning needed |
| Search Twitter/Reddit/HN | `growth <platform> search` (direct API) | No reasoning needed |
| Filter by engagement/keywords | `growth run` with filter modules (direct) | Math, not intelligence |
| Extract URLs from tweets | `growth run` with transform/extract_url (direct) | Pattern matching |
| Deduplicate content | `growth run` with filter/deduplicate (direct) | Set comparison |
| Adapt content for platform | `growth run` with transform/platform_adapt (direct) | Deterministic rules |
| **Write organic Reddit post** | **LLM needed** — use transform/rewrite or agent/promote_reddit | Needs creativity + style |
| **Judge if an idea is novel** | **LLM needed** — use agent/novelty_check or agent/synthesize | Needs reasoning |
| **Pick best items to submit** | **LLM needed** — use agent/synthesize (1 API call) | Needs judgment |

**NEVER use a full LLM agent (agent/scout) when composable modules can do the same job.**
- agent/scout = 175 Claude API calls, 15-30 min, ~$1.00
- twitter/user_tweets × 4 + filter/engagement = 0 Claude API calls, 30 sec, $0.00

**When building strategies, compose modules in this order:**
1. Source modules (direct API) — scrape data
2. Filter modules (direct) — reduce data
3. Transform modules (direct) — adapt format
4. agent/synthesize (1 LLM call) — ONLY IF you need intelligent selection
5. Action modules (direct API) — post/engage

## Strategy Execution Modes

Each strategy in `growth run --list` uses one of two modes:

| Mode | When | Speed | Cost | Example |
|------|------|-------|------|---------|
| **Module DAG** (default) | Strategy has `modules:` key | 30 seconds | $0.00-0.01 | hn-scout-and-filter, combined-routes |
| **LLM Agent** (legacy) | Strategy has `steps:` with `type: agent` | 15-30 min | $0.50-2.00 | route1-github-growth, route2-hn-submit |

**Always prefer Module DAG strategies.** Use LLM Agent strategies only when the full agent is genuinely needed (e.g., building GitHub repos from ideas).

**Hybrid strategies** (like route2-hybrid) use modules for everything + agent/synthesize for one LLM call at the end. Best of both worlds.

## Available Commands

- `growth status` — check connected accounts
- `growth twitter post --as <id> "text"` — post a tweet
- `growth twitter search "query"` — search tweets
- `growth twitter user <username>` — get user's latest tweets
- `growth twitter like --as <id> <tweet_id>` — like a tweet
- `growth reddit search "query" --sub <subreddit>` — search Reddit
- `growth reddit submit --sub <sub> --title "..." --body "..."` — post to Reddit
- `growth hn search "query"` — search Hacker News
- `growth hn top` — HN front page
- `growth hn submit --title "..." --url "..."` — submit to HN
- `growth run <strategy> [--dry-run]` — run a strategy
- `growth run --list` — list available strategies
- `growth modules list` — browse composable modules
- `growth modules info <name>` — module details
- `growth modules create <name>` — scaffold new strategy
- `growth traction` — check live engagement
- `growth traction --json` — engagement data for analysis

## Traction Analysis

When the user asks about engagement, performance, or "how are my posts doing":

1. Run `growth traction --json` to get live engagement data
2. Analyze the numbers: compare across platforms, identify trends, spot outliers
3. Give actionable recommendations

## Tips

- Always use `--dry-run` first to preview actions
- Use `--json` flag for structured output
- Rate limits are always on — accounts are protected by default
- Use burner accounts, not your personal accounts
- Compose small modules (twitter/search → filter → transform → action) instead of monolithic agents
