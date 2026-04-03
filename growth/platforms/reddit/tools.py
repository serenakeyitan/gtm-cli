"""Reddit MCP tools — for agents via Claude SDK."""

from __future__ import annotations

import json

from claude_code_sdk import tool
import httpx


@tool("reddit_search_subreddits", "Search for subreddits", {"query": str})
async def reddit_search_subreddits(args):
    query = args.get("query", "")
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"https://www.reddit.com/subreddits/search.json?q={query}&limit=10",
                              headers={"User-Agent": "growth-cli/0.1"})
        return {"content": [{"type": "text", "text": json.dumps([s["data"] for s in resp.json().get("data", {}).get("children", [])], indent=2)}]}


@tool("reddit_top_posts", "Get top posts from a subreddit", {"subreddit": str, "count": int})
async def reddit_top_posts(args):
    subreddit = args["subreddit"]
    count = args.get("count", 10)
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"https://www.reddit.com/r/{subreddit}/top.json?t=week&limit={count}",
                              headers={"User-Agent": "growth-cli/0.1"})
        return {"content": [{"type": "text", "text": json.dumps([p["data"] for p in resp.json().get("data", {}).get("children", [])], indent=2)}]}


@tool("reddit_subreddit_rules", "Get subreddit rules", {"subreddit": str})
async def reddit_subreddit_rules(args):
    subreddit = args["subreddit"]
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"https://www.reddit.com/r/{subreddit}/about/rules.json",
                              headers={"User-Agent": "growth-cli/0.1"})
        return {"content": [{"type": "text", "text": json.dumps(resp.json(), indent=2)}]}


@tool("reddit_user_posts", "Get a user's recent posts", {"username": str})
async def reddit_user_posts(args):
    username = args["username"]
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"https://www.reddit.com/user/{username}/submitted.json?limit=10",
                              headers={"User-Agent": "growth-cli/0.1"})
        return {"content": [{"type": "text", "text": json.dumps([p["data"] for p in resp.json().get("data", {}).get("children", [])], indent=2)}]}


@tool("reddit_check_post", "Check a Reddit post's score and status", {"url": str})
async def reddit_check_post(args):
    url = args["url"]
    async with httpx.AsyncClient() as http:
        resp = await http.get(url.rstrip("/") + ".json", headers={"User-Agent": "growth-cli/0.1"}, follow_redirects=True)
        data = resp.json()
        if isinstance(data, list) and data:
            post = data[0]["data"]["children"][0]["data"]
            return {"content": [{"type": "text", "text": json.dumps({"score": post.get("score"), "comments": post.get("num_comments")}, indent=2)}]}
        return {"content": [{"type": "text", "text": "{}"}]}


@tool("reddit_browser_submit", "Submit a post to Reddit", {"subreddit": str, "title": str, "selftext": str})
async def reddit_browser_submit(args):
    from growth.platforms.reddit.client import PlaywrightRedditClient
    client = PlaywrightRedditClient()
    try:
        result = await client.submit_api_post(args["subreddit"], args["title"], selftext=args.get("selftext", ""))
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
    finally:
        await client.close()


@tool("reddit_browser_check_post", "Check a Reddit post via browser", {"url": str})
async def reddit_browser_check_post(args):
    return await reddit_check_post(args)


@tool("reddit_browser_subreddit_rules", "Get subreddit rules via browser", {"subreddit": str})
async def reddit_browser_subreddit_rules(args):
    return await reddit_subreddit_rules(args)
