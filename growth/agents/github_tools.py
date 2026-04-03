"""GitHub tools — for novelty checking and repo building.

Uses GitHub's public API (no auth needed for search/read).
"""

from __future__ import annotations

import json
from typing import Any
import httpx

GITHUB_API = "https://api.github.com"


async def github_search_repos(args: dict[str, Any]) -> dict[str, Any]:
    query = args["query"]
    count = args.get("count", 10)
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"{GITHUB_API}/search/repositories",
                              params={"q": query, "per_page": count, "sort": "stars"},
                              headers={"Accept": "application/vnd.github.v3+json"})
        data = resp.json()
        repos = [{"name": r["full_name"], "stars": r["stargazers_count"],
                  "description": r.get("description", ""), "url": r["html_url"],
                  "updated_at": r.get("updated_at", "")}
                 for r in data.get("items", [])]
        return {"content": [{"type": "text", "text": json.dumps(repos, indent=2)}]}


async def github_get_repo(args: dict[str, Any]) -> dict[str, Any]:
    repo = args["repo"]  # "owner/name"
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"{GITHUB_API}/repos/{repo}",
                              headers={"Accept": "application/vnd.github.v3+json"})
        return {"content": [{"type": "text", "text": json.dumps(resp.json(), indent=2)}]}


async def github_search_code(args: dict[str, Any]) -> dict[str, Any]:
    query = args["query"]
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"{GITHUB_API}/search/code",
                              params={"q": query, "per_page": 5},
                              headers={"Accept": "application/vnd.github.v3+json"})
        return {"content": [{"type": "text", "text": json.dumps(resp.json().get("items", []), indent=2)}]}


async def github_create_repo(args: dict[str, Any]) -> dict[str, Any]:
    """Create a GitHub repo. Requires GITHUB_TOKEN env var."""
    import os
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return {"content": [{"type": "text", "text": '{"error": "GITHUB_TOKEN not set"}'}], "isError": True}
    
    name = args["name"]
    description = args.get("description", "")
    async with httpx.AsyncClient() as http:
        resp = await http.post(f"{GITHUB_API}/user/repos",
                               json={"name": name, "description": description, "auto_init": True},
                               headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"})
        return {"content": [{"type": "text", "text": json.dumps(resp.json(), indent=2)}]}


async def github_create_pr(args: dict[str, Any]) -> dict[str, Any]:
    """Create a pull request. Requires GITHUB_TOKEN env var."""
    import os
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return {"content": [{"type": "text", "text": '{"error": "GITHUB_TOKEN not set"}'}], "isError": True}
    
    repo = args["repo"]
    title = args["title"]
    body = args.get("body", "")
    head = args.get("head", "main")
    base = args.get("base", "main")
    async with httpx.AsyncClient() as http:
        resp = await http.post(f"{GITHUB_API}/repos/{repo}/pulls",
                               json={"title": title, "body": body, "head": head, "base": base},
                               headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"})
        return {"content": [{"type": "text", "text": json.dumps(resp.json(), indent=2)}]}
