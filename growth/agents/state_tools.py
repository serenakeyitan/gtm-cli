"""State tools — read/write phase output for agents."""

from __future__ import annotations

import json
import logging
from typing import Any

from claude_code_sdk import tool

log = logging.getLogger(__name__)

_phase_outputs: dict[str, Any] = {}


@tool("write_phase_output", "Write output for a pipeline phase", {"phase": str, "data": str})
async def write_phase_output(args):
    phase = args.get("phase", "unknown")
    data = args.get("data", {})
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            pass
    _phase_outputs[phase] = data
    log.info("Phase output written: %s", phase)
    return {"content": [{"type": "text", "text": f"Phase '{phase}' output saved."}]}


@tool("read_run_state", "Read current run state and phase outputs", {})
async def read_run_state(args):
    return {"content": [{"type": "text", "text": json.dumps(_phase_outputs, indent=2)}]}


def bind_state(state: Any) -> None:
    """Bind a RunState object (compatibility stub)."""
    pass


def get_phase_output(phase: str) -> Any:
    return _phase_outputs.get(phase)


def reset():
    global _phase_outputs
    _phase_outputs = {}
