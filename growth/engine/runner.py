"""Strategy runner — sequential execution of strategy steps.

Migrated and simplified from growth-sop-pipeline/runner.py.
v0.1: Sequential execution only. v0.2 will add DAG/parallel.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from growth.engine.strategy_loader import Strategy, StrategyStep
from growth.identity.manager import IdentityManager
from growth.safety.rate_limiter import get_rate_limiter

log = logging.getLogger(__name__)


async def run_strategy(
    strategy: Strategy,
    user_params: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute a strategy sequentially.

    Returns a run state dict with results from each step.
    """
    from growth.platforms.base import get_platform

    mgr = IdentityManager()
    limiter = get_rate_limiter()
    user_params = user_params or {}

    state = {
        "strategy": strategy.name,
        "started_at": datetime.now().isoformat(),
        "status": "running",
        "params": user_params,
        "steps": {},
        "errors": [],
    }

    log.info("Running strategy: %s (%d steps)", strategy.name, len(strategy.steps))

    # Resolve params (merge strategy defaults with user overrides)
    resolved_params = {}
    for name, param_def in strategy.params.items():
        if name in user_params:
            resolved_params[name] = user_params[name]
        elif "default" in param_def:
            resolved_params[name] = param_def["default"]
        elif param_def.get("required", False):
            state["status"] = "failed"
            state["errors"].append(f"Missing required param: {name}")
            return state

    # Execute steps sequentially
    step_outputs: dict[str, Any] = {}

    for step in strategy.steps:
        step_id = step.id
        log.info("Step [%s]: type=%s platform=%s action=%s",
                 step_id, step.type, step.platform, step.action)

        # Check dependency
        if step.after and step.after not in step_outputs:
            log.warning("Step [%s]: dependency '%s' not found, skipping", step_id, step.after)
            state["steps"][step_id] = {"status": "skipped", "reason": f"dependency {step.after} missing"}
            continue

        # Resolve identity
        identity = None
        if step.identity_ref:
            ref = step.identity_ref.lstrip("$")
            identity_spec = strategy.identities.get(ref, {})
            platform = identity_spec.get("platform", step.platform)
            try:
                identity = mgr.get_for_platform(platform)
            except ValueError as e:
                if identity_spec.get("optional"):
                    log.info("Step [%s]: optional identity not available, skipping", step_id)
                    state["steps"][step_id] = {"status": "skipped", "reason": str(e)}
                    continue
                raise
        elif step.platform:
            try:
                identity = mgr.get_for_platform(step.platform)
            except ValueError:
                pass

        if dry_run:
            log.info("Step [%s]: DRY RUN — would execute %s/%s", step_id, step.platform, step.action)
            state["steps"][step_id] = {
                "status": "dry_run",
                "platform": step.platform,
                "action": step.action,
                "params": step.params,
            }
            step_outputs[step_id] = {"dry_run": True}
            continue

        # Execute tool step
        if step.type == "tool" and step.platform and step.action:
            try:
                plat = get_platform(step.platform)
                result = await _execute_tool_step(plat, identity, step, resolved_params, limiter)
                state["steps"][step_id] = {"status": "success", "result": result}
                step_outputs[step_id] = result
            except Exception as e:
                log.error("Step [%s] failed: %s", step_id, e)
                state["steps"][step_id] = {"status": "failed", "error": str(e)}
                state["errors"].append(f"Step {step_id}: {e}")

        # Agent steps (v0.3 — placeholder)
        elif step.type == "agent":
            log.info("Step [%s]: agent steps not yet implemented (v0.3)", step_id)
            state["steps"][step_id] = {"status": "skipped", "reason": "agent steps coming in v0.3"}

        else:
            log.warning("Step [%s]: unknown step type or missing platform/action", step_id)
            state["steps"][step_id] = {"status": "skipped", "reason": "unknown step type"}

    # Finalize
    has_errors = len(state["errors"]) > 0
    state["status"] = "completed_with_errors" if has_errors else "completed"
    state["completed_at"] = datetime.now().isoformat()

    # Log the run
    from growth.output.logger import log_run
    log_run(strategy.name, state)

    return state


async def _execute_tool_step(
    platform,
    identity,
    step: StrategyStep,
    resolved_params: dict[str, Any],
    limiter,
) -> dict[str, Any]:
    """Execute a single tool step."""
    action = step.action
    params = step.params

    # Substitute resolved params into step params
    for key, val in params.items():
        if isinstance(val, str) and val.startswith("{{ params."):
            param_name = val.replace("{{ params.", "").replace(" }}", "").strip()
            if param_name in resolved_params:
                params[key] = resolved_params[param_name]

    identity_dir = identity.identity_dir if identity else None

    if action == "search":
        query = params.get("query", "")
        count = params.get("count", 20)
        results = await platform.search(identity_dir, query, count=count)
        return {"results": [{"id": r.id, "title": r.title, "score": r.score} for r in results]}

    elif action in ("post", "submit"):
        content = params.get("content", params.get("text", ""))
        result = await platform.post(identity_dir, content, **params)
        return {"success": result.success, "post_id": result.post_id, "url": result.url}

    elif action == "trending":
        results = await platform.trending(identity_dir, **params)
        return {"results": [{"id": r.id, "title": r.title, "score": r.score} for r in results]}

    else:
        return {"warning": f"Unknown action: {action}"}
