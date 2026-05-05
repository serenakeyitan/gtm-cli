# MCP Quickstart — give your agent typed access to gtm

The `gtm` MCP server exposes the module registry as **typed tools** to any
[MCP](https://modelcontextprotocol.io/)-aware agent (Claude Code, Cursor, etc.).
The agent stops parsing `gtm ...` stdout and starts calling tools with
structured inputs and JSON outputs.

This is Phase 2 of the [Claude-Code-shaped redesign](./PLAN-claude-code-shape.md).

## What the agent sees

26 tools exposed over stdio:

| Category | Tools | What |
|---|---|---|
| **Sources** (5) | `hn_top_stories`, `hn_search`, `twitter_search`, `twitter_user_tweets`, `reddit_search` | Pull content from a platform |
| **Filters** (4) | `filter_engagement`, `filter_keyword`, `filter_deduplicate`, `filter_limit` | Process and reduce data |
| **Transforms** (4) | `transform_rewrite`, `transform_extract_url`, `transform_platform_adapt`, `transform_summarize` | Adapt content for a target |
| **Actions** (5) | `reddit_submit`, `hn_submit_link`, `twitter_post`, `twitter_like`, `twitter_retweet` | Mutate platform state |
| **Monitors** (1) | `track_engagement` | Live engagement metrics |
| **Control** (4) | `control_delay`, `control_jitter`, `control_for_each`, `control_condition` | Flow control inside DAG runs |
| **Agent** (1) | `agent_synthesize` | LLM-backed ranking with deterministic fallback |
| **Coord** (2) | `list_modules`, `run_strategy` | Discovery + run a YAML DAG as one call |

Excluded by design:
- `agent_scout`, `agent_novelty_check`, `agent_promote_*`, `agent_build`, `agent_test` — these are prompt-wrapping Python files; their behavior moves into [skills](../skills/) (Phase 3) and the Python is deleted (Phase 5).
- `strategy_*` — runnable via `run_strategy(path)` instead.

## Tool I/O contract

Every module tool accepts:

```json
{
  "<param>": <value>,                   // module's own params
  "dry_run": false,                     // skip destructive side effects
  "identity": "twitter:my_handle",      // optional, only on auth-required tools
  "input": {                            // optional, chain from a previous tool
    "success": true,
    "data": [{"id": 1}, {"id": 2}],
    "metadata": {},
    "errors": []
  }
}
```

Every tool returns **JSON text** with the `ModuleResult` shape:

```json
{
  "success": true,
  "count": 3,
  "data": [...],
  "metadata": {...},
  "errors": []
}
```

## Install

```bash
pip install 'gtm-cli[mcp]'
# or, for development:
uv sync --extra mcp
```

The `mcp` extra pulls in the `mcp` Python package.
(If you're using the `agents` extra it's already there — `claude-agent-sdk` depends on `mcp`.)

## Wire up in Claude Code

Drop this in the project's `.mcp.json`:

```json
{
  "mcpServers": {
    "gtm": {
      "command": "gtm",
      "args": ["mcp", "serve"]
    }
  }
}
```

Restart Claude Code. The agent now has 26 tools prefixed with `mcp__gtm__*`.

To verify, ask the agent:

> Show me the top 3 HN stories about AI agents.

It will call `mcp__gtm__hn_search` with `{"query": "AI agents", "count": 3}` and show structured results — no `gtm hn search ...` shelling.

## Try it manually

The CLI also boots the server directly:

```bash
gtm mcp serve     # blocks; reads MCP frames on stdin, writes on stdout
```

For local testing, use any MCP client. Quick-and-dirty Python:

```python
import asyncio
from gtm.mcp_server import build_server

async def main():
    server = build_server()
    # Iterate the configured tools
    handler = server.request_handlers
    print("tools handler:", handler)

asyncio.run(main())
```

The full server tests in `tests/test_mcp_server.py` show the request/response loop without spinning up a real transport.

## Design notes

- **Schemas are auto-generated** from each module's `param_schema` field. Add a new module and it becomes an MCP tool automatically — no schema duplication.
- **Tool names use `_` not `/`** (e.g. `twitter_search`, not `twitter/search`). Some MCP clients reject `/` in tool names; `_` is universal.
- **Errors come back as JSON, not exceptions.** `{"error": "..."}` lets the agent branch on a key instead of catching stack traces.
- **The CLI and MCP server are peers.** Both consume `gtm.sdk`. There's no "one wraps the other" — they're parallel front ends to the same registry.

## What's next (other phases)

- **Phase 3** — Migrate `prompts/*.md` → `skills/` (voice / workflows / decisions / reference). The agent's *judgment* lives in markdown, not Python.
- **Phase 4** — Rewrite top-level `SKILL.md` to teach the MCP tool surface, drop bash recipes.
- **Phase 5** — Delete the legacy `agent/*` Python files (their work moved into skills).
- **Phase 6** — Collapse `gtm/cli.py` from 2470 lines to ~800 (Click handlers become SDK shims).

See [PLAN-claude-code-shape.md](./PLAN-claude-code-shape.md).
