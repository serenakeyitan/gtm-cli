"""Agent: Engagement Loop — monitor live launch posts and triage comments.

Driven by the user (or a cron) — pass in the list of live posts to watch
and the agent returns a digest with classified comments + draft replies.
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
from gtm.platforms.reddit.tools import (
    reddit_browser_check_post,
    reddit_browser_submit,
)
from gtm.platforms.twitter.browser_tools import (
    twitter_browser_check_tweet,
    twitter_browser_reply,
)

log = logging.getLogger(__name__)


async def run_engagement_loop(
    posts: list[dict[str, Any]],
    config: Any,
    *,
    draft_only: bool = True,
    activity_logger: ActivityLogger | None = None,
) -> dict[str, Any]:
    """Triage comments on a set of live posts.

    Args:
        posts: list of {platform, url, id, title, identity}.
        draft_only: if True, do not auto-post; just emit drafts.
    """
    system_prompt = load_prompt("engagement_loop")

    posts_json = json.dumps(posts, indent=2)
    mode = "DRAFT ONLY — do not post replies" if draft_only else (
        "AUTO MODE — only auto-post for buy_signal bucket; everything else stays draft"
    )

    prompt = (
        f"Triage comments on these live posts.\n\n"
        f"Posts:\n{posts_json}\n\n"
        f"Mode: {mode}\n\n"
        f"For each post: fetch latest status, list new comments since last check, "
        f"classify each into one of the 5 buckets, draft a reply where appropriate. "
        f"Return the digest JSON specified in the system prompt."
    )

    server = create_sdk_mcp_server(
        "engagement-tools",
        tools=[
            reddit_browser_check_post,
            reddit_browser_submit,
            twitter_browser_check_tweet,
            twitter_browser_reply,
            read_run_state,
            write_phase_output,
        ],
    )

    options = ClaudeAgentOptions(
        model=getattr(config.models, "engagement_loop", config.models.promoter),
        system_prompt=system_prompt,
        mcp_servers={"engagement": server},
        allowed_tools=["WebFetch"],
        max_turns=40,
        permission_mode="bypassPermissions",
    )

    result_text = await run_tracked_agent(
        agent_name="engagement_loop",
        options=options,
        prompt=prompt,
        logger=activity_logger,
    )

    return validate_build_output(extract_json_from_result(result_text))
