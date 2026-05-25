"""Reddit platform adapter — implements the Platform interface.

Auth: Opens headed Chrome → user logs in manually → Playwright session saved.
Posting: Uses Reddit's OAuth API via browser context (fetch + token_v2 cookie).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from gtm.platforms.base import (
    HealthStatus,
    Platform,
    PostResult,
    SearchResult,
    register_platform,
)

log = logging.getLogger(__name__)


class RedditPlatform(Platform):
    name = "reddit"

    def _get_client(self, identity_dir: Path):
        from gtm.platforms.reddit.client import PlaywrightRedditClient
        session_dir = identity_dir / "session"
        return PlaywrightRedditClient(session_dir=str(session_dir))

    async def auth_interactive(self, identity_dir: Path, **kwargs) -> dict[str, Any]:
        """Open Chrome for manual Reddit login."""
        from gtm.platforms.reddit.client import PlaywrightRedditClient

        session_dir = identity_dir / "session"
        session_dir.mkdir(parents=True, exist_ok=True)

        client = PlaywrightRedditClient(session_dir=str(session_dir))
        await client.login_manual()
        await client.close()

        return {
            "platform": "reddit",
            "username": kwargs.get("username", "unknown"),
            "auth_method": "browser",
        }

    async def health_check(self, identity_dir: Path) -> HealthStatus:
        from datetime import datetime
        client = self._get_client(identity_dir)
        try:
            await client.preflight()
            return HealthStatus(healthy=True, reason="Session valid",
                                last_checked=datetime.now().isoformat())
        except Exception as e:
            return HealthStatus(healthy=False, reason=f"Session expired: {e}",
                                last_checked=datetime.now().isoformat())
        finally:
            await client.close()

    async def post(self, identity_dir: Path, content: str, **kwargs) -> PostResult:
        """Submit a post to a subreddit."""
        subreddit = kwargs.get("subreddit", "")
        title = kwargs.get("title", "")
        url = kwargs.get("url", "")
        flair_text = kwargs.get("flair_text") or kwargs.get("flair", "")

        if not subreddit:
            return PostResult(success=False, error="--sub required for Reddit posts")
        if not title:
            return PostResult(success=False, error="--title required for Reddit posts")

        client = self._get_client(identity_dir)
        try:
            if url:
                result = await client.submit_api_post(
                    subreddit, title, url=url, kind="link"
                )
            else:
                # Use browser-based submit so flair can be selected via UI
                # (API submit requires a flair_id which we don't always have).
                result = await client.submit_post(
                    subreddit, title, content, flair_text=flair_text or None
                )
            return PostResult(
                success=True,
                post_id=result.get("post_id", ""),
                url=result.get("url", ""),
                raw=result,
            )
        except Exception as e:
            return PostResult(success=False, error=str(e))
        finally:
            await client.close()

    async def search(self, identity_dir: Path, query: str, **kwargs) -> list[SearchResult]:
        """Search Reddit via public JSON API (no auth needed)."""
        import httpx

        count = kwargs.get("count", 20)
        subreddit = kwargs.get("subreddit")

        if subreddit:
            url = f"https://www.reddit.com/r/{subreddit}/search.json?q={query}&restrict_sr=1&limit={count}"
        else:
            url = f"https://www.reddit.com/search.json?q={query}&limit={count}"

        try:
            async with httpx.AsyncClient() as http:
                resp = await http.get(url, headers={"User-Agent": "gtm-cli/0.1"})
                data = resp.json()

            posts = data.get("data", {}).get("children", [])
            return [
                SearchResult(
                    id=p["data"].get("id", ""),
                    title=p["data"].get("title", ""),
                    text=p["data"].get("selftext", "")[:200],
                    url=f"https://reddit.com{p['data'].get('permalink', '')}",
                    author=p["data"].get("author", ""),
                    score=p["data"].get("score", 0),
                    raw=p["data"],
                )
                for p in posts
            ]
        except Exception as e:
            log.error("Reddit search failed: %s", e)
            return []


_reddit = RedditPlatform()
register_platform(_reddit)
