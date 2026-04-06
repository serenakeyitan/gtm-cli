"""agent/novelty_check — LLM-powered GitHub novelty filter.

Input: list of idea dicts (from scout)
Output: filtered list — only ideas that don't already exist on GitHub
"""

from __future__ import annotations

import logging
from typing import Any

from gtm.modules.base import Module, ModuleResult, ModuleContext
from gtm.modules.registry import register

log = logging.getLogger(__name__)


class NoveltyCheckAgentModule(Module):
    name = "agent/novelty_check"
    category = "agent"
    description = "LLM-powered novelty filter — check GitHub for existing implementations"
    requires_auth = False
    param_schema = {}

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        if not input_data or not input_data.data:
            return ModuleResult(success=True, data=[])

        if context.dry_run:
            return ModuleResult(success=True, data=input_data.data,
                                metadata={"note": "Would check GitHub for existing projects"})

        try:
            from gtm.agents.novelty_checker import run_novelty_checker
            from gtm.engine.state import RunState
            from gtm.engine.runner import _build_agent_config
            from gtm.config import IDENTITIES_DIR

            config = _build_agent_config(IDENTITIES_DIR)
            state = RunState.create("gtm-cli-novelty")
            # Legacy agent expects {"ideas": [...], "config": config}
            result = await run_novelty_checker(state, {"ideas": input_data.data, "config": config})
            novel = result if isinstance(result, list) else [result]

            return ModuleResult(success=True, data=novel,
                                metadata={"input": len(input_data.data), "novel": len(novel)})
        except ImportError:
            return ModuleResult(success=False, errors=["claude-code-sdk not installed"])
        except Exception as e:
            return ModuleResult(success=False, errors=[str(e)])


register(NoveltyCheckAgentModule())
