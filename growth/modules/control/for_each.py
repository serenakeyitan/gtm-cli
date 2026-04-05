"""control/for_each — Run a module for each item in the input list."""

from __future__ import annotations

import logging
from typing import Any

from growth.modules.base import Module, ModuleResult, ModuleContext
from growth.modules import registry as mod_registry
from growth.modules.registry import register

log = logging.getLogger(__name__)


class ForEachModule(Module):
    name = "control/for_each"
    category = "control"
    description = "Run a module once per item in the input list"
    param_schema = {
        "use": {"type": "str", "required": True},
        "item_params": {"type": "dict", "default": {}},
    }

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        if not input_data or not input_data.data:
            return ModuleResult(success=True, data=[])

        module_name = params.get("use", "")
        item_params = params.get("item_params", {})

        try:
            module = mod_registry.get(module_name)
        except KeyError as e:
            return ModuleResult(success=False, errors=[str(e)])

        all_results = []
        errors = []

        for i, item in enumerate(input_data.data):
            # Build per-item params — merge item_params with item fields
            merged_params = dict(item_params)
            for key, val in merged_params.items():
                if isinstance(val, str) and val.startswith("item."):
                    field = val[5:]  # strip "item."
                    merged_params[key] = item.get(field, val)

            single_input = ModuleResult(success=True, data=[item])
            try:
                result = await module.run(single_input, merged_params, context)
                all_results.extend(result.data)
                if result.errors:
                    errors.extend(result.errors)
            except Exception as e:
                log.warning("for_each item %d failed: %s", i, e)
                errors.append(f"Item {i}: {e}")

        return ModuleResult(
            success=len(errors) == 0,
            data=all_results,
            errors=errors,
            metadata={"items_processed": len(input_data.data), "results": len(all_results)},
        )


register(ForEachModule())
