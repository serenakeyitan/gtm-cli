"""hn/top_stories — Current HN front page."""

from __future__ import annotations
from typing import Any
import httpx
from growth.modules.base import Module, ModuleResult, ModuleContext
from growth.modules.registry import register


class HNTopStoriesModule(Module):
    name = "hn/top_stories"
    category = "source"
    description = "Get current Hacker News front page stories"
    platform = "hn"
    requires_auth = False
    param_schema = {"count": {"type": "int", "default": 15}}

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        try:
            async with httpx.AsyncClient() as http:
                resp = await http.get("https://hn.algolia.com/api/v1/search",
                    params={"tags": "front_page", "hitsPerPage": params.get("count", 15)})
                hits = resp.json().get("hits", [])
            return ModuleResult(success=True, data=hits)
        except Exception as e:
            return ModuleResult(success=False, errors=[str(e)])


register(HNTopStoriesModule())
