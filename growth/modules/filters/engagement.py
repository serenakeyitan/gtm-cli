"""filter/engagement — Keep items above engagement thresholds."""

from __future__ import annotations
from typing import Any
from growth.modules.base import Module, ModuleResult, ModuleContext
from growth.modules.registry import register


class EngagementFilterModule(Module):
    name = "filter/engagement"
    category = "filter"
    description = "Keep items above engagement thresholds (likes, score, points)"
    param_schema = {
        "min_likes": {"type": "int", "default": 0},
        "min_score": {"type": "int", "default": 0},
        "min_retweets": {"type": "int", "default": 0},
        "min_comments": {"type": "int", "default": 0},
    }

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        if not input_data or not input_data.data:
            return ModuleResult(success=True, data=[], metadata={"filtered": 0})

        min_likes = params.get("min_likes", 0)
        min_score = params.get("min_score", 0)
        min_rts = params.get("min_retweets", 0)
        min_comments = params.get("min_comments", 0)

        filtered = []
        for item in input_data.data:
            likes = item.get("favorite_count", item.get("score", item.get("points", 0)))
            rts = item.get("retweet_count", 0)
            comments = item.get("num_comments", item.get("reply_count", 0))

            if likes >= min_likes and likes >= min_score and rts >= min_rts and comments >= min_comments:
                filtered.append(item)

        return ModuleResult(
            success=True,
            data=filtered,
            metadata={"input_count": len(input_data.data), "output_count": len(filtered)},
        )


register(EngagementFilterModule())
