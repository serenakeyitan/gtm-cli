"""gtm MCP server — expose the module registry as typed tools to agents.

Phase 2 of the Claude-Code-shaped redesign. The CLI is one consumer of
gtm.sdk; this server is the second. They share the same registry, the
same ModuleResult contract, and the same identity/rate-limit infra.

What the agent sees:
  - Sources (5):   hn_top_stories, hn_search, twitter_search, ...
  - Filters (4):   filter_engagement, filter_keyword, ...
  - Transforms(4): transform_rewrite, transform_platform_adapt, ...
  - Actions (5):   reddit_submit, hn_submit_link, twitter_post, ...
  - Monitors (1):  track_engagement
  - Control (4):   control_delay, control_jitter, ...
  - Agent  (1):    agent_synthesize

Plus two coordination tools:
  - run_strategy(path, params, dry_run)
  - list_modules()

We intentionally exclude the prompt-wrapping legacy modules
(agent/scout, agent/novelty_check, agent/promote_*, agent/build,
agent/test) — those become markdown skills in Phase 3 and are
deleted in Phase 5.

Wire-up:
    gtm mcp serve     # starts a stdio MCP server (CLI Phase 2 commit)

Or programmatically:
    from gtm.mcp_server import build_server
    await build_server().run(...)

See docs/mcp-quickstart.md for client config (Claude Code's
`.mcp.json` etc).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from gtm import sdk

log = logging.getLogger(__name__)


# Categories the agent should reach for. Excludes prompt-wrapping legacy
# `agent/*` (kept synthesize) and `strategy/*` (use run_strategy instead).
_EXPOSED_CATEGORIES = {
    "source",
    "filter",
    "transform",
    "action",
    "monitor",
    "control",
}
_EXPOSED_AGENT_MODULES = {"agent/synthesize"}


# ── Schema conversion ────────────────────────────────────────────────


_TYPE_MAP = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
}


def _param_schema_to_json_schema(param_schema: dict[str, Any]) -> dict[str, Any]:
    """Convert a Module's `param_schema` to a JSON Schema input object.

    Module param_schema shape (custom):
        {param_name: {type: 'str|int|...', required: bool, default: ..., enum: [...]}}

    JSON Schema shape (MCP standard):
        {type: 'object', properties: {...}, required: [...]}
    """
    properties: dict[str, Any] = {}
    required: list[str] = []

    for name, spec in param_schema.items():
        if not isinstance(spec, dict):
            continue
        prop: dict[str, Any] = {}
        py_type = spec.get("type", "str")
        prop["type"] = _TYPE_MAP.get(py_type, "string")
        if "default" in spec and spec["default"] is not None:
            prop["default"] = spec["default"]
        if "enum" in spec:
            prop["enum"] = list(spec["enum"])
        if "description" in spec:
            prop["description"] = spec["description"]
        properties[name] = prop
        if spec.get("required"):
            required.append(name)

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


def _module_to_tool_name(module_name: str) -> str:
    """Convert `twitter/search` → `twitter_search` (MCP-friendly)."""
    return module_name.replace("/", "_").replace("-", "_")


def _tool_to_module_name(tool_name: str, name_index: dict[str, str]) -> str | None:
    """Reverse lookup tool_name → module_name. Returns None if not a module call."""
    return name_index.get(tool_name)


def _module_input_schema(module) -> dict[str, Any]:
    """Build the input schema for a module call.

    Includes the module's params plus three orchestration knobs the agent
    needs to control runs without reaching past the SDK:
      - dry_run: skip destructive side effects
      - identity: which platform identity to use ('twitter' or 'twitter:handle')
      - input: optional structured input from a previous tool's result
    """
    base = _param_schema_to_json_schema(module.param_schema)
    base.setdefault("properties", {})
    base["properties"]["dry_run"] = {
        "type": "boolean",
        "default": False,
        "description": "If true, run without destructive side effects.",
    }
    if module.requires_auth:
        base["properties"]["identity"] = {
            "type": "string",
            "description": (
                "Platform name (e.g. 'twitter') or full identity "
                "('twitter:my_handle'). Defaults to platform's primary identity."
            ),
        }
    base["properties"]["input"] = {
        "type": "object",
        "description": (
            "Optional ModuleResult from an upstream tool — pass through to chain "
            "calls (e.g. scrape → filter). Shape: {success: bool, data: list, ...}."
        ),
    }
    return base


# ── Tool registration ────────────────────────────────────────────────


def _build_tools() -> tuple[list[Tool], dict[str, str]]:
    """Enumerate the registry, return (mcp_tools, tool_name → module_name index)."""
    tools: list[Tool] = []
    index: dict[str, str] = {}

    for mod in sdk.list_modules():
        if mod.category not in _EXPOSED_CATEGORIES and mod.name not in _EXPOSED_AGENT_MODULES:
            continue
        tool_name = _module_to_tool_name(mod.name)
        index[tool_name] = mod.name
        tools.append(
            Tool(
                name=tool_name,
                description=(
                    f"[{mod.category}] {mod.description}"
                    + (f"  (auth: {mod.platform})" if mod.requires_auth else "")
                ),
                inputSchema=_module_input_schema(mod),
            )
        )

    # Coordination tools — not registry modules, but agent-facing.
    tools.append(
        Tool(
            name="list_modules",
            description=(
                "List all available gtm tools, grouped by category. "
                "Useful for discovery; the agent can also see them in its tool list."
            ),
            inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
        )
    )
    tools.append(
        Tool(
            name="run_strategy",
            description=(
                "Run a strategy YAML file as a DAG. Use this only when the agent "
                "wants to materialize a reproducible playbook; for ad-hoc work, "
                "call individual module tools."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to strategy YAML."},
                    "params": {"type": "object", "description": "Strategy params."},
                    "dry_run": {"type": "boolean", "default": False},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        )
    )

    return tools, index


# ── Result serialization ─────────────────────────────────────────────


def _result_to_json(result) -> str:
    """Serialize a ModuleResult to a JSON string the agent can read.

    We always return JSON — agents parse it deterministically.
    """
    payload = {
        "success": bool(result.success),
        "count": result.count,
        "data": result.data,
        "metadata": result.metadata,
    }
    if result.errors:
        payload["errors"] = list(result.errors)
    return json.dumps(payload, indent=2, default=str)


# ── Server ───────────────────────────────────────────────────────────


def build_server() -> Server:
    """Build the MCP server with handlers wired to gtm.sdk.

    Returns the configured Server. Caller runs it via stdio_server() or
    other transport.
    """
    server = Server("gtm-cli")
    tools, name_index = _build_tools()

    @server.list_tools()
    async def _list_tools() -> list[Tool]:
        return tools

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        # Coordination tools first — they don't go through the registry.
        if name == "list_modules":
            mods = sdk.list_modules()
            grouped: dict[str, list[dict[str, str]]] = {}
            for m in mods:
                grouped.setdefault(m.category, []).append(
                    {"name": m.name, "description": m.description}
                )
            return [TextContent(type="text", text=json.dumps(grouped, indent=2))]

        if name == "run_strategy":
            path = arguments["path"]
            params = arguments.get("params") or {}
            dry_run = bool(arguments.get("dry_run", False))
            state = await sdk.run_strategy(path, params, dry_run=dry_run)
            return [TextContent(type="text", text=json.dumps(state, indent=2, default=str))]

        # Module call — translate tool name back to module name.
        module_name = name_index.get(name)
        if not module_name:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

        # Pull orchestration args off the side; rest go to the module as params.
        args = dict(arguments or {})
        dry_run = bool(args.pop("dry_run", False))
        identity = args.pop("identity", None)
        upstream_raw = args.pop("input", None)

        upstream = None
        if isinstance(upstream_raw, dict) and "success" in upstream_raw:
            upstream = sdk.ModuleResult(
                success=bool(upstream_raw.get("success", False)),
                data=list(upstream_raw.get("data", []) or []),
                metadata=dict(upstream_raw.get("metadata", {}) or {}),
                errors=list(upstream_raw.get("errors", []) or []),
            )

        try:
            result = await sdk.run_module(
                module_name,
                args,
                upstream,
                dry_run=dry_run,
                identity=identity,
            )
        except KeyError as e:
            return [TextContent(type="text", text=json.dumps({"error": f"Module not found: {e}"}))]
        except Exception as e:
            log.exception("MCP tool call failed: %s", name)
            return [TextContent(type="text", text=json.dumps({"error": f"{type(e).__name__}: {e}"}))]

        return [TextContent(type="text", text=_result_to_json(result))]

    return server


async def serve_stdio() -> None:
    """Run the server over stdio. Used by `gtm mcp serve`."""
    server = build_server()
    async with stdio_server() as (read, write):
        await server.run(
            read,
            write,
            server.create_initialization_options(),
        )
