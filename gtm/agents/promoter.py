"""Agent 4: Promoter — post to Reddit, monitor performance, handle deletions."""

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
from gtm.platforms.reddit.tools import (
    # PRAW-based (read-only, legacy)
    reddit_search_subreddits,
    reddit_top_posts,
    reddit_subreddit_rules,
    reddit_user_posts,
    reddit_check_post,
    # Browser-based (preferred for posting)
    reddit_browser_submit,
    reddit_browser_check_post,
    reddit_browser_subreddit_rules,
)
from gtm.agents.state_tools import read_run_state, write_phase_output

log = logging.getLogger(__name__)

# User's past Reddit post style references
STYLE_REFERENCES = [
    "https://www.reddit.com/r/ClaudeAI/comments/1qqry2c/",
    "https://www.reddit.com/r/notebooklm/comments/1qn1d6a/",
    "https://www.reddit.com/r/notebooklm/comments/1qk69wl/",
    "https://www.reddit.com/r/Bard/comments/1qdz6e1/",
    "https://www.reddit.com/r/notebooklm/comments/1qdyudh/",
]


async def run_promoter(
    state: RunState,
    input_data: Any,
    activity_logger: ActivityLogger | None = None,
) -> dict[str, Any]:
    """Run the Promoter agent for a single idea+build."""
    idea = input_data["idea"]
    build = input_data["build"]
    config = input_data["config"]

    system_prompt = load_prompt("promoter")

    target_subs = ", ".join(config.reddit.target_subreddits)
    stagger = config.reddit.post_stagger_hours
    max_subs = config.reddit.max_subreddits_per_idea
    style_refs = "\n".join(f"  - {url}" for url in STYLE_REFERENCES)

    idea_json = json.dumps(idea, indent=2)
    build_json = json.dumps(build, indent=2)

    prompt = (
        f"Promote this open-source project on Reddit.\n\n"
        f"Idea:\n{idea_json}\n\n"
        f"Build result:\n{build_json}\n\n"
        f"## WRITING STYLE (follow exactly)\n"
        f"- always use 'i' never 'we'. you are one solo person.\n"
        f"- all lowercase. no capitalized letters except proper nouns.\n"
        f"- no dashes to connect clauses. use periods. short sentences.\n"
        f"- write like a community college student. simple and direct.\n"
        f"- for strict subs: NEVER use 'i built', 'i created', 'i made' in titles OR body.\n"
        f"  frame as neutral resource sharing: 'useful tool for X', 'handy reference for Y'.\n"
        f"- for lenient subs: can mention making it but bury it naturally. don't lead with it.\n"
        f"- banned phrases: 'check out', 'we just launched', 'excited to share', "
        f"'introducing', 'game changer', link shorteners.\n"
        f"- keep ALL titles under 75 characters. some subs enforce this strictly.\n\n"
        f"## POSTING TOOLS\n"
        f"Use `reddit_browser_submit` for ALL posting. It supports both text posts "
        f"(kind='self', pass selftext) and link posts (kind='link', pass url).\n"
        f"- For subs that only allow link posts (e.g. r/coolgithubprojects): "
        f"use kind='link' with the GitHub repo URL.\n"
        f"- For subs that allow text posts: use kind='self' with body text.\n"
        f"- Wait at least 15 seconds between posts.\n"
        f"- Use `reddit_browser_check_post` to check post status after posting.\n\n"
        f"## ANTI SELF-PROMOTION (CRITICAL)\n"
        f"Reddit moderators aggressively remove self-promotion posts.\n"
        f"- Real example: 'i built a searchable cli reference for all google workspace "
        f"admin commands' was REMOVED by r/GoogleWorkspace moderators.\n"
        f"- Rewritten as 'searchable reference for google workspace cli commands' "
        f"and it WORKED.\n"
        f"- If a post is removed, NEVER repost same content. rewrite completely.\n"
        f"- Getting banned means the account can never post there again.\n\n"
        f"## Instructions\n"
        f"Phase A — Subreddit Discovery:\n"
        f"  Target subreddits to consider: {target_subs}\n"
        f"  Max subreddits per idea: {max_subs}\n"
        f"  Search for AI-related subs, check activity + rules, read top posts\n"
        f"  Classify each sub as 'strict' or 'lenient' on self-promotion\n"
        f"  Check allowed post types (text, link, image). some subs only allow links.\n\n"
        f"Phase B — Post Crafting:\n"
        f"  Reference these past posts for style:\n{style_refs}\n"
        f"  Vary titles across subs. all lowercase. no dashes. under 75 chars.\n"
        f"  For strict subs: NO first-person language at all. neutral resource sharing.\n"
        f"  For lenient subs: can be slightly more direct but still casual\n\n"
        f"Phase C — Staggered Posting:\n"
        f"  Use `reddit_browser_submit` for each post.\n"
        f"  First sub immediately, remaining at {stagger}-hour intervals\n"
        f"  Record all URLs and post IDs\n\n"
        f"Phase D — Monitoring:\n"
        f"  Use `reddit_browser_check_post` to check each post after posting.\n"
        f"  Detect deletion (author=None or removed status), record metrics.\n"
        f"  If deleted: note for rewrite, do NOT repost same content.\n\n"
        f"Output a JSON object with: idea_id, posts (array of "
        f"{{subreddit, url, post_id, title, kind, score, num_comments, "
        f"deleted, sub_strictness}})"
    )

    server = create_sdk_mcp_server(
        "reddit-tools",
        tools=[
            # Read-only PRAW tools (for discovery/research)
            reddit_search_subreddits, reddit_top_posts, reddit_subreddit_rules,
            reddit_user_posts, reddit_check_post,
            # Browser-based tools (for posting and checking)
            reddit_browser_submit, reddit_browser_check_post,
            reddit_browser_subreddit_rules,
            # State tools
            read_run_state, write_phase_output,
        ],
    )

    options = ClaudeAgentOptions(
        model=config.models.promoter,
        system_prompt=system_prompt,
        mcp_servers={"reddit": server},
        allowed_tools=["WebSearch", "WebFetch"],
        max_turns=40,
        permission_mode="bypassPermissions",
    )

    result_text = await run_tracked_agent(
        agent_name=f"promoter:{idea.get('id', 'unknown')}",
        options=options,
        prompt=prompt,
        logger=activity_logger,
    )

    result = extract_json_from_result(result_text)
    promo = validate_build_output(result)
    promo.setdefault("idea_id", idea.get("id"))
    return promo
