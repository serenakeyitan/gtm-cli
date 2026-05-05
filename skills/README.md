# gtm skills — how the agent thinks

This directory is the agent's instruction set. **You (the agent) read this
file first.** Then you load the specific skills you need for the task at
hand.

Skills are markdown. They tell you *how to think* about a marketing task.
The MCP tools (see `gtm mcp serve`) give you *what to act with*. Together,
they replace the legacy Python `agent/*` files that just wrapped a prompt
around a `query()` call.

This is Phase 3 of the [Claude-Code-shaped redesign](../docs/PLAN-claude-code-shape.md).

---

## How to use this directory

When the user gives you a marketing task, do this in order:

1. **Read `decisions/which-platform.md`** if the user hasn't said where to post.
2. **Read the matching `voice/<platform>.md`** for the platform you're posting to.
3. **Read the matching `workflows/<task>.md`** if one fits (Show HN launch, Reddit seed, scout, traction watch).
4. **Read `decisions/safety-checks.md`** before any `*_submit` or `*_post` MCP tool call.
5. Use the MCP tools. Never shell out to `gtm` commands when an MCP tool exists.

Skip steps that don't apply. A small task may only need one voice file and one MCP call.

---

## Index

### Voice — platform-specific tone rules

| File | When to load |
|---|---|
| [voice/reddit-organic.md](voice/reddit-organic.md) | Posting/commenting on Reddit. Strict: lowercase, no "i built", banned phrases. |
| [voice/hn-technical.md](voice/hn-technical.md) | Submitting to Hacker News. Neutral, factual, original article titles. |
| [voice/twitter-engagement.md](voice/twitter-engagement.md) | Tweets and threads. Engagement-optimized, more direct than Reddit. |

### Workflows — multi-step playbooks

| File | When to load |
|---|---|
| [workflows/show-hn-launch.md](workflows/show-hn-launch.md) | User wants to launch on HN. End-to-end: dedup check → submit → watch → respond. |
| [workflows/reddit-organic-seed.md](workflows/reddit-organic-seed.md) | User wants to seed Reddit posts (one or many subs, possibly multi-account). |
| [workflows/cross-platform-scout.md](workflows/cross-platform-scout.md) | User asks "what's trending in X" — pull HN+Reddit+Twitter, synthesize, recommend. |
| [workflows/traction-watch.md](workflows/traction-watch.md) | User wants to monitor live posts for engagement. Daily digest, alerts on threshold. |

### Decisions — judgment skills

| File | When to load |
|---|---|
| [decisions/which-platform.md](decisions/which-platform.md) | User says "launch this" but doesn't say where. You decide. |
| [decisions/when-to-amplify.md](decisions/when-to-amplify.md) | A post is climbing — should you bring in supporter accounts? |
| [decisions/safety-checks.md](decisions/safety-checks.md) | About to call `*_submit` / `*_post`. Run these checks first. |

### Reference — gotchas

| File | When to load |
|---|---|
| [reference/platform-quirks.md](reference/platform-quirks.md) | Subreddit quirks, HN automod patterns, Twitter rate limits in practice. |

---

## Hard rules across all skills

These are **non-negotiable** regardless of what any specific skill says:

1. **Always dry-run first** when calling `*_submit` or `*_post` MCP tools.
   - Show the user what you're about to send. Get explicit OK. Then call without `dry_run`.
2. **Never bypass `decisions/safety-checks.md`** before a posting tool call.
   - The checklist is short. Skipping it is how accounts get banned.
3. **Never repost content that was removed.** If a post was mod-removed, the same content from a different account is still the same content.
4. **Stay under platform rate limits.** The MCP tools enforce them, but if a rate-limit error comes back, **stop**. Don't retry from another identity to bypass it.
5. **Always use the user's own voice.** Read `voice/<platform>.md` before drafting. Don't write generic marketing copy that the voice rules forbid.

---

## How to discover MCP tools at runtime

If you need to remember what tools exist:

- Call `mcp__gtm__list_modules` — returns the registry grouped by category.
- Read `docs/mcp-quickstart.md` — has the full tool table.

The schemas are typed. Each tool tells you its required + optional params. Don't guess — read the schema.

---

## When a workflow doesn't exist for the user's task

Don't force-fit. **Plan ad-hoc:** read the relevant `voice/` + `decisions/` skills, pick MCP tools, narrate your plan to the user, dry-run, get OK, execute.

Only materialize a YAML strategy (`gtm/strategies/`) **if the user asks for repeatability** ("save this so I can run it again next month"). Strategies are artifacts, not authoring surface.

---

## Forking skills

Skills are filesystem files. The user can drop their own variant in:
- `~/.config/gtm/skills/<path>` — user-global override (precedence: highest)
- `<project>/.gtm/skills/<path>` — project-local override
- `<repo>/skills/<path>` — repo defaults (this directory)

When you read a skill, check user-global → project-local → repo, in that order. Use the first one found. *(This precedence isn't enforced by code yet — it's a contract for when Phase 4 wires it up via `SKILL.md`.)*
