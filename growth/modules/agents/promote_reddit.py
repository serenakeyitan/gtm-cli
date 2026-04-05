"""agent/promote_reddit — LLM-powered Reddit promoter.

Input: list of build/idea dicts
Output: list of Reddit post results (URLs, scores)

Uses the battle-tested style guide for organic, anti-self-promotion writing.
"""

from __future__ import annotations

import logging
from typing import Any

from growth.modules.base import Module, ModuleResult, ModuleContext
from growth.modules.registry import register

log = logging.getLogger(__name__)


class PromoteRedditAgentModule(Module):
    name = "agent/promote_reddit"
    category = "agent"
    description = "LLM-powered Reddit promoter — organic posts with anti-self-promotion style"
    platform = "reddit"
    requires_auth = True
    param_schema = {
        "subreddits": {"type": "str", "default": "SaaS,startups,programming"},
    }

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        if not input_data or not input_data.data:
            return ModuleResult(success=True, data=[])

        if context.dry_run:
            return ModuleResult(success=True, data=input_data.data,
                                metadata={"note": f"Would post to subreddits: {params.get('subreddits')}"})

        try:
            from growth.agents.promoter import run_promoter
            from growth.engine.state import RunState
            from growth.engine.runner import _build_agent_config
            from growth.config import IDENTITIES_DIR

            config = _build_agent_config(IDENTITIES_DIR)
            # Use strategy-selected identity if available
            if context.identity_dir:
                config.reddit.session_dir = str(context.identity_dir / "session")
            subs = params.get("subreddits", "SaaS,startups,programming")
            config.reddit.target_subreddits = [s.strip() for s in subs.split(",")]

            state = RunState.create("growth-cli-promote")
            posts = []
            for item in input_data.data:
                result = await run_promoter(state, {"idea": item, "build": item, "config": config})
                if isinstance(result, list):
                    posts.extend(result)
                else:
                    posts.append(result)

            return ModuleResult(success=True, data=posts,
                                metadata={"items": len(input_data.data), "posts": len(posts)})
        except ImportError:
            return ModuleResult(success=False, errors=["claude-code-sdk not installed"])
        except Exception as e:
            return ModuleResult(success=False, errors=[str(e)])


register(PromoteRedditAgentModule())
