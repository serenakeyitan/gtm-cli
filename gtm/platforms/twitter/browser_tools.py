"""MCP tools for Twitter posting via Playwright (browser sessions).

Mirrors gtm/platforms/reddit/tools.py browser tools. Uses IdentityManager —
pass `identity` to route through a specific saved session.
"""

from __future__ import annotations

import json
import logging

from claude_agent_sdk import tool

log = logging.getLogger(__name__)


@tool(
    "twitter_browser_post",
    (
        "Post a single tweet (<=280 chars) using a saved browser session. "
        "Pass `identity` to choose which registered Twitter identity posts. "
        "Returns {tweet_id, url}."
    ),
    {"text": str, "identity": str},
)
async def twitter_browser_post(args):
    try:
        from gtm.platforms.twitter.browser_client import (
            get_twitter_browser_client,
            get_twitter_browser_client_for_identity,
        )

        identity = args.get("identity") or ""
        client = (
            get_twitter_browser_client_for_identity(identity)
            if identity else get_twitter_browser_client()
        )
        result = await client.post_tweet(args["text"])
        if identity:
            result["identity"] = identity
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}


@tool(
    "twitter_browser_post_thread",
    (
        "Post a thread (list of tweets, each <=280 chars). Each item replies "
        "to the previous. Returns list of {tweet_id, url}."
    ),
    {"tweets": list, "identity": str},
)
async def twitter_browser_post_thread(args):
    try:
        from gtm.platforms.twitter.browser_client import (
            get_twitter_browser_client,
            get_twitter_browser_client_for_identity,
        )

        identity = args.get("identity") or ""
        client = (
            get_twitter_browser_client_for_identity(identity)
            if identity else get_twitter_browser_client()
        )
        results = await client.post_thread(list(args.get("tweets", [])))
        if identity:
            for r in results:
                r["identity"] = identity
        return {"content": [{"type": "text", "text": json.dumps(results, indent=2)}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}


@tool(
    "twitter_browser_reply",
    (
        "Reply to a tweet by URL with text (<=280 chars). "
        "Pass `identity` to choose which registered identity replies."
    ),
    {"parent_url": str, "text": str, "identity": str},
)
async def twitter_browser_reply(args):
    try:
        from gtm.platforms.twitter.browser_client import (
            get_twitter_browser_client,
            get_twitter_browser_client_for_identity,
        )

        identity = args.get("identity") or ""
        client = (
            get_twitter_browser_client_for_identity(identity)
            if identity else get_twitter_browser_client()
        )
        result = await client.reply_to(args["parent_url"], args["text"])
        if identity:
            result["identity"] = identity
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}


@tool(
    "twitter_browser_check_tweet",
    "Check tweet status (deletion, raw page sample) by URL.",
    {"tweet_url": str, "identity": str},
)
async def twitter_browser_check_tweet(args):
    try:
        from gtm.platforms.twitter.browser_client import (
            get_twitter_browser_client,
            get_twitter_browser_client_for_identity,
        )

        identity = args.get("identity") or ""
        client = (
            get_twitter_browser_client_for_identity(identity)
            if identity else get_twitter_browser_client()
        )
        result = await client.check_tweet(args["tweet_url"])
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}
