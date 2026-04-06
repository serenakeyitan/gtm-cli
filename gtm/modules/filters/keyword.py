"""filter/keyword — Keep or exclude items matching keywords."""

from __future__ import annotations
from typing import Any
from gtm.modules.base import Module, ModuleResult, ModuleContext
from gtm.modules.registry import register


class KeywordFilterModule(Module):
    name = "filter/keyword"
    category = "filter"
    description = "Keep or exclude items matching keywords"
    param_schema = {
        "include": {"type": "list[str]", "default": []},
        "exclude": {"type": "list[str]", "default": []},
        "fields": {"type": "list[str]", "default": ["text", "title", "selftext"]},
    }

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        if not input_data or not input_data.data:
            return ModuleResult(success=True, data=[])

        include = [k.lower() for k in params.get("include", [])]
        exclude = [k.lower() for k in params.get("exclude", [])]
        fields = params.get("fields", ["text", "title", "selftext"])

        filtered = []
        for item in input_data.data:
            text = " ".join(str(item.get(f, "")) for f in fields).lower()

            if exclude and any(k in text for k in exclude):
                continue
            if include and not any(k in text for k in include):
                continue

            filtered.append(item)

        return ModuleResult(success=True, data=filtered,
            metadata={"input_count": len(input_data.data), "output_count": len(filtered)})


register(KeywordFilterModule())
