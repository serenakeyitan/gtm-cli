"""Traction alerts — notify when engagement crosses thresholds.

Compares current traction data against configured thresholds.
Returns a list of alerts for posts that crossed a milestone.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from gtm.config import GrowthConfig, RATE_LIMITS_DIR

log = logging.getLogger(__name__)

# Default alert thresholds
DEFAULT_THRESHOLDS = {
    "twitter": {"likes": [50, 100, 500, 1000], "retweets": [10, 50, 100]},
    "reddit": {"score": [10, 50, 100, 500], "comments": [5, 20, 50]},
    "hn": {"points": [10, 50, 100, 500], "comments": [5, 20, 50]},
}

ALERTS_FILE = RATE_LIMITS_DIR / "alerts_state.json"


def check_alerts(traction_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Check traction data against thresholds. Returns new alerts.

    Only triggers each threshold once per post (persists seen alerts).
    """
    seen = _load_seen()
    alerts = []

    for item in traction_data:
        platform = item.get("platform", "")
        post_id = item.get("post_id", "")
        if not platform or not post_id:
            continue

        thresholds = DEFAULT_THRESHOLDS.get(platform, {})
        seen_key = f"{platform}:{post_id}"

        for metric, levels in thresholds.items():
            value = item.get(metric)
            if value is None:
                continue

            try:
                value = int(value)
            except (ValueError, TypeError):
                continue

            for level in levels:
                alert_key = f"{seen_key}:{metric}:{level}"
                if value >= level and alert_key not in seen:
                    alerts.append({
                        "platform": platform,
                        "post_id": post_id,
                        "metric": metric,
                        "threshold": level,
                        "current": value,
                        "content": item.get("content", "")[:60],
                        "url": item.get("url", ""),
                        "triggered_at": datetime.now().isoformat(),
                    })
                    seen.add(alert_key)

    _save_seen(seen)
    return alerts


def _load_seen() -> set[str]:
    if ALERTS_FILE.exists():
        try:
            with open(ALERTS_FILE) as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def _save_seen(seen: set[str]) -> None:
    try:
        ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(ALERTS_FILE, "w") as f:
            json.dump(list(seen), f)
    except OSError as e:
        log.warning("Could not save alerts state: %s", e)
