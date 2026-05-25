"""Custom MCP tools wrapping gh CLI for GitHub operations."""

from __future__ import annotations

import json
import subprocess

from claude_agent_sdk import tool


def _run_gh(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh"] + args, capture_output=True, text=True, timeout=timeout,
    )


def _gh_default_owner() -> str | None:
    """Look up the currently-authenticated GitHub user via `gh api user`.

    Returns the login string, or None if gh is not authenticated.
    Used as a fallback when no owner is explicitly configured.
    """
    try:
        result = _run_gh(["api", "user", "--jq", ".login"], timeout=10)
        if result.returncode == 0:
            return result.stdout.strip() or None
    except Exception:
        pass
    return None


@tool(
    "github_search_repos",
    "Search GitHub repositories by query",
    {"query": str, "sort": str, "limit": int},
)
async def github_search_repos(args):
    """Search GitHub for repositories matching a query."""
    query = args["query"]
    sort = args.get("sort", "stars")
    limit = args.get("limit", 10)
    try:
        result = _run_gh([
            "api", "search/repositories",
            "-X", "GET",
            "-f", f"q={query}",
            "-f", f"sort={sort}",
            "-f", f"per_page={limit}",
        ])
        if result.returncode != 0:
            return {"content": [{"type": "text", "text": f"Error: {result.stderr}"}], "isError": True}
        data = json.loads(result.stdout)
        repos = []
        for item in data.get("items", []):
            repos.append({
                "full_name": item["full_name"],
                "description": item.get("description", ""),
                "stars": item["stargazers_count"],
                "forks": item["forks_count"],
                "url": item["html_url"],
                "updated_at": item.get("updated_at", ""),
                "language": item.get("language", ""),
            })
        return {"content": [{"type": "text", "text": json.dumps(repos, indent=2)}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}


@tool(
    "github_create_repo",
    "Create a new GitHub repository",
    {"name": str, "description": str, "owner": str},
)
async def github_create_repo(args):
    """Create a new public GitHub repository."""
    name = args["name"]
    description = args.get("description", "")
    import os
    owner = args.get("owner") or os.environ.get("GITHUB_OWNER") or _gh_default_owner()
    if not owner:
        return {
            "success": False,
            "error": "No GitHub owner specified. Pass owner=..., or set GITHUB_OWNER env, or `gh auth login`.",
        }
    try:
        result = _run_gh([
            "repo", "create", f"{owner}/{name}",
            "--public",
            "--description", description,
            "--clone",
        ])
        if result.returncode != 0:
            return {"content": [{"type": "text", "text": f"Error: {result.stderr}"}], "isError": True}
        return {"content": [{"type": "text", "text": json.dumps({
            "repo": f"{owner}/{name}",
            "url": f"https://github.com/{owner}/{name}",
            "cloned": True,
        })}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}


@tool(
    "github_create_pr",
    "Create a pull request",
    {"repo": str, "branch": str, "title": str, "body": str, "base": str},
)
async def github_create_pr(args):
    """Create a pull request on a GitHub repository."""
    repo = args["repo"]
    branch = args["branch"]
    title = args["title"]
    body = args.get("body", "")
    base = args.get("base", "main")
    try:
        result = _run_gh([
            "pr", "create",
            "--repo", repo,
            "--head", branch,
            "--base", base,
            "--title", title,
            "--body", body,
        ])
        if result.returncode != 0:
            return {"content": [{"type": "text", "text": f"Error: {result.stderr}"}], "isError": True}
        pr_url = result.stdout.strip()
        return {"content": [{"type": "text", "text": json.dumps({
            "pr_url": pr_url,
            "repo": repo,
            "branch": branch,
        })}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}
