"""control/jitter — Random wait within a range (human-like timing)."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

from growth.modules.base import Module, ModuleResult, ModuleContext
from growth.modules.registry import register

log = logging.getLogger(__name__)


class JitterModule(Module):
    name = "control/jitter"
    category = "control"
    description = "Wait a random duration within a range (human-like pacing)"
    param_schema = {
        "min_seconds": {"type": "int", "required": True},
        "max_seconds": {"type": "int", "required": True},
    }

    async def run(self, input_data, params: dict[str, Any], context: ModuleContext) -> ModuleResult:
        min_s = params.get("min_seconds", 1)
        max_s = params.get("max_seconds", 10)
        wait = random.uniform(min_s, max_s)

        if context.dry_run:
            log.info("control/jitter: would wait %.1fs (range %d-%ds, dry-run)", wait, min_s, max_s)
            return input_data or ModuleResult(success=True)

        log.info("control/jitter: waiting %.1fs (range %d-%ds)", wait, min_s, max_s)
        await asyncio.sleep(wait)
        return input_data or ModuleResult(success=True)


register(JitterModule())
