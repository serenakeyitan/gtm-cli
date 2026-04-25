"""Agent: HN Promoter — find trending content on Twitter and post to Hacker News.

This is the promoter for Route 2 (Twitter → HN). Unlike the Reddit promoter
which posts self-built projects, the HN promoter curates interesting content
from Twitter and submits the original source links to HN.

Flow:
1. Receive trending content from Twitter Scout
2. For each item, find the original source URL (not the tweet)
3. Check if already submitted to HN (dedup via Algolia)
4. Submit the best candidates with clean titles
5. Monitor performance
"""

from __future__ import annotations

import json
import logging
from typing import Any

from claude_agent_sdk import (
    ClaudeAgentOptions,
    create_sdk_mcp_server,
)

from gtm.agents.base import (
    extract_json_from_result,
    load_prompt,
    validate_build_output,
)
from gtm.agents.agent_wrapper import run_tracked_agent
from gtm.agents.activity_log import ActivityLogger
from gtm.engine.state import RunState
from gtm.platforms.hn.tools import (
    hn_search,
    hn_check_duplicate,
    hn_submit_link,
    hn_submit_text,
    hn_check_item,
    hn_top_stories,
    hn_user_profile,
)
from gtm.agents.state_tools import read_run_state, write_phase_output

log = logging.getLogger(__name__)


async def run_hn_promoter(
    state: RunState,
    input_data: Any,
    activity_logger: ActivityLogger | None = None,
) -> dict[str, Any]:
    """Run the HN Promoter agent for a batch of scouted content.

    input_data:
        ideas: list of dicts from Twitter Scout (trending content)
        config: Config object
    """
    ideas = input_data["ideas"]
    config = input_data["config"]

    system_prompt = load_prompt("hn_promoter")

    ideas_json = json.dumps(ideas, indent=2)

    prompt = (
        f"You have {len(ideas)} trending content items from Twitter.\n"
        f"Your job: find the best ones to submit to Hacker News.\n\n"
        f"Content items:\n{ideas_json}\n\n"
        f"## PROCESS\n\n"
        f"### Step 1: Find Original Sources\n"
        f"For each item, the tweet likely references a blog post, paper, "
        f"GitHub repo, or article. Use WebSearch/WebFetch to find the "
        f"ORIGINAL SOURCE URL. HN wants original sources, not tweets.\n\n"
        f"### Step 2: Check for Duplicates\n"
        f"Use `hn_check_duplicate` with the source URL to see if it's "
        f"already been posted. Also use `hn_search` with the title.\n"
        f"Skip anything already on HN.\n\n"
        f"### Step 3: Check Current Front Page\n"
        f"Use `hn_top_stories` to see what's trending now. Don't submit "
        f"something that's already on the front page or similar to it.\n\n"
        f"### Step 4: Submit the Best Candidates\n"
        f"Use `hn_submit_link` to post. Max 2-3 submissions per run.\n"
        f"- Title must follow HN guidelines: use the original article title\n"
        f"- Don't editorialize or use clickbait\n"
        f"- Don't use ALL CAPS or exclamation marks\n"
        f"- If title has 'N things to do X', simplify to 'How to do X'\n"
        f"- Wait at least 30 seconds between submissions\n\n"
        f"### Step 5: Record Results\n"
        f"After posting, use `hn_check_item` on each submission to verify.\n\n"
        f"## OUTPUT\n"
        f"Return a JSON object:\n"
        f'{{"submissions": [\n'
        f'  {{"title": "...", "url": "...", "hn_url": "...", '
        f'"item_id": 123, "source_tweet": "...", "submitted": true}},\n'
        f'  {{"title": "...", "url": "...", "skipped": true, '
        f'"reason": "duplicate"}}\n'
        f"]}}"
    )

    server = create_sdk_mcp_server(
        "hn-tools",
        tools=[
            hn_search, hn_check_duplicate, hn_submit_link, hn_submit_text,
            hn_check_item, hn_top_stories, hn_user_profile,
            read_run_state, write_phase_output,
        ],
    )

    options = ClaudeAgentOptions(
        model=config.models.promoter,
        system_prompt=system_prompt,
        mcp_servers={"hn": server},
        allowed_tools=[
            "WebSearch", "WebFetch",
            "mcp__hn__hn_search",
            "mcp__hn__hn_check_duplicate",
            "mcp__hn__hn_submit_link",
            "mcp__hn__hn_submit_text",
            "mcp__hn__hn_check_item",
            "mcp__hn__hn_top_stories",
            "mcp__hn__hn_user_profile",
            "mcp__hn__read_run_state",
            "mcp__hn__write_phase_output",
        ],
        max_turns=30,
        permission_mode="bypassPermissions",
    )

    result_text = await run_tracked_agent(
        agent_name="hn_promoter",
        options=options,
        prompt=prompt,
        logger=activity_logger,
    )

    # The agent may save results via write_phase_output tool. Check state first.
    if state.promote_results:
        log.info("HN Promoter saved %d results via write_phase_output", len(state.promote_results))
        # Return the last result (most recent)
        return validate_build_output(state.promote_results[-1])

    # Try to parse JSON from the agent's final message
    try:
        result = extract_json_from_result(result_text)
        return validate_build_output(result)
    except ValueError:
        # Agent didn't return structured JSON. Return a minimal result.
        log.warning("HN Promoter didn't return JSON. Returning minimal result.")
        return {
            "submissions": [],
            "status": "completed",
            "agent_summary": result_text[:500] if result_text else "No output",
        }
