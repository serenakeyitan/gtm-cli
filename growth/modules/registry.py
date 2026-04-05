"""Module registry — discover, register, and look up composable modules.

Every module registers itself here. Strategies reference modules by name.
The runner resolves names to module instances via this registry.
"""

from __future__ import annotations

import logging
from typing import Any

from growth.modules.base import Module

log = logging.getLogger(__name__)

# Global registry: name → Module instance
_modules: dict[str, Module] = {}


def register(module: Module) -> None:
    """Register a module by name."""
    if not module.name:
        raise ValueError(f"Module has no name: {module}")
    if module.name in _modules:
        log.warning("Overwriting module: %s", module.name)
    _modules[module.name] = module
    log.debug("Registered module: %s (%s)", module.name, module.category)


def get(name: str) -> Module:
    """Get a module by name. Raises KeyError if not found."""
    _ensure_loaded()
    if name not in _modules:
        available = ", ".join(sorted(_modules.keys()))
        raise KeyError(f"Module not found: '{name}'. Available: {available}")
    return _modules[name]


def list_all() -> list[Module]:
    """List all registered modules."""
    _ensure_loaded()
    return sorted(_modules.values(), key=lambda m: (m.category, m.name))


def list_by_category(category: str) -> list[Module]:
    """List modules in a category."""
    _ensure_loaded()
    return [m for m in list_all() if m.category == category]


def list_categories() -> list[str]:
    """List all module categories."""
    _ensure_loaded()
    return sorted(set(m.category for m in _modules.values()))


def search(query: str) -> list[Module]:
    """Search modules by name or description."""
    _ensure_loaded()
    q = query.lower()
    return [m for m in list_all() if q in m.name.lower() or q in m.description.lower()]


# ── Auto-discovery ───────────────────────────────────────────────────

_loaded = False


def _ensure_loaded() -> None:
    """Load all built-in modules on first access."""
    global _loaded
    if _loaded:
        return
    _loaded = True

    # Import all module packages to trigger registration
    _safe_import("growth.modules.sources")
    _safe_import("growth.modules.filters")
    _safe_import("growth.modules.transforms")
    _safe_import("growth.modules.actions")
    _safe_import("growth.modules.monitors")


def _safe_import(module_path: str) -> None:
    """Import a module, ignoring errors (optional dependencies)."""
    try:
        __import__(module_path)
    except ImportError as e:
        log.debug("Could not load %s: %s", module_path, e)
