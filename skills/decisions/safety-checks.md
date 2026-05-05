# Decision: safety checks before posting

**When to load this:** **always**, before any `mcp__gtm__*_submit` or
`mcp__gtm__*_post` tool call.

This is a checklist. Run it every time. It's short.

---

## The checklist

| # | Check | Pass criterion | Fail action |
|---|---|---|---|
| 1 | **Identity exists** | The named identity is loaded in `gtm` | Tell user; ask for correct identity |
| 2 | **Identity warm** | Account has prior activity on this platform/sub | Don't post; tell user |
| 3 | **Karma minimum** (Reddit) | Identity has met sub's `min_total_karma` from `reddit_sub_rules.yaml` | Don't post; suggest different sub or warm-up |
| 4 | **Cooldown elapsed** | No post to this platform/sub from this identity in last platform-default window (rate limiter enforces; if it errors, don't override) | Don't post; tell user when cooldown ends |
| 5 | **No banned phrases** | Body/title doesn't contain banned phrases from the relevant `voice/<platform>.md` | Don't post; rewrite |
| 6 | **No duplicate content** | Same content not posted by this identity in last 90 days | Don't post; rewrite |
| 7 | **URL accessible** (if URL post) | URL returns 200, content is what user expects | Don't post; tell user |
| 8 | **Dry-run shown to user** | User has seen the dry-run output and explicitly OKed | Don't post; show dry-run first |

If **any** check fails, **stop and tell the user**. Do not "try it anyway."

---

## How to run each check

### 1. Identity exists

The MCP tools take an `identity` argument. If you pass a bad name, the
tool will return an error. **Check first** by calling with `dry_run: true`
— if the error is "identity not found", catch it before the live call.

### 2. Identity warm

For each platform:

- **Reddit:** identity has comment karma > 0 in the target sub OR has been on Reddit for > 30 days with general activity.
- **HN:** identity is at least 30 days old and has any prior submission or comment.
- **Twitter:** identity has > 5 prior tweets and > 30 days old.

If you don't have a way to query identity history programmatically, **ask the user**: "Have you posted from `<identity>` to `<sub>` before? When was the last activity?"

### 3. Karma minimum (Reddit only)

Read `gtm/data/reddit_sub_rules.yaml` if accessible. Per-sub schema:

```yaml
min_total_karma: 100
min_link_karma: null
min_comment_karma: 50
min_age_days: 30
permanent_skip: true   # if mod-removed before
```

If `permanent_skip` is true, **don't post to that sub from any identity** — the content is the problem, not the account.

### 4. Cooldown

`gtm` rate limiter enforces this. Defaults from the README:

- Reddit: 1 post/hr, 3/day, 10min cooldown
- HN: 1 submit/hr, 2/day, 30min cooldown
- Twitter: 2 posts/hr, 6/day, 5min cooldown

If `mcp__gtm__*_submit` returns a rate-limit error, **stop**. Don't try a different identity to bypass it — that's account harvesting, and the platforms detect it.

### 5. No banned phrases

For each draft:

- **Reddit:** scan against the banned list in [voice/reddit-organic.md](../voice/reddit-organic.md). The list is: `check out`, `we just launched`, `i just launched`, `excited to share`, `excited to announce`, `introducing`, `presenting`, `game changer`, `revolutionary`, `cutting-edge`, link shorteners.
- **HN:** clickbait phrases, ALL CAPS, multiple `!`, emoji in titles.
- **Twitter:** `🚀` overuse, "blow your mind", "you won't believe".

Do this **manually**. Don't trust the LLM to catch all of them — read the draft, scan for the patterns.

### 6. Duplicate content

If the user has posted similar content before:

- Reddit: search `mcp__gtm__reddit_search({"query": "<unique phrase from body>", "count": 30})`. If a hit from the same identity, **don't repost**.
- HN: `mcp__gtm__hn_search({"query": "<URL or title>", "count": 30})`. If a hit in last 90 days, **don't resubmit**.

Same content from a different identity = same content. Mods notice.

### 7. URL accessible

If posting a URL:

- The URL should return 200.
- The content should be what the user described (don't post a placeholder page).
- If it's the user's domain, check it's not flagged on the platform's blocklist.

You can check status programmatically by fetching the URL (any HTTP tool). If you can't, ask user to confirm.

### 8. Dry-run shown

This is the user-facing one. Always:

1. Call the posting tool with `dry_run: true`.
2. Show the user the formatted output (title, body, sub, identity).
3. Get **explicit "go" / "yes" / "send it"**. Not "looks good" — that's ambiguous.
4. Then call without `dry_run`.

If the user says "just send it" without seeing the dry-run, **still show them**. They can OK it in one second; the cost of not is a bad post going live.

---

## What to do if you find yourself skipping checks

This list is here because **every check came from a real incident.** If you're tempted to skip:

- "It's just a small post" → Removed posts hurt the identity for 30+ days.
- "The user is in a hurry" → A removed post is slower than 60 seconds of checks.
- "I checked similar posts last week" → Subs change rules; redo it.

**Run the list. Every time.**
