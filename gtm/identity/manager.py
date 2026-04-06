"""Identity manager — add, list, remove, health-check platform accounts.

Identities are stored under ~/.config/gtm/identities/<platform>/<username>/
Each identity has:
  - cookies/session file (platform-specific, SECRET)
  - identity.yaml (metadata: platform, username, auth_method, status, etc.)
  - health.json (last health check result)
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from gtm.config import IDENTITIES_DIR, REGISTRY_PATH

log = logging.getLogger(__name__)


@dataclass
class Identity:
    """A single platform identity (account)."""

    name: str  # "twitter:myhandle"
    platform: str  # "twitter", "reddit", "hn"
    username: str
    auth_method: str = "unknown"  # "password", "browser", "cookies_manual"
    role: str = "default"  # "brand", "organic", "supporter", "scout", "default"
    rate_profile: str = "conservative"  # "conservative", "moderate", "aggressive"
    status: str = "healthy"  # "healthy", "warning", "suspended", "expired"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_used: str | None = None
    notes: str = ""

    @property
    def identity_dir(self) -> Path:
        """Path to this identity's directory."""
        return IDENTITIES_DIR / self.platform / self.username

    @property
    def identity_yaml_path(self) -> Path:
        return self.identity_dir / "identity.yaml"

    @property
    def health_json_path(self) -> Path:
        return self.identity_dir / "health.json"

    def save(self) -> None:
        """Save identity metadata to disk with secure permissions."""
        import os
        import stat

        self.identity_dir.mkdir(parents=True, exist_ok=True)
        # Secure the identity directory — owner-only
        try:
            os.chmod(self.identity_dir, stat.S_IRWXU)  # 0700
        except OSError:
            pass

        with open(self.identity_yaml_path, "w") as f:
            yaml.dump(asdict(self), f, default_flow_style=False)

        # Secure ALL credential files — owner-only read/write
        # Covers .json (cookies), .yaml, and any browser session artifacts
        for secret_file in self.identity_dir.iterdir():
            if secret_file.is_file():
                try:
                    os.chmod(secret_file, stat.S_IRUSR | stat.S_IWUSR)  # 0600
                except OSError as e:
                    log.warning("Cannot secure %s: %s", secret_file, e)

    @classmethod
    def load(cls, identity_dir: Path) -> Identity:
        """Load identity from its directory."""
        yaml_path = identity_dir / "identity.yaml"
        if not yaml_path.exists():
            raise FileNotFoundError(f"No identity.yaml in {identity_dir}")
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def save_health(self, healthy: bool, reason: str = "") -> None:
        """Save health check result."""
        health = {
            "healthy": healthy,
            "reason": reason,
            "checked_at": datetime.now().isoformat(),
        }
        with open(self.health_json_path, "w") as f:
            json.dump(health, f, indent=2)
        self.status = "healthy" if healthy else "expired"
        self.save()


class IdentityManager:
    """Manages all identities across platforms."""

    def __init__(self) -> None:
        IDENTITIES_DIR.mkdir(parents=True, exist_ok=True)

    def list_all(self) -> list[Identity]:
        """List all registered identities."""
        identities = []
        if not IDENTITIES_DIR.exists():
            return identities

        for platform_dir in sorted(IDENTITIES_DIR.iterdir()):
            if not platform_dir.is_dir() or platform_dir.name.startswith("."):
                continue
            for user_dir in sorted(platform_dir.iterdir()):
                if not user_dir.is_dir() or user_dir.name.startswith("_"):
                    continue
                try:
                    identities.append(Identity.load(user_dir))
                except (FileNotFoundError, Exception) as e:
                    log.warning("Skipping %s: %s", user_dir, e)
        return identities

    def list_platform(self, platform: str) -> list[Identity]:
        """List identities for a specific platform."""
        return [i for i in self.list_all() if i.platform == platform]

    def get(self, name: str) -> Identity:
        """Get identity by name (e.g., 'twitter:myhandle').

        Also accepts just the username if there's only one match.
        """
        identities = self.list_all()

        # Exact match on name
        for i in identities:
            if i.name == name:
                return i

        # Try platform:username format
        if ":" in name:
            platform, username = name.split(":", 1)
            identity_dir = IDENTITIES_DIR / platform / username
            if identity_dir.exists():
                return Identity.load(identity_dir)

        # Try matching just username across platforms
        matches = [i for i in identities if i.username == name]
        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            names = [i.name for i in matches]
            raise ValueError(f"Ambiguous identity '{name}'. Matches: {names}")

        raise ValueError(f"Identity not found: {name}")

    def get_for_platform(self, platform: str) -> Identity:
        """Get the identity for a platform (v0.1: single account per platform)."""
        identities = self.list_platform(platform)
        if not identities:
            raise ValueError(
                f"No {platform} account connected. Run: gtm auth {platform}"
            )
        return identities[0]

    def add(self, identity: Identity) -> None:
        """Register a new identity."""
        identity.save()
        self._update_registry()
        log.info("Added identity: %s", identity.name)

    def remove(self, name: str) -> None:
        """Remove an identity and its credentials."""
        import shutil

        identity = self.get(name)
        if identity.identity_dir.exists():
            shutil.rmtree(identity.identity_dir)
        self._update_registry()
        log.info("Removed identity: %s", name)

    def resolve_as_flag(self, as_value: str | None, platform: str) -> Identity:
        """Resolve the --as flag to an Identity.

        If --as is provided, look it up. Otherwise, use the default for the platform.
        """
        if as_value:
            return self.get(as_value)
        return self.get_for_platform(platform)

    def _update_registry(self) -> None:
        """Regenerate registry.yaml from disk state."""
        identities = self.list_all()
        data = {
            "identities": [
                {"name": i.name, "platform": i.platform, "username": i.username}
                for i in identities
            ]
        }
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(REGISTRY_PATH, "w") as f:
            yaml.dump(data, f, default_flow_style=False)
