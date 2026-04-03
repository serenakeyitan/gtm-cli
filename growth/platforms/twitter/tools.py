"""Twitter MCP tools — thin wrappers around the client for agent use.

These are imported by agents as callable tool functions.
They match the MCP tool signatures from the original pipeline.
"""

from __future__ import annotations

import json
from typing import Any

from growth.platforms.twitter.client import TwitterClient, get_twitter_client


async def twitter_search(args: dict[str, Any]) -> dict[str, Any]:
    """Search tweets by query."""
    query = args["query"]
    count = args.get("count", 20)
    client = get_twitter_client()
    tweets = await client.search(query, count=count)
    return {"content": [{"type": "text", "text": json.dumps(tweets, indent=2)}]}


async def twitter_user_tweets(args: dict[str, Any]) -> dict[str, Any]:
    """Get recent tweets from a user."""
    username = args["username"]
    count = args.get("count", 20)
    client = get_twitter_client()
    tweets = await client.get_user_tweets(username, count=count)
    return {"content": [{"type": "text", "text": json.dumps(tweets, indent=2)}]}


async def twitter_get_tweet(args: dict[str, Any]) -> dict[str, Any]:
    """Get a single tweet by ID."""
    tweet_id = args["tweet_id"]
    client = get_twitter_client()
    tweet = await client.get_tweet(tweet_id)
    return {"content": [{"type": "text", "text": json.dumps(tweet, indent=2)}]}
