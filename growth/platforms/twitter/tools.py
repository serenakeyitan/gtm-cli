"""Twitter MCP tools — backed by twikit. Used by agents via Claude SDK."""

from __future__ import annotations

import json

from claude_code_sdk import tool

from growth.platforms.twitter.client import get_twitter_client, TwitterClientError


@tool("twitter_search", "Search tweets by query", {"query": str, "count": int})
async def twitter_search(args):
    query = args["query"]
    count = args.get("count", 20)
    try:
        client = get_twitter_client()
        tweets = await client.search(query, count=count)
        return {"content": [{"type": "text", "text": json.dumps(tweets, indent=2)}]}
    except TwitterClientError as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}


@tool("twitter_user_tweets", "Get recent tweets from a specific user", {"username": str, "count": int})
async def twitter_user_tweets(args):
    username = args["username"]
    count = args.get("count", 20)
    try:
        client = get_twitter_client()
        tweets = await client.get_user_tweets(username, count=count)
        return {"content": [{"type": "text", "text": json.dumps(tweets, indent=2)}]}
    except TwitterClientError as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}


@tool("twitter_get_tweet", "Get a single tweet by ID", {"tweet_id": str})
async def twitter_get_tweet(args):
    tweet_id = args["tweet_id"]
    try:
        client = get_twitter_client()
        tweet = await client.get_tweet(tweet_id)
        return {"content": [{"type": "text", "text": json.dumps(tweet, indent=2)}]}
    except TwitterClientError as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}
