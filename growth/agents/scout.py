"""Agent 1: Twitter Scout — find trending AI topics and generate project ideas."""

from __future__ import annotations

import json
import logging
from typing import Any

from claude_code_sdk import (
    ClaudeCodeOptions,
    create_sdk_mcp_server,
)

from growth.agents.base import (
    extract_json_from_result,
    load_prompt,
    validate_ideas_output,
)
from growth.agents.agent_wrapper import run_tracked_agent
from growth.agents.activity_log import ActivityLogger
from growth.engine.state import RunState
from growth.platforms.twitter.tools import (
    twitter_search,
    twitter_user_tweets,
    twitter_get_tweet,
)
from growth.agents.state_tools import read_run_state, write_phase_output

log = logging.getLogger(__name__)


async def preflight_check_twitter(cookie_path: str | None = None) -> None:
    """Verify twikit cookies are present and loadable.

    Raises RuntimeError if cookies are missing or auth fails.
    """
    from growth.platforms.twitter.client import (
        get_twitter_client,
        TwitterAuthError,
    )

    try:
        client = get_twitter_client(cookie_path)
        await client.preflight()
    except TwitterAuthError as e:
        raise RuntimeError(str(e)) from e


async def run_twitter_scout(
    state: RunState,
    config: Any,
    activity_logger: ActivityLogger | None = None,
) -> list[dict[str, Any]]:
    """Run the Twitter Scout agent to find trending AI topics."""

    # ── Pre-flight: fail fast if Twitter tools won't work ──
    log.info("Pre-flight: verifying Twitter authentication...")
    await preflight_check_twitter(config.twitter.cookie_path)
    log.info("Pre-flight: Twitter auth OK")

    # Read engagement thresholds from config
    min_likes = config.twitter.min_engagement.get("likes", 1000)
    min_retweets = config.twitter.min_engagement.get("retweets", 200)

    system_prompt = load_prompt("twitter_scout").format(
        min_likes=min_likes, min_retweets=min_retweets,
    )

    # Build the account lists for the user prompt
    seed_accounts = config.twitter.seed_accounts
    seed_companies = getattr(config.twitter, "seed_company_accounts", [])

    # Format accounts as numbered lists for clarity
    group_a_list = "\n".join(f"  {i+1}. @{a}" for i, a in enumerate(seed_accounts))
    group_b_list = "\n".join(f"  {i+1}. @{a}" for i, a in enumerate(seed_companies))

    prompt = (
        f"Fetch recent tweets from every account below and identify the top 10 "
        f"implementable open-source project ideas.\n\n"
        f"## TIME WINDOW\n"
        f"**Last 24 hours only.** Ignore any tweet older than 24 hours.\n\n"
        f"## ENGAGEMENT THRESHOLD\n"
        f"A tweet must have **at least {min_likes} likes AND {min_retweets} "
        f"retweets** to be recorded. Skip tweets below this threshold.\n\n"
        f"## Phase 1: FETCH — Read each account's tweets\n\n"
        f"Use the `twitter_user_tweets` tool on each account below. For each "
        f"account, keep only tweets from the last 24 hours that meet the "
        f"engagement threshold ({min_likes}+ likes, {min_retweets}+ RTs). "
        f"If the account has no qualifying tweets, skip it.\n\n"
        f"**Group A — {len(seed_accounts)} AI Influencers & Key Voices:**\n"
        f"{group_a_list}\n\n"
        f"**Group B — {len(seed_companies)} AI Companies:**\n"
        f"{group_b_list}\n\n"
        f"## Phase 2: SYNTHESIZE — Pick the top 10 ideas\n\n"
        f"After fetching ALL accounts, analyze the collected tweets and output "
        f"the top 10 implementable project ideas as a JSON array.\n\n"
        f"Each idea needs: id, title, type (awesome-list|skill|cli-tool|freeform|"
        f"open-source-alt), description, evidence (tweets, trend_signal, "
        f"engagement_total, accounts_discussing, existing_similar_project), "
        f"suggested_repo_name."
    )

    server = create_sdk_mcp_server(
        "twitter-tools",
        tools=[twitter_search, twitter_user_tweets, twitter_get_tweet, read_run_state, write_phase_output],
    )

    options = ClaudeCodeOptions(
        model=config.models.scout,
        system_prompt=system_prompt,
        mcp_servers={"twitter": server},
        allowed_tools=[
            "mcp__twitter__twitter_search",
            "mcp__twitter__twitter_user_tweets",
            "mcp__twitter__twitter_get_tweet",
            "mcp__twitter__read_run_state",
            "mcp__twitter__write_phase_output",
        ],
        max_turns=200,
        permission_mode="bypassPermissions",
    )

    result_text = await run_tracked_agent(
        agent_name="scout",
        options=options,
        prompt=prompt,
        logger=activity_logger,
    )

    ideas = extract_json_from_result(result_text)
    return validate_ideas_output(ideas)
