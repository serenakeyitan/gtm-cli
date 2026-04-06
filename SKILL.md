---
name: gtm-cli
description: |
  Terminal-native go-to-market CLI. Automate Twitter, Reddit, and HN from
  the terminal. 30+ composable modules. Parallel execution. Multi-account.
  Use when asked about social media, marketing, growth, content, posting,
  engagement tracking, or go-to-market tasks.
allowed-tools:
  - Bash
  - Read
  - Write
---

## CRITICAL: Direct API First

**NEVER use LLM agents when composable modules can do the job.**

```
Can a module do it? → YES → use gtm commands (free, instant)
                      NO  → use agent/synthesize (1 LLM call, $0.01)
                      
NEVER use agent/scout (175 API calls, $1). Use twitter/user_tweets × N instead.
```

## Quick Reference

```bash
# Search (no auth needed for Reddit/HN)
gtm twitter search "query"           # needs auth
gtm twitter user karpathy --count 5  # needs auth
gtm reddit search "query" --sub SaaS
gtm hn search "query"
gtm hn top --count 10

# Post (rate-limited, always --dry-run first)
gtm twitter post "text" --dry-run
gtm reddit submit --sub X --title "..." --body "..." --dry-run
gtm hn submit --title "..." --url "..." --dry-run

# Strategies
gtm run --list                           # see all + execution mode
gtm run <name> -p key=value --dry-run    # preview
gtm run <name> -p key=value              # execute
gtm run combined-routes -p query="AI"    # Route 1+2 composed

# Modules
gtm modules list                         # 30+ composable blocks
gtm modules info <name>                  # params + schema
gtm modules create my-strategy           # scaffold new YAML

# Track + Manage
gtm traction                             # live engagement
gtm traction --json                      # for analysis
gtm status                               # connected accounts
gtm log                                  # recent activity
```

## Execution Modes (CHECK BEFORE RUNNING)

```bash
gtm run --list    # shows mode per strategy
```

| Mode | Icon | Speed | Cost | When to use |
|------|------|-------|------|-------------|
| `module-dag` | 🟢 | 30s | $0.00 | Default. Scrape, filter, transform, post |
| `hybrid` | 🟡 | 60s | $0.01 | Need intelligent selection (1 LLM call) |
| `llm-agent` | 🔴 | 30min | $1.00 | AVOID. Only for code generation tasks |
| `legacy-steps` | 🔵 | varies | varies | Old format, being migrated |

**Always prefer 🟢 module-dag strategies.**

## How to Handle Common Tasks

### "Search for trending topics"
```bash
gtm hn top --count 15                    # HN front page
gtm twitter user karpathy --count 10     # specific account's tweets
gtm reddit search "AI launch" --sub SaaS # subreddit search
gtm run cross-platform-scout -p query="AI agents"  # all 3 at once
```

### "Post across platforms"
```bash
# ALWAYS dry-run first
gtm twitter post "text" --dry-run
gtm reddit submit --sub SaaS --title "..." --body "..." --dry-run
gtm hn submit --title "..." --url "..." --dry-run

# If user approves, remove --dry-run
```

### "Analyze my traction / how are my posts doing"
```bash
gtm traction --json
```
Then analyze the JSON: compare platforms, identify trends, recommend actions.

### "Create a campaign / strategy"
```bash
gtm modules list                    # show available blocks
gtm modules create my-campaign      # scaffold YAML
# Then edit ~/.config/gtm/strategies/my-campaign.yaml
gtm run my-campaign --dry-run       # preview
```

### "Which account should I use?"
When user has multiple accounts, `gtm` will prompt interactively.
With `--as`, specify by name or role:
```bash
gtm twitter post "..." --as brand_main     # specific account
gtm twitter post "..." --as supporter      # any supporter account
```

### "An account failed / got rate limited"
`gtm` asks: rotate to another account or stop?
Rate limits are always enforced. `--force` exists but warns loudly.

## Strategy YAML Format

```yaml
name: "My Strategy"
version: "2.0"
params:
  query: { required: true }
modules:
  scout:    { use: twitter/search, params: { query: "{{ query }}" } }
  filter:   { use: filter/engagement, input: scout, params: { min_likes: 100 } }
  adapt:    { use: transform/platform_adapt, input: filter, params: { platform: reddit } }
```

Modules with no mutual dependencies run in **parallel** automatically.

## Module Categories

| Category | Count | Examples |
|----------|-------|---------|
| SOURCES | 5 | twitter/search, hn/top_stories, reddit/search |
| FILTERS | 4 | filter/engagement, filter/keyword, filter/deduplicate |
| TRANSFORMS | 4 | transform/rewrite, transform/extract_url, transform/platform_adapt |
| ACTIONS | 5 | twitter/post, reddit/submit, hn/submit_link |
| CONTROL | 4 | control/delay, control/jitter, control/for_each, control/condition |
| AGENTS | 8 | agent/synthesize, agent/scout, strategy/* |
| MONITORS | 1 | track/engagement |

## Content Style Guide

When generating content for posting, follow platform-specific rules:
- **Reddit**: all lowercase, no self-promotion phrases, organic tone
- **HN**: original source URL, don't editorialize title, no clickbait  
- **Twitter**: 280 char limit, hashtags okay, threads for long content

Full rules: `prompts/style_guide.md`

## File Locations

```
~/.config/gtm/                  User config (private)
├── identities/                 Accounts + cookies
├── strategies/                 User's strategies
├── rate_limits/                Rate limit state
└── output/                     Posted content log (git repo)
```
