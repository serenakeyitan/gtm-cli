# Plan: Reshape gtm-cli into a Claude-Code-shaped product

**Status:** drafted 2026-05-05, revised same day for agentic + markdown-first constraints.
**Premise:** the product thesis is "the agent is the marketer." The agent's intelligence lives in **markdown skills** that read context and choose tools. Code is reserved for things markdown genuinely can't do: platform API calls, auth, rate limiting, dry-run semantics, parallel execution.

This plan is **additive and back-compatible.** It does not block any of the 10 in-flight launch/preflight PRs (#5–#14). It exposes structure that already exists (`Module` ABC, `prompts/` markdown library) and reframes how marketers interact with it.

---

## Two design rules

### Rule 1: Agentic, not scripted

The agent decides the sequence. Skills (markdown) tell it *how to think*; tools (Python) give it *what to act with*. The current YAML DAG model — where a human writes the exact steps in advance — is the opposite of agentic. It moves to legacy.

### Rule 2: Markdown over TypeScript / Python when MD is enough

If a behavior can be expressed as a markdown instruction the agent reads at runtime, it does not need a Python wrapper. We already have `prompts/style_guide.md`, `prompts/twitter_scout.md`, etc. — proof that markdown does real work in this repo. We extend that pattern instead of fighting it.

**Litmus test:** "Could a competent marketer-agent do this correctly given a 200-line markdown brief and the existing platform tools?" If yes → it's a skill, not code.

---

## Architecture decision: SDK-first, agent-driven, markdown-thick

Three options were considered:

- **A. CLI-first, skills wrap CLI.** Skills are markdown that tells the agent which `gtm ...` commands to chain. *Rejected:* the agent degrades to subprocess + stdout parsing, throwing away the typed `ModuleResult` semantics this repo already paid to build.
- **B. SDK-first, CLI and MCP both wrap the SDK, plus a thick markdown skill library.** The Module registry is the SDK; the MCP server exposes it as typed tools; the CLI is one consumer; skills (`SKILL.md` + per-task playbooks in `skills/`) are the agent's instruction set. *Selected.*
- **C. MCP-only, kill the CLI.** *Rejected:* loses `gtm auth twitter` (Playwright cookie capture), scriptability, and 15 PRs of muscle memory.

### Why B is the right shape

The SDK seam already exists in `gtm/modules/base.py` (`Module`, `ModuleResult`, `ModuleContext`). The markdown seam already exists in `prompts/`. Today's `gtm/cli.py` (2470 lines) re-implements parameter parsing on top of an interface that's already typed. The work is **(a)** exposing the registry to a second consumer (MCP), **(b)** moving the agent's *judgment* out of Python and into markdown, and **(c)** making the CLI a thin shim.

This matches Claude Code's own design: typed tools (`Read`, `Bash`), markdown skills that orchestrate them, and the model as the runtime that picks which tool to call when.

### What stays, what changes

| Layer | Today | After |
|---|---|---|
| `gtm/modules/` (Module ABC, registry, 30+ modules) | ✅ exists | unchanged — it IS the SDK core |
| `gtm/platforms/` (Twitter/Reddit/HN adapters, auth) | ✅ exists | unchanged |
| `prompts/*.md` (9 files: style guide + agent prompts) | tucked into `prompts/`, used by Python agents | **promoted** to `skills/` — the primary authoring surface |
| `gtm/sdk.py` (top-level `gtm.scrape`, `gtm.post`) | ❌ missing | **new, minimal** — facade over registry, ~150 lines |
| `gtm/mcp_server.py` (MCP tool schemas from registry) | ❌ missing | **new** — second consumer of SDK |
| `gtm/cli.py` (2470 lines mixing parsing + logic) | monolith | **shim:** Click → `gtm.sdk.<verb>()` → pretty-print |
| `SKILL.md` (teaches `gtm ... --dry-run` chains) | bash-recipe doc | **rewritten** as the agent's primary briefing |
| `strategies/*.yaml` (hand-authored DAGs) | primary authoring surface | **deprecated path** — kept runnable, no new ones authored by humans |
| `gtm/engine/dag_runner.py` (348 lines, topo-sort + parallel) | core | **legacy** — still callable, but not the recommended path |
| `gtm/modules/agents/*.py` (scout, novelty, promoters — wrappers around prompts) | Python files invoking LLM with the prompts | **collapsed into skills** — the prompts BECOME the skills |

---

## Tool surface: keep it small, let the skill do the thinking

**Reject the "six coarse verbs as Python `Module` subclasses" idea from the previous draft.** Adding `scrape`, `post`, `listen` as new Python modules is exactly the kind of TS/Python wrapper-around-prompt that Rule 2 forbids. The platform-routing logic ("for Twitter use `twitter/search`, for Reddit use `reddit/search`") belongs in a markdown skill the agent reads, not in a `ScrapeModule.run()` dispatch table.

### What the agent sees via MCP

Just the existing fine-grained registry, exposed as typed tools:

- **Sources** (5): `twitter/search`, `twitter/user_tweets`, `reddit/search`, `hn/search`, `hn/top_stories`
- **Filters** (4 registered): `filter/engagement`, `filter/keyword`, `filter/deduplicate`, `filter/limit`. (`identity_affinity.py` exists but is not yet imported in `gtm/modules/filters/__init__.py` — wire-up is a one-line PR if needed.)
- **Transforms** (4): `transform/rewrite`, `transform/extract_url`, `transform/platform_adapt`, `transform/summarize`
- **Actions** (5): `twitter/post`, `twitter/like`, `twitter/retweet`, `reddit/submit`, `hn/submit_link`. (`twitter/like` and `twitter/retweet` are separate Module subclasses living in `gtm/modules/actions/twitter_engage.py`.)
- **Monitors** (1): `track/engagement`

That's **19 platform/data tools**. Plus 4 control modules (`control/delay`, `control/jitter`, `control/for_each`, `control/condition`) and 1 LLM ranker (`agent/synthesize`) the agent will also call directly. Plus 7 legacy `agent/*` and 11 `strategy/*` modules, which are *callable* via the SDK but **the agent should not pick** — they're the prompt-wrapping layer Phase 5 deletes.

Each module has a typed schema generated from `Module.param_schema`. No new "verb" wrappers. The agent picks the right primitive based on what its skill tells it.

### What lives in markdown (skills)

This is where the product's intelligence goes. New top-level `skills/` directory:

```
skills/
├── README.md                    Index — when to use which skill
├── voice/
│   ├── reddit-organic.md        Reddit voice rules (was prompts/style_guide.md, split)
│   ├── hn-technical.md          HN guidelines
│   └── twitter-engagement.md    Twitter tone
├── workflows/
│   ├── show-hn-launch.md        End-to-end Show HN playbook
│   ├── reddit-organic-seed.md   Multi-account Reddit seeding
│   ├── cross-platform-scout.md  Scout HN+Reddit+Twitter, synthesize
│   ├── traction-watch.md        Engagement monitoring + amplification triggers
│   └── post-mortem.md           After a launch: what worked, what didn't
├── decisions/
│   ├── which-platform.md        Decision tree: where should this go first?
│   ├── when-to-amplify.md       When does a post deserve supporter accounts?
│   └── safety-checks.md         Pre-post checks (duplicate, rate, voice match)
└── reference/
    └── platform-quirks.md       The "gotchas" learned from real removals
```

Every skill is markdown the agent reads at task time. Skills are **forkable** — a user can drop their own variant into `~/.config/gtm/skills/` and the agent picks it up. Skills are **versioned in git** alongside campaigns.

This subsumes the `prompts/` directory: `prompts/twitter_scout.md` becomes `skills/workflows/twitter-scout.md`, etc. The current Python "agents" (`gtm/modules/agents/scout.py`, 64 lines) that just wrap a prompt with `query()` get **deleted** — the agent reads the skill directly via MCP.

---

## YAML DAGs: kept runnable, deprecated as authoring surface

The `dag_runner` (348 lines, real value: topo-sort + parallel exec) stays. The 8 example YAMLs in `strategies/examples/` stay. But:

- **No new strategy YAMLs are authored by humans.**
- Markdown skills are the new authoring surface.
- If the agent decides reproducibility matters (e.g., "rerun this exact launch sequence next month"), it can *emit* a YAML into `campaigns/<name>/strategies/<slug>.yaml` as an artifact. Reading is fine; humans don't write them.
- The `dag_runner` is exposed via MCP as `run_strategy(path)` for those agent-emitted artifacts.

This is "demoted, not deleted." It's the right level of legacy.

---

## Campaign folder = source of truth (already in flight)

The 10 launch/post/dashboard PRs (#5–#14) are already building the campaign-folder convention: `.gtm-launch.yaml`, `posts/<slug>.md` with frontmatter, `tracking.md` generated by `gtm post sync`, `dashboard.html` generated by `gtm dashboard build`.

This plan **endorses that direction without changing it.** Skills reference the campaign folder as the agent's working memory. Posts are markdown files (already are). Tracking is markdown (already is). Git history IS the campaign history.

After PRs #5–#14 land, the campaign folder is already what we want. The SDK + MCP server expose its operations to the agent as typed tools; skills tell the agent how to use them.

---

## Migration sequence

The PR stack stays sacred. The work is split across phases that don't block each other.

### Phase 0 — finish in-flight (no work in this plan)

Land PRs #5–#14 (launch CP1–CP8 + preflight CP9/CP10 stacks). All additive on the CLI surface; none touches `gtm/modules/`, `gtm/engine/`, or `gtm/platforms/`.

Out-of-tree commits on `feat/cp10-preflight-submit-gate` (`gtm reddit prefill` / `engagement` / `promote`, 5 commits ahead of PR #14) need their own PR after #14 merges.

### Phase 1 — extract the SDK (1 PR, ~150 lines new code)

**Branch:** `feat/sdk-extract` off `main` after #14.

- New `gtm/sdk.py`: thin async functions over `registry.get(name).run(...)`. No coarse verbs. Just `run_module(name, params, context)` and `run_strategy(path)`.
- `gtm/__init__.py` exports the SDK surface.
- Tests in `tests/test_sdk.py`: one happy-path per public function.
- Zero changes to CLI, modules, engine, platforms.

**Acceptance:** `python -c "import asyncio, gtm; print(asyncio.run(gtm.run_module('hn/top_stories', {'count': 3}, ctx)))"` returns a `ModuleResult`.

### Phase 2 — MCP server (1 PR)

**Branch:** `feat/mcp-server` off `main` after Phase 1.

- New `gtm/mcp_server.py`: stdio MCP server that enumerates `registry.list_all()`, generates a tool schema per module from `Module.param_schema`, dispatches `tools/call` to `gtm.sdk.run_module(...)`.
- New CLI command `gtm mcp serve` (10 lines).
- Optional dep `mcp` in `pyproject.toml`.
- Doc at `docs/mcp-quickstart.md`: how to register `gtm-cli` as an MCP server in a Claude Code project.

**Acceptance:** with the server registered, the agent can call `twitter/search({query: "AI"})` and receive structured JSON. End-to-end: agent drafts a Reddit post → calls `reddit/submit({..., dry_run: true})` → reads preflight result → calls again without `dry_run`.

### Phase 3 — skills library (1 PR, all markdown)

**Branch:** `feat/skills-library` off `main` after Phase 2. **No Python in this PR.**

- Create `skills/` directory with the structure above.
- Migrate `prompts/style_guide.md` → split into `skills/voice/{reddit-organic,hn-technical,twitter-engagement}.md`.
- Migrate `prompts/twitter_scout.md`, `promoter.md`, `hn_promoter.md`, etc. → `skills/workflows/*.md`. Rewrite each so it instructs the *agent* (not a Python harness) which MCP tools to call in what order.
- Write `skills/decisions/which-platform.md`, `when-to-amplify.md`, `safety-checks.md` from scratch — these are the judgment calls the current code lacks.
- Write `skills/README.md` as the index. The agent reads this first to decide which skill to load for a task.
- Keep `prompts/` directory working (the Python agents still reference it) — it's deprecated but not deleted.

**Acceptance:** a fresh Claude Code session, given the MCP server (Phase 2) + the skills library, completes a "draft and dry-run a Reddit launch post" task end-to-end without `Bash`. The work is done by the agent reading skills + calling MCP tools, not by Python orchestration.

### Phase 4 — rewrite SKILL.md (1 PR, all markdown)

**Branch:** `docs/skill-mcp-shape` off `main` after Phase 3.

- Rewrite top-level `SKILL.md` as the agent's primary briefing: how to install the MCP server, how to discover skills via `skills/README.md`, the platform safety rules, the rate-limit contract.
- Drop all bash-recipe examples.
- Rewrite `AGENTS.md` — keep the "direct API first, LLM last" principle (still correct), but reframe: the *deterministic* path is fine-grained tools called from skills; the *LLM* path is the agent itself reasoning, not `agent/scout`-style 175-call loops.

**Acceptance:** new Claude Code session, given only `SKILL.md`, completes the v0.1 showcase ("search HN, draft a Reddit post in our voice, dry-run it") via MCP + skills.

### Phase 5 — collapse the Python agents (1 PR)

**Branch:** `refactor/delete-py-agents` off `main` after Phase 4.

- Delete `gtm/modules/agents/scout.py`, `novelty_check.py`, `promote_reddit.py`, `promote_hn.py`, `build.py`, `test.py` — the prompt-wrapping layer. Their behavior is now in `skills/workflows/*.md` and executed by the agent itself.
- Keep `gtm/modules/agents/synthesize.py` (123 lines — does real work: filtering+ranking via 1 LLM call with a deterministic fallback). This is the kind of thing markdown can't do well.
- Keep `gtm/modules/agents/strategy_module.py` (registers strategy YAMLs as modules — needed for the runnable-but-deprecated DAG path).
- Update `prompts/` → `skills/` cross-references. Delete duplicates.

**Acceptance:** `pytest tests/` passes. The capabilities the deleted Python agents provided are now achievable through `skills/workflows/*.md` + MCP tools.

### Phase 6 — collapse `cli.py` (1 PR, mechanical)

**Branch:** `refactor/cli-thin-shims` off `main` after Phase 5.

- Each Click handler becomes 3–5 lines: parse args, await `gtm.sdk.run_module(...)`, pretty-print `ModuleResult`.
- Target: `cli.py` shrinks 2470 → ~800 lines.
- No behavior change.

**Acceptance:** all existing CLI commands behave identically. `pytest tests/` passes.

---

## What this plan does NOT do

- **Does not change `gtm/modules/` internals.** Module authors keep the existing contract.
- **Does not delete `gtm/engine/dag_runner.py`.** Demoted, not removed.
- **Does not touch in-flight PRs.** Phase 0 lands them as-is.
- **Does not deprecate the CLI.** Stays a first-class consumer for non-Claude users.
- **Does not add new Python "verb" wrappers** (`ScrapeModule`, `PostModule`, etc.). Verbs live in markdown skills; primitives live in the existing fine-grained modules.
- **Does not add a TUI, web UI, or `gtm chat`.** Claude Code is the UI.
- **Does not invent new infrastructure for skill discovery.** Filesystem + a `skills/README.md` index is enough; if we need more later, we add it.

## Open questions (flagged, not blocking)

1. **Skill discovery contract.** Does the agent read `skills/README.md` first and decide what to load, or does the MCP server expose a `list_skills` / `read_skill` tool? Lean: filesystem-only at first, since Claude Code can already `Read` markdown files. Add a tool only if we need it.
2. **MCP transport.** stdio (local-only) vs HTTP (Growth Cloud roadmap)? Phase 2 starts stdio.
3. **Auth via MCP.** `gtm auth twitter` shells into Playwright. Lean: stay CLI-only — auth is a one-time human action, not something the agent should drive.
4. **User-forked skills location.** `~/.config/gtm/skills/`? `<repo>/.gtm/skills/`? Both? Lean: both, with project-local taking precedence (matches Claude Code's settings model).

## Success criteria

After Phase 4:

- A marketer in a Claude Code session, with the gtm-cli MCP server registered and skills library available, runs a full Show HN + Reddit + Twitter launch by talking to the agent. They never type a `gtm` command. They never write a YAML. The agent reads `skills/workflows/show-hn-launch.md`, calls typed MCP tools, drafts content into the campaign folder, dry-runs, gets approval, posts, and reports traction.
- A scripter outside Claude Code runs the same workflow via `gtm` CLI commands. The CLI is unchanged.
- A power user opens `skills/workflows/show-hn-launch.md` and reads exactly how the agent decides what to do — and forks it.

That's the agentic, markdown-thick, Claude-Code-shaped product.
