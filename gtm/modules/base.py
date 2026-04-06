"""Module base — the contract every module implements.

Every module: Source, Filter, Transform, Action, Monitor, Control
takes ModuleResult in, produces ModuleResult out.

This is the Lego interface. If it implements Module, it composes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModuleResult:
    """Standard I/O for all modules.

    Every module produces this. Every module consumes this (or None for sources).
    This is what makes composition work — uniform interface.
    """
    success: bool
    data: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.data)

    def __bool__(self) -> bool:
        return self.success

    def pipe(self, other_result: ModuleResult) -> ModuleResult:
        """Merge two results (for parallel branches joining)."""
        return ModuleResult(
            success=self.success and other_result.success,
            data=self.data + other_result.data,
            metadata={**self.metadata, **other_result.metadata},
            errors=self.errors + other_result.errors,
        )


@dataclass
class ModuleContext:
    """Infrastructure passed to every module — transparent to the user.

    The user never creates this. The runner builds it from config + identity.
    """
    identity_dir: Any = None       # Path to identity credentials
    identity_name: str = ""        # e.g., "twitter:myhandle"
    rate_limiter: Any = None       # RateLimiter instance
    config: Any = None             # GrowthConfig
    dry_run: bool = False


class Module(ABC):
    """Abstract base for all composable modules.

    Subclass this to create any module — source, filter, transform,
    action, monitor, or control.
    """

    # Every module declares these
    name: str = ""                  # "twitter/search", "filter/engagement"
    category: str = ""              # "source", "filter", "transform", "action", "monitor", "control"
    description: str = ""
    platform: str = ""              # "twitter", "reddit", "hn", "" (platform-agnostic)
    requires_auth: bool = False     # Does this module need an identity?

    # Schema for documentation / validation
    input_schema: dict[str, Any] = {}
    output_schema: dict[str, Any] = {}
    param_schema: dict[str, Any] = {}

    @abstractmethod
    async def run(
        self,
        input_data: ModuleResult | None,
        params: dict[str, Any],
        context: ModuleContext,
    ) -> ModuleResult:
        """Execute the module.

        Args:
            input_data: Output from upstream module. None for sources.
            params: User-provided parameters from the strategy YAML.
            context: Identity, rate limiter, config (transparent infrastructure).

        Returns:
            ModuleResult with standardized data format.
        """
        ...

    def __repr__(self) -> str:
        return f"<Module {self.name} ({self.category})>"
