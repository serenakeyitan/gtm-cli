"""agent/scout — LLM-powered Twitter scout (scan accounts, synthesize ideas).

Wraps the legacy scout agent as a composable module.
Input: None (source module) or search params
Output: list of trending topic dicts with engagement data
"""

from __future__ import annotations

import logging
from typing import Any

from gtm.modules.base import Module, ModuleResult, ModuleContext
from gtm.modules.registry import register

log = logging.getLogger(__name__)


class ScoutAgentModule(Module):
    name = "agent/scout"
    category = "agent"
    description = "LLM-powered Twitter scout — scan AI accounts, find viral topics, synthesize ideas"
    platform = "twitter"
    requires_auth = True
    param_schema = {
        "min_likes": {"type": "int", "default": 1000},
        "min_retweets": {"type": "int", "default": 200},
        "lookback_hours": {"type": "int", "default": 24},
        "num_ideas": {"type": "int", "default": 10},
    }

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        if context.dry_run:
            return ModuleResult(success=True, data=[{"dry_run": True, "agent": "scout"}],
                                metadata={"note": "Scout agent would scan 87 Twitter accounts (~15-30 min)"})

        try:
            from gtm.agents.scout import run_twitter_scout
            from gtm.engine.state import RunState
            from gtm.engine.runner import _build_agent_config
            from gtm.config import IDENTITIES_DIR

            config = _build_agent_config(IDENTITIES_DIR)
            # Use strategy-selected identity if available
            if context.identity_dir:
                config.twitter.cookie_path = str(context.identity_dir / "cookies.json")
            config.twitter.min_engagement = {
                "likes": params.get("min_likes", 1000),
                "retweets": params.get("min_retweets", 200),
            }
            config.twitter.lookback_hours = params.get("lookback_hours", 24)

            state = RunState.create("gtm-cli-scout")
            ideas = await run_twitter_scout(state, config)

            return ModuleResult(success=True, data=ideas if isinstance(ideas, list) else [ideas],
                                metadata={"ideas_found": len(ideas) if isinstance(ideas, list) else 1})
        except ImportError:
            return ModuleResult(success=False, errors=["claude-code-sdk not installed. Run: pip install gtm-cli[agents]"])
        except Exception as e:
            return ModuleResult(success=False, errors=[str(e)])


register(ScoutAgentModule())
