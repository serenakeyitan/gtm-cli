"""DAG-based strategy runner — parallel execution of composable modules.

Parses a module DAG from strategy YAML, resolves execution order via
topological sort, and runs independent branches in parallel.

Strategy YAML format (v0.2):
  modules:
    scout:
      use: twitter/search
      params: { query: "AI agents" }
    filter:
      use: filter/engagement
      input: scout                  # dependency
      params: { min_likes: 1000 }
    post_reddit:
      use: reddit/submit
      input: filter                 # depends on filter
    post_hn:
      use: hn/submit_link
      input: filter                 # also depends on filter
    # post_reddit and post_hn run in PARALLEL (same input, no mutual dependency)
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from growth.modules.base import Module, ModuleContext, ModuleResult
from growth.modules import registry
from growth.identity.manager import IdentityManager
from growth.safety.rate_limiter import get_rate_limiter

log = logging.getLogger(__name__)


async def run_dag_strategy(
    strategy: dict[str, Any],
    user_params: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute a module-based strategy as a DAG.

    Args:
        strategy: Parsed strategy dict (from YAML) with 'modules' key.
        user_params: User-provided parameter overrides.
        dry_run: If True, modules run in dry_run mode.

    Returns:
        Run state dict with per-module results.
    """
    user_params = user_params or {}
    modules_def = strategy.get("modules", {})
    identities_def = strategy.get("identities", {})
    param_defs = strategy.get("params", {})
    mgr = IdentityManager()

    # Resolve params
    resolved_params = _resolve_params(param_defs, user_params)

    # Build the DAG — validate references
    dag = _build_dag(modules_def)
    _validate_dag_refs(modules_def, dag)

    # Topological sort
    execution_order = _topological_sort(dag)

    state = {
        "strategy": strategy.get("name", "unnamed"),
        "started_at": datetime.now().isoformat(),
        "status": "running",
        "params": resolved_params,
        "modules": {},
        "errors": [],
    }

    log.info("DAG strategy: %s (%d modules, order: %s)",
             strategy.get("name", "?"), len(modules_def), " → ".join(execution_order))

    # Execute in topological order, parallelizing where possible
    results: dict[str, ModuleResult] = {}

    for batch in _parallel_batches(execution_order, dag):
        # Separate skipped vs runnable modules — track names for correct zip
        runnable_names = []
        tasks = []
        for module_name in batch:
            # Skip if any upstream dependency failed
            deps = dag.get(module_name, [])
            failed_deps = [d for d in deps if d in results and not results[d].success]
            if failed_deps:
                log.warning("Module [%s]: skipping — upstream %s failed", module_name, failed_deps)
                state["modules"][module_name] = {"status": "skipped", "reason": f"upstream failed: {failed_deps}"}
                results[module_name] = ModuleResult(success=False, errors=[f"upstream {failed_deps} failed"])
                continue

            mod_def = modules_def[module_name]
            runnable_names.append(module_name)
            tasks.append(_run_module(
                module_name, mod_def, results, resolved_params,
                identities_def, mgr, dry_run, state,
            ))

        # Run batch in parallel
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Zip with runnable_names (not batch) to avoid misalignment
        for module_name, result in zip(runnable_names, batch_results):
            if isinstance(result, Exception):
                log.error("Module [%s] failed: %s", module_name, result)
                state["modules"][module_name] = {"status": "failed", "error": str(result)}
                state["errors"].append(f"{module_name}: {result}")
                results[module_name] = ModuleResult(success=False, errors=[str(result)])
            elif not result.success:
                state["errors"].append(f"{module_name}: {'; '.join(result.errors)}")
                results[module_name] = result
            else:
                results[module_name] = result

    # Finalize
    state["status"] = "completed_with_errors" if state["errors"] else "completed"
    state["completed_at"] = datetime.now().isoformat()

    # Log the run
    from growth.output.logger import log_run
    log_run(strategy.get("name", "unnamed"), state)

    return state


async def _run_module(
    name: str,
    mod_def: dict[str, Any],
    results: dict[str, ModuleResult],
    resolved_params: dict[str, Any],
    identities_def: dict[str, Any],
    mgr: IdentityManager,
    dry_run: bool,
    state: dict[str, Any],
) -> ModuleResult:
    """Run a single module with resolved inputs and context."""
    use = mod_def.get("use", "")
    params = dict(mod_def.get("params", {}))
    input_ref = mod_def.get("input")
    identity_ref = mod_def.get("as", "")

    # Resolve module
    try:
        module = registry.get(use)
    except KeyError as e:
        state["modules"][name] = {"status": "failed", "error": str(e)}
        return ModuleResult(success=False, errors=[str(e)])

    # Resolve input data from upstream module(s)
    input_data = None
    if input_ref:
        if isinstance(input_ref, list):
            # Multiple inputs — merge results
            merged = ModuleResult(success=True)
            for ref in input_ref:
                if ref in results:
                    merged = merged.pipe(results[ref])
            input_data = merged
        elif input_ref in results:
            input_data = results[input_ref]

    # Resolve params — substitute {{ param_name }} references
    for key, val in params.items():
        if isinstance(val, str) and "{{" in val:
            resolved = False
            for param_name, param_val in resolved_params.items():
                placeholder = f"{{{{ {param_name} }}}}"
                if val.strip() == placeholder:
                    # Exact match — preserve the original type (int, float, etc.)
                    params[key] = param_val
                    resolved = True
                    break  # Don't let further iterations overwrite with string
            if not resolved:
                # Partial substitution (multiple placeholders in one string)
                for param_name, param_val in resolved_params.items():
                    placeholder = f"{{{{ {param_name} }}}}"
                    val = val.replace(placeholder, str(param_val))
                params[key] = val

    # Resolve identity
    context = ModuleContext(dry_run=dry_run)
    if identity_ref:
        ref = identity_ref.lstrip("$")
        identity_spec = identities_def.get(ref, {})
        platform = identity_spec.get("platform", module.platform)
        try:
            identity = mgr.get_for_platform(platform)
            context.identity_dir = identity.identity_dir
            context.identity_name = identity.name
        except ValueError as e:
            if identity_spec.get("optional"):
                log.info("Module [%s]: optional identity not available, skipping", name)
                state["modules"][name] = {"status": "skipped", "reason": str(e)}
                return ModuleResult(success=True, data=[], metadata={"skipped": True})
            state["modules"][name] = {"status": "failed", "error": str(e)}
            return ModuleResult(success=False, errors=[str(e)])
    elif module.requires_auth and module.platform:
        try:
            identity = mgr.get_for_platform(module.platform)
            context.identity_dir = identity.identity_dir
            context.identity_name = identity.name
        except ValueError as e:
            if not dry_run:
                state["modules"][name] = {"status": "failed", "error": f"Auth required: {e}"}
                return ModuleResult(success=False, errors=[f"Auth required: {e}"])
            # In dry-run, proceed without auth — module handles it internally
            log.debug("Module [%s]: auth not available (dry-run, continuing)", name)

    # Execute
    log.debug("Module [%s] params keys: %s", name, list(params.keys()))  # Don't log values (may contain secrets)
    log.info("Module [%s] (%s): running%s", name, use, " (dry-run)" if dry_run else "")
    result = await module.run(input_data, params, context)

    # Record state
    status = "success" if result.success else "failed"
    state["modules"][name] = {
        "status": status,
        "use": use,
        "count": result.count,
        "metadata": result.metadata,
        "errors": result.errors,
    }

    log.info("Module [%s]: %s (%d items)", name, status, result.count)
    return result


def _resolve_params(param_defs: dict, user_params: dict) -> dict[str, Any]:
    """Merge strategy param defaults with user overrides."""
    resolved = {}
    for name, defn in param_defs.items():
        if name in user_params:
            resolved[name] = user_params[name]
        elif isinstance(defn, dict) and "default" in defn:
            resolved[name] = defn["default"]
        elif isinstance(defn, dict) and defn.get("required"):
            raise ValueError(f"Missing required param: {name}")
    return resolved


def _build_dag(modules_def: dict) -> dict[str, list[str]]:
    """Build adjacency list: module → list of dependencies."""
    dag: dict[str, list[str]] = {}
    for name, defn in modules_def.items():
        input_ref = defn.get("input")
        if input_ref is None:
            dag[name] = []
        elif isinstance(input_ref, list):
            dag[name] = [r for r in input_ref if r in modules_def]
        elif input_ref in modules_def:
            dag[name] = [input_ref]
        else:
            dag[name] = []
    return dag


def _topological_sort(dag: dict[str, list[str]]) -> list[str]:
    """Kahn's algorithm for topological sort."""
    in_degree: dict[str, int] = defaultdict(int)
    for node in dag:
        in_degree.setdefault(node, 0)
        for dep in dag[node]:
            in_degree[node] += 1

    # Reverse: build adjacency for "what depends on me"
    dependents: dict[str, list[str]] = defaultdict(list)
    for node, deps in dag.items():
        for dep in deps:
            dependents[dep].append(node)

    queue = [n for n in dag if in_degree[n] == 0]
    order = []

    while queue:
        queue.sort()  # deterministic order
        node = queue.pop(0)
        order.append(node)
        for dep in dependents[node]:
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)

    if len(order) != len(dag):
        missing = set(dag.keys()) - set(order)
        raise ValueError(f"Cycle detected in module DAG: {missing}")

    return order


def _validate_dag_refs(modules_def: dict, dag: dict) -> None:
    """Validate that all input references point to existing modules."""
    for name, defn in modules_def.items():
        input_ref = defn.get("input")
        if input_ref is None:
            continue
        refs = input_ref if isinstance(input_ref, list) else [input_ref]
        for ref in refs:
            if ref not in modules_def:
                raise ValueError(
                    f"Module '{name}' references unknown input '{ref}'. "
                    f"Available: {list(modules_def.keys())}"
                )


def _parallel_batches(order: list[str], dag: dict[str, list[str]]) -> list[list[str]]:
    """Group topologically sorted modules into parallel batches.

    Modules in the same batch have all their dependencies satisfied
    by previous batches, so they can run concurrently.
    """
    completed: set[str] = set()
    batches: list[list[str]] = []
    remaining = list(order)

    while remaining:
        batch = []
        for node in remaining:
            deps = dag.get(node, [])
            if all(d in completed for d in deps):
                batch.append(node)

        if not batch:
            raise ValueError(f"Cannot resolve batch — stuck on: {remaining}")

        batches.append(batch)
        completed.update(batch)
        remaining = [n for n in remaining if n not in completed]

    return batches
