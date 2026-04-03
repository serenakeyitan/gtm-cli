# growth-cli

> Claude Code gave developers a terminal for everything.  
> **growth-cli gives marketers the same.**

One terminal. Every platform. No more switching between Twitter, Reddit, and HN dashboards. No more copy-pasting across tabs.

Your accounts, your strategies, your terminal.

```bash
$ growth twitter user karpathy --count 3
  @karpathy — latest 3 tweets:

  LLM Knowledge Bases...                    ❤️ 11,025  🔁 1,124
  New supply chain attack for npm axios...  ❤️ 10,444  🔁 1,121
  Drafted a blog post, asked LLM to argue   ❤️ 30,946  🔁 2,407
    the opposite. It demolished me. lol.

$ growth hn top --count 3
  1. [1558] LinkedIn is searching your browser extensions
  2. [1131] Google releases Gemma 4 open models
  3. [440] Lemonade by AMD: open source local LLM server

$ growth run cross-search -p query="AI agents"
  ✅ twitter_search: 5 results
  ✅ reddit_search: 5 results
  ✅ hn_search: 5 results
  Status: completed
```

## Who This Is For

**Go-to-market engineers and growth engineers** who already live in the terminal. You build features in Claude Code, then switch to 3 browser tabs to market them. Stop switching. Do it all from here.

## Install — 60 Seconds

```bash
pip install -e .
growth init
```

Then connect your accounts:

```bash
growth auth twitter
growth auth reddit
growth auth hn
```

Each platform asks you to paste cookies from the [Cookie-Editor](https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm) browser extension. One click export, one paste. Done.

### Inside Claude Code

Paste this into Claude Code and it handles everything:

> Install growth-cli: run `pip install -e /path/to/growth-cli && growth init` then help me connect my social media accounts. After setup, run `growth run --list` to show available strategies.

## What You Can Do

### Read — Eyes on Every Platform

```bash
# Twitter
growth twitter search "AI agents" --count 10
growth twitter user karpathy --count 5

# Reddit
growth reddit search "launch strategy" --sub startups --count 10

# Hacker News
growth hn search "Show HN" --count 10
growth hn top --count 15
```

### Write — Post From Your Terminal

```bash
# Preview first (always)
growth twitter post "Just shipped v2! 🚀" --dry-run
growth reddit submit --sub test --title "Hello" --body "From the terminal" --dry-run
growth hn submit --title "Show HN: My Project" --url "https://example.com" --dry-run

# Post for real
growth twitter post "Just shipped v2! 🚀"
growth reddit submit --sub SaaS --title "Show r/SaaS: My Project" --body "..."
```

### Run — Composable Strategies

```bash
# List available strategies
growth run --list

# Scout Twitter for trending topics
growth run twitter-scout -p query="growth hacking" -p count=10

# Get HN front page
growth run hn-trending -p count=10

# Search across all platforms at once
growth run cross-search -p query="open source marketing"

# Dry-run any strategy
growth run cross-search --dry-run -p query="AI"

# Write your own strategy (YAML)
growth run ./my-strategy.yaml -p topic="my product"
```

### Track — Live Engagement Metrics

```bash
# Check how your posts are performing
growth traction

  🐦 twitter  2026-03-27
     Just shipped v2! 🚀
     ❤️ 142  🔁 23  💬 12  👁 8,401

  🤖 reddit  2026-03-27
     Show r/SaaS: growth-cli
     ⬆️ 38  💬 7  📊 0.92

  🟠 hn  2026-03-27
     Show HN: growth-cli
     ▲ 23  💬 4

# JSON for agent consumption
growth traction --json

# Skip live refresh (use cached data)
growth traction --no-refresh
```

Fetches live data from each platform's API. Snapshots are saved to the output repo for historical tracking.

Inside Claude Code, ask "how are my posts doing?" and the agent will run `growth traction --json`, analyze the numbers, and give you actionable recommendations.

### Manage — Accounts & Activity

```bash
growth status              # Show connected accounts
growth log                 # Show recent activity
growth migrate from-openclaw  # Import from old pipeline
```

## Account Safety

**Built-in rate limits protect your accounts from day one.** You cannot accidentally spam. The rate limiter is always on — conservative defaults well below platform detection thresholds.

```
Twitter:  2 posts/hr,  6/day,  5min cooldown between posts
Reddit:   1 post/hr,   3/day, 10min cooldown
HN:       1 submit/hr, 2/day, 30min cooldown
```

If you hit a limit, growth-cli tells you exactly how long to wait:

```
⏳ Rate limit: Cooldown active (4m 56s remaining)
   Wait 4m 56s or use --force (risky!)
```

`--force` exists but prints a scary warning. You can wait. You can't un-ban your account.

### ⚠️ Use Burner Accounts

growth-cli automates actions on social media. Platform detection is always a risk. **Use dedicated accounts, not your personal ones.** Future versions will offer pre-warmed accounts for purchase.

## How Auth Works

Each platform uses cookies — no API keys needed.

| Platform | Auth Method | What You Do |
|----------|------------|-------------|
| Twitter | Cookie paste | Export from Cookie-Editor, paste JSON |
| Reddit | Cookie paste | Export from Cookie-Editor, paste JSON |
| HN | Cookie paste | Export from Cookie-Editor, paste JSON |

Credentials are stored locally at `~/.config/growth/identities/` with `0700` permissions. **Never in git. Never uploaded anywhere.**

Cookies expire. When they do, you'll see:

```
🔑 Session expired

  Re-authenticate:  growth auth twitter
```

## Write Your Own Strategy

Strategies are YAML files. They define **what steps to run, in what order** — agents generate the actual content at runtime.

```yaml
# strategies/my-strategy.yaml
name: "My Launch Strategy"
description: "Scout trends then search Reddit for related discussions"

identities:
  twitter_account: { platform: twitter }

params:
  topic: { type: str, required: true }
  count: { type: int, default: 10 }

steps:
  - id: scout
    type: tool
    platform: twitter
    action: search
    as: $twitter_account
    params:
      query: "{{ params.topic }}"
      count: "{{ params.count }}"

  - id: reddit_research
    type: tool
    platform: reddit
    action: search
    after: scout
    params:
      query: "{{ params.topic }}"
      count: "{{ params.count }}"
```

```bash
growth run ./strategies/my-strategy.yaml -p topic="AI coding agents"
```

## JSON Output

Every command supports `--json` for agent consumption:

```bash
growth twitter user karpathy --count 1 --json
growth hn top --count 5 --json
growth run hn-trending --json -p count=3
```

## Project Structure

```
~/.config/growth/               Your private data (never in git)
├── config.yaml                 Settings
├── identities/                 Cookies & sessions (0700)
│   ├── twitter/<username>/
│   ├── reddit/<username>/
│   └── hn/<username>/
├── rate_limits/state.json      Rate limit counters
└── output/                     Git repo: drafts, posts, run logs

growth-cli/                     The tool (open source)
├── growth/
│   ├── cli.py                  Click CLI
│   ├── platforms/              Twitter, Reddit, HN adapters
│   ├── safety/                 Rate limiter
│   ├── engine/                 Strategy loader + runner
│   ├── identity/               Account management
│   └── output/                 Git-backed logger
├── strategies/                 Built-in strategies (YAML)
└── SKILL.md                    Claude Code integration
```

## Roadmap

- [x] **v0.1** — CLI, 3 platforms, rate limiter, strategies, auth, traction tracker
- [ ] **v0.2** — Multi-account, proxy support, advanced rate limiting
- [ ] **v0.3** — Chat TUI, content generation, social listening, traction alerts
- [ ] **v0.4** — Growth Cloud (buy pre-warmed accounts & IPs)
- [ ] **v0.5** — GitHub PR workflow for content review
- [ ] **v1.0** — Public launch
- [ ] **v2.0** — Plugin system, strategy marketplace, team features

## License

BSL-1.1 (Business Source License)

Free to use, modify, and fork for your own marketing. Cannot be used to offer a competing managed service. Converts to open source after 4 years.
