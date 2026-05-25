"""Agent 3: Builder — create open-source projects from validated ideas."""

from __future__ import annotations

import json
import logging
from typing import Any

from claude_agent_sdk import (
    ClaudeAgentOptions,
    create_sdk_mcp_server,
)

from gtm.agents.base import (
    extract_json_from_result,
    load_prompt,
    validate_build_output,
)
from gtm.agents.agent_wrapper import run_tracked_agent
from gtm.agents.activity_log import ActivityLogger
from gtm.engine.state import RunState
from gtm.agents.github_tools import github_create_repo, github_create_pr

log = logging.getLogger(__name__)


async def run_builder(
    state: RunState,
    input_data: Any,
    activity_logger: ActivityLogger | None = None,
) -> dict[str, Any]:
    """Run the Builder agent for a single idea."""
    idea = input_data["idea"]
    config = input_data["config"]

    system_prompt = load_prompt("builder")
    owner = config.github.owner
    git_email = getattr(config.github, "commit_email", f"{owner}@users.noreply.github.com")

    idea_json = json.dumps(idea, indent=2)
    prompt = (
        f"Build an open-source project for this idea:\n{idea_json}\n\n"
        f"IMPORTANT: All git operations must use the {owner} GitHub account.\n"
        f"Before your first commit, run:\n"
        f"  git config user.name '{owner}'\n"
        f"  git config user.email '{git_email}'\n\n"
        f"Instructions:\n"
        f"1. Create a new GitHub repo under '{owner}' using the github_create_repo tool\n"
        f"   - Repo name: {idea.get('suggested_repo_name', 'new-project')}\n"
        f"2. Clone locally, create branch 'initial-build'\n"
        f"3. Build based on type '{idea.get('type', 'unknown')}':\n"
        f"   - awesome-list: curated README.md with categories, links, descriptions, contribution guide\n"
        f"   - cli-tool: Click-based CLI, pyproject.toml, tests\n"
        f"   - skill: skill definition files + scripts\n"
        f"   - freeform: whatever structure best fits the trending concept — use your judgment\n"
        f"   - open-source-alt: re-create a closed-source tool as an open-source alternative\n"
        f"4. Include: README (badges, install, examples), LICENSE (MIT), .gitignore, GitHub Actions CI\n"
        f"5. Atomic commits: one per logical step\n"
        f"6. Push the branch and create a PR (branch → main, do NOT merge)\n\n"
        f"Output a JSON object with: repo_url, pr_url, idea_id, idea_title, files_created"
    )

    server = create_sdk_mcp_server(
        "github-tools",
        tools=[github_create_repo, github_create_pr],
    )

    options = ClaudeAgentOptions(
        model=config.models.builder,
        system_prompt=system_prompt,
        mcp_servers={"github": server},
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep", "WebSearch", "WebFetch", "Agent"],
        max_turns=50,
        permission_mode="bypassPermissions",
    )

    result_text = await run_tracked_agent(
        agent_name=f"builder:{idea.get('id', 'unknown')}",
        options=options,
        prompt=prompt,
        logger=activity_logger,
    )

    result = extract_json_from_result(result_text)
    build = validate_build_output(result)
    build.setdefault("idea_id", idea.get("id"))
    build.setdefault("idea_title", idea.get("title"))
    build.setdefault("failed", False)
    return build
