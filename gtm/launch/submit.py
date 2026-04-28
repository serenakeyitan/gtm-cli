"""Helpers for `gtm post submit` — channel parsing, URL → live_id extraction,
frontmatter mutation on success/failure.

Kept pure (no Click, no Playwright) so the e2e tests can call this directly with
mocked submit functions.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional


# ── Channel parsing ──────────────────────────────────────────────────


def parse_reddit_channel(channel: str) -> Optional[str]:
    """Extract the subreddit name from a channel string.

    Examples
    --------
    "reddit r/AI_Agents"   → "AI_Agents"
    "Reddit r/AI_Agents"   → "AI_Agents"  (case-insensitive prefix)
    "reddit  r/foo"        → "foo"
    "reddit AI_Agents"     → "AI_Agents"  (no r/ prefix is OK)
    "twitter"              → None
    "hn"                   → None
    """
    if not channel:
        return None
    c = channel.strip()
    if not c.lower().startswith("reddit"):
        return None
    rest = c[len("reddit"):].strip()
    if not rest:
        return None
    # Strip any number of leading r/ or / segments
    rest = rest.lstrip("/")
    if rest.lower().startswith("r/"):
        rest = rest[2:]
    rest = rest.strip().split()[0] if rest.strip() else ""
    return rest or None


def channel_platform(channel: str) -> str:
    """Return the platform key for a channel string.

    "reddit r/foo" → "reddit"; "twitter" → "twitter"; "hn" → "hn"; else "unknown".
    """
    if not channel:
        return "unknown"
    c = channel.strip().lower()
    if c.startswith("reddit"):
        return "reddit"
    if c.startswith("twitter") or c.startswith("x "):
        return "twitter"
    if c.startswith("hn") or c.startswith("hacker"):
        return "hn"
    return "unknown"


# ── live_id extraction ──────────────────────────────────────────────


_LIVE_ID_RE = re.compile(r"/comments/([a-z0-9]+)", re.IGNORECASE)


def extract_live_id(url: str) -> Optional[str]:
    """Pull the post id out of a Reddit URL like /r/foo/comments/abc123/title.

    Returns None if the URL doesn't have the /comments/<id>/ shape.
    """
    if not url:
        return None
    m = _LIVE_ID_RE.search(url)
    return m.group(1) if m else None


# ── Frontmatter mutation ────────────────────────────────────────────


def now_iso_utc() -> str:
    """ISO-8601 UTC timestamp with seconds precision and 'Z' suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def mark_post_live(frontmatter: dict, *, url: str, live_id: Optional[str],
                   posted_at: Optional[str] = None) -> dict:
    """Return a new frontmatter dict with status=live + live_url/live_id/posted_at.

    Does not mutate the input dict. Clears any prior `note` since we succeeded.
    """
    fm = dict(frontmatter)
    fm["url"] = url
    fm["live_id"] = live_id or extract_live_id(url)
    fm["posted_at"] = posted_at or now_iso_utc()
    fm["status"] = "live"
    # On success, drop any prior failure note.
    if "note" in fm and fm.get("note") and isinstance(fm["note"], str) \
            and fm["note"].startswith("submit failed:"):
        fm["note"] = None
    return fm


def mark_post_failed(frontmatter: dict, reason: str) -> dict:
    """Return a new frontmatter dict with note='submit failed: <reason>', status unchanged."""
    fm = dict(frontmatter)
    fm["note"] = f"submit failed: {reason}"
    return fm
