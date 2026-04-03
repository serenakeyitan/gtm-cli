"""Reddit MCP tools — thin wrappers for agent use."""

from __future__ import annotations

import json
from typing import Any
import httpx


async def reddit_search_subreddits(args: dict[str, Any]) -> dict[str, Any]:
    query = args.get("query", "")
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"https://www.reddit.com/subreddits/search.json?q={query}&limit=10",
                              headers={"User-Agent": "growth-cli/0.1"})
        subs = [s["data"] for s in resp.json().get("data", {}).get("children", [])]
        return {"content": [{"type": "text", "text": json.dumps(subs, indent=2)}]}


async def reddit_top_posts(args: dict[str, Any]) -> dict[str, Any]:
    subreddit = args["subreddit"]
    count = args.get("count", 10)
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"https://www.reddit.com/r/{subreddit}/top.json?t=week&limit={count}",
                              headers={"User-Agent": "growth-cli/0.1"})
        posts = [p["data"] for p in resp.json().get("data", {}).get("children", [])]
        return {"content": [{"type": "text", "text": json.dumps(posts, indent=2)}]}


async def reddit_subreddit_rules(args: dict[str, Any]) -> dict[str, Any]:
    subreddit = args["subreddit"]
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"https://www.reddit.com/r/{subreddit}/about/rules.json",
                              headers={"User-Agent": "growth-cli/0.1"})
        return {"content": [{"type": "text", "text": json.dumps(resp.json(), indent=2)}]}


async def reddit_user_posts(args: dict[str, Any]) -> dict[str, Any]:
    username = args["username"]
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"https://www.reddit.com/user/{username}/submitted.json?limit=10",
                              headers={"User-Agent": "growth-cli/0.1"})
        posts = [p["data"] for p in resp.json().get("data", {}).get("children", [])]
        return {"content": [{"type": "text", "text": json.dumps(posts, indent=2)}]}


async def reddit_check_post(args: dict[str, Any]) -> dict[str, Any]:
    url = args["url"]
    async with httpx.AsyncClient() as http:
        json_url = url.rstrip("/") + ".json"
        resp = await http.get(json_url, headers={"User-Agent": "growth-cli/0.1"}, follow_redirects=True)
        data = resp.json()
        if isinstance(data, list) and data:
            post = data[0]["data"]["children"][0]["data"]
            return {"content": [{"type": "text", "text": json.dumps({"score": post.get("score"), "comments": post.get("num_comments"), "removed": post.get("removed_by_category") is not None}, indent=2)}]}
        return {"content": [{"type": "text", "text": "{}"}]}


async def reddit_browser_submit(args: dict[str, Any]) -> dict[str, Any]:
    from growth.platforms.reddit.client import PlaywrightRedditClient
    client = PlaywrightRedditClient()
    result = await client.submit_api_post(args["subreddit"], args["title"], selftext=args.get("selftext", ""))
    await client.close()
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


async def reddit_browser_check_post(args: dict[str, Any]) -> dict[str, Any]:
    return await reddit_check_post(args)


async def reddit_browser_subreddit_rules(args: dict[str, Any]) -> dict[str, Any]:
    return await reddit_subreddit_rules(args)
