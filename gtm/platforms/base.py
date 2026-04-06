"""Base platform interface.

Every platform adapter must implement this interface.
Adding a new platform = implementing Platform + registering it.

This interface is designed to be extractable to a plugin system later
(v2.0) via setuptools entry_points.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PostResult:
    """Result of a post/submit action."""
    success: bool
    post_id: str | None = None
    url: str | None = None
    error: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class EngageResult:
    """Result of an engagement action (like, upvote, retweet, etc.)."""
    success: bool
    error: str | None = None


@dataclass
class SearchResult:
    """A single search result."""
    id: str
    title: str = ""
    text: str = ""
    url: str = ""
    author: str = ""
    score: int = 0
    timestamp: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthStatus:
    """Result of a health check on an identity's credentials."""
    healthy: bool
    reason: str = ""
    last_checked: str = ""


class Platform(ABC):
    """Abstract base for all platform adapters.

    Each platform provides:
    - Auth: how to log in and save credentials
    - Actions (hands): post, engage, reply
    - Read (eyes): search, get posts, trending
    - Health: verify credentials are still valid
    """

    name: str  # "twitter", "reddit", "hn"

    # ── Auth ──────────────────────────────────────────────────────

    @abstractmethod
    async def auth_interactive(self, identity_dir: Path, **kwargs) -> dict[str, Any]:
        """Run the interactive auth flow for this platform.

        Each platform has its own method:
        - Twitter: username + email + password (terminal prompts)
        - Reddit: opens headed Chrome browser (manual login)
        - HN: opens headed Chrome browser (manual login + reCAPTCHA)

        Returns metadata dict to save in identity.yaml.
        Credentials are saved directly to identity_dir/ by the implementation.
        """
        ...

    @abstractmethod
    async def health_check(self, identity_dir: Path) -> HealthStatus:
        """Check if saved credentials are still valid."""
        ...

    # ── Actions (Hands) ──────────────────────────────────────────

    @abstractmethod
    async def post(self, identity_dir: Path, content: str, **kwargs) -> PostResult:
        """Create a new post/tweet/submission."""
        ...

    @abstractmethod
    async def search(self, identity_dir: Path, query: str, **kwargs) -> list[SearchResult]:
        """Search for content on the platform."""
        ...

    # ── Optional Actions ─────────────────────────────────────────

    async def engage(self, identity_dir: Path, target_id: str, action: str, **kwargs) -> EngageResult:
        """Like, upvote, retweet, etc."""
        raise NotImplementedError(f"{self.name} doesn't support engage()")

    async def reply(self, identity_dir: Path, target_id: str, content: str, **kwargs) -> PostResult:
        """Reply to a post."""
        raise NotImplementedError(f"{self.name} doesn't support reply()")

    async def get_post(self, identity_dir: Path, post_id: str) -> dict[str, Any]:
        """Get a single post by ID."""
        raise NotImplementedError(f"{self.name} doesn't support get_post()")

    async def trending(self, identity_dir: Path, **kwargs) -> list[SearchResult]:
        """Get trending/top content."""
        raise NotImplementedError(f"{self.name} doesn't support trending()")


# ── Platform Registry ────────────────────────────────────────────

_platforms: dict[str, Platform] = {}


def register_platform(platform: Platform) -> None:
    """Register a platform adapter."""
    _platforms[platform.name] = platform


def get_platform(name: str) -> Platform:
    """Get a registered platform by name."""
    if name not in _platforms:
        available = ", ".join(_platforms.keys()) or "none"
        raise ValueError(f"Unknown platform: {name}. Available: {available}")
    return _platforms[name]


def list_platforms() -> list[str]:
    """List all registered platform names."""
    return list(_platforms.keys())
