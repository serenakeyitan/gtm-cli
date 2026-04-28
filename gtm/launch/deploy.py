"""Dashboard deploy + serve helpers (CP7).

Two thin operations:

* ``stage_dashboard(launch)`` — build dashboard fresh and copy to
  ``<launch>/dist/index.html`` (atf-launch's deploy convention).
* ``build_deploy_command(launch, provider, project)`` — return the
  argv list we'd hand to ``subprocess.run`` for the chosen provider.

The CLI layer (``gtm/cli.py``) drives these and also runs the local
``http.server`` for ``gtm dashboard serve``.

Provider config lives under ``dashboard:`` in ``.gtm-launch.yaml``::

    dashboard:
      cloudflare_project: atf-launch
      vercel_project: ""
      provider: cloudflare       # default if --provider not given

Missing ``cloudflare_project`` (or ``vercel_project`` for vercel) raises
``DeployConfigError`` with an actionable message — the CLI surfaces it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from gtm.launch.dir import LaunchDir
from gtm.launch.dashboard import write_dashboard


PROVIDERS = ("cloudflare", "vercel")
DEFAULT_PROVIDER = "cloudflare"


class DeployConfigError(Exception):
    """Raised when required deploy config is missing from .gtm-launch.yaml."""


@dataclass
class DeployPlan:
    """What we'd run, captured for both ``--dry-run`` and live execution."""

    provider: str
    project: str
    cmd: list[str]
    cwd: Path
    dist_dir: Path

    def cmd_str(self) -> str:
        """Shell-ish representation for printing. Not safe for re-execution."""
        return " ".join(self.cmd)


def stage_dashboard(launch: LaunchDir) -> tuple[Path, Path]:
    """Build dashboard fresh and stage to ``<launch>/dist/index.html``.

    Returns ``(dashboard_html_path, dist_index_path)``. Both files are
    written. The dist dir is created if missing (it's gitignored — see
    CP1's scaffold).
    """
    dashboard_html, _ = write_dashboard(launch)
    dist = launch.path / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    index = dist / "index.html"
    # Copy bytes (not symlink) — wrangler/vercel both want a real file.
    index.write_bytes(dashboard_html.read_bytes())
    return dashboard_html, index


def resolve_provider(launch: LaunchDir, override: Optional[str]) -> str:
    """Pick the provider: ``--provider`` flag wins, else yaml, else default."""
    if override:
        if override not in PROVIDERS:
            raise DeployConfigError(
                f"unknown provider {override!r}; must be one of {PROVIDERS}"
            )
        return override
    cfg = launch.dashboard_config
    p = cfg.get("provider") or DEFAULT_PROVIDER
    if p not in PROVIDERS:
        raise DeployConfigError(
            f"dashboard.provider={p!r} in .gtm-launch.yaml is not one of {PROVIDERS}"
        )
    return p


def build_plan(launch: LaunchDir, provider: str) -> DeployPlan:
    """Construct the DeployPlan (no side effects beyond reading config)."""
    cfg = launch.dashboard_config
    dist = launch.path / "dist"

    if provider == "cloudflare":
        project = cfg.get("cloudflare_project")
        if not project:
            raise DeployConfigError(
                "missing `dashboard.cloudflare_project` in .gtm-launch.yaml; "
                "set it to your Cloudflare Pages project name (e.g. atf-launch)"
            )
        cmd = [
            "wrangler",
            "pages",
            "deploy",
            str(dist),
            f"--project-name={project}",
            "--branch=main",
            "--commit-dirty=true",
        ]
    elif provider == "vercel":
        project = cfg.get("vercel_project") or ""
        # vercel doesn't strictly require a project name on the CLI (it
        # picks up .vercel/project.json), but if user set one we pass it.
        if not project:
            raise DeployConfigError(
                "missing `dashboard.vercel_project` in .gtm-launch.yaml; "
                "set it to your Vercel project name"
            )
        cmd = ["vercel", "deploy", str(dist), "--yes"]
    else:  # pragma: no cover — guarded by resolve_provider
        raise DeployConfigError(f"unknown provider: {provider}")

    return DeployPlan(
        provider=provider,
        project=project,
        cmd=cmd,
        cwd=launch.path,
        dist_dir=dist,
    )


# ── URL parsing ─────────────────────────────────────────────────────

import re


_URL_RE = re.compile(r"https?://[^\s<>\"']+")


def parse_deploy_url(stdout: str, stderr: str = "") -> Optional[str]:
    """Best-effort: extract the first ``https://...pages.dev`` (or vercel)
    URL from wrangler/vercel output. Falls back to the first URL we see.

    wrangler prints lines like ``✨ Deployment complete! Take a peek over at https://abc.atf-launch.pages.dev``.
    vercel prints ``✅  Production: https://foo.vercel.app``.
    """
    for blob in (stdout, stderr):
        if not blob:
            continue
        # Prefer pages.dev / vercel.app hits first.
        for m in _URL_RE.finditer(blob):
            url = m.group(0).rstrip(".,);")
            if "pages.dev" in url or "vercel.app" in url:
                return url
    # Fall back to the first URL of any kind.
    for blob in (stdout, stderr):
        if not blob:
            continue
        m = _URL_RE.search(blob)
        if m:
            return m.group(0).rstrip(".,);")
    return None
