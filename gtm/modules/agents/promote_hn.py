"""agent/promote_hn — LLM-powered Hacker News curator and submitter.

Input: list of trending content dicts (from scout)
Output: list of HN submission results

Finds original source URLs, deduplicates, crafts clean titles per HN guidelines.
"""

from __future__ import annotations

import logging
from typing import Any

from gtm.modules.base import Module, ModuleResult, ModuleContext
from gtm.modules.registry import register

log = logging.getLogger(__name__)


class PromoteHNAgentModule(Module):
    name = "agent/promote_hn"
    category = "agent"
    description = "LLM-powered HN promoter — curate content, find sources, submit to HN"
    platform = "hn"
    requires_auth = True
    param_schema = {}

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        if not input_data or not input_data.data:
            return ModuleResult(success=True, data=[])

        if context.dry_run:
            return ModuleResult(success=True, data=input_data.data,
                                metadata={"note": "Would curate and submit top items to HN"})

        try:
            from gtm.agents.hn_promoter import run_hn_promoter
            from gtm.engine.state import RunState
            from gtm.engine.runner import _build_agent_config
            from gtm.config import IDENTITIES_DIR

            config = _build_agent_config(IDENTITIES_DIR)
            # Use strategy-selected identity if available
            if context.identity_dir:
                config.hn.session_dir = str(context.identity_dir / "session")
            state = RunState.create("gtm-cli-hn-promote")
            result = await run_hn_promoter(state, {"ideas": input_data.data, "config": config})

            # Legacy agent returns a dict with "submissions" key or a list
            if isinstance(result, dict):
                submissions = result.get("submissions", result.get("posts", [result]))
            elif isinstance(result, list):
                submissions = result
            else:
                submissions = [result]

            return ModuleResult(success=True, data=submissions,
                                metadata={"items": len(input_data.data), "submitted": len(submissions)})
        except ImportError:
            return ModuleResult(success=False, errors=["claude-agent-sdk not installed"])
        except Exception as e:
            return ModuleResult(success=False, errors=[str(e)])


register(PromoteHNAgentModule())
