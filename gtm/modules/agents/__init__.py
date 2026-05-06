"""Agent modules — LLM-powered composable modules.

The 6 prompt-wrapping modules (scout, novelty_check, build, test,
promote_reddit, promote_hn) were deleted in Phase 5 — their behavior
moved into skills/ which the agent reads directly via MCP. See
docs/PLAN-claude-code-shape.md.

What remains:
  - synthesize: real LLM ranker with deterministic fallback (kept)
  - strategy_module: registers strategy YAMLs as `strategy/*` modules
    so they're callable via run_strategy

Requires: pip install gtm-cli[agents]
"""

import logging as _log

for _mod in [
    "gtm.modules.agents.synthesize",
]:
    try:
        __import__(_mod)
    except ImportError as e:
        _log.getLogger(__name__).debug("Agent module %s unavailable: %s", _mod, e)
