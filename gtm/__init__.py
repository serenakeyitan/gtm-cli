"""gtm-cli — Terminal-native marketing automation."""

__version__ = "0.1.0"

# Public SDK surface — see gtm/sdk.py for design intent.
# Importing here makes `import gtm; gtm.run_module(...)` work.
from gtm.sdk import (  # noqa: E402, F401
    ModuleContext,
    ModuleResult,
    get_module,
    list_modules,
    run_module,
    run_module_sync,
    run_strategy,
    run_strategy_sync,
)
