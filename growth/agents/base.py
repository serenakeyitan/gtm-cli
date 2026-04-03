"""Base agent utilities — shared retry logic and output validation."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a system prompt from the prompts/ directory."""
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text()


def validate_ideas_output(data: Any) -> list[dict[str, Any]]:
    """Validate that output is a list of idea dicts with required fields."""
    if isinstance(data, str):
        data = json.loads(data)
    if not isinstance(data, list):
        raise ValueError(f"Expected list, got {type(data).__name__}")
    for item in data:
        if not isinstance(item, dict):
            raise ValueError(f"Expected dict in list, got {type(item).__name__}")
        if "title" not in item:
            raise ValueError("Each idea must have a 'title' field")
    return data


def validate_build_output(data: Any) -> dict[str, Any]:
    """Validate build agent output."""
    if isinstance(data, str):
        data = json.loads(data)
    if not isinstance(data, dict):
        raise ValueError(f"Expected dict, got {type(data).__name__}")
    return data


def extract_json_from_result(result: str) -> Any:
    """Try to extract JSON from agent text output."""
    # Try direct parse
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        pass

    # Try finding JSON in markdown code blocks
    import re
    patterns = [
        r"```json\s*\n(.*?)\n```",
        r"```\s*\n(.*?)\n```",
        r"\[.*\]",
        r"\{.*\}",
    ]
    for pattern in patterns:
        match = re.search(pattern, result, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1) if match.lastindex else match.group(0))
            except json.JSONDecodeError:
                continue

    raise ValueError(f"Could not extract JSON from result: {result[:200]}")
