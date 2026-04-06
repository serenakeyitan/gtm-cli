"""HN MCP tools — for agents via Claude SDK."""

from __future__ import annotations

import json

from claude_code_sdk import tool
import httpx

ALGOLIA_API = "https://hn.algolia.com/api/v1"


@tool("hn_search", "Search Hacker News via Algolia API", {"query": str, "tags": str, "hits_per_page": int})
async def hn_search(args):
    query = args.get("query", "")
    tags = args.get("tags", "story")
    count = args.get("hits_per_page", 20)
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"{ALGOLIA_API}/search", params={"query": query, "tags": tags, "hitsPerPage": count})
        return {"content": [{"type": "text", "text": json.dumps(resp.json().get("hits", []), indent=2)}]}


@tool("hn_check_duplicate", "Check if a URL has been submitted to HN", {"url": str})
async def hn_check_duplicate(args):
    url = args.get("url", "")
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"{ALGOLIA_API}/search", params={"query": url, "tags": "story", "restrictSearchableAttributes": "url"})
        hits = resp.json().get("hits", [])
        return {"content": [{"type": "text", "text": json.dumps({"is_duplicate": len(hits) > 0, "existing": hits[:3]}, indent=2)}]}


@tool("hn_submit_link", "Submit a link to HN", {"url": str, "title": str})
async def hn_submit_link(args):
    from gtm.platforms.hn.client import PlaywrightHNClient
    client = PlaywrightHNClient()
    result = await client.submit_link(args["url"], args["title"])
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


@tool("hn_submit_text", "Submit a text post to HN", {"title": str, "text": str})
async def hn_submit_text(args):
    from gtm.platforms.hn.client import PlaywrightHNClient
    client = PlaywrightHNClient()
    result = await client.submit_text(args["title"], args.get("text", ""))
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


@tool("hn_check_item", "Check an HN item's score and comments", {"item_id": str})
async def hn_check_item(args):
    item_id = args["item_id"]
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"{ALGOLIA_API}/items/{item_id}")
        return {"content": [{"type": "text", "text": json.dumps(resp.json(), indent=2)}]}


@tool("hn_top_stories", "Get current HN front page stories", {"count": int})
async def hn_top_stories(args):
    count = args.get("count", 15)
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"{ALGOLIA_API}/search", params={"tags": "front_page", "hitsPerPage": count})
        return {"content": [{"type": "text", "text": json.dumps(resp.json().get("hits", []), indent=2)}]}


@tool("hn_user_profile", "Get an HN user's profile", {"username": str})
async def hn_user_profile(args):
    username = args["username"]
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"{ALGOLIA_API}/users/{username}")
        return {"content": [{"type": "text", "text": json.dumps(resp.json(), indent=2)}]}
