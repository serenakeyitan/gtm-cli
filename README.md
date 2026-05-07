# gtm-cli

> Claude Code gave developers a terminal for everything.
> **gtm-cli gives marketers the same.**

Terminal-native go-to-market automation for Twitter, Reddit, and Hacker News.
One CLI for humans, one MCP server for agents — both backed by the same
typed module registry, rate limiter, and multi-account safety net.

```bash
$ gtm hn top --count 3
  1. [1586] LinkedIn is searching your browser extensions
  2. [1207] Google releases Gemma 4 open models
  3. [987]  Show HN: a CLI for testing browser layouts in 100ms

$ gtm reddit submit --sub SaaS --title "..." --body "..." --dry-run
  DRY RUN — nothing will be posted
    Platform: reddit
    Sub:      SaaS
    Account:  organic_alpha
    Title:    ...

$ gtm traction
  🐦 twitter  "Just shipped v2!"     ❤️ 142  🔁 23  👁 8,401
  🤖 reddit   "Show r/SaaS: ..."     ⬆️ 38   💬 7   📊 0.92
  🟠 hn       "Show HN: gtm-cli"     ▲ 23    💬 4
```

> **Just want to launch?** Skip to the [10-minute Launch Onboarding](docs/LAUNCH-ONBOARDING.md) — scaffold a launch dir, draft, ship, sync, deploy.

---

## Two ways to use it

### As a CLI (humans)

```bash
gtm twitter search "AI agents"          # search
gtm reddit submit --sub SaaS ...        # post (rate-limited)
gtm traction                            # live metrics
gtm launch init                         # start a launch repo
gtm dashboard build                     # render the dashboard
```

The CLI is interactive, multi-account aware, and rate-limit-coordinated.
Every posting command takes `--dry-run`. See `gtm --help` for the full
surface.

### As an MCP server (agents)

```json
// .mcp.json in your Claude Code project
{
  "mcpServers": {
    "gtm": { "command": "gtm", "args": ["mcp", "serve"] }
  }
}
```

The agent gets **26 typed tools** auto-generated from the module registry
— `mcp__gtm__hn_search`, `mcp__gtm__reddit_submit`, etc. Each tool returns
a structured `ModuleResult` (no stdout parsing). Pair with the
[`skills/`](skills/) library and the agent reads its own playbooks.

See [docs/mcp-quickstart.md](docs/mcp-quickstart.md) for the full I/O contract.

---

## Install

```bash
pip install -e .                # base
pip install -e ".[mcp]"         # + MCP server
pip install -e ".[agents]"      # + LLM-powered transforms
pip install -e ".[dev]"         # + pytest

gtm init                        # scaffold ~/.config/gtm/
gtm auth twitter                # connect (Cookie-Editor or Playwright)
gtm auth reddit
gtm auth hn
```

### Inside Claude Code

Drop the MCP config above, then ask the agent normally:

> "Search HN for AI agents, draft a Reddit post in our voice, and
> dry-run it."

The agent reads [`skills/README.md`](skills/README.md) for the load order,
follows [`skills/voice/reddit-organic.md`](skills/voice/reddit-organic.md)
for tone, runs [`skills/decisions/safety-checks.md`](skills/decisions/safety-checks.md),
then calls `mcp__gtm__reddit_submit` with `dry_run: true`.

---

## What's in the registry

24 typed Modules, every one a Lego block:

```bash
$ gtm modules list
  SOURCES (5)     twitter/search, twitter/user_tweets, reddit/search,
                  hn/search, hn/top_stories
  FILTERS (4)     filter/engagement, filter/keyword,
                  filter/deduplicate, filter/limit
  TRANSFORMS (4)  transform/rewrite, transform/extract_url,
                  transform/platform_adapt, transform/summarize
  ACTIONS (5)     twitter/post, twitter/like, twitter/retweet,
                  reddit/submit, hn/submit_link
  CONTROL (4)     control/delay, control/jitter,
                  control/for_each, control/condition
  MONITORS (1)    track/engagement
  AGENT (1)       agent/synthesize     # LLM ranker, 1 call, deterministic fallback
  STRATEGIES (8+) Any strategy YAML is also a composable module
```

The MCP server exposes 24 of these (everything except `strategy/*`, which
is callable via `mcp__gtm__run_strategy({"path": ...})`), plus 2
coordination tools (`list_modules`, `run_strategy`). 26 tools total.

---

## Cross-platform pipelines (YAML)

YAML strategies still work — useful when you need reproducible, parallel,
multi-step runs:

```yaml
# strategies/examples/cross-platform-scout.yaml
modules:
  twitter: { use: twitter/search, params: { query: "AI" } }    # ─┐
  reddit:  { use: reddit/search,  params: { query: "AI" } }    # ─┤ PARALLEL
  hn:      { use: hn/search,      params: { query: "AI" } }    # ─┘
  merge:   { use: filter/limit, input: [twitter, reddit, hn] } # waits for all 3
```

```bash
$ gtm run cross-platform-scout
```

Strategies compose — a strategy YAML is itself a `strategy/*` module other
strategies can call. See [`strategies/examples/`](strategies/examples/) for 8
worked examples.

**Note:** strategies are demoted from primary authoring surface to
artifact. The agent plans ad-hoc via MCP tools by default; it materializes
a strategy YAML only when you ask for repeatability ("save this so I can
run it next month").

---

## Launch workflow

End-to-end campaign management for a launch repo. One command per stage:

```bash
gtm launch init                                     # scaffold .gtm-launch.yaml + dirs
gtm launch link <existing-launch-repo>              # adopt an existing repo
gtm post draft <product> --channel "reddit r/X" \   # interactive create
    --title "..." --direction <campaign>
gtm post submit <slug> --as <identity>              # preflight + Playwright submit
gtm post sync                                       # refresh engagement
gtm dashboard build                                 # render dashboard.html
gtm dashboard serve                                 # local preview
gtm dashboard deploy --provider cloudflare          # publish
```

Posts are markdown files with frontmatter; the dashboard is a generated
HTML over them. Git history IS the campaign history. See
[docs/LAUNCH-ONBOARDING.md](docs/LAUNCH-ONBOARDING.md) for the complete walkthrough.

---

## Direct API first, LLM last

This is the architecture thesis and it still holds:

| Approach | LLM calls | Speed | Cost | When |
|---|---|---|---|---|
| Module DAG (default) | 0 | 30s | $0.00 | scrape, filter, transform, post, track |
| Hybrid | 1 | 60s | $0.01 | need ranking or tone adaptation |
| Agent reasoning | varies | varies | varies | open-ended judgment, multi-step orchestration |

The MCP server gives the agent typed tools. The agent reasons over them.
LLM modules (`transform/rewrite`, `agent/synthesize`) all degrade to
deterministic fallbacks on rate-limit / API outage — the pipeline always
produces output.

See [AGENTS.md](AGENTS.md) for the full operational rules.

---

## Account safety

Rate limits are always on. `--force` exists but warns loudly.

| Platform | Per hour | Per day | Min cooldown |
|---|---|---|---|
| Twitter | 2 | 6 | 5 min |
| Reddit | 1 | 3 | 10 min |
| HN | 1 | 2 | 30 min |

A 5-layer rate-limit coordinator wraps the per-account limiter — checks
identity cooldown, sub-specific rules, duplicate detection, daily caps,
and proxy-level limits before any post call.

⚠️ Use burner accounts, not your personal ones. Auto-rotate to backup
identities on failure.

---

## Skills library

Markdown playbooks the agent reads at task time:

```
skills/
├── README.md              ← agent's entry point
├── voice/
│   ├── reddit-organic.md  ← Reddit voice rules (banned phrases, all lowercase)
│   ├── hn-technical.md    ← HN tone (Show HN format, neutral)
│   └── twitter-engagement.md
├── workflows/
│   ├── show-hn-launch.md  ← end-to-end Show HN
│   ├── reddit-organic-seed.md
│   ├── cross-platform-scout.md
│   └── traction-watch.md
├── decisions/
│   ├── which-platform.md  ← HN vs Reddit vs Twitter
│   ├── when-to-amplify.md ← supporter-account boosts
│   └── safety-checks.md   ← always-run pre-post checklist
└── reference/
    └── platform-quirks.md ← real removal patterns from past runs
```

Skills are forkable — drop overrides in `~/.config/gtm/skills/<path>` or
`<project>/.gtm/skills/<path>`. Project-local takes precedence.

---

## File locations

```
~/.config/gtm/                 user config (private)
├── identities/                accounts + cookies
├── strategies/                user strategies (private)
├── rate_limits/               rate limit state
└── output/                    posted content log (git repo)

<repo>/skills/                 agent instruction set
<repo>/strategies/examples/    reference strategies
<repo>/gtm/data/               platform rules (reddit_sub_rules.yaml)
<repo>/docs/                   PLAN-*, mcp-quickstart, LAUNCH-ONBOARDING
```

---

## Project structure

```
gtm/
├── cli.py             CLI entry (~3640 lines, mostly interactive UX)
├── sdk.py             SDK facade — run_module, run_strategy
├── mcp_server.py      MCP server — auto-gen tool schemas from registry
├── config.py          XDG config (~/.config/gtm/)
├── modules/           24 typed Modules
│   ├── sources/       (5)
│   ├── filters/       (4)
│   ├── transforms/    (4)
│   ├── actions/       (5)
│   ├── control/       (4)
│   ├── agents/        (1, synthesize) + strategy_module
│   └── monitors/      (1)
├── platforms/         Twitter, Reddit, HN adapters
├── engine/            DAG runner (parallel, topo-sorted)
├── launch/            Launch dir / post / dashboard helpers
├── identity/          Multi-account manager + selector
├── safety/            Rate limiter + 5-layer coordinator
└── output/            Git-backed logger + traction tracker

skills/                Agent instruction set (markdown)
strategies/examples/   8 reference strategies
prompts/               Live-consumed prompts (style_guide, engagement_loop)
docs/                  PLAN-*, mcp-quickstart, LAUNCH-ONBOARDING, ROADMAP
```

---

## Documentation

- [SKILL.md](SKILL.md) — agent briefing (load order, tool table, hard rules)
- [AGENTS.md](AGENTS.md) — operational rules (direct-API-first, post lifecycle, rate limits)
- [skills/README.md](skills/README.md) — skill index
- [docs/mcp-quickstart.md](docs/mcp-quickstart.md) — MCP server setup
- [docs/LAUNCH-ONBOARDING.md](docs/LAUNCH-ONBOARDING.md) — 10-minute launch walkthrough
- [docs/PLAN-claude-code-shape.md](docs/PLAN-claude-code-shape.md) — architecture
- [ROADMAP.md](ROADMAP.md) — phase-by-phase progress

---

## Contributing

Issues and PRs welcome at [serenakeyitan/gtm-cli](https://github.com/serenakeyitan/gtm-cli).

For local development:

```bash
git clone https://github.com/serenakeyitan/gtm-cli
cd gtm-cli
uv sync --extra dev --extra agents --extra mcp
uv run pytest tests/                    # 28 unit tests
bash tests/e2e/test-launch-cp1.sh       # one of 21 e2e suites
```

---

## License

Apache 2.0 — See [LICENSE](./LICENSE).
