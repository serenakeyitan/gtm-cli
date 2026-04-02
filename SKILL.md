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

## Available Commands

- `growth status` — check connected accounts
- `growth twitter post --as <id> "text"` — post a tweet
- `growth twitter search "query"` — search tweets
- `growth twitter like --as <id> <tweet_id>` — like a tweet
- `growth twitter reply --as <id> <tweet_id> "text"` — reply to a tweet
- `growth run <strategy> [--dry-run]` — run a strategy
- `growth run --list` — list available strategies

## Setup

```bash
pip install growth-cli
growth init
growth auth twitter    # Terminal prompts for username/email/password
growth auth reddit     # Opens Chrome for manual login
growth auth hn         # Opens Chrome for manual login
```

## Tips

- Always use `--dry-run` first to preview actions
- Use `--json` flag for structured output
- Rate limits are always on — accounts are protected by default
- Use burner accounts, not your personal accounts
