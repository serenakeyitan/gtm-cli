"""twitter/post — Post a tweet."""

from __future__ import annotations
from typing import Any
from gtm.modules.base import Module, ModuleResult, ModuleContext
from gtm.modules.registry import register


class TwitterPostModule(Module):
    name = "twitter/post"
    category = "action"
    description = "Post a tweet"
    platform = "twitter"
    requires_auth = True
    param_schema = {"text": {"type": "str", "required": True}}

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        from gtm.platforms.twitter.client import TwitterClient
        text = params.get("text", "")

        if context.dry_run:
            return ModuleResult(success=True, data=[{"dry_run": True, "text": text}])

        client = TwitterClient(cookie_path=context.identity_dir / "cookies.json")
        try:
            tweet = await client.post_tweet(text)
            return ModuleResult(success=True, data=[tweet], metadata={"post_id": tweet.get("id")})
        except Exception as e:
            return ModuleResult(success=False, errors=[str(e)])


register(TwitterPostModule())
