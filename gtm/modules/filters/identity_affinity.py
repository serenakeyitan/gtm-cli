"""Identity × subreddit affinity table (computed from past run history).

STUB — full implementation lands at Checkpoint 7. Provides the API surface
that reddit tools expect so imports resolve.
"""

from __future__ import annotations

from typing import Any


def compute_affinity(runs_dir: str | None = None) -> dict[str, dict[str, dict[str, Any]]]:
    """Return {identity_name: {subreddit: {posts, avg_score, last_post, any_removed}}}.

    Empty until Checkpoint 7 wires this to read from gtm-cli's run output dir.
    """
    return {}


def best_identity_for_sub(
    subreddit: str,
    candidates: list[str],
    table: dict[str, dict[str, dict[str, Any]]],
) -> str | None:
    """Pick the highest-avg-score identity for `subreddit`, skipping those flagged removed.

    Falls back to the first candidate if no history.
    """
    if not candidates:
        return None
    sub = subreddit.lower()
    scored: list[tuple[float, str]] = []
    for name in candidates:
        entry = table.get(name, {}).get(sub)
        if not entry or entry.get("any_removed"):
            continue
        scored.append((float(entry.get("avg_score") or 0.0), name))
    if scored:
        scored.sort(reverse=True)
        return scored[0][1]
    return candidates[0]
