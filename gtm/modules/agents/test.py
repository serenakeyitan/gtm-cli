"""agent/test — LLM-powered test runner.

Input: list of build result dicts (from builder)
Output: list of test result dicts (pass/fail per build)
"""

from __future__ import annotations

import logging
from typing import Any

from gtm.modules.base import Module, ModuleResult, ModuleContext
from gtm.modules.registry import register

log = logging.getLogger(__name__)


class TestAgentModule(Module):
    name = "agent/test"
    category = "agent"
    description = "LLM-powered test runner — run and verify tests on built repos"
    requires_auth = False
    param_schema = {}

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        if not input_data or not input_data.data:
            return ModuleResult(success=True, data=[])

        if context.dry_run:
            return ModuleResult(success=True, data=input_data.data,
                                metadata={"note": "Would run tests on each built repo"})

        try:
            from gtm.agents.tester import run_tester
            from gtm.engine.state import RunState
            from gtm.engine.runner import _build_agent_config
            from gtm.config import IDENTITIES_DIR

            config = _build_agent_config(IDENTITIES_DIR)
            state = RunState.create("gtm-cli-test")
            tested = []
            for i, build in enumerate(input_data.data):
                # Legacy agent expects {"build": dict, "idea": dict, "config": config}
                # Ensure idea has an 'id' field for traceability
                idea = dict(build)
                if "id" not in idea:
                    idea["id"] = idea.get("idea_id", idea.get("repo_name", f"item_{i}"))
                result = await run_tester(state, {"build": build, "idea": idea, "config": config})
                if isinstance(result, dict):
                    tested.append(result)

            return ModuleResult(success=True, data=tested,
                                metadata={"builds": len(input_data.data), "tested": len(tested)})
        except ImportError:
            return ModuleResult(success=False, errors=["claude-agent-sdk not installed"])
        except Exception as e:
            return ModuleResult(success=False, errors=[str(e)])


register(TestAgentModule())
