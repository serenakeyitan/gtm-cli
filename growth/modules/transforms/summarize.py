"""transform/summarize — Condense content for character limits.

Deterministic truncation with smart breaking, or LLM-powered summarization.
"""

from __future__ import annotations

import logging
from typing import Any

from growth.modules.base import Module, ModuleResult, ModuleContext
from growth.modules.registry import register

log = logging.getLogger(__name__)


class SummarizeModule(Module):
    name = "transform/summarize"
    category = "transform"
    description = "Condense content for character limits (smart truncation or LLM summary)"
    param_schema = {
        "max_length": {"type": "int", "default": 280},
        "field": {"type": "str", "default": "text"},
        "method": {"type": "str", "default": "truncate", "enum": ["truncate", "llm"]},
    }

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        if not input_data or not input_data.data:
            return ModuleResult(success=True, data=[])

        max_len = params.get("max_length", 280)
        field = params.get("field", "text")
        method = params.get("method", "truncate")
        results = []

        for item in input_data.data:
            text = item.get(field, "")
            new_item = dict(item)

            if len(text) <= max_len:
                results.append(new_item)
                continue

            if method == "llm":
                try:
                    summarized = await self._llm_summarize(text, max_len)
                    new_item[f"{field}_original"] = text
                    new_item[field] = summarized
                except Exception as e:
                    log.warning("LLM summarize failed, falling back to truncation: %s", e)
                    new_item[field] = self._smart_truncate(text, max_len)
            else:
                new_item[field] = self._smart_truncate(text, max_len)

            results.append(new_item)

        return ModuleResult(success=True, data=results,
                            metadata={"truncated": sum(1 for r in results if f"{field}_original" in r or len(r.get(field, "")) < len(input_data.data[0].get(field, "") if input_data.data else ""))})

    def _smart_truncate(self, text: str, max_len: int) -> str:
        """Truncate at sentence or word boundary."""
        if len(text) <= max_len:
            return text

        # Try to break at sentence boundary
        truncated = text[:max_len - 3]
        last_period = truncated.rfind(". ")
        if last_period > max_len * 0.5:
            return truncated[:last_period + 1]

        # Break at word boundary
        last_space = truncated.rfind(" ")
        if last_space > max_len * 0.5:
            return truncated[:last_space] + "..."

        return truncated + "..."

    async def _llm_summarize(self, text: str, max_len: int) -> str:
        """Use Claude to summarize text to fit within max_len."""
        from claude_code_sdk import query

        prompt = (
            f"Summarize this text in {max_len} characters or fewer. "
            f"Keep the key information. Output ONLY the summary.\n\n{text}"
        )
        result = await query(prompt=prompt, model="claude-sonnet-4-20250514", max_turns=1)
        for block in result:
            if hasattr(block, "content"):
                return block.content[:max_len]
        return self._smart_truncate(text, max_len)


register(SummarizeModule())
