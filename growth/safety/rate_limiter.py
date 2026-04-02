"""Rate limiter — protects accounts from getting banned.

ALWAYS ON. Cannot be bypassed except with --force (which prints a warning).

Conservative defaults well below platform detection thresholds.
"Users can wait. Users cannot bear their accounts getting banned."

State is persisted to disk so limits survive across CLI invocations.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from growth.config import RATE_LIMITS_DIR

log = logging.getLogger(__name__)

# ── Default Rate Limits ──────────────────────────────────────────────
# These are CONSERVATIVE — well below actual platform thresholds.
# The goal is account safety, not speed.

RATE_LIMITS: dict[str, dict[str, dict[str, int]]] = {
    "twitter": {
        "post": {"per_hour": 2, "per_day": 6, "cooldown_seconds": 300},
        "like": {"per_hour": 10, "per_day": 50, "cooldown_seconds": 30},
        "reply": {"per_hour": 3, "per_day": 15, "cooldown_seconds": 120},
        "retweet": {"per_hour": 5, "per_day": 25, "cooldown_seconds": 60},
        "follow": {"per_hour": 5, "per_day": 20, "cooldown_seconds": 60},
        "search": {"per_hour": 30, "per_day": 200, "cooldown_seconds": 8},
    },
    "reddit": {
        "post": {"per_hour": 1, "per_day": 3, "cooldown_seconds": 600},
        "comment": {"per_hour": 3, "per_day": 15, "cooldown_seconds": 180},
        "upvote": {"per_hour": 10, "per_day": 50, "cooldown_seconds": 30},
        "search": {"per_hour": 20, "per_day": 100, "cooldown_seconds": 10},
    },
    "hn": {
        "submit": {"per_hour": 1, "per_day": 2, "cooldown_seconds": 1800},
        "comment": {"per_hour": 2, "per_day": 10, "cooldown_seconds": 300},
        "upvote": {"per_hour": 5, "per_day": 30, "cooldown_seconds": 60},
        "search": {"per_hour": 60, "per_day": 500, "cooldown_seconds": 5},
    },
}

STATE_FILE = RATE_LIMITS_DIR / "state.json"


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    reason: str = ""
    wait_seconds: float = 0.0  # How long to wait before retrying

    @property
    def wait_display(self) -> str:
        """Human-readable wait time."""
        if self.wait_seconds <= 0:
            return ""
        m, s = divmod(int(self.wait_seconds), 60)
        if m > 0:
            return f"{m}m {s:02d}s"
        return f"{s}s"


class RateLimiter:
    """Per-account rate limit enforcement.

    Tracks action counts and cooldowns per identity.
    State persists to disk across CLI invocations.
    """

    def __init__(self) -> None:
        RATE_LIMITS_DIR.mkdir(parents=True, exist_ok=True)
        self._state: dict[str, dict[str, list[float]]] = self._load_state()

    # ── Core API ─────────────────────────────────────────────────────

    def check(self, identity_name: str, platform: str, action: str) -> RateLimitResult:
        """Check if an action is allowed right now.

        Returns RateLimitResult with allowed=True or wait_seconds > 0.
        """
        limits = RATE_LIMITS.get(platform, {}).get(action)
        if not limits:
            return RateLimitResult(allowed=True)  # Unknown action = no limit

        now = time.time()
        key = f"{identity_name}:{action}"
        timestamps = self._get_timestamps(key)

        # Clean old timestamps (older than 24h)
        cutoff_24h = now - 86400
        timestamps = [t for t in timestamps if t > cutoff_24h]
        self._set_timestamps(key, timestamps)

        # Check cooldown (time since last action)
        cooldown = limits.get("cooldown_seconds", 0)
        if timestamps and cooldown > 0:
            elapsed = now - timestamps[-1]
            if elapsed < cooldown:
                wait = cooldown - elapsed
                return RateLimitResult(
                    allowed=False,
                    reason=f"Cooldown active ({int(wait)}s remaining)",
                    wait_seconds=wait,
                )

        # Check per-hour limit
        per_hour = limits.get("per_hour", float("inf"))
        cutoff_1h = now - 3600
        this_hour = [t for t in timestamps if t > cutoff_1h]
        if len(this_hour) >= per_hour:
            oldest_in_hour = min(this_hour)
            wait = oldest_in_hour + 3600 - now
            return RateLimitResult(
                allowed=False,
                reason=f"Hourly limit reached ({len(this_hour)}/{per_hour}). Next slot in {int(wait)}s",
                wait_seconds=max(wait, 0),
            )

        # Check per-day limit
        per_day = limits.get("per_day", float("inf"))
        this_day = timestamps  # already filtered to 24h
        if len(this_day) >= per_day:
            oldest_in_day = min(this_day)
            wait = oldest_in_day + 86400 - now
            return RateLimitResult(
                allowed=False,
                reason=f"Daily limit reached ({len(this_day)}/{per_day}). Next slot in {int(wait)}s",
                wait_seconds=max(wait, 0),
            )

        return RateLimitResult(allowed=True)

    def record(self, identity_name: str, action: str) -> None:
        """Record that an action was taken (call AFTER successful execution)."""
        key = f"{identity_name}:{action}"
        timestamps = self._get_timestamps(key)
        timestamps.append(time.time())
        self._set_timestamps(key, timestamps)
        self._save_state()

    def get_status(self, identity_name: str, platform: str) -> dict[str, Any]:
        """Get current rate limit status for an identity."""
        now = time.time()
        status = {}
        limits = RATE_LIMITS.get(platform, {})

        for action, limit_config in limits.items():
            key = f"{identity_name}:{action}"
            timestamps = self._get_timestamps(key)
            cutoff_1h = now - 3600
            cutoff_24h = now - 86400

            this_hour = len([t for t in timestamps if t > cutoff_1h])
            this_day = len([t for t in timestamps if t > cutoff_24h])

            cooldown_remaining = 0
            if timestamps:
                cooldown = limit_config.get("cooldown_seconds", 0)
                elapsed = now - timestamps[-1]
                if elapsed < cooldown:
                    cooldown_remaining = cooldown - elapsed

            status[action] = {
                "this_hour": f"{this_hour}/{limit_config.get('per_hour', '∞')}",
                "this_day": f"{this_day}/{limit_config.get('per_day', '∞')}",
                "cooldown": f"{int(cooldown_remaining)}s" if cooldown_remaining > 0 else "ready",
            }

        return status

    # ── State persistence ────────────────────────────────────────────

    def _get_timestamps(self, key: str) -> list[float]:
        return self._state.get(key, [])

    def _set_timestamps(self, key: str, timestamps: list[float]) -> None:
        self._state[key] = timestamps

    def _load_state(self) -> dict[str, list[float]]:
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE) as f:
                    return json.load(f)
            except (json.JSONDecodeError, Exception) as e:
                log.warning("Failed to load rate limit state: %s", e)
        return {}

    def _save_state(self) -> None:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(self._state, f)


# ── Module-level singleton ────────────────────────────────────────────

_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter()
    return _limiter
