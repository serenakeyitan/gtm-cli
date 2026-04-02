"""Configuration management for growth-cli.

All user data lives under ~/.config/growth/:
  - config.yaml          Global settings
  - identities/          Platform credentials (SECRET, never in git)
  - rate_limits/          Rate limit state
  - output/              Logs, drafts, posted content (optional git repo)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# XDG-style config directory
CONFIG_DIR = Path(os.environ.get("GROWTH_CONFIG_DIR", "~/.config/growth")).expanduser()
IDENTITIES_DIR = CONFIG_DIR / "identities"
RATE_LIMITS_DIR = CONFIG_DIR / "rate_limits"
OUTPUT_DIR = CONFIG_DIR / "output"
REGISTRY_PATH = IDENTITIES_DIR / "registry.yaml"
CONFIG_PATH = CONFIG_DIR / "config.yaml"


@dataclass
class GrowthConfig:
    """Global growth-cli configuration."""
    output_dir: str = str(OUTPUT_DIR)
    output_git_auto_commit: bool = True
    output_git_auto_push: bool = False
    output_git_remote: str = ""
    default_rate_profile: str = "conservative"
    burner_warning_shown: bool = False

    # Platform-specific seed data
    twitter_seed_accounts: list[str] = field(default_factory=list)

    @classmethod
    def load(cls) -> GrowthConfig:
        """Load config from disk, or return defaults."""
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH) as f:
                data = yaml.safe_load(f) or {}
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        return cls()

    def save(self) -> Path:
        """Save config to disk."""
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            yaml.dump(
                {k: getattr(self, k) for k in self.__dataclass_fields__},
                f,
                default_flow_style=False,
            )
        return CONFIG_PATH


def ensure_dirs() -> None:
    """Create all required directories."""
    for d in [CONFIG_DIR, IDENTITIES_DIR, RATE_LIMITS_DIR, OUTPUT_DIR]:
        d.mkdir(parents=True, exist_ok=True)
