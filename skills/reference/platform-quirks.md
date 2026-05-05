# Reference: platform quirks

**When to load this:** when you need ground-truth gotchas before posting
to a specific subreddit, or before a HN/Twitter action that has known
edge cases.

This is the "踩过的坑" file — only things that came from real removals or
real surprises. Update it when you learn something new.

---

## Reddit — sub-specific notes

The canonical source is `gtm/data/reddit_sub_rules.yaml` — this file is
auto-fetched/curated and the safest thing to read at runtime. The
summary below is a snapshot for quick reference; **always check the
yaml for the latest** before posting.

### High-trust subs (where things have worked)

| Sub | Notes |
|---|---|
| `r/ClaudeAI` | Best performer. Self-promo tolerated if framed as "sharing a thing i tried". 800k subs. **Note: as of 2026-05, user prefers `r/openclaw` for Claude-ecosystem drafts.** |
| `r/devtools` | Low traffic but tolerant. "open to ideas" framing worked. |
| `r/AI_Agents` | Core ICP for agent products. Project posts OK if useful. **Avoid "launch" / "i made" headlines.** Min age 30 days on identity. |
| `r/LangChain` | Tool-sharing OK if framed as "works with LangChain" or "compared to <feature>". |

### Permanent-skip subs (mod-removed, do not retry from any account)

| Sub | What got us removed |
|---|---|
| `r/LocalLLaMA` | 2026-04-20 — strict no-self-promo culture. Only research/findings, never project announcements. |
| `r/opensource` | 2026-04-20 — voice was too "i built". Could potentially retry with neutral "useful resource" framing, but don't unless you've workshopped it heavily. |
| `r/programming` | 2026-04-20 — mod-removed (not just automod). Self-promo intolerant. Only blog-post-quality essays land. |

**The rule:** if `permanent_skip: true` in the yaml, do not post that
content from any identity. The content is the problem, not the account.

### Format-strict subs

| Sub | Format requirement |
|---|---|
| `r/coolgithubprojects` | Link-only. Title format: `[lang] Project: description`. Auto-removes self/text posts. |

If a sub has `submission_type: link` or `flair_required_auto: true` in
the yaml, follow that format exactly — automod is unforgiving.

---

## Hacker News quirks

### Show HN auto-flagging triggers

These get a Show HN dead-on-arrival:

- **Title doesn't start with `Show HN:`** — the prefix is required for the Show HN treatment. Without it, your submission goes to the regular pool with no boost.
- **Hyphen vs en-dash inconsistency** — both work, but be consistent. `Show HN: gtm-cli – terminal-native GTM` is fine.
- **Description longer than 80 chars total** — looks like keyword-stuffing.
- **URL on the spam blocklist** — short URLs (`bit.ly`, `t.co`) are auto-killed. Use canonical URLs.

### When [dead] happens

If your submission shows `[dead]` (you can't see it logged in, but a logged-out check shows it gone):

- Most common cause: **URL on a blocklist.** Try the same submission with a different URL (your own domain instead of GitHub, etc.).
- Sometimes: **identity is shadowbanned.** Check by submitting a test from the same identity to a different URL — if that's also dead, the identity is the problem.

### When [flagged] happens

Multiple users flagged the post. Don't resubmit. Wait 30+ days, retry with a different angle.

### Comment culture

- "thanks!" / "great point!" → reads as low-effort. Always add substance.
- Wrong corrections → reply with evidence (link, code, numbers). HN respects this.
- Drive-by snark → ignore. Don't dunk for the audience.

---

## Twitter quirks

### Rate-limit detection

- The `gtm` rate limiter caps at 2 posts/hr, 6/day. If you hit it, the API rate-limits more aggressively for the next ~24h. **Don't try to bypass with another identity** — Twitter pattern-detects.
- Liking/retweeting from a fresh-ish account (less than 30 days, low follower count) on a popular tweet is the fastest way to get an account marked as a bot.

### Threading

- The visual threading only shows for the first ~5 tweets in a thread. Beyond that, viewers stop seeing replies as part of the thread on most clients.
- If you must do a 10-tweet thread, expect the back half to lose 70% of viewers.

### Quote-tweets

- Quote-tweeting your own post is normal and engagement-positive.
- Quote-tweeting from a supporter account about your own post: looks fake unless the supporter has clear reason to comment.

---

## Cross-platform: cooldowns

Default rate limits in `gtm` (enforced by the rate limiter, don't override):

| Platform | Per hour | Per day | Min cooldown |
|---|---|---|---|
| Twitter | 2 | 6 | 5 min |
| Reddit | 1 | 3 | 10 min |
| HN | 1 | 2 | 30 min |

If a posting tool returns a rate-limit error, **stop**. Don't try the
same action from another identity — that's account harvesting, and the
platforms detect it.

---

## When you learn something new

If the user says "we got removed from r/foo" or "HN flagged the
submission":

1. Update this file with the sub/incident and root cause.
2. If it's Reddit, also update `gtm/data/reddit_sub_rules.yaml` with
   `permanent_skip: true` (or the relevant flag).
3. Don't just say "noted" — write it down. Future-you will thank you.

This file is the institutional memory for what doesn't work.
