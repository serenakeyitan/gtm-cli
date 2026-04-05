"""strategy/* — Use any strategy as a composable module.

This is the fractal composability piece: strategies ARE modules.
A "Full Launch Campaign" can reference "Show HN Launch" and
"Reddit Organic Seed" as sub-strategies.

Usage in YAML:
  modules:
    hn_launch:
      use: strategy/show-hn-launch
      params: { topic: "my product" }
    reddit_launch:
      use: strategy/reddit-organic
      params: { topic: "my product" }
    announce:
      use: twitter/post
      input: [hn_launch, reddit_launch]
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from growth.modules.base import Module, ModuleResult, ModuleContext
from growth.modules import registry as mod_registry

log = logging.getLogger(__name__)


class StrategyModule(Module):
    """A module that wraps a strategy YAML file.

    Dynamically created when the registry encounters a 'strategy/*' name.
    """

    category = "strategy"
    description = ""
    requires_auth = False

    def __init__(self, name: str, strategy_path: Path):
        self.name = name
        self.strategy_path = strategy_path

        # Load description from the strategy
        import yaml
        with open(strategy_path) as f:
            data = yaml.safe_load(f) or {}
        self.description = data.get("description", f"Strategy: {strategy_path.stem}")
        self.param_schema = {
            k: v if isinstance(v, dict) else {"default": v}
            for k, v in data.get("params", {}).items()
        }
        self._raw = data

    # Track recursion to prevent infinite loops
    _active_strategies: set[str] = set()
    MAX_DEPTH = 5

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        """Execute the sub-strategy and return its results as a ModuleResult."""
        # Cycle/depth guard
        if self.name in StrategyModule._active_strategies:
            return ModuleResult(success=False, errors=[f"Cycle detected: {self.name} is already running"])
        if len(StrategyModule._active_strategies) >= self.MAX_DEPTH:
            return ModuleResult(success=False, errors=[f"Max nesting depth ({self.MAX_DEPTH}) exceeded"])

        StrategyModule._active_strategies.add(self.name)
        try:
            return await self._execute(params, context)
        finally:
            StrategyModule._active_strategies.discard(self.name)

    async def _execute(self, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        from growth.engine.dag_runner import run_dag_strategy
        from growth.engine.strategy_loader import Strategy

        strategy = Strategy.load(self.strategy_path)

        if strategy.is_dag:
            state = await run_dag_strategy(strategy.raw, params, dry_run=context.dry_run)
        else:
            from growth.engine.runner import run_strategy
            state = await run_strategy(strategy, params, dry_run=context.dry_run)

        # Collect output from sub-strategy — DAG stores in 'modules', legacy in 'steps'
        all_data = []
        modules_state = state.get("modules") or state.get("steps") or {}
        for mod_name, mod_state in modules_state.items():
            # DAG runner stores count/metadata but not raw data in state
            # Legacy runner stores result dicts
            result = mod_state.get("result", {})
            if isinstance(result, dict):
                if "results" in result:
                    all_data.extend(result["results"])
                elif result.get("success"):
                    all_data.append(result)

        success = state.get("status", "").startswith("completed")
        errors = state.get("errors", [])

        return ModuleResult(
            success=success and len(errors) == 0,
            data=all_data,
            metadata={"sub_strategy": self.name, "status": state.get("status"), "modules": len(modules_state)},
            errors=errors,
        )


def register_strategy_modules() -> None:
    """Discover all strategy YAML files and register them as 'strategy/*' modules."""
    from growth.engine.strategy_loader import find_strategies

    for path in find_strategies():
        name = f"strategy/{path.stem}"
        try:
            mod = StrategyModule(name=name, strategy_path=path)
            mod_registry.register(mod)
        except Exception as e:
            log.debug("Could not register strategy module %s: %s", name, e)
