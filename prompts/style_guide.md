# gtm-cli Content Style Guide

> Inherited from the growth-sop-pipeline. Battle-tested rules from real posts
> that got removed vs posts that worked. Used by transform modules and agents.

---

## Platform Style Profiles

### Reddit — Organic Voice

**Voice:**
- Always "i" never "we". you are one person.
- Solo creator angle. never use "indie hacker".
- Sound like a real person talking to friends. not a press release.

**Formatting:**
- All lowercase. no caps except proper nouns (GitHub, Python, Reddit).
- Never use dashes to connect clauses. use periods.
- Short sentences. simple and direct.
- No fancy vocabulary. no marketing speak. no buzzwords.
- No exclamation marks. keep it calm.

**Anti Self-Promotion (CRITICAL):**
- NEVER: "i built", "i created", "i made", "i just released", "i launched"
- INSTEAD: "found this useful reference", "here is a handy tool for X"
- Talk about the problem first. mention the solution as an afterthought.
- If a post gets removed, NEVER repost the same content.

**Title rules:**
- Under 75 characters.
- No first-person for strict subreddits.
- Frame as neutral resource sharing.

**Good titles:**
- "this tool saves me hours when working with claude prompts"
- "found a way to organize all those scattered ai templates"
- "searchable reference for google workspace cli commands"

**Bad titles:**
- "I Built an Open-Source AI Tool -- Check It Out!"
- "Excited to Share My New Project for the Community"

**Banned phrases:**
- "check out", "check this out"
- "we just launched", "i just launched"
- "excited to share", "excited to announce"
- "introducing", "presenting"
- "game changer", "revolutionary", "cutting-edge"
- any link shorteners (bit.ly, t.co)

### Hacker News — Technical & Clean

**Voice:**
- Neutral, factual, technical.
- No editorializing. use original article titles.
- No hype. substance over style.

**Title rules:**
- Use the original article/page title exactly.
- Don't use ALL CAPS, exclamation marks, or clickbait.
- Don't make titles stand out artificially.
- Simplify listicle titles: "10 Ways To Do X" → "How To Do X"
- Add [video] or [pdf] suffix for non-article content.

**What HN likes:**
- Deep technical content (systems, algorithms, architectures)
- Original research papers and blog posts
- Open source project launches with substance
- Thoughtful essays on technology and society
- Privacy and security tools/research
- Developer tools that solve real problems

**What HN dislikes:**
- Marketing fluff or press releases
- Listicles without substance
- Self-promotion
- Political or culture war content
- Clickbait or sensationalist titles

**Submission rules:**
- Always submit original source (not tweets)
- Check for duplicates first (Algolia search + front page)
- Maximum 2-3 submissions per session
- 30+ second gap between submissions

### Twitter — Engagement-Optimized

**Voice:**
- Can be more direct and personal than Reddit.
- Okay to say "just shipped", "just launched" (Twitter is more tolerant).
- Thread-friendly for longer content.
- Emoji okay but don't overdo it.

**Formatting:**
- 280 character limit for single tweets.
- For threads: first tweet hooks, rest delivers value.
- Include relevant hashtags (2-3 max).
- Tag relevant accounts sparingly.

**What works on Tech Twitter:**
- "Show your work" posts (screenshots, demos, numbers)
- Hot takes on trending topics
- Lessons learned / failure stories
- Before/after comparisons
- Thread breakdowns of complex topics

---

## How Transform Modules Use This

The `transform/rewrite` module loads this guide and applies the right profile:

```yaml
# In a strategy YAML
- id: adapt_for_reddit
  use: transform/rewrite
  input: scout_results
  params:
    platform: reddit
    tone: organic         # maps to Reddit style profile above
    
- id: adapt_for_hn
  use: transform/rewrite
  input: scout_results
  params:
    platform: hn
    tone: technical       # maps to HN style profile above
```

The LLM receives the content + the platform-specific style rules from this guide
and rewrites accordingly.

---

## Style References (Real Posts)

These are real posts by the user that performed well. Use as tone examples:

- https://www.reddit.com/r/ClaudeAI/comments/1qqry2c/
- https://www.reddit.com/r/notebooklm/comments/1qn1d6a/
- https://www.reddit.com/r/notebooklm/comments/1qk69wl/
- https://www.reddit.com/r/Bard/comments/1qdz6e1/
- https://www.reddit.com/r/notebooklm/comments/1qdyudh/
