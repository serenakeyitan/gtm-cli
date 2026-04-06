"""control/delay — Fixed wait between modules."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from gtm.modules.base import Module, ModuleResult, ModuleContext
from gtm.modules.registry import register

log = logging.getLogger(__name__)


class DelayModule(Module):
    name = "control/delay"
    category = "control"
    description = "Wait a fixed duration (seconds) — human-like pacing"
    param_schema = {"seconds": {"type": "int", "required": True}}

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        seconds = params.get("seconds", 0)
        if context.dry_run:
            log.info("control/delay: would wait %ds (dry-run)", seconds)
            return input_data or ModuleResult(success=True)

        log.info("control/delay: waiting %ds", seconds)
        await asyncio.sleep(seconds)
        return input_data or ModuleResult(success=True)


register(DelayModule())
