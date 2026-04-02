"""Hacker News platform adapter — implements the Platform interface.

Auth: Opens headed Chrome → user logs in manually (reCAPTCHA) → cookie saved.
Subsequent requests: httpx with saved cookie (no browser needed).
Search: Algolia HN API (free, no auth needed).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx

from growth.platforms.base import (
    HealthStatus,
    Platform,
    PostResult,
    SearchResult,
    register_platform,
)

log = logging.getLogger(__name__)

ALGOLIA_API = "https://hn.algolia.com/api/v1"


class HNPlatform(Platform):
    name = "hn"

    def _get_client(self, identity_dir: Path):
        from growth.platforms.hn.client import PlaywrightHNClient
        session_dir = identity_dir / "session"
        return PlaywrightHNClient(session_dir=str(session_dir))

    async def auth_interactive(self, identity_dir: Path, **kwargs) -> dict[str, Any]:
        """Open Chrome for manual HN login (reCAPTCHA required)."""
        from growth.platforms.hn.client import PlaywrightHNClient

        session_dir = identity_dir / "session"
        session_dir.mkdir(parents=True, exist_ok=True)

        client = PlaywrightHNClient(session_dir=str(session_dir))
        await client.login_manual()

        return {
            "platform": "hn",
            "username": kwargs.get("username", "unknown"),
            "auth_method": "browser",
        }

    async def health_check(self, identity_dir: Path) -> HealthStatus:
        from datetime import datetime
        try:
            client = self._get_client(identity_dir)
            await client.ensure_logged_in()
            return HealthStatus(healthy=True, reason="Cookie valid",
                                last_checked=datetime.now().isoformat())
        except Exception as e:
            return HealthStatus(healthy=False, reason=f"Cookie expired: {e}",
                                last_checked=datetime.now().isoformat())

    async def post(self, identity_dir: Path, content: str, **kwargs) -> PostResult:
        """Submit to Hacker News."""
        title = kwargs.get("title", "")
        url = kwargs.get("url", "")

        if not title:
            return PostResult(success=False, error="--title required for HN submissions")

        try:
            client = self._get_client(identity_dir)
            result = await client.submit_post(url or "", title)
            return PostResult(
                success=True,
                post_id=result.get("item_id", ""),
                url=result.get("url", ""),
                raw=result,
            )
        except Exception as e:
            return PostResult(success=False, error=str(e))

    async def search(self, identity_dir: Path, query: str, **kwargs) -> list[SearchResult]:
        """Search HN via Algolia API (free, no auth needed)."""
        count = kwargs.get("count", 20)

        try:
            async with httpx.AsyncClient() as http:
                resp = await http.get(
                    f"{ALGOLIA_API}/search",
                    params={"query": query, "tags": "story", "hitsPerPage": count},
                )
                data = resp.json()

            return [
                SearchResult(
                    id=str(hit.get("objectID", "")),
                    title=hit.get("title", ""),
                    url=hit.get("url", ""),
                    author=hit.get("author", ""),
                    score=hit.get("points", 0),
                    timestamp=hit.get("created_at", ""),
                    raw=hit,
                )
                for hit in data.get("hits", [])
            ]
        except Exception as e:
            log.error("HN search failed: %s", e)
            return []

    async def trending(self, identity_dir: Path, **kwargs) -> list[SearchResult]:
        """Get current HN front page stories."""
        count = kwargs.get("count", 30)

        try:
            async with httpx.AsyncClient() as http:
                resp = await http.get(
                    f"{ALGOLIA_API}/search",
                    params={"tags": "front_page", "hitsPerPage": count},
                )
                data = resp.json()

            return [
                SearchResult(
                    id=str(hit.get("objectID", "")),
                    title=hit.get("title", ""),
                    url=hit.get("url", ""),
                    author=hit.get("author", ""),
                    score=hit.get("points", 0),
                    timestamp=hit.get("created_at", ""),
                    raw=hit,
                )
                for hit in data.get("hits", [])
            ]
        except Exception as e:
            log.error("HN trending failed: %s", e)
            return []


_hn = HNPlatform()
register_platform(_hn)
