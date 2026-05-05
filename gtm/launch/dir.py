"""LaunchDir — model + discovery for a launch directory.

A launch directory is any directory containing `.gtm-launch.yaml`. This module
handles discovery (walk-up from cwd or explicit path), scaffolding, and
linking existing directories without clobbering files.

See docs/PLAN-launch-workflow.md "Convention: a launch directory" for the layout.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


LAUNCH_MARKER = ".gtm-launch.yaml"
SCHEMA_VERSION = 1


class LaunchDirError(Exception):
    """Raised on launch-dir misuse (missing marker, malformed yaml, etc.)."""


@dataclass
class LaunchDir:
    """A discovered or freshly-scaffolded launch directory.

    Attributes
    ----------
    path: absolute path to the launch dir (the dir containing .gtm-launch.yaml)
    config: parsed contents of .gtm-launch.yaml (may be empty dict for new dirs)
    """

    path: Path
    config: dict = field(default_factory=dict)

    # ── Discovery ────────────────────────────────────────────────────

    @classmethod
    def find(cls, start: Optional[Path] = None) -> Optional["LaunchDir"]:
        """Walk up from `start` (or cwd) looking for `.gtm-launch.yaml`.

        Honors `GTM_LAUNCH_DIR` env var as a hard override (for tests).
        Returns None if no launch dir is anywhere up the tree.
        """
        env = os.environ.get("GTM_LAUNCH_DIR")
        if env:
            p = Path(env).expanduser().resolve()
            if (p / LAUNCH_MARKER).is_file():
                return cls.load(p)
            return None

        cur = Path(start).expanduser().resolve() if start else Path.cwd().resolve()
        # walk up to filesystem root
        for candidate in [cur, *cur.parents]:
            if (candidate / LAUNCH_MARKER).is_file():
                return cls.load(candidate)
        return None

    @classmethod
    def load(cls, path: Path) -> "LaunchDir":
        """Load an existing launch dir at `path`. Raises if no marker."""
        path = Path(path).expanduser().resolve()
        marker = path / LAUNCH_MARKER
        if not marker.is_file():
            raise LaunchDirError(
                f"No {LAUNCH_MARKER} found at {path}. "
                f"Run `gtm launch init` or `gtm launch link` first."
            )
        try:
            data = yaml.safe_load(marker.read_text()) or {}
        except yaml.YAMLError as e:
            raise LaunchDirError(f"Malformed {marker}: {e}")
        if not isinstance(data, dict):
            raise LaunchDirError(f"{marker} must be a YAML mapping at the top level.")
        return cls(path=path, config=data)

    # ── Convenience accessors ────────────────────────────────────────

    @property
    def marker_path(self) -> Path:
        return self.path / LAUNCH_MARKER

    @property
    def products(self) -> list[dict]:
        return list(self.config.get("products") or [])

    @property
    def directions(self) -> list[dict]:
        return list(self.config.get("directions") or [])

    @property
    def default_identity_by_platform(self) -> dict:
        return dict(self.config.get("default_identity_by_platform") or {})

    @property
    def dashboard_config(self) -> dict:
        return dict(self.config.get("dashboard") or {})

    # ── Mutation ─────────────────────────────────────────────────────

    def write_marker(self) -> None:
        """Write .gtm-launch.yaml to disk from self.config."""
        self.path.mkdir(parents=True, exist_ok=True)
        self.marker_path.write_text(
            yaml.safe_dump(self.config, sort_keys=False, default_flow_style=False)
        )


# ── Scaffold helpers ────────────────────────────────────────────────


def build_default_config(
    products: list[dict],
    directions: list[dict],
    default_identity_by_platform: Optional[dict] = None,
    dashboard: Optional[dict] = None,
) -> dict:
    """Construct a fresh `.gtm-launch.yaml` config dict from inputs."""
    return {
        "version": SCHEMA_VERSION,
        "products": products,
        "directions": directions,
        "default_identity_by_platform": default_identity_by_platform or {},
        "dashboard": dashboard or {},
    }


def scaffold_layout(launch_path: Path, products: list[dict]) -> list[Path]:
    """Create the per-product subdirs and top-level user-owned files.

    Returns a list of paths created (for logging). Idempotent: existing files
    are NEVER overwritten — only missing dirs/files get created. This is what
    makes `link` safe on dirs that already have content (atf-launch's case).
    """
    created: list[Path] = []
    launch_path.mkdir(parents=True, exist_ok=True)

    # Top-level user-owned files (only if missing)
    readme = launch_path / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Launch tracker\n\n"
            "Managed by [gtm-cli](https://github.com/serenakeyitan/gtm-cli).\n"
        )
        created.append(readme)

    roadmap = launch_path / "ROADMAP.md"
    if not roadmap.exists():
        roadmap.write_text("# Cross-product roadmap\n\n_TBD_\n")
        created.append(roadmap)

    # dist/ is gitignored deploy staging
    dist = launch_path / "dist"
    if not dist.exists():
        dist.mkdir()
        created.append(dist)

    # .gitignore — append `dist/` if missing
    gitignore = launch_path / ".gitignore"
    existing = gitignore.read_text() if gitignore.exists() else ""
    if "dist/" not in existing.split("\n"):
        new_content = existing
        if existing and not existing.endswith("\n"):
            new_content += "\n"
        new_content += "dist/\n"
        gitignore.write_text(new_content)
        if not existing:
            created.append(gitignore)

    # Per-product layout
    for prod in products:
        key = prod.get("key")
        if not key:
            continue
        pdir = launch_path / key
        pdir.mkdir(exist_ok=True)
        prod_roadmap = pdir / "ROADMAP.md"
        if not prod_roadmap.exists():
            name = prod.get("name", key)
            prod_roadmap.write_text(f"# {name} roadmap\n\n_TBD_\n")
            created.append(prod_roadmap)
        posts = pdir / "posts"
        posts.mkdir(exist_ok=True)
        assets = posts / "assets"
        assets.mkdir(exist_ok=True)
        # Drop a .gitkeep so empty posts/ is committable
        keep = posts / ".gitkeep"
        if not keep.exists() and not any(posts.glob("*.md")):
            keep.touch()
            created.append(keep)

    return created
