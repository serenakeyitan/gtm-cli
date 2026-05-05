# Voice: HN technical

**When to load this:** before submitting anything to Hacker News.

HN's culture is opposite of Reddit's organic voice — neutral, factual,
substance-driven. The audience is savvy and downvotes anything that
smells like marketing.

---

## Voice

- **Neutral, factual, technical.**
- No editorializing. Use original article titles where applicable.
- No hype. Substance over style.
- Don't be funny, don't be casual — be precise.

## Title rules

- **Use the original article/page title exactly** when submitting links.
- No ALL CAPS, no exclamation marks, no clickbait.
- Don't make titles stand out artificially.
- Simplify listicle titles: `10 Ways To Do X` → `How To Do X`.
- Add `[video]` or `[pdf]` suffix for non-article content (case sensitive).

## Show HN posts (special case)

If you're submitting a project of your own, the title format is:

```
Show HN: <project name> – <one-line technical description>
```

Examples:

- `Show HN: gtm-cli – terminal-native go-to-market automation`
- `Show HN: a CLI for testing browser layouts in 100ms`

Rules:

- En-dash (`–`) or hyphen, not colon.
- Lowercase the description (after the project name).
- Description is **what it does**, not why it's cool.
- Maximum 80 chars total.

## What HN likes

- Deep technical content (systems, algorithms, architectures)
- Original research papers and blog posts
- Open-source project launches with substance
- Thoughtful essays on technology and society
- Privacy and security tools/research
- Developer tools that solve real problems

## What HN dislikes (will downvote into oblivion)

- Marketing fluff or press releases
- Listicles without substance
- Self-promotion that isn't a Show HN
- Political or culture-war content
- Clickbait or sensationalist titles
- "X is dead" / "Why X failed" hot takes without data

## Submission rules

- **Always submit the original source.** Never a tweet about a thing — the thing.
- **Check for duplicates first.** Use Algolia search via `mcp__gtm__hn_search` AND scan front page via `mcp__gtm__hn_top_stories` (both are cheap reads).
- Maximum **2-3 submissions per session** per identity.
- **30+ second gap between submissions** — the platform rate limit is enforced by `mcp__gtm__hn_submit_link`, but don't push it.

## Engagement after posting

- HN comment culture is **substance, fast**. If you posted, watch for the first 30 minutes.
- Reply to technical questions with specifics. Code snippets. Numbers.
- Never "thanks!" or "great question!" — that's Reddit voice. On HN it's noise.
- If a comment is wrong, correct it politely with evidence. HN respects this.

## How to apply

1. Get the canonical URL of what you're submitting.
2. Check duplicates: `mcp__gtm__hn_search` for similar titles in last 30 days.
3. Draft the title — apply the rules above.
4. Run [decisions/safety-checks.md](../decisions/safety-checks.md).
5. Call `mcp__gtm__hn_submit_link` with `dry_run: true` first. Show user. Get OK. Submit.
6. Post the URL back to the user. They watch comments; you're available to draft replies.
