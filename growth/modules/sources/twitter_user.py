"""twitter/user_tweets — Get recent tweets from a user."""

from __future__ import annotations
from typing import Any
from growth.modules.base import Module, ModuleResult, ModuleContext
from growth.modules.registry import register


class TwitterUserTweetsModule(Module):
    name = "twitter/user_tweets"
    category = "source"
    description = "Get recent tweets from a specific user"
    platform = "twitter"
    requires_auth = True
    param_schema = {"username": {"type": "str", "required": True}, "count": {"type": "int", "default": 20}}

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        from growth.platforms.twitter.client import TwitterClient
        client = TwitterClient(cookie_path=context.identity_dir / "cookies.json")
        try:
            tweets = await client.get_user_tweets(params["username"], count=params.get("count", 20))
            return ModuleResult(success=True, data=tweets, metadata={"username": params["username"]})
        except Exception as e:
            return ModuleResult(success=False, errors=[str(e)])


register(TwitterUserTweetsModule())
