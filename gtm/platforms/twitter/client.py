"""Async Twikit client wrapper with rate-limiting and cookie management.

Migrated from growth-sop-pipeline/utils/twikit_client.py.
Uses the phin/twikit fork (codeberg.org/phin/twikit) which stays
current with Twitter's detection.

Auth method: Username + email + password → programmatic login → cookies saved.
No browser needed.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from twikit import Client as TwikitClient
from twikit.errors import (
    TooManyRequests,
    Unauthorized,
    BadRequest,
)

log = logging.getLogger(__name__)

# Minimum seconds between consecutive Twitter API calls.
REQUEST_DELAY = float(os.environ.get("GTM_TWITTER_DELAY", "8.0"))

# How long to wait (seconds) after a 429 before retrying.
RATE_LIMIT_BACKOFF = float(os.environ.get("GTM_TWITTER_BACKOFF", "90.0"))


class TwitterClientError(Exception):
    """Base error for all Twitter client operations."""


class TwitterAuthError(TwitterClientError):
    """Raised when authentication fails or cookies are missing/expired."""


class TwitterRateLimitError(TwitterClientError):
    """Raised when Twitter returns HTTP 429."""


class TwitterClient:
    """Async wrapper around twikit.Client.

    Usage::

        client = TwitterClient(cookie_path=Path("~/.config/gtm/identities/twitter/handle/cookies.json"))
        await client.ensure_logged_in()
        tweets = await client.search("AI tools", count=20)
    """

    def __init__(self, cookie_path: Path) -> None:
        self._cookie_path = Path(cookie_path).expanduser()
        self._client = TwikitClient(language="en-US")
        self._logged_in = False
        self._last_request_time: float = 0.0

    # ── Auth ──────────────────────────────────────────────────────────

    async def ensure_logged_in(self) -> None:
        """Load cookies from disk. Raises TwitterAuthError if missing."""
        if self._logged_in:
            return
        if not self._cookie_path.exists():
            raise TwitterAuthError(
                f"Twitter cookies not found at {self._cookie_path}.\n"
                f"Run:  gtm auth twitter"
            )
        try:
            self._client.load_cookies(str(self._cookie_path))
            self._logged_in = True
            log.info("Loaded Twitter cookies from %s", self._cookie_path)
        except Exception as e:
            raise TwitterAuthError(f"Failed to load Twitter cookies: {e}") from e

    async def login_and_save(
        self,
        username: str,
        email: str,
        password: str,
    ) -> None:
        """Interactive login — generates and saves cookies."""
        try:
            await self._client.login(
                auth_info_1=username,
                auth_info_2=email,
                password=password,
            )
            self._cookie_path.parent.mkdir(parents=True, exist_ok=True)
            self._client.save_cookies(str(self._cookie_path))
            self._logged_in = True
            log.info("Logged in and saved cookies to %s", self._cookie_path)
        except Exception as e:
            raise TwitterAuthError(f"Login failed: {e}") from e

    async def preflight(self) -> None:
        """Verify auth works by loading cookies. Raises on failure."""
        await self.ensure_logged_in()
        log.info("Twitter pre-flight check: OK")

    # ── Rate-limit helper ─────────────────────────────────────────────

    async def _throttle(self) -> None:
        """Sleep if needed to respect REQUEST_DELAY between calls."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < REQUEST_DELAY:
            wait = REQUEST_DELAY - elapsed
            log.debug("Throttling %.1fs before next Twitter call", wait)
            await asyncio.sleep(wait)
        self._last_request_time = asyncio.get_event_loop().time()

    async def _retry_on_rate_limit(self, label: str, coro_fn):
        """Call coro_fn(); on 429, back off and retry once."""
        try:
            return await coro_fn()
        except TooManyRequests:
            log.warning(
                "Rate limited on %s — backing off %.0fs then retrying",
                label, RATE_LIMIT_BACKOFF,
            )
            await asyncio.sleep(RATE_LIMIT_BACKOFF)
            self._last_request_time = 0.0
            return await coro_fn()

    # ── Public API ────────────────────────────────────────────────────

    async def search(self, query: str, count: int = 20) -> list[dict[str, Any]]:
        """Search tweets by query. Returns list of dicts."""
        await self.ensure_logged_in()
        await self._throttle()
        try:
            results = await self._retry_on_rate_limit(
                f"search({query!r})",
                lambda: self._client.search_tweet(query, product="Latest", count=count),
            )
            return [_tweet_to_dict(t) for t in results]
        except TooManyRequests as e:
            raise TwitterRateLimitError(f"Rate limit hit on search: {e}") from e
        except (Unauthorized, BadRequest) as e:
            raise TwitterAuthError(f"Auth error on search: {e}") from e
        except Exception as e:
            raise TwitterClientError(f"Search failed: {e}") from e

    async def get_user_tweets(self, username: str, count: int = 20) -> list[dict[str, Any]]:
        """Fetch recent tweets from a user by screen name."""
        await self.ensure_logged_in()
        await self._throttle()
        try:
            user = await self._retry_on_rate_limit(
                f"lookup({username})",
                lambda: self._client.get_user_by_screen_name(username),
            )
            await self._throttle()
            results = await self._retry_on_rate_limit(
                f"tweets({username})",
                lambda: self._client.get_user_tweets(user.id, tweet_type="Tweets", count=count),
            )
            return [_tweet_to_dict(t) for t in results]
        except TooManyRequests as e:
            raise TwitterRateLimitError(f"Rate limit on get_user_tweets({username}): {e}") from e
        except (Unauthorized, BadRequest) as e:
            raise TwitterAuthError(f"Auth error on get_user_tweets({username}): {e}") from e
        except KeyError as e:
            log.warning("No tweet entries for @%s (KeyError: %s) — skipping", username, e)
            return []
        except Exception as e:
            raise TwitterClientError(f"get_user_tweets({username}) failed: {e}") from e

    async def get_tweet(self, tweet_id: str) -> dict[str, Any]:
        """Fetch a single tweet by ID."""
        await self.ensure_logged_in()
        await self._throttle()
        try:
            tweet = await self._retry_on_rate_limit(
                f"get_tweet({tweet_id})",
                lambda: self._client.get_tweet_by_id(tweet_id),
            )
            return _tweet_to_dict(tweet)
        except TooManyRequests as e:
            raise TwitterRateLimitError(f"Rate limit on get_tweet: {e}") from e
        except (Unauthorized, BadRequest) as e:
            raise TwitterAuthError(f"Auth error on get_tweet: {e}") from e
        except Exception as e:
            raise TwitterClientError(f"get_tweet({tweet_id}) failed: {e}") from e

    async def post_tweet(self, text: str) -> dict[str, Any]:
        """Post a tweet. Returns dict with tweet info."""
        await self.ensure_logged_in()
        await self._throttle()
        try:
            tweet = await self._retry_on_rate_limit(
                "post_tweet",
                lambda: self._client.create_tweet(text=text),
            )
            return _tweet_to_dict(tweet)
        except TooManyRequests as e:
            raise TwitterRateLimitError(f"Rate limit on post_tweet: {e}") from e
        except (Unauthorized, BadRequest) as e:
            raise TwitterAuthError(f"Auth error on post_tweet: {e}") from e
        except Exception as e:
            raise TwitterClientError(f"post_tweet failed: {e}") from e

    async def like_tweet(self, tweet_id: str) -> None:
        """Like a tweet by ID."""
        await self.ensure_logged_in()
        await self._throttle()
        try:
            await self._retry_on_rate_limit(
                f"like({tweet_id})",
                lambda: self._client.favorite_tweet(tweet_id),
            )
        except Exception as e:
            raise TwitterClientError(f"like_tweet({tweet_id}) failed: {e}") from e

    async def retweet(self, tweet_id: str) -> None:
        """Retweet by ID."""
        await self.ensure_logged_in()
        await self._throttle()
        try:
            await self._retry_on_rate_limit(
                f"retweet({tweet_id})",
                lambda: self._client.retweet(tweet_id),
            )
        except Exception as e:
            raise TwitterClientError(f"retweet({tweet_id}) failed: {e}") from e

    async def follow_user(self, user_id: str) -> None:
        """Follow a user by ID."""
        await self.ensure_logged_in()
        await self._throttle()
        try:
            await self._retry_on_rate_limit(
                f"follow({user_id})",
                lambda: self._client.follow_user(user_id),
            )
        except Exception as e:
            raise TwitterClientError(f"follow_user({user_id}) failed: {e}") from e

    async def reply_to_tweet(self, tweet_id: str, text: str) -> dict[str, Any]:
        """Reply to a tweet."""
        await self.ensure_logged_in()
        await self._throttle()
        try:
            tweet = await self._retry_on_rate_limit(
                f"reply({tweet_id})",
                lambda: self._client.create_tweet(text=text, reply_to=tweet_id),
            )
            return _tweet_to_dict(tweet)
        except Exception as e:
            raise TwitterClientError(f"reply_to_tweet({tweet_id}) failed: {e}") from e


# ── Helpers ───────────────────────────────────────────────────────────

def _tweet_to_dict(tweet: Any) -> dict[str, Any]:
    """Convert a twikit Tweet object to a plain dict."""
    return {
        "id": tweet.id,
        "text": tweet.text,
        "created_at": tweet.created_at,
        "user": {
            "id": tweet.user.id if tweet.user else None,
            "screen_name": tweet.user.screen_name if tweet.user else None,
            "name": tweet.user.name if tweet.user else None,
            "followers_count": tweet.user.followers_count if tweet.user else None,
        },
        "favorite_count": tweet.favorite_count,
        "retweet_count": tweet.retweet_count,
        "reply_count": tweet.reply_count,
        "quote_count": getattr(tweet, "quote_count", None),
        "view_count": getattr(tweet, "view_count", None),
        "lang": getattr(tweet, "lang", None),
    }


# ── Module-level singleton ────────────────────────────────────────────

_default_client: TwitterClient | None = None


def get_twitter_client(cookie_path: str | None = None) -> TwitterClient:
    """Return (or create) the module-level TwitterClient singleton."""
    global _default_client
    if _default_client is None:
        if cookie_path is None:
            # Find the first available Twitter identity
            from gtm.config import IDENTITIES_DIR
            twitter_dir = IDENTITIES_DIR / "twitter"
            if twitter_dir.exists():
                for d in sorted(twitter_dir.iterdir()):
                    cp = d / "cookies.json"
                    if d.is_dir() and not d.name.startswith("_") and cp.exists():
                        cookie_path = str(cp)
                        break
            if cookie_path is None:
                cookie_path = "~/.config/gtm/identities/twitter/default/cookies.json"
        _default_client = TwitterClient(Path(cookie_path))
    return _default_client


def reset_twitter_client() -> None:
    """Reset the singleton — useful for testing."""
    global _default_client
    _default_client = None
