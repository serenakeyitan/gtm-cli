"""hn/search — Search Hacker News via Algolia."""

from __future__ import annotations
from typing import Any
import httpx
from growth.modules.base import Module, ModuleResult, ModuleContext
from growth.modules.registry import register


class HNSearchModule(Module):
    name = "hn/search"
    category = "source"
    description = "Search Hacker News via Algolia API"
    platform = "hn"
    requires_auth = False
    param_schema = {"query": {"type": "str", "required": True}, "count": {"type": "int", "default": 20}}

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        try:
            async with httpx.AsyncClient() as http:
                resp = await http.get("https://hn.algolia.com/api/v1/search",
                    params={"query": params["query"], "tags": "story", "hitsPerPage": params.get("count", 20)})
                hits = resp.json().get("hits", [])
            return ModuleResult(success=True, data=hits, metadata={"query": params["query"]})
        except Exception as e:
            return ModuleResult(success=False, errors=[str(e)])


register(HNSearchModule())
