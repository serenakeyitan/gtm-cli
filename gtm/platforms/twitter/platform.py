"""Twitter platform adapter — implements the Platform interface."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from gtm.platforms.base import (
    EngageResult,
    HealthStatus,
    Platform,
    PostResult,
    SearchResult,
    register_platform,
)
from gtm.platforms.twitter.client import (
    TwitterClient,
    TwitterAuthError,
    TwitterClientError,
)

log = logging.getLogger(__name__)


class TwitterPlatform(Platform):
    """Twitter adapter using twikit + cookies.

    Auth: Username + email + password → programmatic login → cookies saved.
    No browser needed.
    """

    name = "twitter"

    def _get_client(self, identity_dir: Path) -> TwitterClient:
        cookie_path = identity_dir / "cookies.json"
        return TwitterClient(cookie_path=cookie_path)

    async def auth_interactive(self, identity_dir: Path, **kwargs) -> dict[str, Any]:
        """Log in with username/email/password, save cookies."""
        username = kwargs.get("username")
        email = kwargs.get("email")
        password = kwargs.get("password")

        if not all([username, email, password]):
            raise TwitterAuthError("Twitter auth requires: username, email, password")

        identity_dir.mkdir(parents=True, exist_ok=True)
        client = self._get_client(identity_dir)
        await client.login_and_save(username, email, password)

        return {
            "platform": "twitter",
            "username": username,
            "auth_method": "password",
        }

    async def health_check(self, identity_dir: Path) -> HealthStatus:
        """Verify cookies are still valid by making a lightweight API call."""
        from datetime import datetime

        try:
            client = self._get_client(identity_dir)
            await client.preflight()
            # Try a lightweight call to verify cookies aren't expired
            await client.search("test", count=1)
            return HealthStatus(
                healthy=True,
                reason="Cookies valid",
                last_checked=datetime.now().isoformat(),
            )
        except (TwitterAuthError, TwitterClientError) as e:
            return HealthStatus(
                healthy=False,
                reason=f"Cookies expired or invalid: {e}",
                last_checked=datetime.now().isoformat(),
            )

    async def post(self, identity_dir: Path, content: str, **kwargs) -> PostResult:
        """Post a tweet."""
        try:
            client = self._get_client(identity_dir)
            result = await client.post_tweet(content)
            tweet_id = result.get("id", "")
            screen_name = result.get("user", {}).get("screen_name", "")
            return PostResult(
                success=True,
                post_id=str(tweet_id),
                url=f"https://x.com/{screen_name}/status/{tweet_id}" if tweet_id else None,
                raw=result,
            )
        except TwitterClientError as e:
            _raise_if_expired(e, identity_dir)
            return PostResult(success=False, error=str(e))

    async def search(self, identity_dir: Path, query: str, **kwargs) -> list[SearchResult]:
        """Search tweets."""
        count = kwargs.get("count", 20)
        try:
            client = self._get_client(identity_dir)
            tweets = await client.search(query, count=count)
            return [
                SearchResult(
                    id=t["id"],
                    text=t["text"],
                    author=t.get("user", {}).get("screen_name", ""),
                    score=t.get("favorite_count", 0),
                    timestamp=t.get("created_at", ""),
                    raw=t,
                )
                for t in tweets
            ]
        except TwitterClientError as e:
            _raise_if_expired(e, identity_dir)
            log.error("Twitter search failed: %s", e)
            return []

    async def engage(self, identity_dir: Path, target_id: str, action: str, **kwargs) -> EngageResult:
        """Like or retweet a tweet."""
        try:
            client = self._get_client(identity_dir)
            if action == "like":
                await client.like_tweet(target_id)
            elif action in ("retweet", "rt"):
                await client.retweet(target_id)
            else:
                return EngageResult(success=False, error=f"Unknown action: {action}")
            return EngageResult(success=True)
        except TwitterClientError as e:
            _raise_if_expired(e, identity_dir)
            return EngageResult(success=False, error=str(e))

    async def reply(self, identity_dir: Path, target_id: str, content: str, **kwargs) -> PostResult:
        """Reply to a tweet."""
        try:
            client = self._get_client(identity_dir)
            result = await client.reply_to_tweet(target_id, content)
            tweet_id = result.get("id", "")
            return PostResult(success=True, post_id=str(tweet_id), raw=result)
        except TwitterClientError as e:
            _raise_if_expired(e, identity_dir)
            return PostResult(success=False, error=str(e))


def _raise_if_expired(error: Exception, identity_dir: Path) -> None:
    """Detect expired cookies and raise a clear auth error with re-auth instructions."""
    err_str = str(error).lower()
    expired_signals = ["401", "403", "404", "unauthorized", "forbidden", "auth"]
    if any(sig in err_str for sig in expired_signals):
        username = identity_dir.name
        raise TwitterAuthError(
            f"Twitter session expired for '{username}'.\n"
            f"\n"
            f"  Re-authenticate:  gtm auth twitter\n"
        )


# Register on import
_twitter = TwitterPlatform()
register_platform(_twitter)
