"""Agent modules — LLM-powered composable modules.

These wrap the Claude SDK agents as standard Module interface,
so they compose with tool modules, filters, and transforms.

Requires: pip install growth-cli[agents]
"""

import logging as _log

# Import each agent module independently so one broken import doesn't disable all
for _mod in [
    "growth.modules.agents.scout",
    "growth.modules.agents.novelty_check",
    "growth.modules.agents.build",
    "growth.modules.agents.test",
    "growth.modules.agents.promote_reddit",
    "growth.modules.agents.promote_hn",
]:
    try:
        __import__(_mod)
    except ImportError as e:
        _log.getLogger(__name__).debug("Agent module %s unavailable: %s", _mod, e)
