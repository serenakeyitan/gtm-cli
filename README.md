# gtm-cli

> Claude Code gave developers a terminal for everything.
> **gtm-cli gives marketers the same.**

Search, draft, post, and track Twitter / Reddit / HN from one terminal.
Multi-account. Rate-limit-safe. Drives by hand or by agent.

```bash
$ gtm hn top --count 3
  1. [1586] LinkedIn is searching your browser extensions
  2. [1207] Google releases Gemma 4 open models
  3. [987]  Show HN: a CLI for testing browser layouts in 100ms

$ gtm reddit submit --sub SaaS --title "..." --body "..." --dry-run
  DRY RUN — nothing will be posted
    Account: organic_alpha
    Title:   ...
```

## Install

```bash
pip install -e ".[mcp]"
gtm init
gtm auth twitter      # also: reddit, hn
```

## Use it as a CLI

```bash
gtm twitter search "AI agents"
gtm reddit submit --sub SaaS --title "..." --dry-run
gtm traction                          # live engagement across platforms
gtm launch init                       # start a launch repo (10-min walkthrough below)
```

## Use it as an MCP server

Drop this in your project's `.mcp.json` and the agent gets 26 typed tools:

```json
{
  "mcpServers": {
    "gtm": { "command": "gtm", "args": ["mcp", "serve"] }
  }
}
```

Then ask Claude Code:

> "Search HN for AI agents, draft a Reddit post in our voice, dry-run it."

The agent reads [`skills/`](skills/) for voice rules and safety checks,
then calls `mcp__gtm__hn_search` → `mcp__gtm__reddit_submit` directly.
No bash. No YAML.

## Hard rules baked in

- **Rate limits always on.** Twitter 2/hr, Reddit 1/hr, HN 1/hr. `--force` warns loudly.
- **Dry-run first** on every posting command.
- **Multi-account aware** — `--as <handle>` or interactive picker; auto-rotates on failure.
- **No reposting removed content** — voice-rule and duplicate-detection gates run before submit.

## Want to launch something?

10-minute walkthrough: [docs/LAUNCH-ONBOARDING.md](docs/LAUNCH-ONBOARDING.md).
Scaffold → draft → ship → sync engagement → render dashboard → deploy.
Posts are markdown files. The dashboard is generated HTML. Git history IS the campaign history.

## Docs

- [SKILL.md](SKILL.md) — agent briefing
- [skills/README.md](skills/README.md) — agent's skill index
- [docs/mcp-quickstart.md](docs/mcp-quickstart.md) — MCP I/O contract
- [docs/architecture-principles.md](docs/architecture-principles.md) — why deterministic-first
- [ROADMAP.md](ROADMAP.md) — what shipped, what's next

## License

Apache 2.0.
