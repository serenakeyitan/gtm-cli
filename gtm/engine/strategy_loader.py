"""Strategy YAML loader — parse and validate strategy files.

A strategy is a declarative flow definition:
- Which steps to execute, in what order
- Which platform identities to use
- What parameters to pass
- Agents generate content at runtime (not in the YAML)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)


@dataclass
class StrategyStep:
    """A single step in a strategy."""
    id: str
    type: str = "tool"           # "tool" or "agent"
    platform: str = ""           # "twitter", "reddit", "hn"
    action: str = ""             # "search", "post", "submit", etc.
    agent: str = ""              # agent name (for type=agent)
    identity_ref: str = ""       # e.g., "$twitter_account"
    after: str = ""              # step dependency
    params: dict[str, Any] = field(default_factory=dict)
    when: str = ""               # conditional execution


@dataclass
class Strategy:
    """A parsed strategy definition."""
    name: str
    description: str = ""
    version: str = "1.0"
    author: str = ""
    identities: dict[str, dict[str, Any]] = field(default_factory=dict)
    params: dict[str, dict[str, Any]] = field(default_factory=dict)
    steps: list[StrategyStep] = field(default_factory=list)
    source_path: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_dag(self) -> bool:
        """True if this strategy uses the v0.2 module DAG format."""
        return len(self.steps) == 0 and bool(self.raw.get("modules"))

    @classmethod
    def load(cls, path: Path) -> Strategy:
        """Load a strategy from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        if not data or not isinstance(data, dict):
            raise ValueError(f"Invalid strategy file: {path}")

        steps = []
        for step_data in data.get("steps", []):
            steps.append(StrategyStep(
                id=step_data.get("id", "unnamed"),
                type=step_data.get("type", "tool"),
                platform=step_data.get("platform", ""),
                action=step_data.get("action", ""),
                agent=step_data.get("agent", ""),
                identity_ref=step_data.get("as", ""),
                after=step_data.get("after", ""),
                params=step_data.get("params", {}),
                when=step_data.get("when", ""),
            ))

        strategy = cls(
            name=data.get("name", path.stem),
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            author=data.get("author", ""),
            identities=data.get("identities", {}),
            params=data.get("params", {}),
            steps=steps,
            source_path=str(path),
        )
        strategy.raw = data  # Keep raw for DAG detection
        return strategy


def find_strategies() -> list[Path]:
    """Find all available strategy files.

    Search order (user strategies first, then examples):
    1. User strategies: ~/.config/gtm/strategies/ (LOCAL, private)
    2. Project strategies: ./strategies/ (project-specific)
    3. Built-in examples: <package>/strategies/examples/ (shipped with repo)
    """
    paths = []
    seen = set()

    search_dirs = [
        Path("~/.config/gtm/strategies").expanduser(),                  # user's own (local, private)
        Path("./strategies"),                                              # project local
        Path(__file__).parent.parent.parent / "strategies" / "examples",   # shipped examples
    ]

    for d in search_dirs:
        if d.exists():
            for f in sorted(d.glob("*.yaml")) + sorted(d.glob("*.yml")):
                if f.name not in seen:
                    paths.append(f)
                    seen.add(f.name)

    return paths
