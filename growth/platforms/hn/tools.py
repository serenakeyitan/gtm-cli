"""HN MCP tools — thin wrappers for agent use."""

from __future__ import annotations

import json
from typing import Any
import httpx

ALGOLIA_API = "https://hn.algolia.com/api/v1"


async def hn_search(args: dict[str, Any]) -> dict[str, Any]:
    query = args.get("query", "")
    tags = args.get("tags", "story")
    count = args.get("hits_per_page", 20)
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"{ALGOLIA_API}/search", params={"query": query, "tags": tags, "hitsPerPage": count})
        return {"content": [{"type": "text", "text": json.dumps(resp.json().get("hits", []), indent=2)}]}


async def hn_check_duplicate(args: dict[str, Any]) -> dict[str, Any]:
    url = args.get("url", "")
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"{ALGOLIA_API}/search", params={"query": url, "tags": "story", "restrictSearchableAttributes": "url"})
        hits = resp.json().get("hits", [])
        return {"content": [{"type": "text", "text": json.dumps({"is_duplicate": len(hits) > 0, "existing": hits[:3]}, indent=2)}]}


async def hn_submit_link(args: dict[str, Any]) -> dict[str, Any]:
    from growth.platforms.hn.client import PlaywrightHNClient
    url = args["url"]
    title = args["title"]
    client = PlaywrightHNClient()
    result = await client.submit_link(url, title)
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


async def hn_submit_text(args: dict[str, Any]) -> dict[str, Any]:
    from growth.platforms.hn.client import PlaywrightHNClient
    title = args["title"]
    text = args.get("text", "")
    client = PlaywrightHNClient()
    result = await client.submit_text(title, text)
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}


async def hn_check_item(args: dict[str, Any]) -> dict[str, Any]:
    item_id = args["item_id"]
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"{ALGOLIA_API}/items/{item_id}")
        return {"content": [{"type": "text", "text": json.dumps(resp.json(), indent=2)}]}


async def hn_top_stories(args: dict[str, Any]) -> dict[str, Any]:
    count = args.get("count", 15)
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"{ALGOLIA_API}/search", params={"tags": "front_page", "hitsPerPage": count})
        return {"content": [{"type": "text", "text": json.dumps(resp.json().get("hits", []), indent=2)}]}


async def hn_user_profile(args: dict[str, Any]) -> dict[str, Any]:
    username = args["username"]
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"{ALGOLIA_API}/users/{username}")
        return {"content": [{"type": "text", "text": json.dumps(resp.json(), indent=2)}]}
