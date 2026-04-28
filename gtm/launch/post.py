"""Post — frontmatter parser/serializer for `<launch>/<product>/posts/*.md`.

A post file is YAML frontmatter delimited by `---` lines, followed by a
markdown body. See docs/PLAN-launch-workflow.md "Post frontmatter" for the
schema. This module only handles read/write/validation; CLI surface lives in
`gtm.cli` under the `post` group.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from gtm.launch.dir import LaunchDir


REQUIRED_FIELDS = ("id", "product", "channel", "status")
STATUS_ENUM = ("drafting", "scheduled", "live", "removed")
KIND_ENUM = ("image", "self", "link")


class PostError(Exception):
    """Raised on malformed frontmatter, missing required fields, or bad enums."""


@dataclass
class Post:
    """One launch post: frontmatter + body, backed by a single .md file."""

    path: Path
    frontmatter: dict = field(default_factory=dict)
    body: str = ""

    # ── Convenience accessors ────────────────────────────────────────

    @property
    def slug(self) -> str:
        return self.path.stem

    @property
    def id(self) -> str:
        return str(self.frontmatter.get("id", ""))

    @property
    def product(self) -> str:
        return str(self.frontmatter.get("product", ""))

    @property
    def channel(self) -> str:
        return str(self.frontmatter.get("channel", ""))

    @property
    def status(self) -> str:
        return str(self.frontmatter.get("status", ""))

    @property
    def kind(self) -> Optional[str]:
        k = self.frontmatter.get("kind")
        return str(k) if k else None

    @property
    def direction(self) -> Optional[str]:
        d = self.frontmatter.get("direction")
        return str(d) if d else None

    @property
    def identity(self) -> Optional[str]:
        i = self.frontmatter.get("identity")
        return str(i) if i else None

    @property
    def posted_at(self) -> Optional[str]:
        p = self.frontmatter.get("posted_at")
        return str(p) if p else None

    @property
    def metrics(self) -> dict:
        m = self.frontmatter.get("metrics") or {}
        return dict(m) if isinstance(m, dict) else {}

    @property
    def score(self) -> int:
        v = self.metrics.get("score")
        try:
            return int(v) if v is not None else 0
        except (TypeError, ValueError):
            return 0

    @property
    def comments(self) -> int:
        v = self.metrics.get("comments")
        try:
            return int(v) if v is not None else 0
        except (TypeError, ValueError):
            return 0

    # ── Direction (post-vs-comment, not the strategic "direction" tag) ──

    @property
    def post_direction(self) -> str:
        """Coarse direction inferred from kind/channel for the dashboard column.

        Not in the plan's frontmatter schema — derived. `image`/`link`/`self`
        all map to "post" for now; future kinds (e.g., "comment") may change.
        """
        k = self.kind or "self"
        return "post" if k in KIND_ENUM else "other"

    # ── Load / Save ──────────────────────────────────────────────────

    @classmethod
    def load(cls, path: Path) -> "Post":
        """Read `path`, split frontmatter from body, validate schema."""
        path = Path(path).expanduser().resolve()
        if not path.is_file():
            raise PostError(f"Post file not found: {path}")
        text = path.read_text()
        frontmatter, body = _split_frontmatter(text, path)
        _validate(frontmatter, path)
        return cls(path=path, frontmatter=frontmatter, body=body)

    def save(self, path: Optional[Path] = None) -> None:
        """Write back to `path` (or self.path), preserving the `---` shape."""
        target = Path(path).expanduser().resolve() if path else self.path
        # Re-validate before write so we never persist garbage
        _validate(self.frontmatter, target)
        fm = yaml.safe_dump(
            self.frontmatter,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        )
        # Trim trailing newline from yaml dump, we add our own
        fm = fm.rstrip("\n")
        body = self.body
        # Ensure body starts on its own line, no leading whitespace eaten
        if body and not body.startswith("\n"):
            body = "\n" + body
        if body and not body.endswith("\n"):
            body += "\n"
        out = f"---\n{fm}\n---\n{body}" if body else f"---\n{fm}\n---\n"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(out)

    # ── Bulk discovery ───────────────────────────────────────────────

    @classmethod
    def find_all(cls, launch: LaunchDir) -> list["Post"]:
        """Glob every `<product>/posts/*.md` under `launch`, parse, sort newest first.

        Files that fail to parse are skipped with no error (so a half-written
        draft can't break `gtm post list`). Sort key: `posted_at` desc, then
        file mtime desc as a tiebreaker for unposted drafts.
        """
        posts: list[Post] = []
        for prod in launch.products:
            key = prod.get("key")
            if not key:
                continue
            posts_dir = launch.path / key / "posts"
            if not posts_dir.is_dir():
                continue
            for md in sorted(posts_dir.glob("*.md")):
                try:
                    posts.append(cls.load(md))
                except PostError:
                    continue

        def _key(p: Post):
            pa = p.posted_at or ""
            mtime = p.path.stat().st_mtime if p.path.exists() else 0.0
            # Sort: posts with posted_at first (newest first), then drafts by mtime
            return (0 if pa else 1, _negate_str(pa), -mtime)

        posts.sort(key=_key)
        return posts


# ── Internals ───────────────────────────────────────────────────────


def _negate_str(s: str) -> tuple:
    """Trick to sort strings descending inside a tuple-key sort.

    Turn each char into its negated codepoint so `sorted` ascending == reverse
    lexicographic. Empty string sorts last.
    """
    return tuple(-ord(c) for c in s)


def _split_frontmatter(text: str, path: Path) -> tuple[dict, str]:
    """Split `---\\n<yaml>\\n---\\n<body>`. Raise PostError on malformed shape."""
    if not text.lstrip().startswith("---"):
        raise PostError(
            f"{path}: missing opening `---` frontmatter delimiter "
            f"(got: {text[:40]!r})"
        )
    # Strip leading blank lines, then drop the first `---` line
    lines = text.splitlines()
    # Find first --- line
    try:
        first = next(i for i, ln in enumerate(lines) if ln.strip() == "---")
    except StopIteration:
        raise PostError(f"{path}: no `---` frontmatter opener")
    # Find closing --- after first
    try:
        second = next(
            i for i, ln in enumerate(lines[first + 1:], start=first + 1)
            if ln.strip() == "---"
        )
    except StopIteration:
        raise PostError(f"{path}: missing closing `---` frontmatter delimiter")

    fm_text = "\n".join(lines[first + 1:second])
    body = "\n".join(lines[second + 1:])
    # Normalize body leading newline
    body = body.lstrip("\n")

    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError as e:
        raise PostError(f"{path}: malformed YAML frontmatter: {e}")
    if not isinstance(fm, dict):
        raise PostError(f"{path}: frontmatter must be a YAML mapping")
    return fm, body


def _validate(fm: dict, path: Path) -> None:
    """Enforce required fields + enum membership. Optional fields may be null."""
    missing = [k for k in REQUIRED_FIELDS if k not in fm or fm.get(k) in (None, "")]
    if missing:
        raise PostError(
            f"{path}: missing required frontmatter field(s): {', '.join(missing)}. "
            f"Required: {', '.join(REQUIRED_FIELDS)}"
        )
    status = fm.get("status")
    if status not in STATUS_ENUM:
        raise PostError(
            f"{path}: invalid status {status!r}. Must be one of: {', '.join(STATUS_ENUM)}"
        )
    kind = fm.get("kind")
    if kind is not None and kind not in KIND_ENUM:
        raise PostError(
            f"{path}: invalid kind {kind!r}. Must be one of: {', '.join(KIND_ENUM)} "
            f"(or omit/null)"
        )
