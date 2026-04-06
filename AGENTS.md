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
```
