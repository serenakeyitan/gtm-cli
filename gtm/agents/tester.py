"""Agent 3.5: Tester — validate built repos before promotion.

Runs after Builder (Agent 3), before Promoter (Agent 4).
Clones each built repo, installs dependencies, runs tests,
checks CI status, and produces a pass/fail report.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from claude_code_sdk import (
    ClaudeCodeOptions,
)

from gtm.agents.base import (
    extract_json_from_result,
    load_prompt,
)
from gtm.agents.agent_wrapper import run_tracked_agent
from gtm.agents.activity_log import ActivityLogger
from gtm.engine.state import RunState

log = logging.getLogger(__name__)


async def run_tester(
    state: RunState,
    input_data: Any,
    activity_logger: ActivityLogger | None = None,
) -> dict[str, Any]:
    """Run the Testing agent for a single built repo."""
    build = input_data["build"]
    idea = input_data["idea"]
    config = input_data["config"]

    system_prompt = load_prompt("tester")

    build_json = json.dumps(build, indent=2)
    idea_json = json.dumps(idea, indent=2)

    prompt = (
        f"Test this built project:\n\n"
        f"## Build Info\n{build_json}\n\n"
        f"## Idea Info\n{idea_json}\n\n"
        f"Clone the repo, checkout the PR branch, install dependencies, "
        f"run the full test suite, check for lint errors, verify the build "
        f"succeeds, and produce a comprehensive test report.\n\n"
        f"The repo URL is: {build.get('repo_url', 'unknown')}\n"
        f"The PR URL is: {build.get('pr_url', 'unknown')}\n"
        f"The PR branch is: initial-build\n\n"
        f"Output a JSON object with test results including: tests_passed (bool), "
        f"total_tests, passed_tests, failed_tests, coverage_pct, lint_clean (bool), "
        f"build_success (bool), issues (array), test_output (string)"
    )

    # Use tester model if specified, otherwise fall back to builder model
    model = getattr(config.models, 'tester', config.models.builder)

    options = ClaudeCodeOptions(
        model=model,
        system_prompt=system_prompt,
        allowed_tools=[
            "Bash", "Read", "Write", "Edit", "Glob", "Grep",
            "WebSearch", "WebFetch",
        ],
        max_turns=60,
        permission_mode="bypassPermissions",
    )

    result_text = await run_tracked_agent(
        agent_name=f"tester:{idea.get('id', 'unknown')}",
        options=options,
        prompt=prompt,
        logger=activity_logger,
    )

    result = extract_json_from_result(result_text)

    # Validate and set defaults
    if not isinstance(result, dict):
        result = {}

    result.setdefault("idea_id", idea.get("id"))
    result.setdefault("repo_url", build.get("repo_url"))
    result.setdefault("pr_url", build.get("pr_url"))
    result.setdefault("tests_passed", False)
    result.setdefault("total_tests", 0)
    result.setdefault("passed_tests", 0)
    result.setdefault("failed_tests", 0)
    result.setdefault("coverage_pct", None)
    result.setdefault("lint_clean", False)
    result.setdefault("build_success", False)
    result.setdefault("issues", [])
    result.setdefault("test_output", "")

    return result
