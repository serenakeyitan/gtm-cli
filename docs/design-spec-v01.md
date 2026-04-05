# growth-cli — Design Specification v0.1

> **"Claude Code gave developers a terminal for everything. growth-cli gives marketers the same."**

**Author:** Serena Key  
**Date:** 2026-03-27  
**Status:** Draft — awaiting review before implementation  
**License:** BSL (Business Source License)

---

## Table of Contents

1. [Vision & Positioning](#1-vision--positioning)
2. [Target User](#2-target-user)
3. [Architecture Overview](#3-architecture-overview)
4. [Repo & File Structure](#4-repo--file-structure)
5. [Platform Adapters](#5-platform-adapters)
6. [Identity Management](#6-identity-management)
7. [Rate Limiter](#7-rate-limiter)
8. [Content Workflow](#8-content-workflow)
9. [Strategy System](#9-strategy-system)
10. [Onboarding Flow](#10-onboarding-flow)
11. [CLI Commands](#11-cli-commands)
12. [Safety & Guardrails](#12-safety--guardrails)
13. [Agent Integration](#13-agent-integration)
14. [Migration from Existing Pipeline](#14-migration-from-existing-pipeline)
15. [Roadmap](#15-roadmap)
16. [Open Questions](#16-open-questions)

---

## 1. Vision & Positioning

### What Is This?

growth-cli is a **terminal-native marketing automation tool** that lets go-to-market engineers manage social media presence entirely from their terminal — no switching between Twitter, Reddit, and HN dashboards.

### The Parallel

| Developer (Claude Code) | Marketer (growth-cli) |
|---|---|
| "Write a REST API" → agent writes code | "Announce our launch" → agent drafts posts |
| Creates files → runs tests → opens PR | Creates drafts → runs safety checks → queues for review |
| Human reviews → merges → deploys | Human reviews → approves → posts go live |
| All from terminal | All from terminal |

### Core Principles

1. **Terminal-native.** Everything happens in the terminal / inside Claude Code. No web UI.
2. **Account safety first.** Built-in rate limits protect user accounts from day one. Users wait longer, but accounts don't get banned.
3. **Composable.** Strategies are modular YAML files. Platform modules are pluggable. Everything is remixable.
4. **Open core.** The tool is open source (BSL). Monetization comes later through managed account/IP infrastructure (one-time purchase, not rental).
5. **Agent-friendly.** Works equally well when a human types commands or when an AI agent calls them inside Claude Code.

### Business Model (Future — Not v0.1)

- **Free tier:** Open-source tool + bring your own accounts + bring your own proxies.
- **Paid tier:** Purchase pre-warmed accounts and residential IP bundles from growth-cloud. One-time purchase, not rental. Once sold, user owns the account.
- **Future:** Strategy marketplace where users share/fork growth playbooks.

---

## 2. Target User

**Primary:** Go-to-market engineers and growth engineers who already use Claude Code or Codex.

**Profile:**
- Technical enough to use a CLI
- Building a product (SaaS, open-source project, dev tool)
- Doing their own marketing (not a dedicated marketing team)
- Active on Twitter, Reddit, and/or Hacker News
- Tired of switching between platform UIs to post, engage, and monitor

**Not targeting (for now):**
- Non-technical marketers (need GUI)
- Marketing agencies (need multi-client, team features)
- Enterprise (need compliance, SSO, etc.)

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI LAYER                               │
│  growth <command> [options]                                   │
│  └── Click-based CLI with subcommands                       │
├─────────────────────────────────────────────────────────────┤
│                      AGENT LAYER                             │
│  Copywriter (generate content)                               │
│  Scout (discover trends)                                     │
│  └── Claude Code SDK (v0.1), abstractable later             │
├─────────────────────────────────────────────────────────────┤
│                      ENGINE LAYER                            │
│  Strategy Loader → Runner → State Machine → Checkpoint       │
│  └── Sequential execution (v0.1), DAG execution (v0.2)      │
├─────────────────────────────────────────────────────────────┤
│                      SAFETY LAYER                            │
│  Rate Limiter (per-account, per-platform)                    │
│  Content Safety (spam, TOS, duplicate detection)             │
│  └── ALWAYS ON, cannot be bypassed (except --force)         │
├─────────────────────────────────────────────────────────────┤
│                      IDENTITY LAYER                          │
│  Identity Manager (add/list/remove/health-check)             │
│  └── One account per platform (v0.1)                        │
│  └── Multi-account per platform (v0.2)                      │
├─────────────────────────────────────────────────────────────┤
│                      PLATFORM LAYER                          │
│  twitter/client.py ─── twikit + cookies                      │
│  reddit/client.py ──── Playwright + browser session          │
│  hn/client.py ──────── Playwright login + httpx requests     │
│  └── Each platform: client (transport) + tools (actions)    │
├─────────────────────────────────────────────────────────────┤
│                      OUTPUT LAYER                            │
│  Git-backed local repo for drafts, posted content, run logs  │
│  └── Optional GitHub push for visibility                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Repo & File Structure

### Public Repo: `serenakeyitan/growth-cli`

```
growth-cli/
├── pyproject.toml                     # Package definition, dependencies
├── README.md                          # "Claude Code for marketers" pitch
├── LICENSE                            # BSL
├── SKILL.md                           # Claude Code skill integration
├── AGENTS.md                          # Agent discovery + setup instructions
├── CONTRIBUTING.md
│
├── growth/                            # Main package
│   ├── __init__.py
│   ├── cli.py                         # Click CLI entry point
│   ├── config.py                      # Config loading (~/.config/growth/)
│   │
│   ├── identity/                      # Identity management
│   │   ├── __init__.py
│   │   ├── manager.py                 # Add/remove/list/health-check
│   │   ├── registry.py                # Registry YAML CRUD
│   │   └── migrate.py                 # Migration from openclaw pipeline
│   │
│   ├── platforms/                     # Platform adapters
│   │   ├── __init__.py
│   │   ├── base.py                    # Abstract platform interface
│   │   ├── twitter/
│   │   │   ├── __init__.py
│   │   │   ├── client.py             # twikit wrapper (from twikit_client.py)
│   │   │   └── tools.py              # Twitter actions (post, like, search, etc.)
│   │   ├── reddit/
│   │   │   ├── __init__.py
│   │   │   ├── client.py             # Playwright wrapper (from playwright_reddit_client.py)
│   │   │   └── tools.py              # Reddit actions (submit, comment, search, etc.)
│   │   └── hn/
│   │       ├── __init__.py
│   │       ├── client.py             # Playwright login + httpx (from playwright_hn_client.py)
│   │       └── tools.py              # HN actions (submit, comment, search, etc.)
│   │
│   ├── safety/                        # Safety & rate limiting
│   │   ├── __init__.py
│   │   ├── rate_limiter.py            # Per-account rate limit enforcement
│   │   └── content_check.py           # Pre-post safety checks
│   │
│   ├── engine/                        # Strategy execution
│   │   ├── __init__.py
│   │   ├── runner.py                  # Sequential strategy runner
│   │   ├── state.py                   # Run state machine
│   │   ├── checkpoint.py              # Checkpoint/resume
│   │   └── strategy_loader.py         # YAML strategy parser
│   │
│   ├── agents/                        # LLM-powered components
│   │   ├── __init__.py
│   │   ├── base.py                    # Agent base class
│   │   ├── scout.py                   # Twitter trend scanner
│   │   └── copywriter.py             # Content generator
│   │
│   └── output/                        # Output management
│       ├── __init__.py
│       ├── logger.py                  # Write drafts/posted/runs to output dir
│       └── git_ops.py                 # Auto-commit + optional push
│
├── strategies/                        # Built-in strategy library
│   ├── twitter-scout.yaml             # Scout trending AI topics
│   ├── hn-submit.yaml                 # Find and submit to HN
│   └── cross-post.yaml               # Draft content for all platforms
│
└── tests/
    ├── conftest.py
    ├── test_identity/
    ├── test_platforms/
    ├── test_safety/
    ├── test_engine/
    └── test_cli.py
```

### Local Private Files: `~/.config/growth/`

```
~/.config/growth/
├── config.yaml                        # User config (output path, defaults, etc.)
├── identities/
│   ├── registry.yaml                  # Master list of all identities
│   ├── twitter/
│   │   └── <username>/
│   │       ├── cookies.json           # Session cookies (SECRET)
│   │       ├── identity.yaml          # Metadata (role, rate profile, etc.)
│   │       └── health.json            # Last health check result
│   ├── reddit/
│   │   └── <username>/
│   │       ├── storage_state.json     # Playwright session (SECRET)
│   │       ├── identity.yaml
│   │       └── health.json
│   └── hn/
│       └── <username>/
│           ├── hn_cookie.json         # HN session cookie (SECRET)
│           ├── identity.yaml
│           └── health.json
└── rate_limits/
    └── state.json                     # Current rate limit counters
```

### Output Repo: `~/.config/growth/output/` (per-project, git-initialized)

```
~/.config/growth/output/
├── .git/                              # Auto-initialized by `growth init`
├── drafts/                            # Pending review
│   └── 2026-03-27_twitter_launch.md
├── posted/                            # Audit trail of all posts
│   └── 2026-03-27_twitter_handle_18294.md
├── runs/                              # Strategy execution logs
│   └── 2026-03-27_1430/
│       ├── state.json
│       ├── strategy.yaml
│       └── report.md
└── rejected/                          # Content that didn't pass review
```

---

## 5. Platform Adapters

### Base Interface

```python
# growth/platforms/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class PostResult:
    success: bool
    post_id: str | None = None
    url: str | None = None
    error: str | None = None

@dataclass
class HealthStatus:
    healthy: bool
    reason: str = ""
    last_checked: str = ""

class Platform(ABC):
    """Base interface for all platform adapters.
    
    Every platform must implement these methods.
    Adding a new platform = implementing this interface.
    """
    name: str  # "twitter", "reddit", "hn"
    
    # ── Auth ──
    @abstractmethod
    async def auth_interactive(self, **kwargs) -> dict:
        """Authenticate and return credentials to save."""
        ...
    
    @abstractmethod
    async def health_check(self, identity_dir: Path) -> HealthStatus:
        """Check if saved credentials are still valid."""
        ...
    
    # ── Actions (Hands) ──
    @abstractmethod
    async def post(self, identity_dir: Path, content: str, **kwargs) -> PostResult:
        """Create a new post/tweet/submission."""
        ...
    
    # ── Read (Eyes) ──
    @abstractmethod
    async def search(self, identity_dir: Path, query: str, **kwargs) -> list[dict]:
        """Search for content on the platform."""
        ...
    
    # ── Optional ──
    async def engage(self, identity_dir: Path, target_id: str, action: str) -> PostResult:
        """Like, upvote, retweet, etc."""
        raise NotImplementedError(f"{self.name} doesn't support engage()")
    
    async def reply(self, identity_dir: Path, target_id: str, content: str) -> PostResult:
        """Reply to a post."""
        raise NotImplementedError(f"{self.name} doesn't support reply()")
```

### Platform Auth Methods (Determined by Platform Reality)

| Platform | Auth Flow | User Experience | Stored Credential |
|----------|-----------|-----------------|-------------------|
| **Twitter** | Username + email + password → twikit programmatic login | Terminal prompts only. No browser. ~5 seconds. | `cookies.json` |
| **Reddit** | Playwright opens headed Chrome → user logs in manually | Browser window pops up. User handles CAPTCHA. ~30-60s. | `storage_state.json` |
| **HN** | Playwright opens headed Chrome → user logs in manually | Browser window pops up. User handles reCAPTCHA. ~30-60s. Then all subsequent requests use httpx (no browser). | `hn_cookie.json` |

### Migrated Code Sources

| New File | Source File | Source Repo |
|----------|------------|-------------|
| `growth/platforms/twitter/client.py` | `utils/twikit_client.py` | `growth-sop-pipeline` (org) |
| `growth/platforms/twitter/tools.py` | `tools/twitter_tools.py` | `growth-sop-pipeline` (org) |
| `growth/platforms/reddit/client.py` | `utils/playwright_reddit_client.py` | `growth-sop-pipeline` (org) |
| `growth/platforms/reddit/tools.py` | `tools/reddit_browser_tools.py` | `growth-sop-pipeline` (org) |
| `growth/platforms/hn/client.py` | `utils/playwright_hn_client.py` | `growth-sop-pipeline-serena` (personal) |
| `growth/platforms/hn/tools.py` | `tools/hn_tools.py` | `growth-sop-pipeline-serena` (personal) |
| `growth/engine/runner.py` | `runner.py` | `growth-sop-pipeline` (org) |
| `growth/engine/state.py` | `state.py` | `growth-sop-pipeline` (org) |
| `growth/engine/checkpoint.py` | `checkpoint.py` | `growth-sop-pipeline` (org) |
| `growth/agents/base.py` | `agents/base.py` | `growth-sop-pipeline` (org) |
| `growth/agents/scout.py` | `agents/twitter_scout.py` | `growth-sop-pipeline` (org) |

---

## 6. Identity Management

### v0.1 Scope: One Account Per Platform

```yaml
# ~/.config/growth/identities/registry.yaml
identities:
  - name: "twitter:myhandle"
    platform: twitter
    username: myhandle
    auth_method: password    # password | cookies_manual
    created_at: "2026-03-27T14:00:00Z"
    
  - name: "reddit:myuser"
    platform: reddit
    username: myuser
    auth_method: browser     # browser login via Playwright
    created_at: "2026-03-27T14:01:00Z"
    
  - name: "hn:myhacker"
    platform: hn
    username: myhacker
    auth_method: browser     # browser login + reCAPTCHA
    created_at: "2026-03-27T14:02:00Z"
```

### Identity YAML (Per-Identity Metadata)

```yaml
# ~/.config/growth/identities/twitter/myhandle/identity.yaml
platform: twitter
username: myhandle
auth_method: password
rate_profile: conservative    # conservative | moderate | aggressive
created_at: "2026-03-27T14:00:00Z"
last_used: "2026-03-27T15:30:00Z"
status: healthy               # healthy | warning | suspended | expired
notes: "Burner account for growth automation"
```

### v0.2+: Multi-Account with Roles

```yaml
# Future: identity.yaml with role and proxy
platform: twitter
username: organic_sarah
role: supporter              # brand | organic | supporter | scout
proxy:
  type: socks5
  endpoint: "socks5://user:pass@proxy.example.com:1080"
rate_profile: conservative
tags: [launch-team, english]
```

---

## 7. Rate Limiter

### Design: Always On, Conservative Defaults

The rate limiter runs on EVERY action. It cannot be bypassed except with `--force` (which prints a warning about ban risk).

```python
# growth/safety/rate_limiter.py

RATE_LIMITS = {
    "twitter": {
        "post":    {"per_hour": 2,  "per_day": 6,   "cooldown_seconds": 300},
        "like":    {"per_hour": 10, "per_day": 50,   "cooldown_seconds": 30},
        "reply":   {"per_hour": 3,  "per_day": 15,   "cooldown_seconds": 120},
        "retweet": {"per_hour": 5,  "per_day": 25,   "cooldown_seconds": 60},
        "follow":  {"per_hour": 5,  "per_day": 20,   "cooldown_seconds": 60},
        "search":  {"per_hour": 30, "per_day": 200,  "cooldown_seconds": 8},
    },
    "reddit": {
        "post":    {"per_hour": 1,  "per_day": 3,    "cooldown_seconds": 600},
        "comment": {"per_hour": 3,  "per_day": 15,   "cooldown_seconds": 180},
        "upvote":  {"per_hour": 10, "per_day": 50,   "cooldown_seconds": 30},
        "search":  {"per_hour": 20, "per_day": 100,  "cooldown_seconds": 10},
    },
    "hn": {
        "submit":  {"per_hour": 1,  "per_day": 2,    "cooldown_seconds": 1800},
        "comment": {"per_hour": 2,  "per_day": 10,   "cooldown_seconds": 300},
        "upvote":  {"per_hour": 5,  "per_day": 30,   "cooldown_seconds": 60},
        "search":  {"per_hour": 60, "per_day": 500,  "cooldown_seconds": 5},
    },
}
```

### Rate Limit State Persistence

```json
// ~/.config/growth/rate_limits/state.json
{
  "twitter:myhandle": {
    "post": {
      "this_hour": [
        {"at": "2026-03-27T14:05:00Z", "action": "post"},
        {"at": "2026-03-27T14:35:00Z", "action": "post"}
      ],
      "this_day": [
        {"at": "2026-03-27T09:00:00Z", "action": "post"},
        {"at": "2026-03-27T14:05:00Z", "action": "post"},
        {"at": "2026-03-27T14:35:00Z", "action": "post"}
      ],
      "last_action": "2026-03-27T14:35:00Z"
    }
  }
}
```

### Flow: Every Action Goes Through the Limiter

```
User or Agent calls: growth twitter post --as myhandle "Hello!"
         │
         ▼
┌─ RATE LIMITER CHECK ─────────────────────────────┐
│  1. Load state for twitter:myhandle               │
│  2. Check: posts this hour < 2?         ✅ yes   │
│  3. Check: posts today < 6?             ✅ yes   │
│  4. Check: last post > 300s ago?        ❌ 2m ago│
│  5. RESULT: Wait 3 minutes                       │
└──────────────────────────────────────────────────┘
         │
         ▼
    ⏳ "Rate limit: cooldown active (3m 00s remaining). Waiting..."
         │
         ▼ (after 3 minutes)
┌─ SAFETY CHECK ───────────────────────────────────┐
│  1. Spam detection (LLM)                 ✅ pass │
│  2. Platform TOS check (rules)           ✅ pass │
│  3. Duplicate content check              ✅ pass │
└──────────────────────────────────────────────────┘
         │
         ▼
    Platform client: twitter_client.post("Hello!")
         │
         ▼
    ✓ Posted (tweet ID: 18294)
    ✓ Rate limit state updated
    ✓ Logged to output/posted/
    ✓ Git committed
```

---

## 8. Content Workflow

### The Draft → Review → Post Flow

Everything posted goes through a staging pipeline. This is the "PR for content" model.

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  DRAFT   │────▶│  REVIEW  │────▶│ APPROVE  │────▶│  POSTED  │
│          │     │          │     │          │     │          │
│ Agent or │     │ Safety   │     │ Human    │     │ Platform │
│ human    │     │ checks   │     │ confirms │     │ API call │
│ creates  │     │ run auto │     │ in term  │     │ + log    │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                      │
                      ▼
                 ┌──────────┐
                 │ REJECTED │
                 │          │
                 │ Safety   │
                 │ failed   │
                 └──────────┘
```

### Direct Mode vs Draft Mode

For quick actions, users can skip the draft stage:

```bash
# Draft mode (recommended for strategies)
$ growth draft "Announce our new feature across all platforms"
  → Drafts created in output/drafts/
  → Review with: growth review

# Direct mode (for quick one-offs)  
$ growth twitter post --as myhandle "Quick update!"
  → Safety checks run inline
  → Posts immediately if checks pass
  → Still logged to output/posted/
```

### Draft File Format

```markdown
<!-- output/drafts/2026-03-27_twitter_launch.md -->
---
platform: twitter
identity: twitter:myhandle
created_at: "2026-03-27T14:00:00Z"
strategy: cross-post
status: draft           # draft | approved | posted | rejected
safety:
  spam: null            # null = not yet checked
  tos: null
  duplicate: null
---

Just shipped GrowthCLI v0.1! 🚀

Terminal-native growth automation for go-to-market engineers.

No more switching between Twitter, Reddit, and HN.
Everything from your terminal. Everything composable.

pip install growth-cli

#buildinpublic #growthhacking
```

### Output Git Log

Every action is a git commit in the output repo:

```
$ cd ~/.config/growth/output && git log --oneline
a3f2c1d post(twitter:myhandle): "Just shipped GrowthCLI v0.1!"
b7e4a2f approve: 2 drafts approved (twitter, reddit)
c9d1b3e draft: cross-post strategy generated 3 drafts
d2f5c4a run(twitter-scout): found 12 trending topics (dry-run)
e1a3d5b init: growth output initialized
```

---

## 9. Strategy System

### Strategy YAML Schema

A strategy is a declarative flow definition. Agents generate content at runtime — the YAML defines the steps, not the text.

```yaml
# strategies/twitter-scout.yaml
name: "Twitter Scout"
description: "Scan AI influencer accounts for trending topics"
version: "1.0"

# What identities this strategy needs
identities:
  scout: { platform: twitter }

# Input parameters (user provides at runtime or uses defaults)
params:
  lookback_hours: { type: int, default: 24 }
  min_likes: { type: int, default: 1000 }
  min_retweets: { type: int, default: 200 }

# Execution steps
steps:
  - id: scan
    type: agent            # "agent" = LLM-powered, "tool" = deterministic
    agent: scout
    as: $scout
    params:
      seed_accounts: "config://twitter.seed_accounts"
      lookback_hours: "{{ params.lookback_hours }}"
      min_likes: "{{ params.min_likes }}"
      min_retweets: "{{ params.min_retweets }}"
    output: trending_topics

  - id: report
    type: tool
    tool: output/save_report
    params:
      data: "{{ scan.trending_topics }}"
      format: markdown
```

```yaml
# strategies/cross-post.yaml
name: "Cross-Post"
description: "Draft an announcement across all connected platforms"
version: "1.0"

identities:
  twitter_account: { platform: twitter, optional: true }
  reddit_account: { platform: reddit, optional: true }
  hn_account: { platform: hn, optional: true }

params:
  topic: { type: str, required: true }
  tone: { type: str, default: "professional", enum: [professional, casual, organic, technical] }
  url: { type: str, required: false }

steps:
  - id: generate_twitter
    type: agent
    agent: copywriter
    when: "$twitter_account exists"
    params:
      platform: twitter
      topic: "{{ params.topic }}"
      tone: "{{ params.tone }}"
      url: "{{ params.url }}"
      constraints: "280 char limit, include hashtags"
    output: twitter_draft

  - id: generate_reddit
    type: agent
    agent: copywriter
    when: "$reddit_account exists"
    params:
      platform: reddit
      topic: "{{ params.topic }}"
      tone: organic       # Always organic on Reddit
      url: "{{ params.url }}"
      constraints: "Story-style, no self-promotion language"
    output: reddit_draft

  - id: generate_hn
    type: agent
    agent: copywriter
    when: "$hn_account exists"
    params:
      platform: hn
      topic: "{{ params.topic }}"
      tone: technical
      url: "{{ params.url }}"
      constraints: "Show HN format if original work, clean title"
    output: hn_draft

  - id: stage_drafts
    type: tool
    tool: output/stage_drafts
    params:
      drafts:
        - "{{ generate_twitter.twitter_draft }}"
        - "{{ generate_reddit.reddit_draft }}"
        - "{{ generate_hn.hn_draft }}"
```

### Strategy Variables

The `{{ }}` references are for **data flow between steps** (passing output from one step to the next) and **parameter injection** (user-provided values). They are NOT content templates.

All actual content (tweet text, Reddit post body, HN title) is generated by agents at runtime, based on the parameters. Different users running the same strategy get different content.

### Creating Custom Strategies

Users can:
1. Copy and modify built-in strategies: `cp strategies/cross-post.yaml my-strategy.yaml`
2. Have Claude Code generate one: "Create a strategy that scouts Twitter and posts summaries to HN"
3. Build from scratch following the schema

New strategies are just YAML files. They're composable because each step is modular.

---

## 10. Onboarding Flow

### Inside Claude Code (Primary — gstack-style)

User pastes one prompt into Claude Code:

```
Install growth-cli: run `pip install growth-cli && growth init`
then help me connect my social media accounts step by step.
After setup, show me available strategies and do a dry-run.
```

Claude Code handles everything:
1. Installs the package
2. Runs `growth init`
3. Asks which platforms to connect
4. Runs `growth auth <platform>` for each (opens browser when needed)
5. Shows the burner account warning
6. Lists built-in strategies
7. Runs a dry-run of one strategy

### Direct CLI (Alternative)

```bash
pip install growth-cli
growth init
growth auth twitter      # Terminal prompts for username/email/password
growth auth reddit       # Opens Chrome for manual login
growth auth hn           # Opens Chrome for manual login
growth status            # Verify everything is connected
growth run twitter-scout --dry-run   # Test it out
```

### Burner Account Warning

Displayed during onboarding and in README:

```
⚠️  ACCOUNT SAFETY NOTICE

growth-cli automates actions on your social media accounts.
Built-in rate limits protect your accounts, but platform detection
is always a risk with any automation tool.

RECOMMENDATION: Use dedicated/burner accounts, not your
personal accounts, for automated posting and engagement.

Future: growth-cli will offer pre-warmed accounts for purchase
so you don't need to risk any of your own.
```

### Demo Mode

For users who want to explore without connecting real accounts:

```bash
$ growth demo
  Starting demo mode...
  
  Demo identities loaded:
    twitter:demo_user    (simulated)
    reddit:demo_user     (simulated)
    hn:demo_user         (simulated)
  
  Try any command — nothing will actually be posted:
    growth twitter post --as demo_user "Hello world!"
    growth run twitter-scout --dry-run
    growth draft "Announce my product"
```

---

## 11. CLI Commands

### Command Tree

```
growth
├── init                               # Initialize config directory
├── auth <platform>                    # Connect a platform account
│   └── twitter | reddit | hn
├── status                             # Show connected accounts + health
│
├── twitter                            # Twitter direct commands
│   ├── post --as <id> <text>          # Post a tweet
│   ├── like --as <id> <tweet_id>      # Like a tweet
│   ├── reply --as <id> <tweet_id>     # Reply to a tweet
│   ├── retweet --as <id> <tweet_id>   # Retweet
│   ├── search <query>                 # Search tweets
│   └── user-tweets <username>         # Get user's recent tweets
│
├── reddit                             # Reddit direct commands
│   ├── submit --as <id> --sub <sub>   # Submit a post
│   ├── comment --as <id> <post_id>    # Comment on a post
│   ├── search <query>                 # Search Reddit
│   └── upvote --as <id> <post_id>     # Upvote a post
│
├── hn                                 # HN direct commands
│   ├── submit --as <id> --title --url # Submit to HN
│   ├── comment --as <id> <item_id>    # Comment on HN
│   ├── search <query>                 # Search via Algolia
│   └── top                            # Show current top stories
│
├── draft <description>                # Generate content drafts (agent-powered)
├── review                             # Review pending drafts
├── approve [--all | --id <draft_id>]  # Approve drafts for posting
├── reject [--id <draft_id>]           # Reject a draft
│
├── run <strategy> [--dry-run]         # Execute a strategy
├── run --list                         # List available strategies
│
├── log                                # Show recent activity
├── traction [run_id]                  # Check engagement on posted content
│
├── migrate from-openclaw              # Import from existing pipeline
│
└── demo                               # Demo mode (simulated accounts)
```

### Common Flags

| Flag | Description | Available On |
|------|-------------|-------------|
| `--as <identity>` | Which account to use | All action commands |
| `--dry-run` | Show what would happen without doing it | All action commands, `run` |
| `--force` | Override rate limits (with warning) | All action commands |
| `--json` | Output in JSON format (for agent consumption) | All commands |
| `-v, --verbose` | Verbose logging | All commands |

---

## 12. Safety & Guardrails

### Pre-Post Safety Checks

Every post goes through these checks before being sent:

| Check | Method | v0.1 | Required? |
|-------|--------|------|-----------|
| **Rate limit** | Deterministic counter | ✅ Yes | **Required** (cannot be bypassed) |
| **Duplicate content** | Fuzzy match vs recent posts | ✅ Yes | Required |
| **Spam detection** | LLM classification | ✅ Yes | Advisory (warn but allow) |
| **Platform TOS** | Rule-based keyword/pattern check | ✅ Yes | Advisory |

### The `--force` Escape Hatch

```bash
$ growth twitter post --as myhandle "Hello" --force
  
  ⚠️  FORCE OVERRIDE ACTIVE
  
  You are bypassing the following safety checks:
    - Rate limit: cooldown has 2m 30s remaining
  
  This increases the risk of account suspension.
  growth-cli is NOT responsible for accounts banned while using --force.
  
  Continue? [y/N]
```

`--force` can override rate limits and advisory checks. It can NEVER override:
- Required checks (duplicate detection)
- Account health blocks (suspended/expired accounts)

---

## 13. Agent Integration

### SKILL.md (for Claude Code Discovery)

```markdown
---
name: growth-cli
description: |
  Terminal-native marketing automation. Post to Twitter, Reddit, and HN.
  Scout trends, draft content, run multi-platform strategies.
  Use when asked to help with social media, content marketing,
  go-to-market, or growth engineering tasks.
allowed-tools:
  - Bash
  - Read
  - Write
---

## Available Commands

- `growth status` — check connected accounts
- `growth twitter post --as <id> "text"` — post a tweet
- `growth reddit submit --as <id> --sub <subreddit> --title "..." --body "..."` — post to Reddit
- `growth hn submit --as <id> --title "..." --url "..."` — submit to HN
- `growth draft "description"` — generate content drafts
- `growth review` — review pending drafts
- `growth approve --all` — approve and post all drafts
- `growth run <strategy> [--dry-run]` — run a strategy
- `growth run --list` — list available strategies

## Tips

- Always use `--dry-run` first to preview actions
- Use `--json` flag for structured output
- Check `growth status` before running strategies
- See `growth run --list` for available strategies
```

### JSON Output Mode

All commands support `--json` for agent consumption:

```bash
$ growth twitter post --as myhandle "Hello" --json
{
  "success": true,
  "platform": "twitter",
  "identity": "twitter:myhandle",
  "post_id": "18294...",
  "url": "https://x.com/myhandle/status/18294...",
  "safety_checks": {
    "rate_limit": "pass",
    "spam": "pass",
    "tos": "pass",
    "duplicate": "pass"
  }
}
```

---

## 14. Migration from Existing Pipeline

### What Gets Migrated

```bash
$ growth migrate from-openclaw

Scanning ~/.openclaw-growth-pipeline/...

Found credentials:
  ✓ Twitter cookies: ~/.openclaw-growth-pipeline/secrets/twitter_cookies.json
  ✓ Reddit session:  ~/.openclaw-growth-pipeline/secrets/reddit_session/storage_state.json
  ✓ HN cookies:      ~/.openclaw-growth-pipeline/secrets/hn_session/hn_cookie.json

Migrating to ~/.config/growth/identities/...
  ✓ twitter:scout_account → cookies copied
  ✓ reddit:promoter_account → session copied
  ✓ hn:main_account → cookie copied

Running health checks...
  ✓ twitter:scout_account — cookies valid
  ✓ reddit:promoter_account — session valid
  ✓ hn:main_account — cookie valid

Migration complete! Your existing sessions are preserved.
No re-authentication needed.

Run 'growth status' to verify.
```

### Code Migration Map

The existing pipeline code is restructured but the logic is preserved:

| What | From | To | Changes |
|------|------|-----|---------|
| Twitter client | `twikit_client.py` | `platforms/twitter/client.py` | Remove claude_code_sdk dependency, add Platform interface |
| Reddit client | `playwright_reddit_client.py` | `platforms/reddit/client.py` | Same pattern, update config paths |
| HN client | `playwright_hn_client.py` (personal fork) | `platforms/hn/client.py` | Same pattern, update config paths |
| Runner | `runner.py` | `engine/runner.py` | Add strategy YAML input, keep retry logic |
| State | `state.py` | `engine/state.py` | Generalize from pipeline-specific to strategy-generic |
| Scout agent | `agents/twitter_scout.py` | `agents/scout.py` | Keep logic, update imports |

### The Two Existing Strategies

Your current pipeline has two routes that become the first built-in strategies:

| Current | New Strategy |
|---------|-------------|
| Route 1: Scout → Novelty → Build → Test → Promote (Reddit) | `strategies/github-growth.yaml` (advanced, uses all agents) |
| Route 2: Scout → Curate → Submit (HN) | `strategies/hn-submit.yaml` (simpler, scout + submit) |

---

## 15. Roadmap

```
═══════════════════════════════════════════════════════════════════

v0.1 — "Marketing from your terminal"                    Weeks 1-3
─────────────────────────────────────────────
  Single user, own accounts, CLI works, built-in strategies
  
  ☐ Project scaffold (pyproject.toml, CLI, config)
  ☐ Platform clients migrated (Twitter, Reddit, HN)
  ☐ Platform base interface
  ☐ Identity manager (single account per platform)
  ☐ Auth flow per platform (terminal + browser)
  ☐ Rate limiter (per-account, always on, conservative defaults)
  ☐ Basic safety checks (duplicate, spam, TOS)
  ☐ Output git repo (auto-commit every action)
  ☐ Draft → Review → Approve → Post workflow
  ☐ Strategy YAML loader + sequential runner
  ☐ Built-in strategies (twitter-scout, hn-submit, cross-post)
  ☐ Direct CLI commands (growth twitter post, etc.)
  ☐ Migration script (from-openclaw)
  ☐ Demo mode
  ☐ SKILL.md + AGENTS.md
  ☐ README ("Claude Code for marketers")
  ☐ Burner account warning
  ☐ --dry-run on everything
  ☐ --json output mode
  ☒ Traction tracker (`growth traction`)
      ☒ Fetch live engagement from Twitter (likes, RTs, replies, views)
      ☒ Fetch live engagement from Reddit (score, comments, upvote ratio)
      ☒ Fetch live engagement from HN (points, comments)
      ☒ Snapshots saved to output repo for historical tracking
      ☒ SKILL.md integration for AI-powered traction analysis

v0.2 — "Multi-account & protection"                      Weeks 4-6
───────────────────────────────────────────
  Multiple accounts per platform, advanced rate limiting
  
  ☐ Multi-identity support (N accounts per platform)
  ☐ Identity roles (brand, organic, supporter, scout)
  ☐ Rate Limit Coordinator (5 layers):
      ☐ Layer 1: Per-account limits
      ☐ Layer 2: Per-IP limits
      ☐ Layer 3: Per-platform global limits
      ☐ Layer 4: Behavioral jitter/randomization
      ☐ Layer 5: Cross-platform correlation prevention
  ☐ BYOP proxy support (SOCKS5/HTTP per identity)
  ☐ Sticky IP assignment
  ☐ Ban detection & identity status (healthy/warning/suspended)
  ☐ Auto-rotate to backup identity on failure
  ☐ IP quarantine logic
  ☐ Strategy: DAG execution (parallel steps)
  ☐ Strategy: Delay scheduling with jitter
  ☐ Strategy: Identity role-based resolution
  ☐ Strategy: Graceful degradation (missing accounts → prompt)
  ☐ --as flag supports roles: --as supporter (picks from pool)

v0.3 — "Intelligence & chat"                             Weeks 7-9
──────────────────────────────────────
  Natural language interface, content generation, social listening
  
  ☐ Chat TUI mode (growth chat)
  ☐ NL → strategy planning agent
  ☐ Content generation (--generate flag)
  ☐ Platform-native tone adaptation
  ☐ Social listening tools (eyes):
      ☐ Twitter trend monitoring (from scout)
      ☐ Reddit subreddit monitoring
      ☐ HN front page monitoring
  ☐ Traction historical trends + comparison across runs
  ☐ Engagement alerts (webhook/CLI notification)
  ☐ Traction-triggered strategies ("score > 50 → amplify")
  ☐ Migrate remaining agents (novelty, builder, tester, promoter)
  ☐ More built-in strategies (5-10 total)

v0.4 — "Growth Cloud"                                    Weeks 10-14
───────────────────────────
  Monetization: sell pre-warmed accounts + IPs (one-time purchase)
  
  ☐ Supabase backend (users, inventory, payments)
  ☐ growth cloud shop (browse available accounts/IPs)
  ☐ growth cloud buy (purchase → Stripe checkout)
  ☐ growth cloud redeem (download + auto-configure identity)
  ☐ Account tiers: Fresh / Warmed / Aged / Premium
  ☐ IP bundles: Residential / Datacenter
  ☐ One-time purchase model (no rental, no ongoing risk)
  ☐ Purchased identities auto-integrate with local config

v0.5 — "GitHub integration"                              Weeks 15-17
──────────────────────────────
  Optional GitHub PR workflow for content review
  
  ☐ growth draft → git branch + PR (optional)
  ☐ Safety checks as GitHub Actions CI
  ☐ Team review via GitHub UI
  ☐ Merge → auto-post webhook
  ☐ Content history browsable on GitHub

v1.0 — "Public launch"                                   Weeks 18-20
─────────────────────────
  ☐ Documentation polish
  ☐ Video demo / walkthrough
  ☐ Landing page + pricing
  ☐ Launch campaign (dogfooding growth-cli to launch growth-cli)
  ☐ BSL license setup

v2.0 — "Ecosystem" (future)
────────────────────────────
  ☐ Plugin system for new platforms (LinkedIn, Instagram, TikTok...)
  ☐ Strategy marketplace (share/fork strategies)
  ☐ Team features (shared identity pools, RBAC)
  ☐ Web analytics dashboard
  ☐ Scheduled/cron strategies
  ☐ Event-driven triggers ("HN score > 50 → amplify")
  ☐ Account warming automation

v3.0 — "Autonomous growth agent" (future)
──────────────────────────────────────────
  ☐ Self-optimizing strategies (A/B test content, adjust timing)
  ☐ LLM memory integration (learn what works across runs)
  ☐ Continuous monitoring + autonomous response
  ☐ Agency mode (multi-client)

═══════════════════════════════════════════════════════════════════
```

---

## 16. Open Questions

These are decisions deferred for later or needing further discussion:

| # | Question | Status | Notes |
|---|----------|--------|-------|
| 1 | **Pricing for managed accounts** | Deferred to v0.4 | One-time purchase, tiers by account age |
| 2 | **Content safety: LLM provider for checks** | v0.1 decision | Use Claude SDK (same as agents) or cheaper model? |
| 3 | **Strategy marketplace design** | Deferred to v2.0 | How are strategies shared? GitHub? Registry? |
| 4 | **Team RBAC model** | Deferred to v2.0 | Who can use which accounts? |
| 5 | **Account warming pipeline** | Deferred to v2.0 | How are accounts provisioned and warmed? |
| 6 | **CLI command name** | ✅ Confirmed | `growth` |
| 7 | **Repo name** | ✅ Confirmed | `serenakeyitan/growth-cli` |

---

*End of Design Specification*
