"""Strategy runner — sequential execution of strategy steps.

Migrated and simplified from growth-sop-pipeline/runner.py.
v0.1: Sequential execution only. v0.2 will add DAG/parallel.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from gtm.engine.strategy_loader import Strategy, StrategyStep
from gtm.identity.manager import IdentityManager
from gtm.safety.rate_limiter import get_rate_limiter

log = logging.getLogger(__name__)


async def run_strategy(
    strategy: Strategy,
    user_params: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute a strategy sequentially.

    Returns a run state dict with results from each step.
    """
    from gtm.platforms.base import get_platform

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

        # Agent steps — requires claude-agent-sdk (pip install gtm-cli[agents])
        elif step.type == "agent":
            try:
                result = await _execute_agent_step(step, resolved_params, step_outputs, mgr)
                state["steps"][step_id] = {"status": "success", "result": result}
                step_outputs[step_id] = result
            except ImportError:
                log.warning("Step [%s]: claude-agent-sdk not installed. Run: pip install gtm-cli[agents]", step_id)
                state["steps"][step_id] = {"status": "skipped", "reason": "Install agents: pip install gtm-cli[agents]"}
            except Exception as e:
                log.error("Step [%s] failed: %s", step_id, e)
                state["steps"][step_id] = {"status": "failed", "error": str(e)}
                state["errors"].append(f"Step {step_id}: {e}")

        else:
            log.warning("Step [%s]: unknown step type or missing platform/action", step_id)
            state["steps"][step_id] = {"status": "skipped", "reason": "unknown step type"}

    # Finalize
    has_errors = len(state["errors"]) > 0
    state["status"] = "completed_with_errors" if has_errors else "completed"
    state["completed_at"] = datetime.now().isoformat()

    # Log the run
    from gtm.output.logger import log_run
    log_run(strategy.name, state)

    return state


async def _execute_agent_step(
    step: StrategyStep,
    resolved_params: dict[str, Any],
    step_outputs: dict[str, Any],
    mgr: IdentityManager,
) -> dict[str, Any]:
    """Execute an LLM agent step using Claude Code SDK.

    Maps agent names to their run functions from gtm.agents.*
    """
    agent_name = step.agent
    params = dict(step.params)

    # Resolve param references
    for key, val in params.items():
        if isinstance(val, str) and val.startswith("{{ params."):
            param_name = val.replace("{{ params.", "").replace(" }}", "").strip()
            if param_name in resolved_params:
                params[key] = resolved_params[param_name]
        # Resolve step output references like "{{ scout.output }}"
        if isinstance(val, str) and "{{" in val:
            for step_id, output in step_outputs.items():
                ref = f"{{{{ {step_id}.output }}}}"
                if val.strip() == ref:
                    params[key] = output
                    break

    # Map agent names to their functions
    agent_map = {
        "scout": ("gtm.agents.scout", "run_twitter_scout"),
        "novelty_checker": ("gtm.agents.novelty_checker", "run_novelty_checker"),
        "builder": ("gtm.agents.builder", "run_builder"),
        "tester": ("gtm.agents.tester", "run_tester"),
        "promoter": ("gtm.agents.promoter", "run_promoter"),
        "hn_promoter": ("gtm.agents.hn_promoter", "run_hn_promoter"),
    }

    if agent_name not in agent_map:
        raise ValueError(f"Unknown agent: {agent_name}. Available: {list(agent_map.keys())}")

    module_path, func_name = agent_map[agent_name]

    import importlib
    module = importlib.import_module(module_path)
    agent_fn = getattr(module, func_name)

    log.info("Running agent: %s (function: %s.%s)", agent_name, module_path, func_name)

    # Build state and config objects the agents expect
    from gtm.engine.state import RunState
    run_state = RunState.create("gtm-cli-run")

    # Build a config-like object with the attributes agents expect
    from gtm.config import IDENTITIES_DIR
    config = _build_agent_config(IDENTITIES_DIR)

    # Agents have different signatures — adapt per agent
    if agent_name == "scout":
        result = await agent_fn(run_state, config, activity_logger=None)
    elif agent_name in ("promoter", "hn_promoter"):
        result = await agent_fn(run_state, {"ideas": params.get("ideas", []), "config": config}, activity_logger=None)
    elif agent_name == "novelty_checker":
        result = await agent_fn(run_state, params.get("ideas", []), activity_logger=None)
    elif agent_name == "builder":
        result = await agent_fn(run_state, params.get("ideas", []), activity_logger=None)
    elif agent_name == "tester":
        result = await agent_fn(run_state, params.get("builds", []), activity_logger=None)
    else:
        result = await agent_fn(run_state, params, activity_logger=None)

    return result


def _build_agent_config(identities_dir: Path) -> Any:
    """Build a config object with attributes the legacy agents expect."""

    class _TwitterConfig:
        def __init__(self):
            twitter_dir = identities_dir / "twitter"
            self.cookie_path = str(twitter_dir / "default" / "cookies.json")
            if twitter_dir.exists():
                for d in sorted(twitter_dir.iterdir()):
                    cp = d / "cookies.json"
                    if d.is_dir() and not d.name.startswith("_") and cp.exists():
                        self.cookie_path = str(cp)
                        break
            self.seed_accounts = []
            self.seed_company_accounts = []
            self.request_delay = 8.0
            self.min_engagement = {"likes": 1000, "retweets": 200}
            self.lookback_hours = 24

    class _RedditConfig:
        def __init__(self):
            self.credentials_path = ""
            self.user_agent = "gtm-cli/0.1"
            self.target_subreddits = ["SaaS", "startups", "programming"]
            self.session_dir = str(identities_dir / "reddit")
            self.post_stagger_seconds = 15
            self.post_stagger_hours = 0      # Legacy field (promoter reads this)
            self.max_subreddits_per_idea = 3

    class _HNConfig:
        def __init__(self):
            self.session_dir = str(identities_dir / "hn")

    class _ModelsConfig:
        def __init__(self):
            self.scout = "claude-sonnet-4-20250514"
            self.novelty = "claude-sonnet-4-20250514"
            self.builder = "claude-sonnet-4-20250514"
            self.tester = "claude-sonnet-4-20250514"
            self.promoter = "claude-sonnet-4-20250514"
            self.hn_promoter = "claude-sonnet-4-20250514"
            self.twitter_promoter = "claude-sonnet-4-20250514"
            self.engagement_loop = "claude-sonnet-4-20250514"

    class _GitHubConfig:
        def __init__(self):
            import os
            self.owner = os.environ.get("GITHUB_OWNER", "")
            self.token = os.environ.get("GITHUB_TOKEN", "")

    class _Config:
        def __init__(self):
            self.twitter = _TwitterConfig()
            self.reddit = _RedditConfig()
            self.hn = _HNConfig()
            self.github = _GitHubConfig()
            self.models = _ModelsConfig()

    return _Config()


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
