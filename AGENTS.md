# gtm-cli — Agent Instructions

## CRITICAL RULE: Direct API First, LLM Last

**When executing growth tasks, ALWAYS prefer direct API modules over LLM agents.**

This is NOT a suggestion — it's a hard rule. Breaking it wastes money, hits rate limits, and makes pipelines fragile.

### Decision Tree

```
Can this be done with a direct API call?
  YES → Use a module (twitter/search, filter/engagement, etc.)
        Cost: $0.00, Speed: instant, Risk: none
  NO  → Does it need reasoning/creativity?
          YES → Use agent/synthesize (1 LLM call) or transform/rewrite
                Cost: ~$0.01, Speed: 10s, Risk: low
          NO  → You probably CAN do it with a module. Think harder.
                
NEVER use agent/scout (175 API calls) when twitter/user_tweets × N works.
NEVER use agent/promote_reddit when transform/rewrite + reddit/submit works.
```

### What Each Module Type Costs

| Module Type | Claude API Calls | Cost | Speed |
|-------------|-----------------|------|-------|
| Source (twitter/search, hn/top) | 0 | $0.00 | 1-8s |
| Filter (engagement, keyword) | 0 | $0.00 | <1ms |
| Transform (platform_adapt, extract_url) | 0 | $0.00 | <1ms |
| Transform (rewrite, summarize) | 1 per item | ~$0.01 | 5-10s |
| agent/synthesize | 1 total | ~$0.01 | 5-10s |
| agent/scout (LEGACY) | ~175 | ~$1.00 | 15-30min |
| agent/promote_reddit (LEGACY) | ~20 | ~$0.20 | 5-10min |

### Strategy Execution Modes

When running or creating strategies, check the `execution_mode` comment at the top:

```yaml
# execution_mode: module-dag       → PREFERRED. Fast, free, reliable.
# execution_mode: hybrid           → OK. Mostly modules + 1 LLM call.
# execution_mode: llm-agent        → AVOID unless genuinely needed.
```

### Fallback Behavior

All LLM modules have deterministic fallbacks:
- agent/synthesize → sorts by engagement score
- transform/rewrite → returns original text
- transform/summarize → smart truncation

If you see rate limit errors, the pipeline still completes via fallback.

## Available Modules

Run `gtm modules list` for the full catalog (30+ modules).

## Key Commands

```bash
gtm run --list                    # See all strategies + their execution mode
gtm modules list                  # Browse composable modules
gtm run <strategy> --dry-run      # Preview without executing
gtm run <strategy> --json         # Machine-readable output
gtm traction                      # Check engagement on posted content
gtm reddit prefill --as <u> --sub <s> --title "..." --body-file <p>
                                  # Open submit page prefilled, human clicks Post
gtm reddit submit ...             # Auto-submit (be careful: silent-success risk)
gtm reddit engagement --dashboard <html>
                                  # Refresh score/comments for live posts
gtm reddit promote <draft_id> --url <permalink>
                                  # Atomic draft→live: delete draft entry, add pN row
```

## Post lifecycle (dashboard contract)

When a tracking dashboard (e.g. `atf-launch`) is involved, posts move through these statuses. `paused` is reserved for the human — never set it from automation.

| status | meaning | who sets it |
|---|---|---|
| `drafting` | active queue — 100% intended to ship | agent |
| `paused` | human waitlist (skip / hold / reconsider) | **human only** |
| `scheduled` / `planned` | future, not yet drafted | either |
| `live` | posted; canonical row carries permalink + engagement | agent |
| `removed` | killed by mods | agent |

**When a draft ships:** delete the draft entry. Do **not** re-tag it as `paused` — the corresponding `pN` `live` row is the source of truth. Re-tagging shipped drafts as paused conflates "human held this back" with "this already shipped" and loses the human-intent signal.
