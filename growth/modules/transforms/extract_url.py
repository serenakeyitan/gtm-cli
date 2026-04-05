"""transform/extract_url — Find original source URLs from tweets/posts.

When a tweet references a blog post, paper, or repo, this module
extracts the original URL so you submit THAT instead of the tweet.
Critical for HN submissions (always submit original source).
"""

from __future__ import annotations

import re
import logging
from typing import Any

import httpx

from growth.modules.base import Module, ModuleResult, ModuleContext
from growth.modules.registry import register

log = logging.getLogger(__name__)

# Common URL shorteners to resolve
SHORTENER_DOMAINS = {"t.co", "bit.ly", "goo.gl", "ow.ly", "tinyurl.com", "buff.ly", "is.gd"}


class ExtractUrlModule(Module):
    name = "transform/extract_url"
    category = "transform"
    description = "Extract original source URLs from tweets (resolve t.co links)"
    param_schema = {
        "field": {"type": "str", "default": "text"},
        "resolve_shorteners": {"type": "bool", "default": True},
    }

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        if not input_data or not input_data.data:
            return ModuleResult(success=True, data=[])

        field = params.get("field", "text")
        resolve = params.get("resolve_shorteners", True)
        results = []
        errors = []

        for item in input_data.data:
            text = item.get(field, item.get("text", ""))
            urls = re.findall(r'https?://\S+', text)

            # Filter to external URLs (not twitter/x.com)
            external_urls = []
            for url in urls:
                url = url.rstrip(".,;:!?)")
                domain = _extract_domain(url)
                if domain and domain not in ("x.com", "twitter.com"):
                    external_urls.append(url)
                elif domain in SHORTENER_DOMAINS and resolve:
                    try:
                        resolved = await _resolve_url(url)
                        if resolved and _extract_domain(resolved) not in ("x.com", "twitter.com"):
                            external_urls.append(resolved)
                    except Exception as e:
                        errors.append(f"Failed to resolve {url}: {e}")

            new_item = dict(item)
            new_item["extracted_urls"] = external_urls
            new_item["source_url"] = external_urls[0] if external_urls else ""
            results.append(new_item)

        return ModuleResult(success=True, data=results, errors=errors,
                            metadata={"items_with_urls": sum(1 for r in results if r.get("source_url"))})


def _extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return ""


async def _resolve_url(url: str) -> str:
    """Resolve a shortened URL to its final destination."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as http:
            resp = await http.head(url)
            return str(resp.url)
    except Exception:
        return url


register(ExtractUrlModule())
