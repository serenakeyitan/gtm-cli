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
            # Support both raw platform keys AND normalized keys from traction tracker
            likes = item.get("favorite_count") or item.get("likes")
            score = item.get("score") or item.get("points")
            rts = item.get("retweet_count") or item.get("retweets")
            comments = item.get("num_comments") or item.get("reply_count") or item.get("comments")

            # Only apply a threshold if the item has that field
            if min_likes and likes is not None and likes < min_likes:
                continue
            if min_score and score is not None and score < min_score:
                continue
            if min_rts and rts is not None and rts < min_rts:
                continue
            if min_comments and comments is not None and comments < min_comments:
                continue
            filtered.append(item)

        return ModuleResult(
            success=True,
            data=filtered,
            metadata={"input_count": len(input_data.data), "output_count": len(filtered)},
        )


register(EngagementFilterModule())
