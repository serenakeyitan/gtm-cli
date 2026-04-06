"""transform/rewrite — LLM rewrite content for platform-specific tone.

Uses the style guide from prompts/style_guide.md to adapt content
for Reddit (organic), HN (technical), or Twitter (engagement).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from gtm.modules.base import Module, ModuleResult, ModuleContext
from gtm.modules.registry import register

log = logging.getLogger(__name__)


class RewriteModule(Module):
    name = "transform/rewrite"
    category = "transform"
    description = "LLM rewrite content for platform-specific tone (organic, technical, engagement)"
    param_schema = {
        "platform": {"type": "str", "required": True, "enum": ["reddit", "hn", "twitter"]},
        "tone": {"type": "str", "default": "auto"},
        "field": {"type": "str", "default": "text"},
    }

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        if not input_data or not input_data.data:
            return ModuleResult(success=True, data=[])

        platform = params["platform"]
        field = params.get("field", "text")

        # Load platform-specific style rules
        from gtm.agents.base import load_style_guide
        style_rules = load_style_guide(platform)

        if not style_rules:
            log.warning("No style guide found for platform: %s", platform)
            return ModuleResult(success=True, data=input_data.data)

        # Try LLM rewrite via Claude SDK
        try:
            rewritten = await self._llm_rewrite(input_data.data, field, platform, style_rules)
            return ModuleResult(success=True, data=rewritten,
                                metadata={"platform": platform, "rewritten": len(rewritten)})
        except ImportError:
            log.warning("claude-code-sdk not installed. Returning original content. Run: pip install gtm-cli[agents]")
            return ModuleResult(success=True, data=input_data.data,
                                metadata={"platform": platform, "rewritten": 0, "note": "LLM not available"})
        except Exception as e:
            log.error("LLM rewrite failed: %s. Returning original.", e)
            return ModuleResult(success=True, data=input_data.data, errors=[str(e)])

    async def _llm_rewrite(self, items: list[dict], field: str, platform: str, style_rules: str) -> list[dict]:
        """Use Claude to rewrite each item's text field for the target platform."""
        from claude_code_sdk import query

        rewritten = []
        for item in items:
            original = str(item.get(field, item.get("title", item.get("text", ""))) or "")
            if not original:
                rewritten.append(item)
                continue

            prompt = (
                f"Rewrite this content for {platform}. Follow the style rules EXACTLY.\n\n"
                f"## Style Rules\n{style_rules}\n\n"
                f"## Original Content\n{original}\n\n"
                f"## Rewritten (output ONLY the rewritten text, nothing else)"
            )

            try:
                from claude_code_sdk import ClaudeCodeOptions
                options = ClaudeCodeOptions(model="claude-sonnet-4-20250514", max_turns=1)

                rewritten_text = ""
                async for message in query(prompt=prompt, options=options):
                    rewritten_text = _extract_text(message)
                    if rewritten_text:
                        break

                new_item = dict(item)
                new_item[f"{field}_original"] = original
                new_item[field] = rewritten_text or original
                new_item["_rewritten_for"] = platform
                rewritten.append(new_item)
            except Exception as e:
                log.warning("Rewrite failed for item: %s", e)
                rewritten.append(item)

        return rewritten


def _extract_text(message) -> str:
    """Extract plain text from a Claude SDK message.

    Handles AssistantMessage (content=[TextBlock(text=...)]),
    ResultMessage (result=str), and plain string content.
    """
    # ResultMessage
    if hasattr(message, "result") and isinstance(message.result, str):
        return message.result

    # AssistantMessage with content blocks
    if hasattr(message, "content"):
        content = message.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts = []
            for block in content:
                if hasattr(block, "text"):
                    texts.append(block.text)
                elif isinstance(block, str):
                    texts.append(block)
            return "\n".join(texts)

    return ""


register(RewriteModule())
