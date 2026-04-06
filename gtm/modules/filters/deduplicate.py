"""filter/deduplicate — Remove items already posted or seen."""

from __future__ import annotations
from typing import Any
from pathlib import Path
from gtm.modules.base import Module, ModuleResult, ModuleContext
from gtm.modules.registry import register


class DeduplicateFilterModule(Module):
    name = "filter/deduplicate"
    category = "filter"
    description = "Remove items already posted (checks output repo)"
    param_schema = {
        "field": {"type": "str", "default": "id"},
        "check_output": {"type": "bool", "default": True},
    }

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        if not input_data or not input_data.data:
            return ModuleResult(success=True, data=[])

        field = params.get("field", "id")
        seen_ids = set()

        # Load already-posted IDs from output repo
        if params.get("check_output", True):
            seen_ids = self._load_posted_ids(field)

        filtered = []
        for item in input_data.data:
            item_id = str(item.get(field, ""))
            if item_id and item_id not in seen_ids:
                seen_ids.add(item_id)
                filtered.append(item)

        return ModuleResult(success=True, data=filtered,
            metadata={"input_count": len(input_data.data), "output_count": len(filtered), "duplicates_removed": len(input_data.data) - len(filtered)})

    def _load_posted_ids(self, field: str) -> set[str]:
        """Load IDs of already-posted content from output repo.
        
        Uses the specified field to match against posted metadata.
        Falls back to post_id if the field isn't found.
        """
        import yaml
        from gtm.config import GrowthConfig
        output_dir = Path(GrowthConfig.load().output_dir).expanduser()
        posted_dir = output_dir / "posted"
        ids = set()
        if posted_dir.exists():
            for f in posted_dir.glob("*.md"):
                try:
                    text = f.read_text(errors="replace")
                except (OSError, IOError):
                    continue
                if text.startswith("---"):
                    parts = text.split("---", 2)
                    if len(parts) >= 3:
                        try:
                            meta = yaml.safe_load(parts[1])
                            # Try the requested field first, fall back to post_id
                            val = meta.get(field) or meta.get("post_id")
                            if val:
                                ids.add(str(val))
                        except Exception:
                            pass
        return ids


register(DeduplicateFilterModule())
