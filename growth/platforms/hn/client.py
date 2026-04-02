"""Async Playwright-based Hacker News client with session persistence.

Follows the same patterns as playwright_reddit_client.py:
- Singleton getter with reset function
- Cookie/session persistence to disk
- Rate limiting between requests
- Custom exception hierarchy

HN requires reCAPTCHA on login, so the user must log in manually once
in a headed browser. After that, the session cookie is reused for all
subsequent requests via HTTP (no browser needed for posting).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

# Minimum seconds between consecutive HN actions.
REQUEST_DELAY = float(os.environ.get("HN_REQUEST_DELAY", "30.0"))

# Default session storage path.
DEFAULT_SESSION_DIR = "~/.config/growth/identities/hn/_session"

HN_BASE = "https://news.ycombinator.com"


class HNClientError(Exception):
    """Base error for all HN client operations."""
    pass


class HNAuthError(HNClientError):
    """Raised when authentication fails or session is missing/expired."""
    pass


class HNPostError(HNClientError):
    """Raised when a post submission fails."""
    pass


class HNRateLimitError(HNClientError):
    """Raised when HN throttles actions."""
    pass


class PlaywrightHNClient:
    """Async Playwright-based HN client for login, then HTTP for actions.

    Login requires a headed browser (reCAPTCHA). After login, the
    session cookie (user=...) is saved and reused via httpx for all
    subsequent actions (submit, comment, check).

    Usage::

        client = PlaywrightHNClient()
        await client.ensure_logged_in()
        result = await client.submit_post("https://example.com", "Show HN: Cool Thing")
    """

    def __init__(self, session_dir: str = DEFAULT_SESSION_DIR) -> None:
        self._session_dir = Path(session_dir).expanduser()
        self._cookie_path = self._session_dir / "hn_cookie.json"
        self._logged_in = False
        self._cookie: str | None = None  # The "user" cookie value
        self._last_request_time: float = 0.0

    # ── Auth ─────────────────────────────────────────────────────────

    async def ensure_logged_in(self) -> None:
        """Load saved cookie from disk. Raises HNAuthError if missing/expired."""
        if self._logged_in and self._cookie:
            return

        if not self._cookie_path.exists():
            raise HNAuthError(
                f"HN session not found at {self._cookie_path}.\n"
                f"Run:  growth auth hn"
            )

        with open(self._cookie_path) as f:
            data = json.load(f)
        self._cookie = data.get("user_cookie")

        if not self._cookie:
            raise HNAuthError("HN cookie file exists but 'user_cookie' is empty.")

        # Verify the cookie works by fetching the user page.
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{HN_BASE}/user",
                cookies={"user": self._cookie},
                follow_redirects=True,
                timeout=15,
            )
            if "login" in resp.url.path or "Bad login" in resp.text:
                raise HNAuthError(
                    "HN session expired. Please re-authenticate.\n"
                    "Run:  growth auth hn"
                )

        self._logged_in = True
        log.info("HN session verified — logged in")

    async def login_manual(self) -> None:
        """Open a headed browser to the HN login page.

        User logs in manually (solves reCAPTCHA). Session cookie
        is extracted and saved once login succeeds.
        """
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            channel="chrome",
            headless=False,
        )
        context = await browser.new_context()
        page = await context.new_page()

        try:
            log.info("Opening HN login page — log in manually in the browser.")
            await page.goto(
                f"{HN_BASE}/login?goto=news",
                wait_until="domcontentloaded",
            )

            # Poll until user finishes login (URL leaves /login or cookie appears).
            for _ in range(150):  # 5 minutes max
                try:
                    await page.wait_for_timeout(2000)
                except Exception:
                    raise HNAuthError("Browser was closed before login completed.")

                cookies = await context.cookies()
                user_cookie = None
                for c in cookies:
                    if c["name"] == "user" and "news.ycombinator.com" in c.get("domain", ""):
                        user_cookie = c["value"]
                        break

                if user_cookie:
                    # Save the cookie with secure permissions.
                    import os, stat
                    self._session_dir.mkdir(parents=True, exist_ok=True)
                    os.chmod(self._session_dir, stat.S_IRWXU)  # 0700
                    with open(self._cookie_path, "w") as f:
                        json.dump({"user_cookie": user_cookie}, f)
                    os.chmod(self._cookie_path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
                    self._cookie = user_cookie
                    self._logged_in = True
                    log.info("HN login successful — cookie saved to %s", self._cookie_path)
                    return
            else:
                raise HNAuthError("Login timed out after 5 minutes.")

        finally:
            await page.close()
            await context.close()
            await browser.close()
            await pw.stop()

    # ── Rate limiting ────────────────────────────────────────────────

    async def _throttle(self) -> None:
        """Sleep if needed to respect REQUEST_DELAY between actions."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < REQUEST_DELAY:
            wait = REQUEST_DELAY - elapsed
            log.debug("Throttling %.1fs before next HN action", wait)
            await asyncio.sleep(wait)
        self._last_request_time = asyncio.get_event_loop().time()

    def _get_http_client(self) -> httpx.AsyncClient:
        """Create an httpx client with the HN session cookie."""
        return httpx.AsyncClient(
            cookies={"user": self._cookie},
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            },
            follow_redirects=True,
            timeout=30,
        )

    # ── Posting ──────────────────────────────────────────────────────

    async def submit_link(self, url: str, title: str) -> dict[str, Any]:
        """Submit a link post to HN.

        Returns dict with: hn_url, item_id, title, url, success.
        """
        await self.ensure_logged_in()
        await self._throttle()

        async with self._get_http_client() as client:
            # First, get the submit page to extract the fnid (CSRF token).
            resp = await client.get(f"{HN_BASE}/submit")
            fnid = self._extract_fnid(resp.text)
            if not fnid:
                raise HNPostError("Could not extract fnid from submit page.")

            # Submit the form.
            data = {
                "fnid": fnid,
                "fnop": "submit-page",
                "title": title,
                "url": url,
                "text": "",
            }
            resp = await client.post(f"{HN_BASE}/r", data=data)

            return self._parse_submit_response(resp, title, url=url)

    async def submit_text(self, title: str, text: str) -> dict[str, Any]:
        """Submit a text post (Ask HN, etc.) to HN.

        Returns dict with: hn_url, item_id, title, success.
        """
        await self.ensure_logged_in()
        await self._throttle()

        async with self._get_http_client() as client:
            resp = await client.get(f"{HN_BASE}/submit")
            fnid = self._extract_fnid(resp.text)
            if not fnid:
                raise HNPostError("Could not extract fnid from submit page.")

            data = {
                "fnid": fnid,
                "fnop": "submit-page",
                "title": title,
                "url": "",
                "text": text,
            }
            resp = await client.post(f"{HN_BASE}/r", data=data)

            return self._parse_submit_response(resp, title)

    async def post_comment(self, parent_id: int, text: str) -> dict[str, Any]:
        """Post a comment on an HN item.

        Returns dict with: parent_id, success, comment_url.
        """
        await self.ensure_logged_in()
        await self._throttle()

        async with self._get_http_client() as client:
            # Load the item page to get the hmac token.
            resp = await client.get(f"{HN_BASE}/item?id={parent_id}")
            hmac = self._extract_hmac(resp.text, parent_id)
            if not hmac:
                raise HNPostError(
                    f"Could not extract hmac for item {parent_id}. "
                    "May need to re-login or item doesn't allow comments."
                )

            data = {
                "parent": str(parent_id),
                "goto": f"item?id={parent_id}",
                "hmac": hmac,
                "text": text,
            }
            resp = await client.post(f"{HN_BASE}/comment", data=data)

            if resp.status_code == 200 and "item?id=" in str(resp.url):
                log.info("Commented on item %d", parent_id)
                return {
                    "parent_id": parent_id,
                    "success": True,
                    "comment_url": str(resp.url),
                }
            else:
                body_text = resp.text[:500]
                if "too fast" in body_text.lower() or "slow down" in body_text.lower():
                    raise HNRateLimitError(
                        f"HN rate limit on comment for item {parent_id}"
                    )
                raise HNPostError(
                    f"Comment failed on item {parent_id}. "
                    f"Status: {resp.status_code}, Body: {body_text[:200]}"
                )

    # ── Checking posts ───────────────────────────────────────────────

    async def check_item(self, item_id: int) -> dict[str, Any]:
        """Check an HN item's score, comments, and status via the API."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
            )
            if resp.status_code != 200:
                raise HNClientError(f"HN API error for item {item_id}: {resp.status_code}")

            data = resp.json()
            if data is None:
                return {"item_id": item_id, "exists": False, "dead": True}

            return {
                "item_id": item_id,
                "exists": True,
                "type": data.get("type"),
                "title": data.get("title"),
                "url": data.get("url"),
                "score": data.get("score", 0),
                "descendants": data.get("descendants", 0),
                "by": data.get("by"),
                "time": data.get("time"),
                "dead": data.get("dead", False),
                "deleted": data.get("deleted", False),
            }

    # ── Search (Algolia) ─────────────────────────────────────────────

    async def search_hn(
        self,
        query: str,
        *,
        tags: str = "story",
        hits_per_page: int = 10,
        numeric_filters: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search HN via Algolia API (free, no key needed)."""
        params: dict[str, Any] = {
            "query": query,
            "tags": tags,
            "hitsPerPage": hits_per_page,
        }
        if numeric_filters:
            params["numericFilters"] = numeric_filters

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://hn.algolia.com/api/v1/search",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

        return [
            {
                "id": int(hit.get("objectID", 0)),
                "title": hit.get("title", ""),
                "url": hit.get("url", ""),
                "points": hit.get("points", 0),
                "num_comments": hit.get("num_comments", 0),
                "author": hit.get("author", ""),
                "created_at": hit.get("created_at", ""),
            }
            for hit in data.get("hits", [])
        ]

    async def check_duplicate(self, url: str) -> list[dict[str, Any]]:
        """Check if a URL has already been submitted to HN."""
        return await self.search_hn(url, tags="story", hits_per_page=5)

    async def get_top_stories(self, count: int = 30) -> list[dict[str, Any]]:
        """Get current top stories from HN."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://hacker-news.firebaseio.com/v0/topstories.json"
            )
            resp.raise_for_status()
            ids = resp.json()[:count]

            stories = []
            for item_id in ids:
                r = await client.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
                )
                if r.status_code == 200 and r.json():
                    item = r.json()
                    stories.append({
                        "id": item.get("id"),
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "score": item.get("score", 0),
                        "descendants": item.get("descendants", 0),
                        "by": item.get("by", ""),
                        "time": item.get("time"),
                    })

            return stories

    async def get_user(self, username: str) -> dict[str, Any]:
        """Get a user's profile from HN API."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://hacker-news.firebaseio.com/v0/user/{username}.json"
            )
            if resp.status_code != 200 or not resp.json():
                return {"username": username, "exists": False}

            data = resp.json()
            return {
                "username": data.get("id"),
                "karma": data.get("karma", 0),
                "created": data.get("created"),
                "about": data.get("about", ""),
                "exists": True,
            }

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _extract_fnid(html: str) -> str | None:
        """Extract the fnid (CSRF token) from HN submit page."""
        match = re.search(r'name="fnid"\s+value="([^"]+)"', html)
        return match.group(1) if match else None

    @staticmethod
    def _extract_hmac(html: str, parent_id: int) -> str | None:
        """Extract the hmac token for commenting on an item."""
        # HN includes hmac in the comment form
        match = re.search(r'name="hmac"\s+value="([^"]+)"', html)
        return match.group(1) if match else None

    def _parse_submit_response(
        self, resp: httpx.Response, title: str, url: str = ""
    ) -> dict[str, Any]:
        """Parse the response after submitting a post."""
        # After successful submit, HN redirects to /newest or the item page.
        final_url = str(resp.url)
        body = resp.text

        # Check for rate limiting.
        if "submitting too fast" in body.lower() or "slow down" in body.lower():
            raise HNRateLimitError("HN says you're submitting too fast.")

        # Check for other errors.
        if "unknown" in body.lower() and len(body) < 500:
            raise HNPostError(f"HN returned error page: {body[:300]}")

        # Try to extract the item ID from the response.
        item_id = None
        id_match = re.search(r'item\?id=(\d+)', body)
        if id_match:
            item_id = int(id_match.group(1))
        elif "item?id=" in final_url:
            id_match = re.search(r'id=(\d+)', final_url)
            if id_match:
                item_id = int(id_match.group(1))

        # If redirected to /newest, the post was likely successful
        # but we need to find the item ID.
        if item_id is None and ("/newest" in final_url or "/news" in final_url):
            log.info("Submitted successfully, redirected to %s", final_url)
            # The item was likely created — search for it.
            item_id = None  # Will be resolved later via search

        hn_url = f"{HN_BASE}/item?id={item_id}" if item_id else final_url

        log.info("Submitted to HN: %s (item_id=%s)", title[:60], item_id)
        return {
            "hn_url": hn_url,
            "item_id": item_id,
            "title": title,
            "url": url,
            "success": True,
        }

    async def preflight(self) -> None:
        """Verify auth works by checking session."""
        await self.ensure_logged_in()
        log.info("HN browser pre-flight check: OK")


# ── Module-level singleton ───────────────────────────────────────────

_default_client: PlaywrightHNClient | None = None


def get_hn_client(
    session_dir: str | None = None,
) -> PlaywrightHNClient:
    """Return (or create) the module-level PlaywrightHNClient singleton."""
    global _default_client
    if _default_client is None:
        if session_dir is None:
            session_dir = DEFAULT_SESSION_DIR
        _default_client = PlaywrightHNClient(session_dir)
    return _default_client


def reset_hn_client() -> None:
    """Reset the singleton. Useful for testing."""
    global _default_client
    _default_client = None
