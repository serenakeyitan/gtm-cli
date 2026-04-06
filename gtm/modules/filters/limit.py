"""filter/limit — Take top N items, optionally sorted by a field."""

from __future__ import annotations
from typing import Any
from gtm.modules.base import Module, ModuleResult, ModuleContext
from gtm.modules.registry import register


class LimitFilterModule(Module):
    name = "filter/limit"
    category = "filter"
    description = "Take top N items, optionally sorted by engagement"
    param_schema = {
        "count": {"type": "int", "required": True},
        "sort_by": {"type": "str", "default": ""},
        "descending": {"type": "bool", "default": True},
    }

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        if not input_data or not input_data.data:
            return ModuleResult(success=True, data=[])

        data = list(input_data.data)
        sort_by = params.get("sort_by", "")

        if sort_by:
            data.sort(key=lambda x: x.get(sort_by, 0), reverse=params.get("descending", True))

        count = params.get("count", len(data))
        return ModuleResult(success=True, data=data[:count],
            metadata={"input_count": len(input_data.data), "output_count": min(count, len(data))})


register(LimitFilterModule())
