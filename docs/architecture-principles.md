# Architecture Principles

## 1. Deterministic First, LLM Only Where Needed

**Problem:** The original growth-sop-pipeline used LLM agents for EVERYTHING — including simple tasks like "fetch tweets from accounts and filter by likes." This made every run:
- Slow (15-30 min for 87 accounts)
- Expensive ($0.50-2.00 per run)
- Fragile (rate limits, API outages = total failure)

**Solution:** Split every pipeline into deterministic modules + minimal LLM.

```
OLD (100% LLM — 175 API calls):
  agent/scout: Claude decides which accounts to scan,
               calls tools one by one, analyzes results = 175 turns

NEW (5% LLM — 1 API call):
  twitter/user_tweets × 4 accounts    → deterministic, 0 API calls
  filter/engagement                    → deterministic, 0 API calls
  transform/extract_url                → deterministic, 0 API calls
  agent/synthesize                     → 1 LLM call for "pick the best"
```

| Metric | Old (100% LLM) | New (Hybrid) |
|--------|-----------------|--------------|
| Claude API calls | ~175 | 1 |
| Time | 15-30 min | 30 seconds |
| Cost | ~$1.00 | ~$0.01 |
| Rate limit risk | High | Near zero |
| Failure mode | Total failure | Graceful fallback |

**Rule: If a task can be expressed as filter/transform/sort, use a deterministic module. Use LLM only for tasks that genuinely need reasoning (novelty judgment, content writing, strategic analysis).**

## 2. Graceful Degradation: Always Produce Output

Every LLM-powered module has a deterministic fallback:

```python
class SynthesizeModule(Module):
    async def run(self, ...):
        try:
            # Try LLM
            result = await query(prompt=...)
            return parse(result)
        except Exception:
            # On ANY failure (rate limit, API down, parse error):
            # Fall back to deterministic sorting by engagement
            return sorted(input_data, key=lambda x: x.get("score", 0))
```

**The pipeline ALWAYS produces output.** It may be less intelligent without the LLM (sorted by numbers instead of analyzed by AI), but it never hangs, never crashes, never returns empty.

This is critical for production:
- Rate limits → fallback → still works
- API outage → fallback → still works
- Model changes → fallback → still works
- Budget exceeded → fallback → still works

## 3. Parallel by Default

The DAG runner automatically parallelizes modules with no shared dependencies:

```yaml
modules:
  scout_twitter: { use: twitter/search, ... }
  scout_reddit:  { use: reddit/search, ... }
  scout_hn:      { use: hn/search, ... }
  # These 3 run in PARALLEL — no code changes needed

  merge: { use: filter/limit, input: [scout_twitter, scout_reddit, scout_hn] }
  # This waits for all 3, then runs
```

**You never manually manage concurrency.** Just declare dependencies via `input:`. The runner resolves the DAG and runs independent branches concurrently.

## 4. Modules Compose Infinitely

Every module (source, filter, transform, action, monitor, agent, strategy) implements the same interface:

```
Input:  ModuleResult (or None for sources)
Output: ModuleResult
```

This means:
- Any module → any module (universal composability)
- A strategy IS a module (fractal nesting)
- Tool modules, LLM agents, and strategies all compose freely

```yaml
# Mix tool modules + agent modules + strategy modules in one DAG
modules:
  scout:       { use: twitter/user_tweets, ... }       # tool module
  filter:      { use: filter/engagement, ... }          # tool module
  analyze:     { use: agent/synthesize, ... }           # LLM module (1 call)
  sub_launch:  { use: strategy/hn-to-reddit, ... }      # whole strategy as module
  track:       { use: track/engagement, ... }            # monitor module
```

## 5. Rate Limits Are Non-Negotiable

The rate limiter runs on EVERY action. It cannot be bypassed (except `--force` with scary warning). Users wait; users don't get banned.

```
Twitter: 2 posts/hr, 6/day, 5min cooldown
Reddit:  1 post/hr, 3/day, 10min cooldown
HN:      1 submit/hr, 2/day, 30min cooldown
```

**Rate limits are the moat.** Anyone can build a posting tool. But a tool that actively prevents your accounts from getting banned — that's the product.
