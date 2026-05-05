# Decision: when to amplify

**When to load this:** a post is live, it's getting some engagement, and
the question is whether to bring in supporter accounts (upvotes, retweets,
comments).

Amplification is risk. Get it wrong and you spend three accounts to save
one post, all four get flagged. Get it right and you turn a slow burn into
a front-page run.

---

## Hard rules (don't break these)

1. **Never amplify within the first 30 minutes** of the post going live. Looks coordinated.
2. **Never amplify from a cold account** — one with zero prior engagement on the topic, sub, or platform.
3. **Never use more than 3 supporter accounts** for a single post. Beyond that, everything looks like a botnet.
4. **Stagger 15-60 minutes between supporter actions.** Use `mcp__gtm__control_jitter` if running a strategy.
5. **Never amplify a removed post.** Re-uploading from another account = same content = same removal.

If any of these would be broken, **don't amplify**. Tell the user why.

---

## When amplification helps

The post is at a tipping point where small velocity changes shift the algorithm:

| Platform | Tipping zone | What amplification does |
|---|---|---|
| **HN** | Score 15-30, age 1-3h, not yet front page | Pushes onto front page, where score compounds |
| **Reddit** | Score 5-20, age 30min-2h, in `new` queue | Bumps to `hot`, where the sub's regulars see it |
| **Twitter** | 50-200 likes in 1-3h, threading well | Crosses the visibility threshold for non-followers |

Outside these zones, amplification is wasted:
- Before tipping zone → too early, looks fake
- After tipping zone → it's already climbing, you're just chasing
- Stalled below tipping zone → the post itself isn't resonating; amplification papers over a content problem

---

## When amplification hurts

- **The post is gaining negative engagement** (downvotes, hostile comments). Amplification puts the post in front of more people who'll do the same thing. Stop, don't pile on.
- **The user has used these supporters recently** (last 24h) on adjacent content. Pattern detection at the platform side is real.
- **The supporters all share an IP or device fingerprint.** If they're not on different proxies, don't bother — it'll be detected.
- **You're amplifying because the post is underperforming.** That's the wrong reason. Underperforming posts have content problems, not visibility problems.

---

## How to amplify (procedurally)

If you've decided amplification is right:

### Reddit

```
mcp__gtm__track_engagement(...)  # confirm score is in tipping zone
# wait jitter
mcp__gtm__reddit_search(...)     # supporter visits sub naturally
# wait jitter
# (no upvote tool — Reddit doesn't expose this; user does it manually)
```

For Reddit, there's no programmatic upvote in `gtm` — the user upvotes
from the supporter account themselves. What you CAN automate:

- Drafting a substantive comment from a supporter account (read the post, draft a reply that adds value, post via... no, also manual).
- Watching engagement and signaling when to act.

**Honest answer:** Reddit amplification is mostly user-driven. Tell the user what to do and when, then watch.

### Twitter

```
mcp__gtm__twitter_like({"tweet_url": "<url>", "identity": "<supporter1>"})
# wait 15-60 minutes
mcp__gtm__twitter_retweet({"tweet_url": "<url>", "identity": "<supporter2>"})
# wait 15-60 minutes  
mcp__gtm__twitter_like({"tweet_url": "<url>", "identity": "<supporter3>"})
```

Don't make all three identities do the same action. Mix likes and retweets.
Quote-tweets are more visible but require drafting.

### HN

HN has no programmatic upvote either. What works:

- A supporter posts a substantive comment that adds context. Draft it (read the post, find a real angle, write a comment in [voice/hn-technical.md](../voice/hn-technical.md) tone), have user post it.

---

## The "should I" decision tree

```
Is the post in tipping zone? → No → Don't amplify.
                              → Yes ↓
Has it been live 30+ min?    → No → Wait.
                              → Yes ↓
Are supporters warm in this  → No → Don't use them. Find others or skip.
context?                      → Yes ↓
Are the comments positive?   → No → Don't amplify (negative gets amplified too).
                              → Yes ↓
Has user used these          → Yes → Skip; pattern detection.
supporters in last 24h?       → No → Amplify, with stagger.
```

---

## How to tell the user

Be specific. Don't say "should we amplify?" — that's offloading the
decision. Say:

> The HN post is at score 18, 90min in, climbing slow. We're in the
> tipping zone. I'd amplify with one substantive comment from
> @<supporter> (they have 4 prior comments in the same topic last
> month, so they're warm). Draft is below — want me to send it to you
> to post?

That's a concrete recommendation with reasoning. The user says yes or no.
