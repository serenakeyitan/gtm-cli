# Workflow: Cross-platform scout

**When to load this:** the user asks "what's trending in X" / "what are
people talking about" / "what should I post about" / "any opportunities
in <topic>".

Pull HN + Reddit + Twitter in parallel, synthesize, surface the highest-
signal items, recommend an action.

---

## Pre-flight (always)

Confirm with the user:

- **The topic** (be specific: "AI agents" not "AI")
- **The window** (last 24h? last week? default to 24h)
- **What they want from this** (just informed? Find a post angle? Find a comment opportunity?)

If the user is vague, ask. Scout output without a goal is just noise.

---

## Step 1 — scrape in parallel

Three MCP tool calls. They have no shared state, so call them in one batch:

```
mcp__gtm__hn_search({"query": "<topic>", "count": 15})
mcp__gtm__reddit_search({"query": "<topic>", "count": 15})
mcp__gtm__twitter_search({"query": "<topic>", "count": 15})
```

Note: `twitter_search` requires auth. If the user has no Twitter identity,
skip it and tell them.

Each returns a `ModuleResult` with structured items. Store them — you'll
chain into filters next.

---

## Step 2 — filter for engagement

Keep only items above platform-specific engagement thresholds. Different
platforms have different scales.

```
# Reddit: score 50+ in 24h is a real signal
mcp__gtm__filter_engagement({
  "input": <reddit result>,
  "min_score": 50
})

# HN: 30+ points in 24h front page candidate
mcp__gtm__filter_engagement({
  "input": <hn result>,
  "min_score": 30
})

# Twitter: 100+ likes in 24h means it broke through
mcp__gtm__filter_engagement({
  "input": <twitter result>,
  "min_likes": 100
})
```

If any platform returns < 3 items after filtering, lower the threshold
and retry — the user gets nothing useful from "no high-engagement items
this week" without context.

---

## Step 3 — synthesize

`mcp__gtm__agent_synthesize` is the LLM ranker. It takes the merged
results and ranks by relevance + novelty. Use it sparingly — costs ~$0.01.

```
mcp__gtm__agent_synthesize({
  "input": {
    "success": true,
    "data": [<all items from all three platforms, merged>],
    "metadata": {},
    "errors": []
  },
  "task": "rank these by relevance to <topic> and novelty",
  "count": 5
})
```

If `agent_synthesize` returns an error or rate limit, the deterministic
fallback ranks by raw engagement score. That's still useful — don't
block the workflow.

---

## Step 4 — surface to user

Present 3-5 items in a tight format:

```
## Top items for <topic> (last <window>)

### 1. <title>
- Platform: <hn / reddit r/sub / twitter>
- Engagement: <score / upvotes / likes>
- URL: <link>
- Why it matters: <1-2 sentences from synthesize>

### 2. ...
```

Don't dump all 15 items. Don't include items that are duplicates across
platforms (HN often re-shares Reddit posts).

---

## Step 5 — recommend an action

After surfacing items, **always close with a recommendation**. Examples:

- "Item 2 is a question with no good answer in the comments — you have
  expertise here. Want me to draft a reply?"
- "Item 4 is a competitor announcement. Worth a Show HN of your own
  project this week before it gets stale."
- "Nothing actionable this round. Re-run in 24h."

If the user wants to act on the recommendation:

- Reply to a Reddit thread → load [voice/reddit-organic.md](../voice/reddit-organic.md), draft a comment, dry-run.
- Submit to HN → load [workflows/show-hn-launch.md](show-hn-launch.md).
- Quote-tweet → load [voice/twitter-engagement.md](../voice/twitter-engagement.md).
- Reddit organic post → load [workflows/reddit-organic-seed.md](reddit-organic-seed.md).

---

## Save as a strategy (only if asked)

If the user says "do this every Monday" or "save this so I can re-run":

1. Materialize a YAML at `<repo>/strategies/<slug>.yaml`:
   ```yaml
   name: cross-platform-scout-<topic>
   modules:
     hn: { use: hn/search, params: { query: "<topic>" } }
     reddit: { use: reddit/search, params: { query: "<topic>" } }
     twitter: { use: twitter/search, params: { query: "<topic>" } }
     hot_hn: { use: filter/engagement, input: hn, params: { min_score: 30 } }
     hot_reddit: { use: filter/engagement, input: reddit, params: { min_score: 50 } }
     hot_twitter: { use: filter/engagement, input: twitter, params: { min_likes: 100 } }
     ranked: { use: agent/synthesize, input: [hot_hn, hot_reddit, hot_twitter] }
   ```
2. Tell user how to run it: `gtm run cross-platform-scout-<topic>` or
   `mcp__gtm__run_strategy({"path": "<absolute path>"})`.
3. Strategies are reproducible artifacts. **Don't materialize one for a
   one-shot scout** — the YAML is overhead.

---

## Heuristics that help

- **Same item on multiple platforms = stronger signal.** Always note overlap.
- **Threads with high comment-to-upvote ratio = active discussion.** Often a better engagement opportunity than the highest-upvoted post.
- **Old items resurfaced > new items.** "What did everyone read last week" beats "what's hot right now" for synthesis.
