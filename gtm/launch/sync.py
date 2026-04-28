"""Engagement sync — re-fetch score/comments for live posts and update frontmatter.

Pure-ish helpers (no Click). The CLI surface lives in `gtm.cli` under the
`post sync` command. Network I/O is wrapped in `fetch_comments_json` so e2e
tests can monkeypatch `urllib.request.urlopen`.

Why `comments_real`: Reddit's `num_comments` includes AutoModerator stickies
and the OP's own self-replies, which inflate the engagement signal. The "real"
count excludes AutoModerator, [deleted] users, and the post's own author.
See docs/PLAN-launch-workflow.md CP5 for the full rationale.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


COMMENTS_JSON_URL = "https://www.reddit.com/comments/{live_id}.json"
DEFAULT_USER_AGENT = "gtm-cli/0.1 (engagement sync)"
DEFAULT_TIMEOUT_SEC = 15


# ── ISO timestamp ───────────────────────────────────────────────────


def now_iso_utc() -> str:
    """ISO-8601 UTC timestamp with seconds precision and 'Z' suffix.

    Duplicated from gtm.launch.submit so sync stays import-light. Same shape.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Network ─────────────────────────────────────────────────────────


class SyncFetchError(Exception):
    """Raised when the Reddit JSON endpoint cannot be fetched or parsed."""


def fetch_comments_json(live_id: str, *, timeout: int = DEFAULT_TIMEOUT_SEC) -> list:
    """GET https://www.reddit.com/comments/<live_id>.json and return the parsed JSON.

    Reddit returns a 2-element array: [post_listing, comments_listing].
    Raises SyncFetchError on any network or parse failure.
    """
    url = COMMENTS_JSON_URL.format(live_id=live_id)
    req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        raise SyncFetchError(f"HTTP {e.code} fetching {url}")
    except urllib.error.URLError as e:
        raise SyncFetchError(f"network error fetching {url}: {e.reason}")
    except Exception as e:
        raise SyncFetchError(f"error fetching {url}: {e}")

    try:
        raw = resp.read()
    except Exception as e:
        raise SyncFetchError(f"error reading {url}: {e}")

    # Reddit JSON sometimes contains stray control chars in user-supplied
    # bodies. Decode permissively and parse non-strictly.
    if isinstance(raw, (bytes, bytearray)):
        text = raw.decode("utf-8", errors="replace")
    else:
        text = str(raw)

    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError as e:
        raise SyncFetchError(f"malformed JSON at {url}: {e}")


# ── Parse ───────────────────────────────────────────────────────────


@dataclass
class SyncResult:
    """Outcome of syncing one post.

    score / comments / comments_real are the freshly-fetched values.
    removed_by_category is non-None if Reddit has removed the post.
    error is set on per-post failure (network, missing live_id, etc.).
    """

    live_id: str
    score: int = 0
    comments: int = 0
    comments_real: int = 0
    subreddit: str = ""
    removed_by_category: Optional[str] = None
    error: Optional[str] = None


def parse_listing(payload: list, *, op_identity: Optional[str]) -> SyncResult:
    """Pull score, comments, comments_real out of a Reddit comments-page payload.

    `payload` is the 2-element list returned by /comments/<id>.json:
      [0] post listing — has score/num_comments/subreddit/removed_by_category
      [1] comments listing — flat array of t1 children we walk to count realness

    `op_identity` is the post's frontmatter `identity` (the OP's username) so
    we can exclude their own self-replies from comments_real. Pass None to
    disable OP exclusion (counts all non-bot, non-deleted humans).
    """
    if not isinstance(payload, list) or len(payload) < 1:
        raise SyncFetchError(f"unexpected payload shape: {type(payload).__name__}")

    # ── Post listing ────────────────────────────────────────────────
    try:
        post_children = payload[0]["data"]["children"]
        post_data = post_children[0]["data"]
    except (KeyError, IndexError, TypeError) as e:
        raise SyncFetchError(f"missing post listing in payload: {e}")

    score = int(post_data.get("score") or 0)
    comments = int(post_data.get("num_comments") or 0)
    subreddit = str(post_data.get("subreddit") or "")
    removed_by = post_data.get("removed_by_category")
    if removed_by is not None:
        removed_by = str(removed_by)

    # ── Comments listing ───────────────────────────────────────────
    real = 0
    if len(payload) >= 2:
        try:
            comment_children = payload[1]["data"]["children"]
        except (KeyError, IndexError, TypeError):
            comment_children = []
        for child in comment_children or []:
            if not isinstance(child, dict):
                continue
            if child.get("kind") != "t1":
                # Skip "more" markers and other non-comment nodes.
                continue
            cd = child.get("data") or {}
            author = str(cd.get("author") or "")
            if not author:
                continue
            if author == "AutoModerator":
                continue
            if author == "[deleted]":
                continue
            if op_identity and author == op_identity:
                continue
            real += 1

    return SyncResult(
        live_id="",
        score=score,
        comments=comments,
        comments_real=real,
        subreddit=subreddit,
        removed_by_category=removed_by,
    )


# ── Frontmatter mutation ────────────────────────────────────────────


def apply_sync_to_frontmatter(frontmatter: dict, result: SyncResult) -> dict:
    """Return a new frontmatter dict with metrics + (maybe) status/note updated.

    - metrics.score / comments / comments_real always overwritten
    - metrics.last_checked set to now_iso_utc()
    - if result.removed_by_category is non-None, status flips to 'removed' and
      note records the reason
    Does not mutate the input.
    """
    fm = dict(frontmatter)
    metrics = dict(fm.get("metrics") or {})
    metrics["score"] = int(result.score)
    metrics["comments"] = int(result.comments)
    metrics["comments_real"] = int(result.comments_real)
    metrics["last_checked"] = now_iso_utc()
    fm["metrics"] = metrics

    if result.removed_by_category:
        fm["status"] = "removed"
        fm["note"] = f"removed by reddit: {result.removed_by_category}"

    return fm


def resolve_live_id(frontmatter: dict) -> Optional[str]:
    """Return the post's reddit live_id, preferring explicit field over URL parse.

    Looks at frontmatter['live_id'] first; falls back to extracting from `url`
    or `live_url` via the same regex used in submit.py.
    """
    lid = frontmatter.get("live_id")
    if lid:
        return str(lid)
    # Fall back to URL parsing — accept either `url` (current schema) or
    # `live_url` (what the plan brief mentions).
    from gtm.launch.submit import extract_live_id
    for key in ("live_url", "url"):
        u = frontmatter.get(key)
        if u:
            extracted = extract_live_id(str(u))
            if extracted:
                return extracted
    return None
