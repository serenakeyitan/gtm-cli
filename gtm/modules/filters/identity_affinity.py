"""Identity × subreddit affinity table (computed from past run history).

Scans runs/*/state.json, walks promote_results.posts, and aggregates per
(identity, subreddit) pair. Used by:
  - `gtm reddit affinity` (CLI inspection)
  - The promoter agent (to pick which identity posts to which sub)

Each post in promote_results is expected to have:
  subreddit, url, score, num_comments, deleted, sub_strictness
and ideally `identity` (the registered identity name). Falls back to legacy
`account` field, then to inferring from the URL (e.g. /user/<name>/).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DEFAULT_RUNS_DIR = Path("runs")

_USER_RE = re.compile(r"/user/([A-Za-z0-9_-]+)/")


def _infer_identity(post: dict[str, Any]) -> str | None:
    if post.get("identity"):
        return post["identity"]
    if post.get("account"):
        return post["account"]
    url = post.get("url") or ""
    m = _USER_RE.search(url)
    return m.group(1) if m else None


def compute_affinity(
    runs_dir: str | Path | None = None,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Return ``{identity: {subreddit: {posts, avg_score, last_post, any_removed}}}``."""
    runs_dir = Path(runs_dir) if runs_dir else DEFAULT_RUNS_DIR
    table: dict[str, dict[str, dict[str, Any]]] = {}
    if not runs_dir.exists():
        return table

    for run_dir in sorted(runs_dir.iterdir()):
        state_path = run_dir / "state.json"
        if not state_path.exists():
            continue
        try:
            state = json.loads(state_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        run_completed = state.get("completed_at") or state.get("started_at") or ""

        for promo in state.get("promote_results", []) or []:
            for post in promo.get("posts", []) or []:
                ident = _infer_identity(post) or "unknown"
                sub = (post.get("subreddit") or "unknown").lower()
                bucket = table.setdefault(ident, {}).setdefault(
                    sub,
                    {
                        "posts": 0,
                        "score_sum": 0.0,
                        "avg_score": 0.0,
                        "last_post": "",
                        "any_removed": False,
                    },
                )
                bucket["posts"] += 1
                try:
                    bucket["score_sum"] += float(post.get("score") or 0)
                except (TypeError, ValueError):
                    pass
                bucket["avg_score"] = bucket["score_sum"] / bucket["posts"]
                if run_completed > bucket["last_post"]:
                    bucket["last_post"] = run_completed
                if post.get("deleted") or post.get("status") in ("removed", "AUTOMOD_FILTERED"):
                    bucket["any_removed"] = True

    return table


def best_identity_for_sub(
    subreddit: str,
    candidates: list[str],
    table: dict[str, dict[str, dict[str, Any]]] | None = None,
) -> str | None:
    """Pick the best identity from ``candidates`` for posting to ``subreddit``.

    Strategy:
      1. Drop candidates with any past removal in this sub.
      2. Among the rest, pick the one with highest avg_score (ties → most posts).
      3. If no one has history, return the first candidate (caller decides).
    """
    if not candidates:
        return None
    table = table if table is not None else compute_affinity()
    sub = subreddit.lower()

    safe = [
        a for a in candidates
        if not table.get(a, {}).get(sub, {}).get("any_removed")
    ]
    pool = safe or candidates

    def key(a: str) -> tuple[float, int]:
        stats = table.get(a, {}).get(sub, {})
        return (stats.get("avg_score", 0.0), stats.get("posts", 0))

    scored = [a for a in pool if table.get(a, {}).get(sub)]
    if scored:
        return max(scored, key=key)
    return pool[0]
