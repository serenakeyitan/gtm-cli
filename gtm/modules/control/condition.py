"""control/condition — If/then/else based on data."""

from __future__ import annotations

import logging
from typing import Any

from gtm.modules.base import Module, ModuleResult, ModuleContext
from gtm.modules.registry import register

log = logging.getLogger(__name__)


class ConditionModule(Module):
    name = "control/condition"
    category = "control"
    description = "Filter items based on a condition (field comparison)"
    param_schema = {
        "field": {"type": "str", "required": True},
        "operator": {"type": "str", "required": True, "enum": ["gt", "lt", "gte", "lte", "eq", "ne", "contains", "not_contains"]},
        "value": {"type": "any", "required": True},
    }

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        if not input_data or not input_data.data:
            return ModuleResult(success=True, data=[])

        field = params["field"]
        op = params["operator"]
        value = params["value"]

        passed = []
        for item in input_data.data:
            item_val = item.get(field)
            if item_val is None:
                continue

            if self._evaluate(item_val, op, value):
                passed.append(item)

        return ModuleResult(
            success=True,
            data=passed,
            metadata={"input_count": len(input_data.data), "passed": len(passed), "condition": f"{field} {op} {value}"},
        )

    def _evaluate(self, item_val: Any, op: str, value: Any) -> bool:
        try:
            if op == "gt":
                return float(item_val) > float(value)
            elif op == "lt":
                return float(item_val) < float(value)
            elif op == "gte":
                return float(item_val) >= float(value)
            elif op == "lte":
                return float(item_val) <= float(value)
            elif op == "eq":
                return str(item_val) == str(value)
            elif op == "ne":
                return str(item_val) != str(value)
            elif op == "contains":
                return str(value).lower() in str(item_val).lower()
            elif op == "not_contains":
                return str(value).lower() not in str(item_val).lower()
        except (ValueError, TypeError):
            return False
        return False


register(ConditionModule())
