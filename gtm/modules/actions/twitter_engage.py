"""twitter/like, twitter/retweet — Engagement actions."""

from __future__ import annotations
from typing import Any
from gtm.modules.base import Module, ModuleResult, ModuleContext
from gtm.modules.registry import register


class TwitterLikeModule(Module):
    name = "twitter/like"
    category = "action"
    description = "Like a tweet"
    platform = "twitter"
    requires_auth = True
    param_schema = {"tweet_id": {"type": "str", "required": True}}

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        from gtm.platforms.twitter.client import TwitterClient
        if context.dry_run:
            return ModuleResult(success=True, data=[{"dry_run": True, "action": "like"}])
        client = TwitterClient(cookie_path=context.identity_dir / "cookies.json")
        try:
            await client.like_tweet(params["tweet_id"])
            return ModuleResult(success=True, data=[{"liked": params["tweet_id"]}])
        except Exception as e:
            return ModuleResult(success=False, errors=[str(e)])


class TwitterRetweetModule(Module):
    name = "twitter/retweet"
    category = "action"
    description = "Retweet a tweet"
    platform = "twitter"
    requires_auth = True
    param_schema = {"tweet_id": {"type": "str", "required": True}}

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        from gtm.platforms.twitter.client import TwitterClient
        if context.dry_run:
            return ModuleResult(success=True, data=[{"dry_run": True, "action": "retweet"}])
        client = TwitterClient(cookie_path=context.identity_dir / "cookies.json")
        try:
            await client.retweet(params["tweet_id"])
            return ModuleResult(success=True, data=[{"retweeted": params["tweet_id"]}])
        except Exception as e:
            return ModuleResult(success=False, errors=[str(e)])


register(TwitterLikeModule())
register(TwitterRetweetModule())
