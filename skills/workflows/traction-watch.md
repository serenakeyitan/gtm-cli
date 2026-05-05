# Workflow: Traction watch

**When to load this:** user wants ongoing monitoring of live posts —
"watch for engagement", "let me know if it climbs", "daily digest", or
the user is mid-launch and wants to know what's happening.

This workflow has two modes: **on-demand check** (snapshot now) and
**continuous watch** (digest schedule).

---

## On-demand check (default)

User asks "how's my <thing> doing?" — give them numbers fast.

### Step 1 — collect post URLs

Two ways:

- **User provides URLs** — easiest. They paste, you watch.
- **From the launch directory** — if there's a `<launch>/posts/` directory (the launch workflow that landed in the gtm-cli repo creates these), read frontmatter for URLs.

### Step 2 — fetch engagement

```
mcp__gtm__track_engagement({"urls": [<list>]})
```

Returns per-post: score, comments, age, velocity (score-per-hour).

### Step 3 — present

Format tightly:

```
## Traction snapshot

| Post | Score | Comments | Age | Velocity |
|---|---|---|---|---|
| Show HN: gtm-cli | 47 | 8 | 2h | 23/hr |
| r/SaaS: gtm-cli | 12 | 3 | 4h | 3/hr |
```

Then the **diagnosis paragraph**:

- Which post is performing? Why (read the comments — what resonates)?
- Which is stalling? Why (low engagement → bad title? Wrong sub?)
- What's the one action that helps right now?

Don't just dump numbers. The user wants you to *interpret*.

---

## Continuous watch (digest mode)

User says "give me a daily digest" / "watch this for the next 24h".

### Step 1 — establish the watch list

Same as on-demand. Plus: ask the user the **trigger** — what should you
flag?

- **Score thresholds:** "Tell me when any post crosses 100"
- **Velocity:** "Tell me if any post hits 30/hr"
- **Comment activity:** "Tell me when there's a question I should answer"
- **Removal:** "Tell me immediately if something gets removed"

### Step 2 — schedule the watch

This depends on user's setup. Two approaches:

**Approach A — manual re-checks.** The agent isn't a daemon. The user comes back periodically and asks "any updates?", and you re-run the on-demand check.

**Approach B — strategy + cron.** If they want true automation:

1. Materialize a watch strategy at `<repo>/strategies/watch-<topic>.yaml`:
   ```yaml
   name: watch-<topic>
   modules:
     check:
       use: track/engagement
       params: { urls: [<list>] }
     digest:
       use: filter/engagement
       input: check
       params: { min_score: 100 }
   ```
2. Tell the user: "Run this every hour: `gtm run watch-<topic>` (or wire to cron)."
3. Outputs go to the engagement log.

---

## Comment-monitoring

If the user wants to track new comments (not just scores):

### Step 1 — fetch comments

If platform tools support comment fetch:

- Reddit: comments come through `track_engagement` metadata
- HN: same
- Twitter: replies via Twitter timeline

### Step 2 — classify

For each new comment, classify:

- **Question** → user should answer. Draft a reply if asked.
- **Disagreement** → user should engage on merits. Don't ignore. Don't dunk.
- **Praise** → low priority. Don't reply with "thanks!" — see voice files.
- **Spam / off-topic** → ignore.

### Step 3 — surface to user

Daily digest format:

```
## <Date> traction digest

### r/SaaS: gtm-cli (42 score, 8 comments, climbing)

**3 new questions today:**

1. "Does this work with multi-account Twitter?" — yes, identity rotation supported.
   *Draft reply ready, want me to post?*

2. "How is this different from <competitor>?" — needs your take.

3. "Any way to use this without auth?" — reads-only modules don't need auth.
   *Draft reply ready, want me to post?*

**1 disagreement:**

4. "This is just a wrapper around X" — partly true. Want me to draft a clarifying reply?
```

The user reads this in 30 seconds and decides what to act on.

---

## Threshold alerts (when to interrupt the user)

You're a tool, not a notification spammer. Only flag mid-day if:

- **Removal** — they need to know immediately so they don't keep promoting a dead URL.
- **Velocity spike** — score climbing > 50/hr means amplification window is now (see [decisions/when-to-amplify.md](../decisions/when-to-amplify.md)).
- **Hostile comment thread** — multiple downvoted negatives in a row → reputation risk.

Otherwise, wait for the digest cycle.

---

## When the watch should end

Default: 48h after the last post in the watch list. Diminishing returns
after that — Reddit posts go stale, HN drops off front page in 24h.

If the user explicitly asks for longer ("watch this through next week"),
fine. But check in: "this watch has been running for 5 days, item X has
plateaued at 12 score for 24h — drop it from the watch?"
