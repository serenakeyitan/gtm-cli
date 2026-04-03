"""reddit/search — Search Reddit via public API."""

from __future__ import annotations
from typing import Any
import httpx
from growth.modules.base import Module, ModuleResult, ModuleContext
from growth.modules.registry import register


class RedditSearchModule(Module):
    name = "reddit/search"
    category = "source"
    description = "Search Reddit posts"
    platform = "reddit"
    requires_auth = False
    param_schema = {"query": {"type": "str", "required": True}, "subreddit": {"type": "str"}, "count": {"type": "int", "default": 20}}

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        query = params["query"]
        count = params.get("count", 20)
        sub = params.get("subreddit")

        if sub:
            url = f"https://www.reddit.com/r/{sub}/search.json"
            search_params = {"q": query, "restrict_sr": "1", "limit": count}
        else:
            url = "https://www.reddit.com/search.json"
            search_params = {"q": query, "limit": count}

        try:
            async with httpx.AsyncClient() as http:
                resp = await http.get(url, params=search_params, headers={"User-Agent": "growth-cli/0.1"})
                resp.raise_for_status()
                posts = [p["data"] for p in resp.json().get("data", {}).get("children", [])]
            return ModuleResult(success=True, data=posts, metadata={"query": query, "count": len(posts)})
        except Exception as e:
            return ModuleResult(success=False, errors=[str(e)])


register(RedditSearchModule())
