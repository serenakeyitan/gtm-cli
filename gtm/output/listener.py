"""Social listener — monitor platforms for mentions, trends, and opportunities.

Runs a one-shot scan across platforms for a topic, returning structured results.
For continuous monitoring, run via cron or strategy scheduler (v0.3+).
"""

from __future__ import annotations

import logging
from typing import Any

from gtm.modules.base import ModuleResult, ModuleContext
from gtm.modules import registry

log = logging.getLogger(__name__)


async def listen(
    query: str,
    platforms: list[str] | None = None,
    count: int = 10,
    identity_dirs: dict[str, Any] | None = None,
) -> dict[str, list[dict]]:
    """Scan platforms for a topic. Returns results grouped by platform.

    Args:
        query: Search query
        platforms: ["twitter", "reddit", "hn"] or None for all
        count: Results per platform
        identity_dirs: {platform: Path} for auth-required sources

    Returns:
        {"twitter": [...], "reddit": [...], "hn": [...]}
    """
    platforms = platforms or ["twitter", "reddit", "hn"]
    identity_dirs = identity_dirs or {}
    results = {}

    for platform in platforms:
        try:
            if platform == "twitter":
                mod = registry.get("twitter/search")
                ctx = ModuleContext(identity_dir=identity_dirs.get("twitter"))
                r = await mod.run(None, {"query": query, "count": count}, ctx)
            elif platform == "reddit":
                mod = registry.get("reddit/search")
                r = await mod.run(None, {"query": query, "count": count}, ModuleContext())
            elif platform == "hn":
                mod = registry.get("hn/search")
                r = await mod.run(None, {"query": query, "count": count}, ModuleContext())
            else:
                log.warning("Unknown platform: %s (valid: twitter, reddit, hn)", platform)
                results[platform] = []
                continue

            results[platform] = r.data if r.success else []
            log.info("Listen [%s]: %d results for '%s'", platform, len(results[platform]), query)

        except Exception as e:
            log.warning("Listen [%s] failed: %s", platform, e)
            results[platform] = []

    return results
