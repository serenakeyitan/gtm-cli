"""Tests for the gtm MCP server.

Verifies the registry → MCP tool wiring without spinning up a real
stdio transport: we build the server, pull handlers off
`server.request_handlers`, and invoke them directly.
"""

from __future__ import annotations

import json

import pytest
from mcp.types import (
    CallToolRequest,
    CallToolRequestParams,
    ListToolsRequest,
)

from gtm.mcp_server import (
    _build_tools,
    _module_input_schema,
    _module_to_tool_name,
    _param_schema_to_json_schema,
    build_server,
)


# ── Schema conversion ────────────────────────────────────────────────


def test_param_schema_to_json_schema_translates_types():
    src = {
        "count": {"type": "int", "required": True},
        "query": {"type": "str", "default": ""},
        "active": {"type": "bool", "default": True},
        "tags": {"type": "list"},
    }
    js = _param_schema_to_json_schema(src)
    assert js["type"] == "object"
    assert js["additionalProperties"] is False
    assert js["required"] == ["count"]
    assert js["properties"]["count"] == {"type": "integer"}
    assert js["properties"]["query"] == {"type": "string", "default": ""}
    assert js["properties"]["active"] == {"type": "boolean", "default": True}
    assert js["properties"]["tags"] == {"type": "array"}


def test_param_schema_keeps_enum():
    src = {"platform": {"type": "str", "required": True, "enum": ["reddit", "hn"]}}
    js = _param_schema_to_json_schema(src)
    assert js["properties"]["platform"]["enum"] == ["reddit", "hn"]


def test_module_to_tool_name_strips_slashes():
    assert _module_to_tool_name("twitter/search") == "twitter_search"
    assert _module_to_tool_name("filter/engagement") == "filter_engagement"
    assert _module_to_tool_name("control/for_each") == "control_for_each"


def test_module_input_schema_adds_orchestration_knobs():
    """Every tool gets dry_run + input; auth-needing tools get identity."""
    from gtm import get_module

    auth_mod = get_module("reddit/submit")
    schema = _module_input_schema(auth_mod)
    assert "dry_run" in schema["properties"]
    assert "input" in schema["properties"]
    assert "identity" in schema["properties"]

    public_mod = get_module("hn/top_stories")
    schema = _module_input_schema(public_mod)
    assert "dry_run" in schema["properties"]
    assert "input" in schema["properties"]
    assert "identity" not in schema["properties"]  # public source, no auth


# ── Tool list ────────────────────────────────────────────────────────


def test_build_tools_excludes_legacy_agents_and_strategies():
    """Only sources/filters/transforms/actions/monitors/control + agent_synthesize
    + the two coordination tools are exposed.
    """
    tools, index = _build_tools()
    names = {t.name for t in tools}

    # Must have these:
    expected_present = {
        "hn_top_stories", "twitter_search", "reddit_search",  # sources
        "filter_engagement", "filter_limit",  # filters
        "transform_rewrite", "transform_platform_adapt",  # transforms
        "reddit_submit", "twitter_post", "hn_submit_link",  # actions
        "track_engagement",  # monitor
        "control_delay", "control_jitter",  # control
        "agent_synthesize",  # the one keeper
        "list_modules", "run_strategy",  # coordination
    }
    assert expected_present.issubset(names), f"missing: {expected_present - names}"

    # Must NOT have these (legacy, deleted in Phase 5):
    legacy = {"agent_scout", "agent_novelty_check", "agent_promote_reddit",
              "agent_promote_hn", "agent_build", "agent_test"}
    assert legacy.isdisjoint(names), f"leaking legacy: {legacy & names}"

    # No strategy/* either (use run_strategy instead)
    strategy_tools = {n for n in names if n.startswith("strategy_")}
    assert strategy_tools == set(), f"strategy modules exposed: {strategy_tools}"


def test_tool_count_matches_plan():
    """24 module tools + 2 coordination tools = 26 total.

    If this drifts, update the plan or the registry — don't paper over it.
    """
    tools, _ = _build_tools()
    assert len(tools) == 26


# ── End-to-end: list_tools and call_tool through Server handlers ─────


@pytest.mark.asyncio
async def test_list_tools_handler_returns_all_tools():
    server = build_server()
    handler = server.request_handlers[ListToolsRequest]
    req = ListToolsRequest(method="tools/list")
    result = await handler(req)
    # ServerResult wraps a ListToolsResult
    inner = result.root
    assert len(inner.tools) == 26


@pytest.mark.asyncio
async def test_call_tool_passes_input_through_to_module():
    """End-to-end: agent calls filter_limit with upstream data, gets filtered JSON."""
    server = build_server()
    handler = server.request_handlers[CallToolRequest]
    req = CallToolRequest(
        method="tools/call",
        params=CallToolRequestParams(
            name="filter_limit",
            arguments={
                "count": 2,
                "input": {
                    "success": True,
                    "data": [{"id": i} for i in range(5)],
                    "metadata": {},
                    "errors": [],
                },
            },
        ),
    )
    result = await handler(req)
    text = result.root.content[0].text
    parsed = json.loads(text)
    assert parsed["success"] is True
    assert parsed["count"] == 2
    assert [d["id"] for d in parsed["data"]] == [0, 1]


@pytest.mark.asyncio
async def test_call_tool_unknown_returns_json_error_not_exception():
    """Agents should see an `{error: ...}` JSON, not a stack trace.

    This keeps the protocol robust — the agent can branch on `error` key.
    """
    server = build_server()
    handler = server.request_handlers[CallToolRequest]
    req = CallToolRequest(
        method="tools/call",
        params=CallToolRequestParams(name="not_a_real_tool", arguments={}),
    )
    result = await handler(req)
    text = result.root.content[0].text
    parsed = json.loads(text)
    assert "error" in parsed


@pytest.mark.asyncio
async def test_call_tool_list_modules_returns_grouped_catalog():
    server = build_server()
    handler = server.request_handlers[CallToolRequest]
    req = CallToolRequest(
        method="tools/call",
        params=CallToolRequestParams(name="list_modules", arguments={}),
    )
    result = await handler(req)
    text = result.root.content[0].text
    parsed = json.loads(text)
    # Should be grouped by category
    assert "source" in parsed
    assert "filter" in parsed
    assert isinstance(parsed["source"], list)
    assert all("name" in m and "description" in m for m in parsed["source"])
