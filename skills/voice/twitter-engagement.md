# Voice: Twitter engagement

**When to load this:** before drafting tweets, threads, or replies.

Twitter is more tolerant than Reddit and more casual than HN. The voice
is engagement-optimized but stays personal — you're one person, not a
brand.

---

## Voice

- More direct and personal than Reddit.
- Okay to say "just shipped", "just launched" (Twitter is more tolerant).
- Thread-friendly for longer content.
- Emoji okay but **don't overdo it** — 1-2 per tweet max, never just to fill space.
- First-person is fine ("i", "i've", "we" if it's actually a team).

## Formatting

- **280 character limit per tweet.** Count it.
- For threads: first tweet hooks, rest delivers value. Don't bury the hook in tweet 3.
- Hashtags: 2-3 max. Place at the end. Don't `#use` `#them` `#mid` `#sentence`.
- Tag relevant accounts sparingly — if you tag, the tag should add value (the person should care to be in this tweet).

## What works on tech Twitter

- **"Show your work"** — screenshots, demos, numbers, before/after.
- **Hot takes on trending topics** — but only if you have a real angle.
- **Lessons learned / failure stories** — vulnerability beats victory laps.
- **Before/after comparisons** — visual or numeric.
- **Thread breakdowns** — take a complex thing, break it into 5-10 tweets, each one a beat.

## Thread structure (when content > 280 chars)

```
1/ The hook — why should anyone read tweets 2-10?
   Concrete. Specific. Punchy.

2-9/ Beats — one idea per tweet, build on each other.
     Show, don't tell. Code blocks, numbers, screenshots.

10/ The payoff — what now? CTA, link, or wrap.
```

Don't number with "1/" if you can avoid it — let the threading speak. But for technical threads, numbering helps people skim.

## Banned patterns

- **Generic motivational tweets.** "Believe in yourself!" → unfollow material.
- **"Thread 🧵" without a hook.** That's the hook. Make tweet 1 the hook.
- **"This will blow your mind"** / **"You won't believe"** — clickbait, even on Twitter.
- **Overuse of "🚀"** — it's the universal launch emoji and instantly reads as marketing.

## Reply etiquette

- Reply to people with substance. "Great point!" is noise.
- If someone disagrees, engage on the merits. Don't dunk for the audience.
- For DMs from strangers: ignore unless they've engaged on tweets first.

## How to apply

### Single tweet

1. Draft the tweet. Count chars (should be <= 270, leave room for editing).
2. If `mcp__gtm__twitter_post` is what you'll call: dry-run first.
3. Run [decisions/safety-checks.md](../decisions/safety-checks.md) — duplicate detection matters; don't double-post.

### Thread

1. Draft the full thread as a numbered list in markdown.
2. Show the user. Get OK on the whole arc — threads are hard to fix mid-flight.
3. Post tweet 1 with `mcp__gtm__twitter_post`.
4. Post each subsequent tweet as a reply (if the tool supports it; otherwise post separately and chain manually).
5. Stagger by 30-60s between tweets so the threading visual lands.

### Engagement post-launch

If you're amplifying via supporter accounts (`mcp__gtm__twitter_like`, `mcp__gtm__twitter_retweet`):

1. Read [decisions/when-to-amplify.md](../decisions/when-to-amplify.md) — don't amplify too soon or it looks fake.
2. Stagger amplification 5-30 minutes between accounts (use `control_jitter` if running a strategy).
3. Never amplify from an identity that has zero prior activity on the topic.
