#!/usr/bin/env python3
"""Grab Twitter cookies from a real Chrome browser session.

Opens Chrome to twitter.com — if you're already logged in, cookies are
captured automatically. If not, log in manually.

Usage:
    python3 scripts/grab_twitter_cookies.py
"""

import asyncio
import json
import sys
from pathlib import Path


async def grab_cookies():
    from playwright.async_api import async_playwright

    print("Opening Chrome to twitter.com...")
    print("If you're already logged in, cookies will be captured automatically.")
    print("If not, please log in manually.\n")

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(channel="chrome", headless=False)
    context = await browser.new_context()
    page = await context.new_page()

    await page.goto("https://x.com/home", wait_until="domcontentloaded")
    print("Waiting for login (checking every 3s)...")

    for i in range(60):  # Wait up to 3 minutes
        await asyncio.sleep(3)
        url = page.url
        if "/home" in url and "/login" not in url:
            # Check for logged-in indicator
            cookies = await context.cookies("https://x.com")
            auth_cookies = {c["name"]: c["value"] for c in cookies}
            if "auth_token" in auth_cookies:
                print("\n✅ Logged in! Capturing cookies...")
                break
    else:
        print("\n❌ Timeout waiting for login. Please try again.")
        await browser.close()
        await pw.stop()
        sys.exit(1)

    # Save cookies in twikit format (simple dict)
    cookies = await context.cookies("https://x.com")
    cookie_dict = {c["name"]: c["value"] for c in cookies}

    # Determine username from page
    username = "1_reddit27179"  # fallback
    try:
        # Try to get username from the page
        el = await page.query_selector('[data-testid="AppTabBar_Profile_Link"]')
        if el:
            href = await el.get_attribute("href")
            if href:
                username = href.strip("/")
    except Exception:
        pass

    # Save
    identity_dir = Path.home() / ".config" / "growth" / "identities" / "twitter" / username
    identity_dir.mkdir(parents=True, exist_ok=True)
    cookie_path = identity_dir / "cookies.json"

    with open(cookie_path, "w") as f:
        json.dump(cookie_dict, f, indent=2)

    # Set secure permissions
    import os, stat
    os.chmod(cookie_path, stat.S_IRUSR | stat.S_IWUSR)
    os.chmod(identity_dir, stat.S_IRWXU)

    print(f"✅ Cookies saved to {cookie_path}")
    print(f"   Identity: twitter:{username}")
    print(f"\n   Test it: growth twitter search 'AI agents' --count 3")

    await browser.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(grab_cookies())
