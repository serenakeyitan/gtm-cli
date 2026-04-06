"""Agent modules — LLM-powered composable modules.

These wrap the Claude SDK agents as standard Module interface,
so they compose with tool modules, filters, and transforms.

Requires: pip install gtm-cli[agents]
"""

import logging as _log

# Import each agent module independently so one broken import doesn't disable all
for _mod in [
    "gtm.modules.agents.scout",
    "gtm.modules.agents.novelty_check",
    "gtm.modules.agents.build",
    "gtm.modules.agents.test",
    "gtm.modules.agents.promote_reddit",
    "gtm.modules.agents.promote_hn",
    "gtm.modules.agents.synthesize",
]:
    try:
        __import__(_mod)
    except ImportError as e:
        _log.getLogger(__name__).debug("Agent module %s unavailable: %s", _mod, e)
