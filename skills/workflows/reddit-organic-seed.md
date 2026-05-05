# Workflow: Reddit organic seed

**When to load this:** user wants to seed Reddit posts — one or many subs,
maybe across multiple accounts (organic supporters).

The goal is **organic-feeling presence**, not a launch blast. Reddit's
mods and automod aggressively remove anything that looks coordinated.

---

## Pre-flight (always)

1. **Read [voice/reddit-organic.md](../voice/reddit-organic.md).** This is the strictest voice in the system. Banned phrases get posts auto-removed.
2. **Confirm with the user:**
   - What product/topic? (Have a draft post already? If not, you'll draft.)
   - Which subreddit(s)? (If they don't know, run a discovery step — see Step 1.)
   - Which identity/identities? (For multi-account, make sure each one is warmed — see [reference/platform-quirks.md](../reference/platform-quirks.md).)

---

## Step 1 — find the right subreddits (if not specified)

If the user just said "post on Reddit," help them pick:

```
mcp__gtm__reddit_search({"query": "<topic>", "count": 20})
```

Look for subreddits where similar content has high upvotes AND comments. Top score with zero comments is dead traffic. Recommend 1-3 subreddits to the user.

For each candidate sub, also check:

- Does it allow self-posts vs. links only?
- Karma minimums (some subs require 100+ comment karma)
- Has the user posted there before? (Returning to a sub > posting fresh)

If you have access to the platform-rules cache (`gtm/data/reddit_sub_rules.yaml`), read it. If not, the safe path is to ask the user about karma history.

---

## Step 2 — draft the post

For each sub:

1. **Title** (≤ 75 chars, voice rules apply — see voice/reddit-organic.md)
2. **Body** (the post itself)

If the user gave you content already:

- Run it through `mcp__gtm__transform_rewrite({"platform": "reddit", "tone": "organic", "field": "body"})` for tone matching.
- Then **manually scan** for banned phrases. Don't trust the LLM — check every result.

If the user wants you to draft from scratch:

- Lead with the problem, not the product.
- One natural mention of the product, framed as "found this" / "started using this" / "wanted to share".
- Don't link to a landing page. Link to a GitHub repo, a blog post, or the user's own writing.

Show the user the draft. Get OK before any tool call.

---

## Step 3 — safety checks

Run [decisions/safety-checks.md](../decisions/safety-checks.md). For Reddit specifically:

- Identity has met the sub's karma minimum?
- Identity hasn't posted to this sub in the last 24h?
- Identity hasn't been mod-removed from this sub before? (See platform-quirks.md.)
- Body doesn't contain banned phrases? (Voice/reddit-organic.md has the hard list.)

---

## Step 4 — dry-run

```
mcp__gtm__reddit_submit({
  "subreddit": "<sub>",
  "title": "<title>",
  "body": "<body>",        # for self-post
  "url": "<url>",          # OR url, not both
  "dry_run": true,
  "identity": "<identity>"
})
```

Show the dry-run output. Get OK.

---

## Step 5 — submit

Same call without `dry_run`. Capture the post URL. Tell the user.

If posting to **multiple subs**:

- **Stagger.** Do one, wait at least 30-60 minutes, do the next. Reddit watches for cross-posting bursts.
- Use `mcp__gtm__control_jitter({"min_seconds": 1800, "max_seconds": 7200})` between submissions if you're orchestrating in a strategy YAML.
- Never use the **same body** across subs. Reword — even small variations help.

---

## Step 6 — first-hour engagement

For the first hour:

- Watch for comments. Reply substantively to questions (the user does this; you draft if asked).
- If a comment hits a misunderstanding, clarify — don't ignore.
- **Never reply with "thanks!"** — Reddit reads that as low-effort. Add something.

If the user wants metrics:

```
mcp__gtm__track_engagement({"post_url": "<reddit URL>"})
```

---

## Step 7 — amplification (optional, careful)

If the user has supporter identities and the post is climbing, you can amplify with upvotes/comments from other accounts. But:

- Read [decisions/when-to-amplify.md](../decisions/when-to-amplify.md) first.
- **Never amplify from a cold account** that has zero prior activity in the sub.
- **Never amplify within the first 30 minutes** — looks coordinated.
- Stagger 15-60 minutes between supporter actions.

If unsure, **don't amplify**. Better an organic post that climbs slow than a removed post.

---

## Step 8 — what to do on removal

Reddit will mod-remove or automod-remove some posts. That's normal. But:

- **Do not repost the same content.** Same content from different identity = same removal. Update [reference/platform-quirks.md](../reference/platform-quirks.md) if you can; tell the user.
- **Do not cross-post the removed content to a "safer" sub.** Mods talk; you'll get removed there too within a day.
- If the user wants to retry, **rewrite from scratch with a different angle** and wait 7+ days.

---

## Multi-account coordination — when it makes sense

If the user has set up multiple identities (`mcp__gtm__list_modules` won't show identities; check via the `gtm` CLI or ask the user for handles):

- Use **one primary identity** for the actual post.
- **Supporter identities** can upvote and comment, with these rules:
  - Each supporter has its own posting cadence (check rate-limit state).
  - Each supporter has its own voice — don't make them sound the same.
  - Stagger supporter actions; never burst.
- **Never create new accounts to amplify.** Aged accounts only.

When in doubt: post once, organic. The user can amplify manually if they want.
