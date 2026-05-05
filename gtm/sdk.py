"""gtm SDK — call modules and strategies as Python.

Thin facade over `gtm.modules.registry` and `gtm.engine.dag_runner`.
Exposes the same surface to two consumers: the CLI (today) and an MCP
server (Phase 2). No business logic lives here — this file is a router.

Public functions are async by default. Sync wrappers (`*_sync`) are
provided for callers that can't await (e.g. simple scripts, REPL).

See docs/PLAN-claude-code-shape.md Phase 1 for design intent.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import yaml

from gtm.engine.dag_runner import run_dag_strategy
from gtm.identity.manager import IdentityManager
from gtm.modules import registry
from gtm.modules.base import Module, ModuleContext, ModuleResult

log = logging.getLogger(__name__)


__all__ = [
    "run_module",
    "run_module_sync",
    "run_strategy",
    "run_strategy_sync",
    "list_modules",
    "get_module",
    "ModuleResult",
    "ModuleContext",
]


def _ensure_platforms_registered() -> None:
    """Import platform modules to trigger registration.

    The CLI does this before every command; the SDK does it before every
    call so importers don't have to remember.
    """
    for mod in (
        "gtm.platforms.twitter.platform",
        "gtm.platforms.reddit.platform",
        "gtm.platforms.hn.platform",
    ):
        try:
            __import__(mod)
        except ImportError:
            pass


def _build_context(
    module: Module,
    *,
    dry_run: bool,
    identity: str | None,
) -> ModuleContext:
    """Build a ModuleContext, resolving identity if the module needs auth.

    `identity` is a platform name ("twitter") or an explicit identity name.
    If None, falls back to the module's default platform identity.
    """
    ctx = ModuleContext(dry_run=dry_run)

    if not module.requires_auth:
        return ctx

    platform = module.platform
    if not platform:
        return ctx

    mgr = IdentityManager()
    try:
        if identity and ":" in identity:
            ident = mgr.get(identity)
        else:
            ident = mgr.get_for_platform(identity or platform)
        ctx.identity_dir = ident.identity_dir
        ctx.identity_name = ident.name
    except (ValueError, KeyError) as e:
        if not dry_run:
            raise
        log.debug("SDK: auth not available for %s (dry-run, continuing): %s", module.name, e)

    return ctx


# ── Modules ───────────────────────────────────────────────────────────


async def run_module(
    name: str,
    params: dict[str, Any] | None = None,
    input_data: ModuleResult | None = None,
    *,
    dry_run: bool = False,
    identity: str | None = None,
) -> ModuleResult:
    """Run a single module by name.

    Args:
        name: Module name like "twitter/search" or "reddit/submit".
        params: Module params (matches `Module.param_schema`).
        input_data: Upstream ModuleResult (None for sources).
        dry_run: If True, the module skips destructive side effects.
        identity: Platform ("twitter") or full identity ("twitter:handle").
                  Defaults to the platform's primary identity.

    Returns:
        ModuleResult — uniform shape regardless of module category.

    Raises:
        KeyError: module not registered.
        ValueError: auth required but no identity available (and not dry_run).
    """
    _ensure_platforms_registered()
    module = registry.get(name)
    ctx = _build_context(module, dry_run=dry_run, identity=identity)
    return await module.run(input_data, params or {}, ctx)


def run_module_sync(
    name: str,
    params: dict[str, Any] | None = None,
    input_data: ModuleResult | None = None,
    *,
    dry_run: bool = False,
    identity: str | None = None,
) -> ModuleResult:
    """Sync wrapper around `run_module` for non-async callers."""
    return asyncio.run(
        run_module(name, params, input_data, dry_run=dry_run, identity=identity)
    )


def list_modules() -> list[Module]:
    """Return all registered modules, sorted by category then name."""
    _ensure_platforms_registered()
    return registry.list_all()


def get_module(name: str) -> Module:
    """Look up a single module by name. Raises KeyError if missing."""
    _ensure_platforms_registered()
    return registry.get(name)


# ── Strategies ────────────────────────────────────────────────────────


async def run_strategy(
    path: str | Path,
    params: dict[str, Any] | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run a strategy YAML file as a DAG.

    Args:
        path: Path to a strategy YAML.
        params: User param overrides (matches strategy's `params` block).
        dry_run: If True, modules run in dry_run mode.

    Returns:
        Run state dict with per-module results — see `run_dag_strategy`.
    """
    _ensure_platforms_registered()
    strategy = yaml.safe_load(Path(path).read_text())
    if not isinstance(strategy, dict):
        raise ValueError(f"Strategy at {path} is not a YAML mapping")
    return await run_dag_strategy(strategy, params or {}, dry_run=dry_run)


def run_strategy_sync(
    path: str | Path,
    params: dict[str, Any] | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Sync wrapper around `run_strategy`."""
    return asyncio.run(run_strategy(path, params, dry_run=dry_run))
