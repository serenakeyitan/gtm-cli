"""Agent modules — LLM-powered composable modules.

These wrap the Claude SDK agents as standard Module interface,
so they compose with tool modules, filters, and transforms.

Requires: pip install growth-cli[agents]
"""

try:
    from growth.modules.agents.scout import *  # noqa
    from growth.modules.agents.novelty_check import *  # noqa
    from growth.modules.agents.build import *  # noqa
    from growth.modules.agents.test import *  # noqa
    from growth.modules.agents.promote_reddit import *  # noqa
    from growth.modules.agents.promote_hn import *  # noqa
except ImportError:
    pass  # claude-code-sdk not installed
