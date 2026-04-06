"""track/engagement — Fetch live engagement for posted items."""

from __future__ import annotations
from typing import Any
from gtm.modules.base import Module, ModuleResult, ModuleContext
from gtm.modules.registry import register


class EngagementTrackerModule(Module):
    name = "track/engagement"
    category = "monitor"
    description = "Fetch live engagement metrics for posted content"

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        if not input_data or not input_data.data:
            return ModuleResult(success=True, data=[])

        from gtm.output.traction import fetch_twitter_engagement, fetch_reddit_engagement, fetch_hn_engagement

        results = []
        errors = []
        for item in input_data.data:
            platform = item.get("platform", "")
            post_id = item.get("post_id", item.get("id", ""))
            url = item.get("url", "")

            try:
                if platform == "twitter" and post_id:
                    eng = await fetch_twitter_engagement(post_id, context.identity_dir)
                elif platform == "reddit" and url:
                    eng = await fetch_reddit_engagement(url)
                elif platform == "hn" and post_id:
                    eng = await fetch_hn_engagement(post_id)
                else:
                    results.append(item)
                    continue

                # Check if the fetch itself returned an error dict
                if eng.get("error"):
                    results.append({**item, "engagement_error": eng["error"]})
                    errors.append(f"{platform}:{post_id}: {eng['error']}")
                else:
                    results.append({**item, **eng})
            except Exception as e:
                results.append({**item, "engagement_error": str(e)})
                errors.append(f"{platform}:{post_id}: {e}")

        return ModuleResult(success=True, data=results, errors=errors)


register(EngagementTrackerModule())
