---
name: gtm-cli
description: |
  Terminal-native go-to-market for marketers, exposed to agents as typed
  MCP tools + a skills library. Twitter, Reddit, HN scraping, posting,
  engagement tracking. Multi-account. Rate-limit-safe.

  Use when asked about social media, marketing, growth, content, posting,
  engagement tracking, launches, or go-to-market tasks.
allowed-tools:
  - Bash
  - Read
  - Write
---

# gtm-cli — agent briefing

You're working with `gtm-cli`. The user is doing marketing/growth work
and wants you to drive: search, draft, post, watch engagement, respond.

This is the **agentic shape** of the product — you don't shell out to
`gtm` commands. You call MCP tools and read markdown skills. The CLI is
still there for the user; for you, it's the MCP server + skills library.

---

## Load order — read these as you need them

1. **`skills/README.md`** — the agent's index. Tells you which skill to load for which task. Read this first if you haven't.
2. **`skills/voice/<platform>.md`** — before drafting anything for that platform. Reddit voice is the strictest; HN is technical-only; Twitter is engagement-shaped.
3. **`skills/workflows/<task>.md`** — if a workflow matches (`show-hn-launch`, `reddit-organic-seed`, `cross-platform-scout`, `traction-watch`).
4. **`skills/decisions/safety-checks.md`** — **always**, before any `*_submit` or `*_post` MCP call.
5. **`skills/decisions/which-platform.md`** — when the user says "launch this" without specifying where.
6. **`skills/decisions/when-to-amplify.md`** — when a post is climbing and you're considering supporter-account boosts.
7. **`skills/reference/platform-quirks.md`** — for sub-specific gotchas, real removal patterns.

---

## How to act — MCP tools, not bash

The user has the gtm MCP server registered (see `docs/mcp-quickstart.md`).
You see 26 tools in your tool list, all prefixed with the MCP server's name.

**Always prefer MCP tools over `Bash gtm ...`.** If you find yourself
typing `Bash` and `gtm `, you're doing it wrong.

| Need to… | Tool to call |
|---|---|
| Find content on a platform | `mcp__gtm__hn_search`, `mcp__gtm__hn_top_stories`, `mcp__gtm__reddit_search`, `mcp__gtm__twitter_search`, `mcp__gtm__twitter_user_tweets` |
| Process scraped data | `mcp__gtm__filter_engagement`, `mcp__gtm__filter_keyword`, `mcp__gtm__filter_deduplicate`, `mcp__gtm__filter_limit` |
| Adapt content for a target | `mcp__gtm__transform_rewrite`, `mcp__gtm__transform_extract_url`, `mcp__gtm__transform_platform_adapt`, `mcp__gtm__transform_summarize` |
| Post (always dry-run first!) | `mcp__gtm__reddit_submit`, `mcp__gtm__hn_submit_link`, `mcp__gtm__twitter_post`, `mcp__gtm__twitter_like`, `mcp__gtm__twitter_retweet` |
| Pace flow inside a multi-step run | `mcp__gtm__control_delay`, `mcp__gtm__control_jitter`, `mcp__gtm__control_for_each`, `mcp__gtm__control_condition` |
| Watch live posts | `mcp__gtm__track_engagement` |
| Rank with LLM (1 call, has fallback) | `mcp__gtm__agent_synthesize` |
| Discover what tools exist | `mcp__gtm__list_modules` |
| Run a saved YAML strategy as one call | `mcp__gtm__run_strategy` |

Each tool returns a JSON `ModuleResult`:

```json
{
  "success": true,
  "count": 3,
  "data": [...],
  "metadata": {...},
  "errors": []
}
```

You can chain calls — pass an upstream result as the `input` arg of the
next tool: `mcp__gtm__filter_engagement({"min_score": 50, "input": <prev result>})`.

Every tool also accepts `dry_run` and (for auth-required tools) `identity`. Use them.

---

## Hard rules

These override anything a specific skill says:

1. **Always dry-run first** for `*_submit` and `*_post`. Show the user the dry-run output. Get explicit OK ("send it", "yes", "go"). Then call without `dry_run`.
2. **Never bypass `skills/decisions/safety-checks.md`** before a posting call. The 8-item checklist is short. Skipping it is how accounts get banned.
3. **Never repost removed content** from a different identity. The content is the problem; rewrite or skip.
4. **Stop on rate-limit errors.** Don't try another identity to bypass — that's account harvesting and platforms detect it.
5. **Read the user's voice file before drafting.** Don't write generic marketing copy that the voice rules forbid.

---

## Direct API first, LLM last

This is the original gtm thesis and it still holds:

- Most tasks are deterministic: scrape → filter → transform → post. **Zero LLM calls. Use the tools directly.**
- Use `mcp__gtm__agent_synthesize` only when you need LLM ranking (typical: "rank these 30 items by relevance to <topic>"). 1 call, ~$0.01, deterministic fallback to engagement-score sort.
- Use `mcp__gtm__transform_rewrite` for tone adaptation per item — needed for voice-aware rewrites, but check banned phrases yourself afterwards.

If you're tempted to plan a 20-step workflow that calls the LLM at every step, **stop**. Read `skills/workflows/<task>.md` — there's almost certainly a deterministic path.

---

## When to write a strategy YAML

Default: **don't**. Plan ad-hoc, call MCP tools, narrate to the user.

Materialize a YAML at `<repo>/strategies/<slug>.yaml` only if the user
says **"save this so I can run it again"** / **"do this every Monday"**.
Strategies are reproducible artifacts; they're overhead for one-shots.

To run a saved strategy: `mcp__gtm__run_strategy({"path": "<absolute path>"})`.

---

## When MCP isn't enough — `Bash` as escape hatch

A few things still require shelling to `gtm`:

- **`gtm auth <platform>`** — one-time identity setup. Walks the user through Cookie-Editor / Playwright. Don't try to drive this; tell the user to run it.
- **`gtm status`** — list connected identities + cooldowns. Shorter to read than constructing a tool call.
- **`gtm log`** — recent activity from the output git repo.
- **`gtm launch *`, `gtm post *`, `gtm dashboard *`, `gtm reddit prefill/promote/engagement`** — campaign-folder management commands (the launch workflow that landed earlier). These are filesystem-shaped operations the user runs in their launch repo. If the task involves a launch directory (`<dir>/.gtm-launch.yaml`), shell to these commands; don't try to recreate them via MCP.

For everything else: MCP first.

---

## File locations

```
~/.config/gtm/                  user config (private)
├── identities/                 accounts + cookies
├── strategies/                 user's strategies
├── rate_limits/                rate limit state
└── output/                     posted content log (git repo)

<repo>/skills/                  agent's instruction set (this is what you load)
<repo>/strategies/examples/     reference strategies (don't touch unless asked)
<repo>/gtm/data/                platform rules (reddit_sub_rules.yaml lives here)
<repo>/docs/                    PLAN-claude-code-shape.md, mcp-quickstart.md
```

---

## If something feels off

If you're about to:
- Post without dry-running → **stop**.
- Use `Bash` to call a `gtm` command that has an MCP equivalent → **stop**, switch to MCP.
- Skip a safety check because "it's a small post" → **stop**, run the check.
- Repost removed content from a different identity → **stop**, tell the user the content is the problem.

The cost of stopping to re-read a skill is 30 seconds. The cost of a
removed post or banned account is days of recovery.

---

## See also

- [docs/PLAN-claude-code-shape.md](docs/PLAN-claude-code-shape.md) — the architecture this product was built into
- [docs/mcp-quickstart.md](docs/mcp-quickstart.md) — MCP server config + tool I/O
- [skills/README.md](skills/README.md) — skills index (your primary navigation)
- [AGENTS.md](AGENTS.md) — companion file with the post lifecycle contract for launch dashboards
