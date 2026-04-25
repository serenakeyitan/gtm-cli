"""Async Playwright-based Twitter/X client with session persistence.

Mirrors gtm/platforms/reddit/client.py. Used for posting tweets/threads
from the IdentityManager-registered Twitter accounts.

Selectors target the current x.com UI. Twitter A/B-tests the UI
frequently — selectors may need updating.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

REQUEST_DELAY = float(os.environ.get("TWITTER_REQUEST_DELAY", "8.0"))

DEFAULT_SESSION_DIR = "~/.config/gtm/identities/twitter/_session"


class TwitterClientError(Exception):
    pass


class TwitterAuthError(TwitterClientError):
    pass


class TwitterPostError(TwitterClientError):
    pass


class PlaywrightTwitterClient:
    """Browser-based Twitter client. One instance per session dir / identity."""

    def __init__(self, session_dir: str = DEFAULT_SESSION_DIR) -> None:
        self._session_dir = Path(session_dir).expanduser()
        self._storage_path = self._session_dir / "storage_state.json"
        self._pw = None
        self._browser = None
        self._context = None
        self._logged_in = False
        self._last_request_time: float = 0.0

    async def _init_browser(self, *, headless: bool | None = None) -> None:
        if self._browser is not None:
            return
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        if headless is None:
            headless = False

        self._browser = await self._pw.chromium.launch(
            channel="chrome",
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )

        ctx_kwargs: dict[str, Any] = {
            "user_agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "viewport": {"width": 1440, "height": 900},
            "locale": "en-US",
            "timezone_id": "America/Los_Angeles",
        }
        if self._storage_path.exists():
            ctx_kwargs["storage_state"] = str(self._storage_path)

        self._context = await self._browser.new_context(**ctx_kwargs)
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });
        """)

    async def close(self) -> None:
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._pw:
            await self._pw.stop()
            self._pw = None
        self._logged_in = False

    async def ensure_logged_in(self) -> None:
        if self._logged_in:
            return
        await self._init_browser()
        if not self._storage_path.exists():
            raise TwitterAuthError(
                f"Twitter session not found at {self._storage_path}.\n"
                f"Run: gtm auth twitter"
            )
        page = await self._context.new_page()
        try:
            await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)
            if not await self._check_logged_in(page):
                raise TwitterAuthError("Twitter session expired. Re-authenticate.")
            self._logged_in = True
            log.info("Twitter session verified — logged in")
        finally:
            await page.close()

    async def login_manual(self) -> None:
        await self._init_browser(headless=False)
        page = await self._context.new_page()
        try:
            await page.goto("https://x.com/i/flow/login", wait_until="domcontentloaded")
            log.info("Browser opened — log in manually, complete any 2FA/CAPTCHA.")
            for _ in range(150):
                try:
                    await page.wait_for_timeout(2000)
                except Exception:
                    raise TwitterAuthError("Browser closed before login completed.")
                if "/home" in page.url or await self._check_logged_in(page):
                    break
            else:
                raise TwitterAuthError("Login timed out after 5 minutes.")
            await page.wait_for_timeout(2000)
            self._session_dir.mkdir(parents=True, exist_ok=True)
            await self._context.storage_state(path=str(self._storage_path))
            self._logged_in = True
            log.info("Saved Twitter session to %s", self._storage_path)
        finally:
            await page.close()

    async def _check_logged_in(self, page) -> bool:
        for sel in [
            '[data-testid="SideNav_AccountSwitcher_Button"]',
            '[data-testid="AppTabBar_Home_Link"]',
            '[aria-label="Account menu"]',
        ]:
            try:
                if await page.locator(sel).first.is_visible(timeout=1000):
                    return True
            except Exception:
                pass
        return False

    async def _throttle(self) -> None:
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < REQUEST_DELAY:
            await asyncio.sleep(REQUEST_DELAY - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()

    async def post_tweet(self, text: str) -> dict[str, Any]:
        """Post a single tweet. Returns ``{tweet_id, url}``."""
        if len(text) > 280:
            raise TwitterPostError(f"Tweet exceeds 280 chars ({len(text)})")
        await self.ensure_logged_in()
        await self._throttle()

        page = await self._context.new_page()
        try:
            await page.goto("https://x.com/compose/post", wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            box = page.locator('[data-testid="tweetTextarea_0"]').first
            await box.wait_for(timeout=15000)
            await box.click()
            await box.fill(text)
            await page.wait_for_timeout(500)

            for sel in ['[data-testid="tweetButton"]', '[data-testid="tweetButtonInline"]']:
                btn = page.locator(sel).first
                try:
                    if await btn.is_visible(timeout=2000):
                        await btn.click()
                        break
                except Exception:
                    continue
            else:
                raise TwitterPostError("Could not find Post button.")

            await page.wait_for_url(re.compile(r"x\.com/.+/status/\d+"), timeout=20000)
            url = page.url
            m = re.search(r"/status/(\d+)", url)
            tweet_id = m.group(1) if m else ""
            return {"tweet_id": tweet_id, "url": url}
        finally:
            await page.close()

    async def post_thread(self, tweets: list[str]) -> list[dict[str, Any]]:
        """Post a thread by replying to each previous tweet."""
        if not tweets:
            raise TwitterPostError("Empty thread")
        results: list[dict[str, Any]] = []
        first = await self.post_tweet(tweets[0])
        results.append(first)
        for body in tweets[1:]:
            await self._throttle()
            reply = await self.reply_to(results[-1]["url"], body)
            results.append(reply)
        return results

    async def reply_to(self, parent_url: str, text: str) -> dict[str, Any]:
        if len(text) > 280:
            raise TwitterPostError(f"Reply exceeds 280 chars ({len(text)})")
        await self.ensure_logged_in()
        await self._throttle()

        page = await self._context.new_page()
        try:
            await page.goto(parent_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            reply_box = page.locator('[data-testid="tweetTextarea_0"]').first
            await reply_box.wait_for(timeout=15000)
            await reply_box.click()
            await reply_box.fill(text)
            await page.wait_for_timeout(500)

            for sel in ['[data-testid="tweetButtonInline"]', '[data-testid="tweetButton"]']:
                btn = page.locator(sel).first
                try:
                    if await btn.is_visible(timeout=2000):
                        await btn.click()
                        break
                except Exception:
                    continue
            else:
                raise TwitterPostError("Could not find Reply button.")

            await page.wait_for_timeout(3000)
            return {"tweet_id": "", "url": page.url, "parent": parent_url}
        finally:
            await page.close()

    async def check_tweet(self, tweet_url: str) -> dict[str, Any]:
        """Read public metrics + deletion status for a tweet."""
        await self.ensure_logged_in()
        await self._throttle()
        page = await self._context.new_page()
        try:
            await page.goto(tweet_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            body = (await page.content())[:50000]
            deleted = (
                "This post was deleted" in body
                or "Hmm...this page doesn't exist" in body
                or "This post is from a suspended account" in body
            )
            return {
                "url": tweet_url,
                "deleted": deleted,
                "raw_html_sample": body[:2000],
            }
        finally:
            await page.close()

    async def preflight(self) -> None:
        await self.ensure_logged_in()
        log.info("Twitter browser pre-flight: OK")


_clients_by_dir: dict[str, PlaywrightTwitterClient] = {}


def get_twitter_browser_client(session_dir: str | None = None) -> PlaywrightTwitterClient:
    """Return cached PlaywrightTwitterClient per session_dir."""
    if session_dir is None:
        session_dir = DEFAULT_SESSION_DIR
    key = str(Path(session_dir).expanduser())
    if key not in _clients_by_dir:
        _clients_by_dir[key] = PlaywrightTwitterClient(session_dir)
    return _clients_by_dir[key]


def get_twitter_browser_client_for_identity(name: str) -> PlaywrightTwitterClient:
    """Return cached PlaywrightTwitterClient for a registered identity name."""
    from gtm.identity.session import session_dir_for_identity
    session_dir = session_dir_for_identity(name, "twitter")
    return get_twitter_browser_client(session_dir)


def reset_twitter_browser_client() -> None:
    global _clients_by_dir
    _clients_by_dir = {}
