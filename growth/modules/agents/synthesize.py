"""agent/synthesize — LLM-powered analysis of collected data.

The MINIMAL LLM module: takes pre-fetched data and asks Claude to
analyze/rank/synthesize. No tool calls, no MCP, just one prompt.

This is the "5% LLM" piece — everything else is deterministic modules.
Costs ~$0.01 per run instead of $0.50-2.00 for a full agent.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from growth.modules.base import Module, ModuleResult, ModuleContext
from growth.modules.registry import register

log = logging.getLogger(__name__)


class SynthesizeModule(Module):
    name = "agent/synthesize"
    category = "agent"
    description = "LLM analysis of collected data — rank, synthesize, pick top ideas (1-2 API calls)"
    requires_auth = False
    param_schema = {
        "task": {"type": "str", "required": True},
        "output_count": {"type": "int", "default": 10},
    }

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        if not input_data or not input_data.data:
            return ModuleResult(success=True, data=[])

        if context.dry_run:
            return ModuleResult(success=True, data=input_data.data,
                                metadata={"note": f"Would analyze {len(input_data.data)} items with LLM"})

        task = params.get("task", "Analyze and rank these items")
        output_count = params.get("output_count", 10)

        try:
            from claude_code_sdk import query

            # Prepare data summary (truncate to avoid context overflow)
            items_json = json.dumps(input_data.data[:50], indent=1, default=str)
            if len(items_json) > 30000:
                items_json = items_json[:30000] + "\n... (truncated)"

            prompt = (
                f"{task}\n\n"
                f"## Data ({len(input_data.data)} items)\n"
                f"```json\n{items_json}\n```\n\n"
                f"## Instructions\n"
                f"Select the top {output_count} items. For each, explain why.\n"
                f"Output a JSON array of the selected items with an added 'reason' field.\n"
                f"Output ONLY the JSON array, nothing else."
            )

            from claude_code_sdk import ClaudeCodeOptions
            options = ClaudeCodeOptions(model="claude-sonnet-4-20250514", max_turns=1)

            result_text = ""
            async for message in query(prompt=prompt, options=options):
                from growth.modules.transforms.rewrite import _extract_text
                text = _extract_text(message)
                if text:
                    result_text = text
                    break

            # Parse JSON from response
            if result_text:
                # Find JSON array in response
                start = result_text.find("[")
                end = result_text.rfind("]") + 1
                if start >= 0 and end > start:
                    selected = json.loads(result_text[start:end])
                    return ModuleResult(success=True, data=selected,
                                        metadata={"input": len(input_data.data), "selected": len(selected), "api_calls": 1})

            # Fallback: return top N by engagement
            log.warning("LLM synthesis failed to return JSON, falling back to engagement sort")
            sorted_data = sorted(input_data.data,
                                 key=_safe_engagement_score,
                                 reverse=True)
            return ModuleResult(success=True, data=sorted_data[:output_count],
                                metadata={"fallback": True})

        except ImportError:
            return ModuleResult(success=False, errors=["claude-code-sdk not installed. Run: pip install growth-cli[agents]"])
        except Exception as e:
            # On ANY failure (rate limit, etc.), fall back to deterministic ranking
            log.warning("LLM synthesis failed (%s), falling back to engagement sort", e)
            try:
                sorted_data = sorted(input_data.data,
                                     key=_safe_engagement_score,
                                     reverse=True)
                return ModuleResult(success=True, data=sorted_data[:output_count],
                                    metadata={"fallback": True, "error": str(e)})
            except Exception as sort_err:
                # Even sort failed — return unsorted data (absolute last resort)
                log.error("Fallback sort also failed: %s. Returning unsorted.", sort_err)
                return ModuleResult(success=True, data=input_data.data[:output_count],
                                    metadata={"fallback": True, "unsorted": True})


def _safe_engagement_score(item: dict) -> int:
    """Extract a numeric engagement score from any item, safely.

    Handles None, strings, missing keys — always returns int.
    """
    for field in ("favorite_count", "score", "points", "likes"):
        val = item.get(field)
        if val is not None:
            try:
                return int(val)
            except (ValueError, TypeError):
                continue
    return 0


register(SynthesizeModule())
