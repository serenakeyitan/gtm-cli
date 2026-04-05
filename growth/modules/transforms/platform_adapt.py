"""transform/platform_adapt — Format content for platform-specific requirements.

Deterministic transforms (no LLM needed):
- Twitter: truncate to 280 chars, add hashtags
- Reddit: format as markdown, add flair hints
- HN: clean title, add [video]/[pdf] suffixes
"""

from __future__ import annotations

import re
import logging
from typing import Any

from growth.modules.base import Module, ModuleResult, ModuleContext
from growth.modules.registry import register

log = logging.getLogger(__name__)


class PlatformAdaptModule(Module):
    name = "transform/platform_adapt"
    category = "transform"
    description = "Format content for platform requirements (char limits, markdown, etc.)"
    param_schema = {
        "platform": {"type": "str", "required": True, "enum": ["reddit", "hn", "twitter"]},
        "field": {"type": "str", "default": "text"},
    }

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        if not input_data or not input_data.data:
            return ModuleResult(success=True, data=[])

        platform = params["platform"]
        field = params.get("field", "text")
        results = []

        for item in input_data.data:
            new_item = dict(item)
            text = str(item.get(field, item.get("title", item.get("text", ""))) or "")

            if platform == "twitter":
                new_item[field] = self._adapt_twitter(text)
            elif platform == "reddit":
                new_item[field] = self._adapt_reddit(text, item)
            elif platform == "hn":
                new_item = self._adapt_hn(new_item, text)

            new_item["_adapted_for"] = platform
            results.append(new_item)

        return ModuleResult(success=True, data=results,
                            metadata={"platform": platform, "adapted": len(results)})

    def _adapt_twitter(self, text: str) -> str:
        """Truncate to 280 chars, preserve last URL if present."""
        if len(text) <= 280:
            return text

        urls = re.findall(r'https?://\S+', text)
        if urls:
            last_url = urls[-1]
            max_text = 280 - len(last_url) - 2  # space + url
            return text[:max_text].rstrip() + " " + last_url
        return text[:277] + "..."

    def _adapt_reddit(self, text: str, item: dict) -> str:
        """Ensure markdown formatting, add source link if available."""
        source_url = item.get("source_url", item.get("url", ""))
        if source_url and source_url not in text:
            text += f"\n\n[Source]({source_url})"
        return text

    def _adapt_hn(self, item: dict, text: str) -> dict:
        """Clean title for HN: no ALL CAPS, no clickbait, add [video]/[pdf]."""
        title = item.get("title", text)

        # Remove ALL CAPS words (except common acronyms)
        acronyms = {"AI", "API", "CLI", "GPU", "LLM", "ML", "NLP", "OS", "UI", "UX", "HN", "YC", "AWS", "SSH"}
        words = title.split()
        cleaned = []
        for word in words:
            stripped = word.strip(".,!?:;")
            if stripped.isupper() and len(stripped) > 3 and stripped not in acronyms:
                cleaned.append(word.capitalize())
            else:
                cleaned.append(word)
        title = " ".join(cleaned)

        # Remove exclamation marks
        title = title.replace("!", "")

        # Add suffix for video/pdf URLs
        url = item.get("source_url", item.get("url", ""))
        if url:
            if any(x in url.lower() for x in ["youtube.com", "vimeo.com", "youtu.be", ".mp4"]):
                if "[video]" not in title.lower():
                    title += " [video]"
            elif url.lower().endswith(".pdf"):
                if "[pdf]" not in title.lower():
                    title += " [pdf]"

        item["title"] = title.strip()
        return item


register(PlatformAdaptModule())
