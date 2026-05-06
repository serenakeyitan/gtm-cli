# gtm-cli — agent operational rules

Companion to [SKILL.md](SKILL.md). SKILL.md tells you **how to use the
tools**; this file is the **operational discipline** — when LLM calls
are warranted, the post lifecycle contract, and what to do when things
go wrong.

---

## Direct API first, LLM last

This is non-negotiable. It's the original gtm thesis and the reason the
tool exists.

### Decision tree

```
Can this be done with a deterministic MCP tool?
  YES → Use the tool. Cost: $0.00. Speed: instant. Risk: none.
  NO  → Does it genuinely need reasoning or creative writing?
        YES → Use mcp__gtm__agent_synthesize (1 LLM call, ~$0.01)
              or mcp__gtm__transform_rewrite (1 call per item).
        NO  → You probably CAN do it deterministically. Think harder.
              Re-read the tool list in SKILL.md.
```

### Cost / speed reference

| Tool type | Claude API calls | Cost | Speed |
|---|---|---|---|
| Sources (scrape) | 0 | $0.00 | 1-8s |
| Filters | 0 | $0.00 | <1ms |
| Transforms (`platform_adapt`, `extract_url`, `summarize`) | 0 | $0.00 | <1ms |
| `transform_rewrite` (LLM tone adapter) | 1 per item | ~$0.01 | 5-10s |
| `agent_synthesize` (LLM ranker) | 1 total | ~$0.01 | 5-10s |
| Actions (`*_submit`, `*_post`) | 0 | $0.00 | 2-15s + rate-limit gate |

If you find yourself planning a workflow with **more than 2 LLM calls
per task**, you're probably wrong. Re-read [skills/workflows](skills/workflows/)
— most flows are deterministic end-to-end.

### Fallback behavior

LLM tools degrade gracefully on rate limit / API outage:

- `agent_synthesize` → falls back to engagement-score sort.
- `transform_rewrite` → returns original text unchanged.
- `transform_summarize` → smart truncation at sentence boundary.

The pipeline always produces output. If you see a rate-limit error from
an LLM tool, the result still came back — just less smart. Move on.

---

## Post lifecycle (dashboard contract)

When the user is running a launch tracked in a launch directory
(`<dir>/.gtm-launch.yaml`), posts move through these statuses.
**`paused` is reserved for the human — never set it from automation.**

| status | meaning | who sets it |
|---|---|---|
| `drafting` | active queue — 100% intended to ship | you |
| `paused` | human waitlist (skip / hold / reconsider) | **human only** |
| `scheduled` / `planned` | future, not yet drafted | either |
| `live` | posted; canonical row carries permalink + engagement | you |
| `removed` | killed by mods | you |

**When a draft ships:**
1. Delete the draft entry.
2. Add the canonical `pN` row with `status: live` + permalink + engagement.
3. **Do not** re-tag the draft as `paused` — that conflates "human held this back" with "this already shipped" and loses the human-intent signal.

This contract is enforced by the dashboard renderer. If you violate it,
the user's dashboard will lie to them about what's happening.

---

## When to use the legacy `Bash gtm ...` path

A few operations don't have MCP equivalents and require the CLI:

| Need to… | Shell to |
|---|---|
| First-time identity setup | `gtm auth <platform>` (drives Playwright/Cookie-Editor) |
| List connected identities + cooldowns | `gtm status` |
| Read recent posting activity | `gtm log` |
| Manage a launch directory | `gtm launch init/link/info`, `gtm post draft/list/status/submit/sync`, `gtm dashboard build/serve/deploy` |
| Reddit lifecycle helpers (launch flow) | `gtm reddit prefill --as <u> --sub <s> ...`, `gtm reddit promote <draft_id> --url <permalink>`, `gtm reddit engagement --dashboard <html>` |

For **everything else** — search, post, like, retweet, filter, transform,
synthesize, watch — use MCP tools. See [SKILL.md](SKILL.md) for the
full mapping.

---

## Rate limits — the hard floor

The rate limiter is non-negotiable. If `mcp__gtm__*_submit` returns a
rate-limit error:

1. **Stop the workflow.**
2. Tell the user when the cooldown ends.
3. **Do not** call the same tool with a different `identity` argument to bypass — that's account harvesting and platforms detect it.

Defaults (enforced by `gtm.safety.rate_limiter`):

| Platform | Per hour | Per day | Min cooldown between posts |
|---|---|---|---|
| Twitter | 2 | 6 | 5 min |
| Reddit | 1 | 3 | 10 min |
| HN | 1 | 2 | 30 min |

---

## When something gets removed

Reddit and HN remove posts. It happens. The agent rule:

1. **Don't repost the same content** from any identity. Same content = same removal. The mod brain is the same.
2. **Don't cross-post the removed content to a "safer" sub.** Sub mods talk; you'll get removed there too within 24h.
3. **Update [skills/reference/platform-quirks.md](skills/reference/platform-quirks.md)** with what got removed and why. This is institutional memory.
4. If the user wants to retry, **rewrite from scratch with a different angle** and wait 7+ days.

For Reddit specifically: if a sub becomes `permanent_skip: true` in
`gtm/data/reddit_sub_rules.yaml`, that's a hard stop — don't post that
content to that sub from any identity, ever.

---

## See also

- [SKILL.md](SKILL.md) — primary agent briefing (load order, tool table, hard rules)
- [skills/README.md](skills/README.md) — skill index
- [skills/decisions/safety-checks.md](skills/decisions/safety-checks.md) — pre-post checklist (run every time)
- [docs/mcp-quickstart.md](docs/mcp-quickstart.md) — MCP server setup
- [docs/PLAN-claude-code-shape.md](docs/PLAN-claude-code-shape.md) — architecture
