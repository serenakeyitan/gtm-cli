"""Agent 2: Novelty Checker — filter ideas by checking existing open-source work."""

from __future__ import annotations

import json
import logging
from typing import Any

from claude_code_sdk import (
    ClaudeCodeOptions,
    create_sdk_mcp_server,
)

from gtm.agents.base import (
    extract_json_from_result,
    load_prompt,
    validate_ideas_output,
)
from gtm.agents.agent_wrapper import run_tracked_agent
from gtm.agents.activity_log import ActivityLogger
from gtm.engine.state import RunState
from gtm.agents.github_tools import github_search_repos
from gtm.platforms.twitter.tools import twitter_search
from gtm.agents.state_tools import read_run_state, write_phase_output

log = logging.getLogger(__name__)


async def run_novelty_checker(
    state: RunState,
    input_data: Any,
    activity_logger: ActivityLogger | None = None,
) -> list[dict[str, Any]]:
    """Run the Novelty Checker agent to filter ideas."""
    ideas = input_data["ideas"]
    config = input_data["config"]

    system_prompt = load_prompt("novelty_checker")

    ideas_json = json.dumps(ideas, indent=2)
    prompt = (
        f"Evaluate the following {len(ideas)} ideas for novelty. For each:\n"
        f"1. Search GitHub repos by name, description, topic\n"
        f"2. Search the web for 'open source {{idea}}'\n"
        f"3. Search Twitter for existing project announcements\n\n"
        f"Reject if strong, well-maintained existing projects exist.\n"
        f"Allow if only partial/abandoned implementations exist.\n"
        f"Rank remaining by: novelty × trend_strength × feasibility.\n\n"
        f"Ideas to evaluate:\n{ideas_json}\n\n"
        f"Output: filtered + ranked ideas as a JSON array (same schema as input, "
        f"with an added 'novelty_reasoning' field)."
    )

    server = create_sdk_mcp_server(
        "novelty-tools",
        tools=[github_search_repos, twitter_search, read_run_state, write_phase_output],
    )

    options = ClaudeCodeOptions(
        model=config.models.novelty,
        system_prompt=system_prompt,
        mcp_servers={"novelty": server},
        allowed_tools=["WebSearch", "WebFetch"],
        max_turns=30,
        permission_mode="bypassPermissions",
    )

    result_text = await run_tracked_agent(
        agent_name="novelty",
        options=options,
        prompt=prompt,
        logger=activity_logger,
    )

    validated = extract_json_from_result(result_text)
    return validate_ideas_output(validated)
