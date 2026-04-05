"""agent/test — LLM-powered test runner.

Input: list of build result dicts (from builder)
Output: list of test result dicts (pass/fail per build)
"""

from __future__ import annotations

import logging
from typing import Any

from growth.modules.base import Module, ModuleResult, ModuleContext
from growth.modules.registry import register

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
            from growth.agents.tester import run_tester
            from growth.engine.state import RunState

            state = RunState.create("growth-cli-test")
            results = await run_tester(state, input_data.data)
            tested = results if isinstance(results, list) else [results]

            return ModuleResult(success=True, data=tested,
                                metadata={"builds": len(input_data.data), "tested": len(tested)})
        except ImportError:
            return ModuleResult(success=False, errors=["claude-code-sdk not installed"])
        except Exception as e:
            return ModuleResult(success=False, errors=[str(e)])


register(TestAgentModule())
