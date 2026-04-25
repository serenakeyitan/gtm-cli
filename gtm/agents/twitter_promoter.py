"""Agent: Twitter Promoter — post a launch thread for an idea+build on X.

Mirrors the structure of gtm/agents/promoter.py (Reddit) but targets Twitter.
Routes through IdentityManager via `identity` param.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, create_sdk_mcp_server

from gtm.agents.activity_log import ActivityLogger
from gtm.agents.agent_wrapper import run_tracked_agent
from gtm.agents.base import (
    extract_json_from_result,
    load_prompt,
    validate_build_output,
)
from gtm.agents.state_tools import read_run_state, write_phase_output
from gtm.engine.state import RunState
from gtm.platforms.twitter.browser_tools import (
    twitter_browser_check_tweet,
    twitter_browser_post,
    twitter_browser_post_thread,
    twitter_browser_reply,
)

log = logging.getLogger(__name__)


async def run_twitter_promoter(
    state: RunState,
    input_data: Any,
    activity_logger: ActivityLogger | None = None,
) -> dict[str, Any]:
    """Post a launch thread for one idea+build on Twitter."""
    idea = input_data["idea"]
    build = input_data["build"]
    config = input_data["config"]
    identity = input_data.get("identity") or input_data.get("account") or ""

    system_prompt = load_prompt("twitter_promoter")

    idea_json = json.dumps(idea, indent=2)
    build_json = json.dumps(build, indent=2)
    identity_line = f"Identity to post from: {identity}\n\n" if identity else ""

    prompt = (
        f"Launch this open-source project on Twitter as a thread.\n\n"
        f"{identity_line}"
        f"Idea:\n{idea_json}\n\n"
        f"Build result:\n{build_json}\n\n"
        f"Follow the system prompt: lowercase, no em dashes, ICP statement required, "
        f"opener must work standalone with no link.\n\n"
        f"Output a JSON object with: thread (array of {{position, text, tweet_id, url}}), "
        f"opener_url, identity."
    )

    server = create_sdk_mcp_server(
        "twitter-tools",
        tools=[
            twitter_browser_post,
            twitter_browser_post_thread,
            twitter_browser_reply,
            twitter_browser_check_tweet,
            read_run_state,
            write_phase_output,
        ],
    )

    options = ClaudeAgentOptions(
        model=getattr(config.models, "twitter_promoter", config.models.promoter),
        system_prompt=system_prompt,
        mcp_servers={"twitter": server},
        allowed_tools=["WebSearch", "WebFetch"],
        max_turns=30,
        permission_mode="bypassPermissions",
    )

    result_text = await run_tracked_agent(
        agent_name=f"twitter_promoter:{idea.get('id', 'unknown')}",
        options=options,
        prompt=prompt,
        logger=activity_logger,
    )

    result = extract_json_from_result(result_text)
    promo = validate_build_output(result)
    promo.setdefault("idea_id", idea.get("id"))
    if identity and not promo.get("identity"):
        promo["identity"] = identity
    return promo
