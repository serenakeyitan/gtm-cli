"""Tests for the rate limiter."""

import time
from unittest.mock import patch

import pytest

from growth.safety.rate_limiter import RateLimiter, RATE_LIMITS


@pytest.fixture
def limiter(tmp_path):
    """Create a rate limiter with temp state directory."""
    with patch("growth.safety.rate_limiter.RATE_LIMITS_DIR", tmp_path):
        with patch("growth.safety.rate_limiter.STATE_FILE", tmp_path / "state.json"):
            yield RateLimiter()


class TestRateLimiter:
    def test_first_action_allowed(self, limiter):
        result = limiter.check("twitter:test", "twitter", "post")
        assert result.allowed is True

    def test_cooldown_enforced(self, limiter):
        limiter.record("twitter:test", "post")
        result = limiter.check("twitter:test", "twitter", "post")
        assert result.allowed is False
        assert result.wait_seconds > 0
        assert "cooldown" in result.reason.lower()

    def test_hourly_limit_enforced(self, limiter):
        # Twitter post limit is 2/hour
        limiter.record("twitter:test", "post")
        time.sleep(0.01)
        limiter.record("twitter:test", "post")

        # Manually clear cooldown by advancing last timestamp
        key = "twitter:test:post"
        timestamps = limiter._get_timestamps(key)
        # Move timestamps back past cooldown
        adjusted = [t - 400 for t in timestamps]
        limiter._set_timestamps(key, adjusted)

        result = limiter.check("twitter:test", "twitter", "post")
        assert result.allowed is False
        assert "hourly limit" in result.reason.lower()

    def test_different_actions_independent(self, limiter):
        limiter.record("twitter:test", "post")
        # Like should still be allowed even though post was just recorded
        result = limiter.check("twitter:test", "twitter", "like")
        assert result.allowed is True

    def test_different_identities_independent(self, limiter):
        limiter.record("twitter:user1", "post")
        result = limiter.check("twitter:user2", "twitter", "post")
        assert result.allowed is True

    def test_unknown_action_allowed(self, limiter):
        result = limiter.check("twitter:test", "twitter", "unknown_action")
        assert result.allowed is True

    def test_status_report(self, limiter):
        limiter.record("twitter:test", "post")
        status = limiter.get_status("twitter:test", "twitter")
        assert "post" in status
        assert status["post"]["this_hour"] == "1/2"

    def test_search_has_low_cooldown(self, limiter):
        """Search should have very short cooldown (8s for twitter)."""
        limits = RATE_LIMITS["twitter"]["search"]
        assert limits["cooldown_seconds"] == 8
        assert limits["per_hour"] == 30

    def test_hn_submit_strict_limits(self):
        """HN submit should be very strict (1/hr, 2/day, 30min cooldown)."""
        limits = RATE_LIMITS["hn"]["submit"]
        assert limits["per_hour"] == 1
        assert limits["per_day"] == 2
        assert limits["cooldown_seconds"] == 1800
