"""reddit/submit — Submit a post to a subreddit."""

from __future__ import annotations
from typing import Any
from growth.modules.base import Module, ModuleResult, ModuleContext
from growth.modules.registry import register


class RedditSubmitModule(Module):
    name = "reddit/submit"
    category = "action"
    description = "Submit a post to a subreddit"
    platform = "reddit"
    requires_auth = True
    param_schema = {"subreddit": {"type": "str", "required": True}, "title": {"type": "str", "required": True}, "body": {"type": "str"}, "url": {"type": "str"}}

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        if context.dry_run:
            return ModuleResult(success=True, data=[{"dry_run": True, "subreddit": params.get("subreddit")}])

        from growth.platforms.reddit.client import PlaywrightRedditClient
        session_dir = context.identity_dir / "session"
        client = PlaywrightRedditClient(session_dir=str(session_dir))
        try:
            if params.get("url"):
                result = await client.submit_api_post(params["subreddit"], params["title"], url=params["url"], kind="link")
            else:
                result = await client.submit_api_post(params["subreddit"], params["title"], selftext=params.get("body", ""))
            return ModuleResult(success=True, data=[result])
        except Exception as e:
            return ModuleResult(success=False, errors=[str(e)])
        finally:
            await client.close()


register(RedditSubmitModule())
