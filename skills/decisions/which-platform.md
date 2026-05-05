# Decision: which platform first?

**When to load this:** the user said "launch this" / "post about this"
without specifying where, and you need to pick.

This skill is judgment, not procedure. Read the heuristics, weigh the
evidence, recommend. **Don't pick silently — tell the user the why.**

---

## The default answer

For most software / open-source / developer-tool launches, the order is:

1. **Hacker News** (Show HN) — first, because:
   - HN traffic is fast and decisive (front page in 1-2h or never)
   - HN audience is the most likely buyer/user for dev tools
   - HN is the smallest blast radius if it flops (no sub-mod removal)
2. **Reddit** — second, 24-48h later, because:
   - Cross-posting too soon looks like spam
   - You can reference the HN reception ("hit front page yesterday")
   - Different subs surface to different audiences
3. **Twitter** — concurrent or after, because:
   - Twitter rewards activity announcements and links
   - Quote-tweeting your own HN post is normal
   - Threads get the most reach when there's already activity

**For non-dev launches** (consumer apps, content products, services),
flip: Reddit first, Twitter second, HN if at all.

---

## Override the default when

### Skip HN if:
- The product is consumer-focused (HN doesn't care about consumer apps unless they're technically novel).
- The codebase isn't open source AND there's no public technical writeup. Show HN gets brutal otherwise.
- The user has burned through HN cooldown recently (3+ submissions in last 7 days from same identity).
- The URL is a landing page with no substance behind it. HN will flag it.

### Lead with Reddit if:
- The product is consumer-facing (lifestyle, productivity for non-devs, content tools).
- The user has prior karma in 2+ relevant subs. (Going where you have credibility >>> going where audience is biggest.)
- HN voice doesn't fit the product (i.e. it's a beautifully designed thing, not a technically novel thing).

### Lead with Twitter if:
- The user has 1k+ followers in the target audience.
- The product is a feature/update/reflection rather than a launch.
- Visual/design product. Twitter shows screenshots prominently.

---

## How to decide — concrete steps

### 1. Identify the product type

Ask if unclear:
- Is this technically novel? (Show HN material)
- Is this for developers, or for general users?
- Is the codebase public?

### 2. Check user's identity strength per platform

If they have multiple options:
- HN identity — has it been used? When? What submissions?
- Reddit — which subs do they have karma in? How much?
- Twitter — follower count, engagement rate?

The platform where their identity is strongest is the default answer
**even if the audience size is smaller**. A 100-follower aligned audience
beats a 100k cold audience.

### 3. Check for prior coverage

```
mcp__gtm__hn_search({"query": "<product name>"})
mcp__gtm__reddit_search({"query": "<product name>"})
```

If the product was already submitted to HN in last 90 days, HN is out.
If a related Reddit post in r/<target> got removed, that sub is out.

### 4. Stage it

Don't recommend "all platforms at once." Pick **one platform first** and
plan the second platform 24-48h later, contingent on the first's
reception. This is sequencing, not blasting.

---

## Worked examples

### Example 1: developer CLI tool, public repo, technical user

> User: "I want to launch gtm-cli."

**Recommendation:** Show HN first, Reddit r/SaaS or r/programming next day, Twitter thread day-of.

Why: it's a dev tool, public repo, technical user → HN-shaped. Cross-post
to Reddit only after HN settles (avoids "this guy is everywhere" perception).

### Example 2: notebook tool for non-developers

> User: "Want to share my AI-powered notebook app."

**Recommendation:** Reddit first (r/notebooklm, r/productivity, r/Bard
depending on positioning), Twitter second. Skip HN unless there's something
technically novel.

Why: consumer-shaped audience, HN is wrong fit unless reframed as a
technical post about how it's built.

### Example 3: company announcement (Series A, etc.)

> User: "We just raised. Where to announce?"

**Recommendation:** Twitter first (announcements are Twitter-shaped),
*maybe* Show HN if there's a product update bundled. Skip Reddit unless
there's a sub specifically for fundraising news (not most subs).

Why: announcements ≠ launches. Different game.

---

## When to push back on the user

If the user says "post on all platforms today":

- **Push back.** Coordinated cross-posts smell like marketing — exactly what every platform downranks.
- Counter-propose: stagger 24h, lead with the platform where they have the strongest signal.

If the user says "I want to post on r/<niche-sub>" but they have no karma there:

- **Tell them.** Cold-account posts in niche subs auto-fail. Either warm the account first (comment-only for a week) or pick a different sub.

---

## After you pick

Tell the user:

1. **Which platform first** (one).
2. **Why** (one line — match it to a heuristic above).
3. **Which platform next** (and the gap to wait).
4. **Load the matching workflow** to begin:
   - HN → [workflows/show-hn-launch.md](../workflows/show-hn-launch.md)
   - Reddit → [workflows/reddit-organic-seed.md](../workflows/reddit-organic-seed.md)
   - Twitter → load [voice/twitter-engagement.md](../voice/twitter-engagement.md), draft thread.
