"""State tools — read/write phase output for agents.

Stub that provides the same interface as the original pipeline's state_tools.
"""

from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger(__name__)

# In-memory phase outputs (shared across agents in a single run)
_phase_outputs: dict[str, Any] = {}


async def write_phase_output(args: dict[str, Any]) -> dict[str, Any]:
    """Write output for a pipeline phase."""
    phase = args.get("phase", "unknown")
    data = args.get("data", {})
    _phase_outputs[phase] = data
    log.info("Phase output written: %s (%d items)", phase, len(data) if isinstance(data, list) else 1)
    return {"content": [{"type": "text", "text": f"Phase '{phase}' output saved."}]}


async def read_run_state(args: dict[str, Any]) -> dict[str, Any]:
    """Read current run state."""
    return {"content": [{"type": "text", "text": json.dumps(_phase_outputs, indent=2)}]}


def bind_state(state: Any) -> None:
    """Bind a RunState object (compatibility stub)."""
    pass


def get_phase_output(phase: str) -> Any:
    """Get output from a specific phase."""
    return _phase_outputs.get(phase)


def reset():
    """Reset all phase outputs."""
    global _phase_outputs
    _phase_outputs = {}
