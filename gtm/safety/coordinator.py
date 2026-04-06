"""5-Layer Rate Limit Coordinator.

Goes beyond per-account limits to prevent detection at the IP,
platform, behavioral, and cross-platform levels.

Layer 1: Per-account limits (existing rate_limiter.py)
Layer 2: Per-IP limits (multiple accounts on same proxy)
Layer 3: Per-platform global limits (all accounts combined)
Layer 4: Behavioral pattern (time-of-day, action sequencing)
Layer 5: Cross-platform correlation (don't post same URL everywhere at once)
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from gtm.safety.rate_limiter import RateLimiter, RateLimitResult, get_rate_limiter

log = logging.getLogger(__name__)

# Layer 3: Platform-wide limits (all accounts combined)
PLATFORM_GLOBAL_LIMITS = {
    "twitter": {
        "post": {"per_hour": 10, "per_day": 30},      # across ALL twitter accounts
        "like": {"per_hour": 50, "per_day": 200},
    },
    "reddit": {
        "post": {"per_hour": 3, "per_day": 8},
        "comment": {"per_hour": 10, "per_day": 40},
    },
    "hn": {
        "submit": {"per_hour": 2, "per_day": 4},
        "comment": {"per_hour": 5, "per_day": 15},
    },
}

# Layer 4: Behavioral rules
QUIET_HOURS = (1, 6)  # 1am-6am local time — posting looks bot-like
JITTER_RANGE = (0.6, 1.4)  # ±40% timing jitter


@dataclass
class CoordinatorResult:
    """Result from the full 5-layer check."""
    allowed: bool
    layer: str = ""           # which layer blocked it
    reason: str = ""
    wait_seconds: float = 0.0
    jitter_delay: float = 0.0  # recommended additional delay for human-like timing


class RateLimitCoordinator:
    """5-layer rate limit coordinator.

    Every action goes through all 5 layers. ALL must pass.
    State persists to disk so limits survive across CLI invocations.
    """

    def __init__(self):
        self._account_limiter = get_rate_limiter()
        self._state = self._load_state()

    @property
    def _global_actions(self) -> dict[str, list[float]]:
        return self._state.setdefault("global_actions", {})

    @property
    def _cross_platform_urls(self) -> dict[str, float]:
        return self._state.setdefault("cross_platform_urls", {})

    def _load_state(self) -> dict:
        import json
        from gtm.config import RATE_LIMITS_DIR
        path = RATE_LIMITS_DIR / "coordinator_state.json"
        if path.exists():
            try:
                with open(path) as f:
                    return json.load(f)
            except Exception:
                pass
        return {"global_actions": {}, "cross_platform_urls": {}}

    def _save_state(self) -> None:
        import json
        from gtm.config import RATE_LIMITS_DIR
        RATE_LIMITS_DIR.mkdir(parents=True, exist_ok=True)
        path = RATE_LIMITS_DIR / "coordinator_state.json"
        with open(path, "w") as f:
            json.dump(self._state, f)

    def check(
        self,
        identity_name: str,
        platform: str,
        action: str,
        proxy: str = "",
        target_url: str = "",
    ) -> CoordinatorResult:
        """Run all 5 layers. Returns allowed=True only if ALL pass."""

        # Layer 1: Per-account
        l1 = self._account_limiter.check(identity_name, platform, action)
        if not l1.allowed:
            return CoordinatorResult(
                allowed=False, layer="account", reason=l1.reason, wait_seconds=l1.wait_seconds
            )

        # Layer 2: Per-IP (if proxy specified, check other accounts on same proxy)
        if proxy:
            l2 = self._check_ip_limit(proxy, platform, action)
            if not l2.allowed:
                return l2

        # Layer 3: Platform global
        l3 = self._check_platform_global(platform, action)
        if not l3.allowed:
            return l3

        # Layer 4: Behavioral
        l4 = self._check_behavioral(platform, action)
        if not l4.allowed:
            return l4

        # Layer 5: Cross-platform URL correlation
        if target_url:
            l5 = self._check_cross_platform(target_url)
            if not l5.allowed:
                return l5

        # All layers pass — add jitter for human-like timing
        jitter = random.uniform(*JITTER_RANGE)
        base_delay = {"post": 5, "submit": 5, "like": 1, "comment": 3}.get(action, 2)

        return CoordinatorResult(
            allowed=True,
            jitter_delay=base_delay * jitter,
        )

    def record(self, identity_name: str, platform: str, action: str, target_url: str = "") -> None:
        """Record an action across all layers. Persists to disk."""
        self._account_limiter.record(identity_name, action)

        # Layer 3: global
        key = f"{platform}:{action}"
        if key not in self._global_actions:
            self._global_actions[key] = []
        self._global_actions[key].append(time.time())

        # Layer 5: cross-platform URL
        if target_url:
            self._cross_platform_urls[target_url] = time.time()

        self._save_state()

    def _check_ip_limit(self, proxy: str, platform: str, action: str) -> CoordinatorResult:
        """Layer 2: Don't have too many accounts active on the same IP.

        TODO: Track per-proxy action timestamps. For now, passes through
        (per-account limits in Layer 1 provide baseline protection).
        """
        return CoordinatorResult(allowed=True)

    def _check_platform_global(self, platform: str, action: str) -> CoordinatorResult:
        """Layer 3: Total actions across ALL accounts on one platform."""
        limits = PLATFORM_GLOBAL_LIMITS.get(platform, {}).get(action)
        if not limits:
            return CoordinatorResult(allowed=True)

        key = f"{platform}:{action}"
        timestamps = self._global_actions.get(key, [])
        now = time.time()

        # Clean old entries
        timestamps = [t for t in timestamps if t > now - 86400]
        self._global_actions[key] = timestamps

        hour_count = sum(1 for t in timestamps if t > now - 3600)
        day_count = len(timestamps)

        per_hour = limits.get("per_hour", float("inf"))
        per_day = limits.get("per_day", float("inf"))

        if hour_count >= per_hour:
            return CoordinatorResult(
                allowed=False, layer="platform_global",
                reason=f"Platform-wide hourly limit: {hour_count}/{per_hour} {action}s across all {platform} accounts",
            )
        if day_count >= per_day:
            return CoordinatorResult(
                allowed=False, layer="platform_global",
                reason=f"Platform-wide daily limit: {day_count}/{per_day} {action}s across all {platform} accounts",
            )
        return CoordinatorResult(allowed=True)

    def _check_behavioral(self, platform: str, action: str) -> CoordinatorResult:
        """Layer 4: Time-of-day and pattern checks."""
        hour = datetime.now().hour
        if QUIET_HOURS[0] <= hour < QUIET_HOURS[1]:
            return CoordinatorResult(
                allowed=False, layer="behavioral",
                reason=f"Quiet hours ({QUIET_HOURS[0]}am-{QUIET_HOURS[1]}am). Posting now looks automated.",
                wait_seconds=(QUIET_HOURS[1] - hour) * 3600,
            )
        return CoordinatorResult(allowed=True)

    def _check_cross_platform(self, target_url: str) -> CoordinatorResult:
        """Layer 5: Don't post the same URL across platforms too fast."""
        last = self._cross_platform_urls.get(target_url)
        if last:
            elapsed = time.time() - last
            min_gap = 1800  # 30 minutes between same URL on different platforms
            if elapsed < min_gap:
                wait = min_gap - elapsed
                return CoordinatorResult(
                    allowed=False, layer="cross_platform",
                    reason=f"Same URL posted {int(elapsed)}s ago. Wait {int(wait)}s to avoid cross-platform correlation.",
                    wait_seconds=wait,
                )
        return CoordinatorResult(allowed=True)


# Singleton
_coordinator: RateLimitCoordinator | None = None


def get_coordinator() -> RateLimitCoordinator:
    global _coordinator
    if _coordinator is None:
        _coordinator = RateLimitCoordinator()
    return _coordinator
