# growth-cli v0.2 — Module System Design

> **"Every piece is a Lego block. Same blocks, different arrangement."**

## The Quant Trading Analogy

```
Quant Trading                    Growth Marketing (growth-cli)
═══════════════                  ════════════════════════════════
Data Feed (price tick)           Source (twitter/search, hn/top)
Signal (RSI crossover)           Filter (engagement > 1K, deduplicate)
Alpha Model (predict return)     Transform (rewrite tone, adapt platform)
Execution (place order)          Action (post, like, comment, repost)
Risk Mgmt (position sizing)      Safety (rate limit, ban detection)
Portfolio (run N strategies)     Campaign (run N strategies in parallel)
PnL Tracking                     Traction Tracking

KEY: Every piece is a named, discoverable, composable module.
     A strategy IS a module. Modules compose infinitely.
```

## Module Architecture

### The Module Contract

Every module implements one interface:

```python
@dataclass
class ModuleResult:
    """Standard output from any module."""
    success: bool
    data: list[dict[str, Any]]    # The payload — list of items
    metadata: dict[str, Any]      # Execution info (timing, counts, etc.)
    errors: list[str]             # Any non-fatal errors


class Module(ABC):
    """Every module — source, filter, transform, action, monitor — implements this."""
    
    name: str                      # "twitter/search", "filter/engagement"
    category: str                  # "source", "filter", "transform", "action", "monitor", "control"
    description: str
    input_schema: dict             # What this module accepts
    output_schema: dict            # What this module produces
    
    async def run(self, input_data: ModuleResult | None, params: dict, context: ModuleContext) -> ModuleResult:
        """Execute the module.
        
        input_data: output from upstream module (None for sources)
        params: user-provided parameters
        context: identity, rate limiter, config, etc.
        """
        ...
```

### Module Context (Transparent Infrastructure)

The context handles everything the user shouldn't worry about:

```python
@dataclass
class ModuleContext:
    """Passed to every module — handles infrastructure transparently."""
    identity: Identity | None       # Which account to use
    rate_limiter: RateLimiter       # Enforced automatically
    output_logger: OutputLogger     # Logs every action
    config: GrowthConfig
    
    # These are transparent — modules don't need to think about them
    # The context handles rate limiting, identity resolution, logging
```

### Module Categories

```
SOURCES — Gather data from platforms (Eyes)
  Input: None (or query params)
  Output: list of items (tweets, posts, stories)
  
  twitter/search          Search tweets by query
  twitter/user_tweets     Get a user's recent tweets
  twitter/get_tweet       Get a single tweet by ID
  reddit/search           Search Reddit
  reddit/top_posts        Top posts from a subreddit
  reddit/subreddit_rules  Get posting rules
  hn/search               Search HN via Algolia
  hn/top_stories          Current front page
  github/search_repos     Search GitHub repos

FILTERS — Process and reduce data (Brain)
  Input: list of items
  Output: filtered list of items
  
  filter/engagement       Keep items above engagement threshold
  filter/keyword          Keep/exclude items matching keywords
  filter/deduplicate      Remove items already seen/posted
  filter/time_window      Keep items within time range
  filter/novelty          Check if similar content exists (GitHub, HN, etc.)
  filter/limit            Take top N items

TRANSFORMS — Adapt content (Voice)
  Input: list of items
  Output: list of transformed items
  
  transform/rewrite       LLM rewrite for platform tone (organic, technical, etc.)
  transform/summarize     Condense for character limits
  transform/extract_url   Find original source URL from tweets
  transform/platform_adapt  Format content for specific platform requirements

ACTIONS — Execute on platforms (Hands)
  Input: list of items to act on
  Output: list of results (post IDs, URLs, success/fail)
  
  twitter/post            Post a tweet
  twitter/like            Like a tweet
  twitter/retweet         Retweet
  twitter/reply           Reply to a tweet
  twitter/follow          Follow a user
  reddit/submit           Submit to a subreddit
  reddit/comment          Comment on a post
  hn/submit_link          Submit a link to HN
  hn/submit_text          Submit a text post to HN
  github/create_repo      Create a GitHub repo
  github/create_pr        Create a pull request

MONITORS — Track results (Eyes on output)
  Input: list of posted items (with post IDs)
  Output: list of items with engagement data
  
  track/engagement        Fetch live engagement metrics
  track/snapshot          Save engagement snapshot to disk
  track/alert             Notify if thresholds hit

CONTROL — Flow logic (Conductor)
  These are special modules that modify execution flow.
  
  control/delay           Wait a fixed duration
  control/jitter          Wait a random duration within range
  control/parallel        Run multiple branches simultaneously  
  control/condition       If/then/else based on data
  control/retry           Retry a module on failure
  control/for_each        Run a module for each item in the list

AGENTS — LLM-powered complex tasks (Brain++)
  These wrap Claude SDK agents for tasks too complex for deterministic modules.
  
  agent/scout             Full Twitter scout (scan 87 accounts, synthesize ideas)
  agent/novelty_check     Check GitHub for existing implementations
  agent/builder           Build a GitHub repo from an idea
  agent/tester            Run tests on a built repo
  agent/promoter          Write and post Reddit content
  agent/hn_promoter       Curate and submit to HN
```

### Strategy YAML (v0.2 — Module-Based)

```yaml
name: "Show HN Launch"
description: "Scout trends, find content, submit to HN"

params:
  topic: { required: true }
  min_likes: { default: 1000 }

identities:
  twitter_scout: { platform: twitter }
  hn_poster: { platform: hn }

# DAG of modules — each node has a 'use' and optional 'input'
modules:
  # Source: scout Twitter
  scout:
    use: twitter/search
    as: $twitter_scout
    params:
      query: "{{ topic }}"
      count: 50

  # Filter: keep only high-engagement tweets
  hot_tweets:
    use: filter/engagement
    input: scout
    params:
      min_likes: "{{ min_likes }}"

  # Filter: remove already-submitted URLs
  fresh:
    use: filter/deduplicate
    input: hot_tweets
    params:
      check_platform: hn

  # Transform: extract original source URLs
  sources:
    use: transform/extract_url
    input: fresh

  # Transform: clean titles for HN
  formatted:
    use: transform/rewrite
    input: sources
    params:
      tone: technical
      platform: hn

  # Action: submit to HN
  submit:
    use: hn/submit_link
    input: formatted
    as: $hn_poster

  # Monitor: track performance
  track:
    use: track/engagement
    input: submit
    params:
      duration: 24h


# Execution: the runner resolves the DAG automatically
# scout → hot_tweets → fresh → sources → formatted → submit → track
# No need to specify order — dependencies are inferred from 'input'
```

### Composability: Strategy-as-Module

A strategy can be referenced as a module in another strategy:

```yaml
name: "Full Launch Campaign"
modules:
  hn_launch:
    use: strategy/show-hn-launch     # references another strategy
    params:
      topic: "{{ product_name }}"

  reddit_launch:
    use: strategy/reddit-organic     # another strategy
    params:
      topic: "{{ product_name }}"
      subreddits: [SaaS, startups]

  twitter_announce:
    use: twitter/post
    input: [hn_launch, reddit_launch]   # wait for both
    as: $twitter_brand
    params:
      text: "Just launched {{ product_name }}! Links in thread 🧵"

  monitor_all:
    use: track/engagement
    input: [hn_launch, reddit_launch, twitter_announce]
```

### Module Discovery CLI

```bash
$ growth modules list
  SOURCES (9 modules)
    twitter/search          Search tweets by query
    twitter/user_tweets     Get a user's recent tweets
    ...

  FILTERS (6 modules)
    filter/engagement       Keep items above engagement threshold
    filter/deduplicate      Remove already-posted content
    ...

  ACTIONS (10 modules)
    twitter/post            Post a tweet
    reddit/submit           Submit to a subreddit
    ...

$ growth modules info twitter/search
  Name: twitter/search
  Category: source
  Input: None
  Output: list of tweets [{id, text, user, favorite_count, retweet_count, ...}]
  Params:
    query (str, required): Search query
    count (int, default=20): Number of results
  Auth: Requires twitter identity
  Rate limit: 30/hr, 200/day, 8s cooldown

$ growth modules list --category filter
  filter/engagement       Keep items above engagement threshold
  filter/keyword          Keep/exclude items matching keywords
  filter/deduplicate      Remove items already seen/posted
  filter/time_window      Keep items within time range
  filter/novelty          Check if similar content exists
  filter/limit            Take top N items
```

## Updated Roadmap

```
v0.1 ✅ DONE — CLI, 3 platforms, rate limiter, strategies, traction
v0.2 — Module System (THIS)
  Phase 1: Foundation
    ☐ Module base class + ModuleResult contract
    ☐ Module registry (register, discover, list)
    ☐ Wrap existing 25+ tools as modules
    ☐ 'growth modules list/info' CLI commands
  Phase 2: Filters & Transforms
    ☐ filter/engagement, filter/keyword, filter/deduplicate
    ☐ filter/time_window, filter/novelty, filter/limit
    ☐ transform/rewrite (LLM), transform/extract_url
    ☐ transform/platform_adapt
  Phase 3: DAG Runner
    ☐ Parse module DAG from YAML (infer order from 'input')
    ☐ Parallel execution (modules with no dependencies)
    ☐ control/delay, control/jitter
    ☐ control/parallel, control/condition, control/for_each
  Phase 4: Strategy-as-Module
    ☐ Reference strategies inside other strategies
    ☐ 'growth modules create' scaffold tool
  Phase 5: Multi-Account
    ☐ Identity roles (brand, organic, supporter, scout)
    ☐ --as supports roles: --as supporter (picks from pool)
    ☐ BYOP proxy support per identity
v0.3 — Intelligence
  ☐ Chat TUI (NL → module composition)
  ☐ Agent modules (agent/scout, agent/promoter, etc.)
  ☐ Traction alerts + auto-amplify triggers
v0.4 — Growth Cloud
  ☐ Managed accounts + IPs (one-time purchase)
v1.0 — Public Launch
v2.0 — Strategy Marketplace + Plugin System
```

## File Structure Change

```
growth/
├── modules/                    # NEW — the module system
│   ├── __init__.py
│   ├── base.py                 # Module ABC, ModuleResult, ModuleContext
│   ├── registry.py             # Register, discover, list modules
│   │
│   ├── sources/                # Source modules
│   │   ├── twitter_search.py
│   │   ├── twitter_user.py
│   │   ├── reddit_search.py
│   │   ├── hn_search.py
│   │   ├── hn_top.py
│   │   └── github_search.py
│   │
│   ├── filters/                # Filter modules
│   │   ├── engagement.py
│   │   ├── keyword.py
│   │   ├── deduplicate.py
│   │   ├── time_window.py
│   │   ├── novelty.py
│   │   └── limit.py
│   │
│   ├── transforms/             # Transform modules
│   │   ├── rewrite.py
│   │   ├── extract_url.py
│   │   └── platform_adapt.py
│   │
│   ├── actions/                # Action modules
│   │   ├── twitter_post.py
│   │   ├── twitter_engage.py
│   │   ├── reddit_submit.py
│   │   ├── hn_submit.py
│   │   └── github_create.py
│   │
│   ├── monitors/               # Monitor modules
│   │   ├── engagement.py
│   │   └── snapshot.py
│   │
│   └── control/                # Control flow modules
│       ├── delay.py
│       ├── jitter.py
│       ├── parallel.py
│       ├── condition.py
│       └── for_each.py
│
├── engine/
│   ├── dag_runner.py           # NEW — DAG-based strategy execution
│   ├── runner.py               # LEGACY — sequential (kept for compatibility)
│   └── strategy_loader.py      # UPDATED — parse module DAG format
```
