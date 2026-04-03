"""twitter/search — Search tweets by query."""

from __future__ import annotations
from typing import Any
from growth.modules.base import Module, ModuleResult, ModuleContext
from growth.modules.registry import register


class TwitterSearchModule(Module):
    name = "twitter/search"
    category = "source"
    description = "Search tweets by query"
    platform = "twitter"
    requires_auth = True
    param_schema = {"query": {"type": "str", "required": True}, "count": {"type": "int", "default": 20}}

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        from growth.platforms.twitter.client import TwitterClient
        client = TwitterClient(cookie_path=context.identity_dir / "cookies.json")
        try:
            tweets = await client.search(params["query"], count=params.get("count", 20))
            return ModuleResult(success=True, data=tweets, metadata={"query": params["query"], "count": len(tweets)})
        except Exception as e:
            return ModuleResult(success=False, errors=[str(e)])


register(TwitterSearchModule())
