"""Output logger — git-backed audit trail of all growth-cli actions.

Every post, draft, and strategy run is:
1. Written as a markdown file with YAML frontmatter
2. Auto-committed to the output git repo
3. Optionally auto-pushed to a remote (if configured)

Output lives in ~/.config/growth/output/ (a git repo).
"""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from growth.config import GrowthConfig, OUTPUT_DIR

log = logging.getLogger(__name__)


def _get_output_dir() -> Path:
    """Get the output directory, using config override if set."""
    config = GrowthConfig.load()
    return Path(config.output_dir).expanduser()


def _git(output_dir: Path, *args: str) -> bool:
    """Run a git command in the output directory. Returns True on success."""
    try:
        subprocess.run(
            ["git", *args],
            cwd=output_dir,
            capture_output=True,
            timeout=10,
        )
        return True
    except Exception as e:
        log.debug("git %s failed: %s", " ".join(args), e)
        return False


def _auto_commit(output_dir: Path, message: str) -> None:
    """Stage all changes and commit."""
    config = GrowthConfig.load()
    if not config.output_git_auto_commit:
        return

    _git(output_dir, "add", "-A")
    _git(output_dir, "commit", "-m", message, "--allow-empty")

    if config.output_git_auto_push and config.output_git_remote:
        _git(output_dir, "push")


def log_post(
    platform: str,
    identity: str,
    content: str,
    result: dict[str, Any],
    **extra: Any,
) -> Path:
    """Log a successful post to the output repo.

    Creates: output/posted/2026-03-27_twitter_handle_18294.md
    """
    output_dir = _get_output_dir()
    posted_dir = output_dir / "posted"
    posted_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    post_id = result.get("post_id", "unknown")
    filename = f"{now.strftime('%Y-%m-%d')}_{platform}_{identity.split(':')[-1]}_{post_id}.md"
    filepath = posted_dir / filename

    frontmatter = {
        "platform": platform,
        "identity": identity,
        "posted_at": now.isoformat(),
        "post_id": post_id,
        "url": result.get("url", ""),
        **{k: v for k, v in extra.items() if v},
    }

    md = "---\n"
    for k, v in frontmatter.items():
        md += f"{k}: {json.dumps(v) if isinstance(v, (dict, list)) else repr(str(v))}\n"
    md += "---\n\n"
    md += content or "(no text content)"
    md += "\n"

    filepath.write_text(md)
    _auto_commit(output_dir, f"post({identity}): {content[:60]}")
    log.info("Logged post to %s", filepath)
    return filepath


def log_draft(
    platform: str,
    identity: str,
    content: str,
    strategy: str = "manual",
    **extra: Any,
) -> Path:
    """Log a draft to the output repo.

    Creates: output/drafts/2026-03-27_twitter_launch.md
    """
    output_dir = _get_output_dir()
    drafts_dir = output_dir / "drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    slug = extra.get("slug", "draft")
    filename = f"{now.strftime('%Y-%m-%d')}_{platform}_{slug}.md"
    filepath = drafts_dir / filename

    frontmatter = {
        "platform": platform,
        "identity": identity,
        "created_at": now.isoformat(),
        "strategy": strategy,
        "status": "draft",
        **{k: v for k, v in extra.items() if v and k != "slug"},
    }

    md = "---\n"
    for k, v in frontmatter.items():
        md += f"{k}: {json.dumps(v) if isinstance(v, (dict, list)) else repr(str(v))}\n"
    md += "---\n\n"
    md += content or "(no text content)"
    md += "\n"

    filepath.write_text(md)
    _auto_commit(output_dir, f"draft({platform}): {content[:60]}")
    log.info("Logged draft to %s", filepath)
    return filepath


def log_run(
    strategy: str,
    state: dict[str, Any],
) -> Path:
    """Log a strategy run to the output repo.

    Creates: output/runs/2026-03-27_1430/
    """
    output_dir = _get_output_dir()
    now = datetime.now()
    run_id = now.strftime("%Y-%m-%d_%H%M")
    run_dir = output_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Save state
    state_path = run_dir / "state.json"
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)

    # Save strategy name
    meta_path = run_dir / "meta.json"
    with open(meta_path, "w") as f:
        json.dump({
            "strategy": strategy,
            "started_at": now.isoformat(),
            "run_id": run_id,
        }, f, indent=2)

    _auto_commit(output_dir, f"run({strategy}): {run_id}")
    log.info("Logged run to %s", run_dir)
    return run_dir


def get_recent_posts(count: int = 10) -> list[dict[str, Any]]:
    """Read recent posted items from the output repo."""
    output_dir = _get_output_dir()
    posted_dir = output_dir / "posted"
    if not posted_dir.exists():
        return []

    import yaml

    posts = []
    for f in sorted(posted_dir.glob("*.md"), reverse=True)[:count]:
        text = f.read_text()
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                try:
                    meta = yaml.safe_load(parts[1])
                    meta["content"] = parts[2].strip()
                    meta["file"] = f.name
                    posts.append(meta)
                except Exception:
                    pass
    return posts
