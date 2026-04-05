"""agent/build — LLM-powered GitHub repo builder.

Input: list of idea dicts (from novelty check)
Output: list of build result dicts (repo URL, success/fail)
"""

from __future__ import annotations

import logging
from typing import Any

from growth.modules.base import Module, ModuleResult, ModuleContext
from growth.modules.registry import register

log = logging.getLogger(__name__)


class BuildAgentModule(Module):
    name = "agent/build"
    category = "agent"
    description = "LLM-powered repo builder — create GitHub repos from ideas"
    requires_auth = False  # Uses GITHUB_TOKEN env var
    param_schema = {}

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        if not input_data or not input_data.data:
            return ModuleResult(success=True, data=[])

        if context.dry_run:
            return ModuleResult(success=True, data=input_data.data,
                                metadata={"note": "Would build GitHub repos for each idea"})

        try:
            from growth.agents.builder import run_builder
            from growth.engine.state import RunState
            from growth.engine.runner import _build_agent_config
            from growth.config import IDENTITIES_DIR

            config = _build_agent_config(IDENTITIES_DIR)
            state = RunState.create("growth-cli-build")
            builds = []
            for idea in input_data.data:
                # Legacy agent expects {"idea": dict, "config": config}
                result = await run_builder(state, {"idea": idea, "config": config})
                if isinstance(result, dict):
                    builds.append(result)

            return ModuleResult(success=True, data=builds,
                                metadata={"ideas": len(input_data.data), "builds": len(builds)})
        except ImportError:
            return ModuleResult(success=False, errors=["claude-code-sdk not installed"])
        except Exception as e:
            return ModuleResult(success=False, errors=[str(e)])


register(BuildAgentModule())
