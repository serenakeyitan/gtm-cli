"""Tests for the gtm SDK facade.

Each public function gets one happy-path test. Tests use deterministic,
no-network modules (filter/limit, control/delay) so they don't require
auth, network, or rate limiter state.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

import gtm
from gtm.modules.base import ModuleResult


# ── list_modules / get_module ─────────────────────────────────────────


def test_list_modules_returns_registered_modules():
    mods = gtm.list_modules()
    assert len(mods) > 0, "registry should have built-in modules"
    names = {m.name for m in mods}
    # Spot-check the always-present primitives
    assert "filter/limit" in names
    assert "filter/engagement" in names
    assert "hn/top_stories" in names


def test_get_module_returns_typed_module():
    m = gtm.get_module("filter/limit")
    assert m.name == "filter/limit"
    assert m.category == "filter"


def test_get_module_raises_keyerror_on_unknown():
    with pytest.raises(KeyError, match="not found"):
        gtm.get_module("nonexistent/module")


# ── run_module / run_module_sync ──────────────────────────────────────


@pytest.mark.asyncio
async def test_run_module_async_filter_limit():
    """filter/limit is a no-auth, no-network deterministic module."""
    upstream = ModuleResult(
        success=True,
        data=[{"id": i} for i in range(5)],
    )
    result = await gtm.run_module("filter/limit", {"count": 3}, upstream)
    assert result.success
    assert result.count == 3
    assert [d["id"] for d in result.data] == [0, 1, 2]


def test_run_module_sync_wrapper():
    """Sync variant builds its own loop — handy for scripts/REPL."""
    upstream = ModuleResult(
        success=True,
        data=[{"id": i} for i in range(4)],
    )
    result = gtm.run_module_sync("filter/limit", {"count": 2}, upstream)
    assert result.success
    assert result.count == 2


@pytest.mark.asyncio
async def test_run_module_unknown_raises():
    with pytest.raises(KeyError):
        await gtm.run_module("nope/nope", {})


# ── run_strategy ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_strategy_executes_dag(tmp_path: Path):
    """A minimal strategy: no source, no auth — just two filters chained."""
    # The DAG runner expects at least one module; chain two deterministic
    # filters using a stub source. We use control/jitter (no-op when min=max=0)
    # to produce a starting result without network.
    strategy_path = tmp_path / "tiny.yaml"
    strategy_path.write_text(dedent("""
        name: tiny-test-strategy
        version: "2.0"
        modules:
          source:
            use: control/jitter
            params: { min_seconds: 0, max_seconds: 0 }
          limited:
            use: filter/limit
            input: source
            params: { count: 1 }
    """))
    state = await gtm.run_strategy(strategy_path)
    assert state["status"] in {"completed", "running"}, state
    assert "limited" in state["modules"]
    assert state["modules"]["limited"]["status"] in {"success", "skipped"}


# ── Re-exports ────────────────────────────────────────────────────────


def test_module_result_reexported():
    """`ModuleResult` is part of the SDK surface — agents return them."""
    r = gtm.ModuleResult(success=True, data=[{"x": 1}])
    assert r.count == 1
    assert bool(r) is True


def test_module_context_reexported():
    """`ModuleContext` is part of the SDK surface for advanced callers."""
    ctx = gtm.ModuleContext(dry_run=True)
    assert ctx.dry_run is True
