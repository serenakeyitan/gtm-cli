"""hn/submit_link, hn/submit_text — Submit to Hacker News."""

from __future__ import annotations
from typing import Any
from gtm.modules.base import Module, ModuleResult, ModuleContext
from gtm.modules.registry import register


class HNSubmitLinkModule(Module):
    name = "hn/submit_link"
    category = "action"
    description = "Submit a link to Hacker News"
    platform = "hn"
    requires_auth = True
    param_schema = {"url": {"type": "str", "required": True}, "title": {"type": "str", "required": True}}

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        if context.dry_run:
            return ModuleResult(success=True, data=[{"dry_run": True, "title": params.get("title")}])

        from gtm.platforms.hn.client import PlaywrightHNClient
        session_dir = context.identity_dir / "session"
        client = PlaywrightHNClient(session_dir=str(session_dir))
        try:
            result = await client.submit_link(params["url"], params["title"])
            return ModuleResult(success=True, data=[result])
        except Exception as e:
            return ModuleResult(success=False, errors=[str(e)])


register(HNSubmitLinkModule())
