# Workflow: Show HN launch

**When to load this:** the user wants to launch a project on Hacker News.

End-to-end: dedup check → draft title → safety checks → submit → watch
the first hours → draft replies. You drive; the user approves each
posting step.

---

## Pre-flight (always)

Before anything else:

1. **Read [voice/hn-technical.md](../voice/hn-technical.md).** Show HN has a strict title format and HN audience hates marketing voice.
2. **Confirm with the user:**
   - The canonical URL of the project (GitHub repo? Landing page?)
   - The one-line technical description (what it does, not why it's cool)
   - Which identity to post from: `mcp__gtm__list_modules` shows what's available, or check `gtm status` if you can shell.

---

## Step 1 — duplicate check

HN downranks duplicates aggressively. Check both:

```
mcp__gtm__hn_search({"query": "<project name or canonical URL>", "count": 30})
mcp__gtm__hn_top_stories({"count": 30})
```

If you find:

- **Same URL, posted in last 90 days** → don't submit. Tell user the prior submission's score; offer to comment there instead.
- **Same project, different URL, last 90 days** → tell user, ask whether to proceed.
- **Similar project (same problem, different code)** → fine to proceed; user should know who they're up against.

---

## Step 2 — draft the title

Format (from voice/hn-technical.md):

```
Show HN: <project name> – <lowercase one-line description>
```

Constraints:

- Total ≤ 80 chars
- En-dash `–` or hyphen `-` (the minus key, not em-dash)
- Description after the project name is **lowercase** and describes **what it does**, not why it matters

Show the user 2-3 title variants. Let them pick.

---

## Step 3 — safety checks

Run [decisions/safety-checks.md](../decisions/safety-checks.md). For HN specifically:

- Identity has been on HN long enough? (cold accounts get auto-flagged on Show HN)
- Submission count today? (HN tolerates 2-3/day max per account)
- Is the URL accessible? (broken links auto-flag)

If any check fails, **stop and tell the user**. Do not "try anyway."

---

## Step 4 — dry-run the submission

```
mcp__gtm__hn_submit_link({
  "title": "<picked title>",
  "url": "<canonical URL>",
  "dry_run": true,
  "identity": "<identity name>"
})
```

Show the user the dry-run output. **Get explicit OK before the real call.**

---

## Step 5 — submit

Same call without `dry_run`. Capture the returned story ID and URL.

```
{
  "id": "<hn id>",
  "url": "https://news.ycombinator.com/item?id=<id>"
}
```

Tell the user the URL. They should open it now to engage with comments — that's the highest-leverage thing they can do in the next 30 minutes.

---

## Step 6 — early-window watch (first 30 min)

For the first 30 minutes, score velocity matters more than absolute score. Tell the user:

- "Comment on every reply within 5 minutes if possible"
- "If a question is technical, answer with code/numbers, not prose"
- "Don't 'thanks!' anything — see voice/hn-technical.md"

You can offer to draft replies if they paste comment text. **You don't post comments without showing them first.**

If the user wants engagement metrics:

```
mcp__gtm__track_engagement({"story_id": "<hn id>"})
```

---

## Step 7 — amplify decision

Around the 1-2 hour mark, check if the post is climbing. If score > 30 and not on front page yet, read [decisions/when-to-amplify.md](../decisions/when-to-amplify.md) — it tells you whether bringing in supporter accounts is worth the risk.

---

## Step 8 — tell the user when you're done

Default end-state: "submitted, here's the URL, here's the score so far." Don't keep working unless they ask.

If they ask for follow-up work (Twitter announcement, Reddit cross-post), load the matching workflow:

- For Reddit: [workflows/reddit-organic-seed.md](reddit-organic-seed.md)
- For Twitter: load [voice/twitter-engagement.md](../voice/twitter-engagement.md), draft a thread, dry-run.

---

## What to do if HN hides or kills the post

- **[dead]** — usually the URL was on a blocklist. Tell user; suggest a different URL (their own domain instead of GitHub, etc.).
- **[flagged]** — too many users flagged. Don't resubmit. Wait 30+ days, retry with a different framing.
- **Stuck at 1 point** — usually the title sucked or the timing was bad. Don't resubmit same content; rework.

Never resubmit the same content from a different identity. See voice/hn-technical.md.
