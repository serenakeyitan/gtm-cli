"""Base agent utilities — shared retry logic and output validation."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"
USER_PROMPTS_DIR = Path.home() / ".config" / "gtm" / "prompts"


def load_prompt(name: str) -> str:
    """Load a system prompt.

    Search order:
    1. ~/.config/gtm/prompts/<name>.md  (user-local overrides, private strategy)
    2. <package>/prompts/<name>.md      (bundled defaults, public)

    This lets users keep their proprietary prompts out of the gtm-cli repo
    while still benefiting from upstream prompt updates as a fallback.
    """
    user_path = USER_PROMPTS_DIR / f"{name}.md"
    if user_path.exists():
        return user_path.read_text()
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(
            f"Prompt '{name}' not found in {USER_PROMPTS_DIR} or {PROMPTS_DIR}"
        )
    return path.read_text()


def load_style_guide(platform: str | None = None) -> str:
    """Load the content style guide, optionally filtered to a platform section.
    
    Platform: 'reddit', 'hn', 'twitter', or None for the full guide.
    """
    path = PROMPTS_DIR / "style_guide.md"
    if not path.exists():
        return ""
    
    full_guide = path.read_text()
    
    if not platform:
        return full_guide
    
    # Extract the platform-specific section
    platform_headers = {
        "reddit": "### Reddit",
        "hn": "### Hacker News",
        "twitter": "### Twitter",
    }
    
    platform_key = platform.strip().lower()
    header = platform_headers.get(platform_key)
    if not header:
        log.warning("Unknown platform '%s' for style guide. Available: %s", platform, list(platform_headers.keys()))
        return full_guide
    
    start = full_guide.find(header)
    if start == -1:
        return full_guide
    
    # Extract from this header to the next same-level (###) header or end marker (---)
    # Only match "\n### " at the start of a line to avoid matching deeper headings
    import re
    section_text = full_guide[start:]
    # Match the next "### " at line start (same level heading) or "---" separator
    match = re.search(r'\n(?=### [A-Z]|\n---)', section_text[len(header):])
    if match:
        return section_text[:len(header) + match.start()].strip()
    return section_text.strip()


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
