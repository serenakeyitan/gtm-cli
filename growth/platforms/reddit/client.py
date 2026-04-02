"""Async Playwright-based Reddit client with session persistence.

Bypasses the Reddit API entirely by automating the browser UI.
No API credentials or pre-approval needed — just a Reddit account.

Follows the same patterns as twikit_client.py:
- Singleton getter with reset function
- Cookie/session persistence to disk
- Rate limiting between requests
- Custom exception hierarchy
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Minimum seconds between consecutive Reddit page loads.
REQUEST_DELAY = float(os.environ.get("REDDIT_REQUEST_DELAY", "10.0"))

# How long to wait if Reddit throttles us (too many actions).
RATE_LIMIT_BACKOFF = float(os.environ.get("REDDIT_RATE_LIMIT_BACKOFF", "120.0"))

# Default session storage path.
DEFAULT_SESSION_DIR = "~/.config/growth/identities/reddit/_session"


class RedditClientError(Exception):
    """Base error for all Reddit browser client operations."""
    pass


class RedditAuthError(RedditClientError):
    """Raised when authentication fails or session is missing/expired."""
    pass


class RedditPostError(RedditClientError):
    """Raised when a post submission fails."""
    pass


class RedditRateLimitError(RedditClientError):
    """Raised when Reddit throttles browser actions."""
    pass


class PlaywrightRedditClient:
    """Async Playwright-based Reddit browser client.

    Usage::

        client = PlaywrightRedditClient(session_dir="~/.config/growth/identities/reddit/_session")
        await client.ensure_logged_in()
        result = await client.submit_post("python", "my title", "my body text")
    """

    def __init__(self, session_dir: str = DEFAULT_SESSION_DIR) -> None:
        self._session_dir = Path(session_dir).expanduser()
        self._storage_path = self._session_dir / "storage_state.json"
        self._pw = None
        self._browser = None
        self._context = None
        self._logged_in = False
        self._last_request_time: float = 0.0

    # ── Lifecycle ────────────────────────────────────────────────────

    async def _init_browser(self, *, headless: bool | None = None) -> None:
        """Start Playwright and launch browser if needed.

        Uses the real Chrome browser (``channel="chrome"``) instead of
        Playwright's bundled Chromium.  Real Chrome does not carry
        automation markers, so Reddit's CDN is far less likely to
        block or rate-limit requests.

        Always launches in **headed** mode by default.  Reddit's
        Cloudflare WAF trivially detects headless Chrome and returns a
        "blocked by network security" page, so headed mode is required
        for any page that goes through their CDN.
        """
        if self._browser is not None:
            return

        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()

        # Always default to headed mode — Reddit blocks headless Chrome.
        if headless is None:
            headless = False

        # channel="chrome" tells Playwright to use the locally-installed
        # Google Chrome instead of the bundled Chromium.
        # Extra args disable Chromium's automation-related flags that
        # leak to JavaScript (navigator.webdriver, etc.).
        self._browser = await self._pw.chromium.launch(
            channel="chrome",
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
        )

        # Build context kwargs — mimic a real desktop browser session.
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

        # Inject stealth script — runs before every page navigation.
        await self._context.add_init_script("""
            // Remove the navigator.webdriver flag.
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            // Spoof plugins array (headless Chrome has length 0).
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            // Spoof languages.
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            // Remove Playwright-injected window properties.
            delete window.__playwright;
            delete window.__pw_manual;
        """)

    async def close(self) -> None:
        """Close browser and Playwright."""
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

    # ── Auth ─────────────────────────────────────────────────────────

    async def ensure_logged_in(self) -> None:
        """Load saved session from disk. Raises RedditAuthError if missing."""
        if self._logged_in:
            return

        await self._init_browser()

        if not self._storage_path.exists():
            raise RedditAuthError(
                f"Reddit session not found at {self._storage_path}.\n"
                f"Run:  growth auth reddit"
            )

        # Verify the session is still valid by loading Reddit.
        page = await self._context.new_page()
        try:
            await page.goto("https://www.reddit.com/", wait_until="commit", timeout=30000)
            await page.wait_for_timeout(4000)

            # Check if we're logged in by looking for the user menu or login button.
            logged_in = await self._check_logged_in(page)
            if not logged_in:
                raise RedditAuthError(
                    "Reddit session expired. Please re-authenticate.\n"
                    "Run:  growth auth reddit"
                )

            self._logged_in = True
            log.info("Reddit session verified — logged in")
        finally:
            await page.close()

    async def login_manual(self) -> None:
        """Open a headed browser to the Reddit login page.

        The user logs in manually (type creds, handle CAPTCHA/2FA).
        Session is saved once the URL navigates away from /login.

        Uses ``channel="chrome"`` so the real Chrome binary is launched
        instead of Playwright's Chromium, avoiding Reddit's automation
        detection and IP rate-limiting.
        """
        # Force headed mode.
        if self._browser:
            await self.close()

        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            channel="chrome",
            headless=False,
        )
        self._context = await self._browser.new_context()

        page = await self._context.new_page()
        try:
            log.info("Opening Reddit login page — log in manually in the browser.")
            resp = await page.goto(
                "https://www.reddit.com/login/",
                wait_until="domcontentloaded",
            )

            # Detect Reddit IP rate-limit page (HTTP 429 or "too many requests").
            if resp and resp.status == 429:
                body = await page.text_content("body")
                raise RedditRateLimitError(
                    "Reddit is rate-limiting your IP (HTTP 429). "
                    "Wait 15-20 minutes before retrying.\n"
                    f"Page text: {(body or '')[:200]}"
                )
            body_text = await page.text_content("body") or ""
            if "too many requests" in body_text.lower() or "whoa there" in body_text.lower():
                raise RedditRateLimitError(
                    "Reddit is rate-limiting your IP. "
                    "Wait 15-20 minutes before retrying.\n"
                    f"Page text: {body_text[:200]}"
                )

            # Poll until user finishes login (URL leaves /login).
            for _ in range(150):  # 5 minutes max
                try:
                    await page.wait_for_timeout(2000)
                except Exception:
                    # Browser was closed by user — treat as cancel.
                    raise RedditAuthError("Browser was closed before login completed.")
                if "/login" not in page.url:
                    break
            else:
                raise RedditAuthError(
                    "Login timed out after 5 minutes. "
                    "Please try again and complete login faster."
                )

            # Verify we're actually logged in.
            await page.wait_for_timeout(3000)
            logged_in = await self._check_logged_in(page)
            if not logged_in:
                raise RedditAuthError(
                    "Login appeared to succeed but session verification failed."
                )

            # Save session state.
            self._session_dir.mkdir(parents=True, exist_ok=True)
            storage = await self._context.storage_state(path=str(self._storage_path))
            self._logged_in = True
            log.info("Logged in and saved session to %s", self._storage_path)

        finally:
            await page.close()

    async def _check_logged_in(self, page) -> bool:
        """Check if the current page shows a logged-in state."""
        try:
            # New Reddit: look for user avatar/menu or the absence of login buttons.
            # Try multiple selectors that indicate logged-in state.
            selectors = [
                '#expand-search-input',  # search bar (logged in layout)
                'button[aria-label="Open chat"]',  # chat button
                'a[href*="/user/"]',  # any link to user profile
                '[data-testid="user-drawer-button"]',  # user drawer
            ]
            for sel in selectors:
                el = page.locator(sel).first
                if await el.is_visible(timeout=1000):
                    return True
        except Exception:
            pass

        # Fallback: check if login/signup buttons are visible (means NOT logged in).
        try:
            login_link = page.locator('a[href*="/login"]').first
            if await login_link.is_visible(timeout=1000):
                return False
        except Exception:
            pass

        # If we can't determine either way, check cookies for reddit_session.
        cookies = await self._context.cookies()
        for c in cookies:
            if c["name"] == "reddit_session" and ".reddit.com" in c.get("domain", ""):
                return True

        return False

    # ── Rate limiting ────────────────────────────────────────────────

    async def _throttle(self) -> None:
        """Sleep if needed to respect REQUEST_DELAY between page loads."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < REQUEST_DELAY:
            wait = REQUEST_DELAY - elapsed
            log.debug("Throttling %.1fs before next Reddit action", wait)
            await asyncio.sleep(wait)
        self._last_request_time = asyncio.get_event_loop().time()

    # ── Posting ──────────────────────────────────────────────────────

    async def submit_post(
        self,
        subreddit: str,
        title: str,
        selftext: str,
    ) -> dict[str, Any]:
        """Submit a text post to a subreddit via the browser.

        Returns dict with: url, subreddit, title, success.
        """
        await self.ensure_logged_in()
        await self._throttle()

        page = await self._context.new_page()
        try:
            # Go directly to new Reddit's submit page (text post).
            # Old Reddit returns HTTP 403 from Cloudflare, so we skip it
            # entirely and target new Reddit with the ?type=TEXT param.
            submit_url = (
                f"https://www.reddit.com/r/{subreddit}/submit/?type=TEXT"
            )
            log.info("Navigating to %s", submit_url)
            resp = await page.goto(
                submit_url, wait_until="commit", timeout=30000,
            )
            # Let the SPA finish hydrating.
            await page.wait_for_timeout(6000)

            log.info(
                "Submit page loaded (HTTP %s). Current URL: %s",
                resp.status if resp else "?", page.url,
            )
            return await self._submit_new_reddit(page, subreddit, title, selftext)

        except RedditPostError:
            raise
        except Exception as e:
            raise RedditPostError(f"Failed to post to r/{subreddit}: {e}") from e
        finally:
            await page.close()

    async def _submit_old_reddit(
        self, page, subreddit: str, title: str, selftext: str
    ) -> dict[str, Any]:
        """Submit via old.reddit.com form (more stable)."""
        log.info("Old Reddit submit: clicking text tab...")

        # Check for network security block.
        body_text = (await page.text_content("body") or "").lower()
        if "blocked by network security" in body_text:
            raise RedditPostError(
                f"Reddit CDN blocked browser for r/{subreddit} (old Reddit). "
                f"Current URL: {page.url}"
            )

        # Check for rate limit page.
        if "whoa there" in body_text or "too many requests" in body_text:
            raise RedditRateLimitError("Reddit rate limit detected on submit page")

        # Click the "text" tab if not already selected.
        text_tab = page.locator('a.text-button, li.text a')
        if await text_tab.count() > 0:
            await text_tab.first.click()
            await page.wait_for_timeout(500)

        # Fill title.
        log.info("Old Reddit submit: filling title...")
        title_input = page.locator('textarea[name="title"], input[name="title"]')
        try:
            await title_input.first.wait_for(state="visible", timeout=10000)
        except Exception:
            raise RedditPostError(
                f"Title input not found on r/{subreddit} submit page. "
                f"Current URL: {page.url}"
            )
        await title_input.first.fill(title)
        await page.wait_for_timeout(300)

        # Fill body text.
        log.info("Old Reddit submit: filling body text...")
        text_input = page.locator('textarea[name="text"]')
        try:
            await text_input.first.wait_for(state="visible", timeout=10000)
        except Exception:
            raise RedditPostError(
                f"Body textarea not found on r/{subreddit} submit page. "
                f"Current URL: {page.url}"
            )
        await text_input.first.fill(selftext)
        await page.wait_for_timeout(300)

        # Submit.
        log.info("Old Reddit submit: clicking submit button...")
        submit_btn = page.locator('button[name="submit"], button[type="submit"]')
        try:
            await submit_btn.first.wait_for(state="visible", timeout=10000)
        except Exception:
            raise RedditPostError(
                f"Submit button not found on r/{subreddit} submit page. "
                f"Current URL: {page.url}"
            )
        await submit_btn.first.click()

        # Wait for redirect to the new post.
        log.info("Old Reddit submit: waiting for redirect after submit...")
        await page.wait_for_timeout(5000)

        # Check for errors.
        error_el = page.locator('.error, .status-msg.error')
        if await error_el.count() > 0:
            error_text = await error_el.first.text_content()
            if error_text and error_text.strip():
                raise RedditPostError(f"Reddit error: {error_text.strip()}")

        # Extract the post URL.
        post_url = page.url
        post_id = self._extract_post_id(post_url)

        log.info("Posted to r/%s: %s", subreddit, post_url)
        return {
            "url": post_url,
            "post_id": post_id,
            "subreddit": subreddit,
            "title": title,
            "success": True,
        }

    async def _submit_new_reddit(
        self, page, subreddit: str, title: str, selftext: str
    ) -> dict[str, Any]:
        """Submit via new Reddit UI.

        New Reddit (2024+) uses a web-component-based form with
        ``contenteditable`` divs instead of plain ``<textarea>`` inputs.
        The title field is a ``<div>`` inside a ``<shreddit-composer>``
        component, and the body is identified by ``aria-label``.
        """
        log.info("New Reddit submit: checking page state...")

        # ── Pre-flight checks ────────────────────────────────────────
        if "login" in page.url.lower():
            raise RedditAuthError(
                f"Redirected to login on new Reddit for r/{subreddit}. "
                "Session may be expired."
            )

        body_text = (await page.text_content("body") or "").lower()
        if "blocked by network security" in body_text:
            raise RedditPostError(
                f"Reddit CDN blocked browser for r/{subreddit}. "
                f"Current URL: {page.url}"
            )
        if "whoa there" in body_text or "too many requests" in body_text:
            raise RedditRateLimitError(
                "Reddit rate limit detected on submit page"
            )

        # ── Switch to Text post type ─────────────────────────────────
        # The submit page may default to IMAGE or LINK.  We need the
        # Text post type for selftext.  Click the "Text" tab/button.
        text_tab_selectors = [
            'button[role="tab"]:has-text("Text")',
            'a[role="tab"]:has-text("Text")',
            'button:has-text("Text")',
            'li:has-text("Text") a',
            'li:has-text("Text") button',
        ]
        for sel in text_tab_selectors:
            loc = page.locator(sel).first
            try:
                if await loc.is_visible(timeout=2000):
                    await loc.click()
                    log.info("Clicked Text post type tab: %s", sel)
                    await page.wait_for_timeout(1500)
                    break
            except Exception:
                continue
        else:
            log.info("No Text tab found — page may already be in text mode")

        # ── Title ─────────────────────────────────────────────────────
        log.info("New Reddit submit: looking for title input...")
        # New Reddit uses multiple possible title selectors depending on
        # the subreddit / A-B test variant.
        title_selectors = [
            'textarea[placeholder*="Title"]',
            'textarea[placeholder*="title"]',
            'input[aria-label*="Title"]',
            'div[contenteditable="true"][aria-label*="Title"]',
            'div[contenteditable="true"][aria-label*="title"]',
            # The shreddit-composer custom element embeds a textarea
            'shreddit-composer textarea',
            'faceplate-textarea-input textarea',
        ]
        title_el = None
        for sel in title_selectors:
            loc = page.locator(sel).first
            try:
                if await loc.is_visible(timeout=2000):
                    title_el = loc
                    log.info("Title input matched selector: %s", sel)
                    break
            except Exception:
                continue

        if title_el is None:
            # Fallback: look for ANY visible contenteditable div — the
            # first one on the page is typically the title.
            ce_divs = page.locator('div[contenteditable="true"]')
            count = await ce_divs.count()
            if count > 0:
                title_el = ce_divs.first
                log.info("Title input: using first contenteditable div")
            else:
                try:
                    ss = f"/tmp/reddit_submit_debug_{subreddit}.png"
                    await page.screenshot(path=ss)
                    log.info("Debug screenshot saved to %s", ss)
                except Exception:
                    pass
                raise RedditPostError(
                    f"Title input not found on r/{subreddit} submit page. "
                    f"Current URL: {page.url}"
                )

        await title_el.click()
        await page.wait_for_timeout(200)
        await page.keyboard.type(title, delay=20)
        await page.wait_for_timeout(500)
        log.info("New Reddit submit: title filled.")

        # ── Body ──────────────────────────────────────────────────────
        log.info("New Reddit submit: looking for body input...")
        body_selectors = [
            'div[aria-label="Post body text field"]',
            'div[aria-label="Optional Body text field"]',
            'div[contenteditable="true"][role="textbox"]',
            'div[role="textbox"]',
            'textarea[placeholder*="Text"]',
            'textarea[aria-label*="body"]',
        ]
        body_el = None
        for sel in body_selectors:
            loc = page.locator(sel).first
            try:
                if await loc.is_visible(timeout=2000):
                    body_el = loc
                    log.info("Body input matched selector: %s", sel)
                    break
            except Exception:
                continue

        if body_el is None:
            # Use the second contenteditable div if available.
            ce_divs = page.locator('div[contenteditable="true"]')
            count = await ce_divs.count()
            if count >= 2:
                body_el = ce_divs.nth(1)
                log.info("Body input: using second contenteditable div")
            elif count == 1:
                log.warning("Only one contenteditable div — body may be optional")
            else:
                raise RedditPostError(
                    f"Body input not found on r/{subreddit} submit page. "
                    f"Current URL: {page.url}"
                )

        if body_el is not None:
            await body_el.click()
            await page.wait_for_timeout(200)
            await page.keyboard.type(selftext, delay=10)
            await page.wait_for_timeout(500)
            log.info("New Reddit submit: body filled.")

        # ── Submit ────────────────────────────────────────────────────
        log.info("New Reddit submit: clicking Post button...")
        # Find the submit button — may be labelled "Post" or "Submit".
        post_btn = page.locator(
            'button:has-text("Post"):not(:has-text("Repost")), '
            'button[type="submit"]:has-text("Post"), '
            'faceplate-tracker button:has-text("Post"), '
            'button#inner-post-submit-button'
        )
        try:
            await post_btn.first.wait_for(state="visible", timeout=10000)
        except Exception:
            try:
                ss = f"/tmp/reddit_post_btn_debug_{subreddit}.png"
                await page.screenshot(path=ss)
                log.info("Debug screenshot saved to %s", ss)
            except Exception:
                pass
            raise RedditPostError(
                f"Post button not found on r/{subreddit} submit page. "
                f"Current URL: {page.url}"
            )

        # Wait for the button to become enabled (it stays disabled
        # until the required fields are valid for the post type).
        for _ in range(20):
            is_disabled = await post_btn.first.is_disabled()
            if not is_disabled:
                break
            log.debug("Post button still disabled — waiting 500ms")
            await page.wait_for_timeout(500)
        else:
            # Try clicking anyway — some subreddits use JS that
            # enables the button on focus.
            log.warning("Post button stayed disabled after 10s — attempting click")

        await post_btn.first.click(force=True)

        # Wait for navigation to the new post page.
        log.info("New Reddit submit: waiting for redirect after submit...")
        try:
            await page.wait_for_url(
                "**/comments/**", timeout=15000,
            )
        except Exception:
            # Navigation may not match pattern — use timeout fallback.
            await page.wait_for_timeout(5000)

        post_url = page.url
        post_id = self._extract_post_id(post_url)

        log.info("Posted to r/%s: %s", subreddit, post_url)
        return {
            "url": post_url,
            "post_id": post_id,
            "subreddit": subreddit,
            "title": title,
            "success": True,
        }

    # ── API-based posting ────────────────────────────────────────────

    async def submit_api_post(
        self,
        subreddit: str,
        title: str,
        *,
        selftext: str = "",
        url: str = "",
        kind: str = "self",
    ) -> dict[str, Any]:
        """Submit a post using Reddit's OAuth API from the browser context.

        This approach uses ``fetch()`` inside the browser with the
        ``token_v2`` cookie as a Bearer token, bypassing the need for
        UI form automation.

        Parameters
        ----------
        subreddit : str
            Target subreddit name (without ``r/`` prefix).
        title : str
            Post title.
        selftext : str
            Body text for self/text posts (``kind='self'``).
        url : str
            Link URL for link posts (``kind='link'``).
        kind : str
            ``'self'`` for text posts or ``'link'`` for link posts.
        """
        await self.ensure_logged_in()
        await self._throttle()

        page = await self._context.new_page()
        try:
            # Navigate to Reddit to ensure cookies are available.
            await page.goto(
                "https://www.reddit.com/", wait_until="commit", timeout=30000,
            )
            await page.wait_for_timeout(3000)

            # Extract the token_v2 cookie for Bearer auth.
            cookies = await self._context.cookies()
            token = None
            for c in cookies:
                if c["name"] == "token_v2" and ".reddit.com" in c.get("domain", ""):
                    token = c["value"]
                    break

            if not token:
                raise RedditAuthError(
                    "token_v2 cookie not found. Session may be expired."
                )

            # Build the API request body.
            body_params: dict[str, str] = {
                "sr": subreddit,
                "kind": kind,
                "title": title,
                "api_type": "json",
                "resubmit": "true",
            }
            if kind == "self":
                body_params["text"] = selftext
            elif kind == "link":
                body_params["url"] = url

            log.info(
                "API submit: kind=%s, sr=%s, title=%s",
                kind, subreddit, title[:60],
            )

            result = await page.evaluate(
                """async ({ body_params, token }) => {
                    const resp = await fetch(
                        'https://oauth.reddit.com/api/submit',
                        {
                            method: 'POST',
                            headers: {
                                'Authorization': 'Bearer ' + token,
                                'Content-Type': 'application/x-www-form-urlencoded',
                            },
                            body: new URLSearchParams(body_params).toString(),
                        }
                    );
                    const data = await resp.json();
                    return { status: resp.status, data: data };
                }""",
                {"body_params": body_params, "token": token},
            )

            status = result.get("status", 0)
            data = result.get("data", {})
            json_data = data.get("json", {})
            errors = json_data.get("errors", [])
            post_data = json_data.get("data", {})

            if status == 429:
                raise RedditRateLimitError(
                    f"Reddit API rate limit (429) posting to r/{subreddit}"
                )

            if errors:
                raise RedditPostError(
                    f"Reddit API errors posting to r/{subreddit}: {errors}"
                )

            post_url = post_data.get("url", "")
            post_id = post_data.get("id", "")

            if not post_url:
                raise RedditPostError(
                    f"Reddit API returned no URL for r/{subreddit}. "
                    f"Response: {result}"
                )

            log.info("API posted to r/%s: %s", subreddit, post_url)
            return {
                "url": post_url,
                "post_id": post_id,
                "subreddit": subreddit,
                "title": title,
                "kind": kind,
                "success": True,
                "api_response": result,
            }

        except (RedditPostError, RedditRateLimitError, RedditAuthError):
            raise
        except Exception as e:
            raise RedditPostError(
                f"API submit failed for r/{subreddit}: {e}"
            ) from e
        finally:
            await page.close()

    # ── Checking posts ───────────────────────────────────────────────

    async def check_post(self, post_url: str) -> dict[str, Any]:
        """Check a post's score, comments, and deletion status via browser."""
        await self.ensure_logged_in()
        await self._throttle()

        page = await self._context.new_page()
        try:
            # Use old Reddit for easier scraping.
            if "old.reddit.com" not in post_url:
                post_url = post_url.replace("www.reddit.com", "old.reddit.com")
                post_url = post_url.replace("reddit.com", "old.reddit.com")

            await page.goto(post_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            # Check if post was removed.
            removed = False
            removed_el = page.locator('.removed-body, [data-testid="removed"]')
            if await removed_el.count() > 0:
                removed = True

            # Try to get score.
            score = 0
            score_el = page.locator('.score.unvoted, .score.likes, .score.dislikes')
            if await score_el.count() > 0:
                score_text = await score_el.first.text_content()
                try:
                    score = int(score_text.replace(",", ""))
                except (ValueError, TypeError):
                    pass

            # Try to get comment count.
            num_comments = 0
            comments_el = page.locator('a.comments')
            if await comments_el.count() > 0:
                comments_text = await comments_el.first.text_content()
                match = re.search(r"(\d+)", comments_text or "")
                if match:
                    num_comments = int(match.group(1))

            return {
                "url": post_url,
                "score": score,
                "num_comments": num_comments,
                "deleted": removed,
            }
        finally:
            await page.close()

    # ── Subreddit info ───────────────────────────────────────────────

    async def get_subreddit_rules(self, subreddit: str) -> list[dict[str, str]]:
        """Fetch subreddit rules via browser."""
        await self.ensure_logged_in()
        await self._throttle()

        page = await self._context.new_page()
        try:
            rules_url = f"https://www.reddit.com/r/{subreddit}/about/rules/"
            await page.goto(rules_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            rules = []
            # Try to extract rule elements.
            rule_els = page.locator(
                '[data-testid="rule-header"], '
                '.rules-list h3, '
                '.wiki-page-content h3'
            )
            count = await rule_els.count()
            for i in range(min(count, 20)):
                text = await rule_els.nth(i).text_content()
                if text:
                    rules.append({"name": text.strip(), "description": ""})

            return rules
        finally:
            await page.close()

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _extract_post_id(url: str) -> str:
        """Extract Reddit post ID from a URL."""
        # Matches: /comments/ABC123/ or /comments/ABC123
        match = re.search(r"/comments/([a-zA-Z0-9]+)", url)
        if match:
            return match.group(1)
        return ""

    async def preflight(self) -> None:
        """Verify auth works by checking session."""
        await self.ensure_logged_in()
        log.info("Reddit browser pre-flight check: OK")


# ── Module-level singleton ───────────────────────────────────────────

_default_client: PlaywrightRedditClient | None = None


def get_reddit_browser_client(
    session_dir: str | None = None,
) -> PlaywrightRedditClient:
    """Return (or create) the module-level PlaywrightRedditClient singleton."""
    global _default_client
    if _default_client is None:
        if session_dir is None:
            session_dir = DEFAULT_SESSION_DIR
        _default_client = PlaywrightRedditClient(session_dir)
    return _default_client


def reset_reddit_browser_client() -> None:
    """Reset the singleton. Useful for testing."""
    global _default_client
    _default_client = None
