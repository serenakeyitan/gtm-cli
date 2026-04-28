"""Helpers for `gtm post draft` — slug generation, channel/platform inference,
body template, comment stripping, image staging.

Kept separate from `gtm.launch.post` (pure model) and `gtm.cli` (Click surface)
so the pure logic is easy to unit-test from e2e shell scripts.
"""

from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path
from typing import Optional


# Voice-rules starter that opens in $EDITOR. The HTML comment block is
# stripped on save so it never lands in the published post body.
BODY_TEMPLATE = """\
<!--
  Karpathy voice rules:
  - lowercase only (proper nouns OK)
  - no em dashes — use periods
  - "i" not "we"
  - no banned phrases: "check out", "excited to share", "introducing", "🚀", "🔥"
  - opener works standalone
  Delete this comment block before saving (or leave — won't be published).
-->

<write your post body here>
"""

# Strip the leading `<!-- ... -->` block (and any number of trailing blanks)
# so the saved body never carries the voice-rules comment.
_LEADING_COMMENT_RE = re.compile(r"^\s*<!--.*?-->\s*", re.DOTALL)


def strip_template_comment(body: str) -> str:
    """Remove the leading HTML comment block (the voice-rules header) if present.

    Only strips the first comment if it's at the very top of the body. Comments
    inside a real post body are left alone.
    """
    return _LEADING_COMMENT_RE.sub("", body, count=1).lstrip("\n")


def infer_platform(channel: str) -> str:
    """Map a channel string to a platform key.

    Examples
    --------
    "reddit r/AI_Agents" → "reddit"
    "twitter"            → "twitter"
    "hn"                 → "hn"
    "Reddit r/foo"       → "reddit"  (case-insensitive)
    """
    c = (channel or "").strip().lower()
    if c.startswith("reddit"):
        return "reddit"
    if c.startswith("twitter") or c.startswith("x "):
        return "twitter"
    if c.startswith("hn") or c.startswith("hacker"):
        return "hn"
    # default to twitter per spec ("else twitter / hn")
    return "twitter"


def sanitize_channel_for_slug(channel: str) -> str:
    """Compress a channel string into a slug-safe token.

    "reddit r/AI_Agents"   → "reddit-r-ai-agents"
    "twitter"              → "twitter"
    "hn"                   → "hn"
    """
    c = (channel or "").strip().lower()
    # Replace any run of non-alphanumeric with a single hyphen
    c = re.sub(r"[^a-z0-9]+", "-", c)
    return c.strip("-") or "channel"


def slugify_title(title: str, max_words: int = 6) -> str:
    """Build a short slug fragment from the post title.

    Drops stopwords-light (small set), keeps the first ~6 useful words,
    lowercases, hyphenates.
    """
    t = (title or "").lower()
    t = re.sub(r"[^a-z0-9\s-]+", " ", t)
    words = [w for w in re.split(r"[\s-]+", t) if w]
    if not words:
        return "post"
    return "-".join(words[:max_words])


def build_slug(channel: str, title: str, day: Optional[date] = None,
               max_len: int = 60) -> str:
    """Compose the canonical slug: `<YYYY-MM-DD>-<channel>-<title>`.

    Truncates to `max_len` chars at a hyphen boundary so we never cut a word.
    """
    d = day or date.today()
    parts = [d.isoformat(), sanitize_channel_for_slug(channel), slugify_title(title)]
    slug = "-".join(p for p in parts if p)
    slug = re.sub(r"-+", "-", slug).strip("-")
    if len(slug) <= max_len:
        return slug
    # Truncate at a hyphen boundary so we don't slice mid-word
    cut = slug[:max_len].rsplit("-", 1)[0]
    return cut or slug[:max_len]


def find_unique_slug(posts_dir: Path, base_slug: str) -> Optional[str]:
    """Return a non-colliding slug, suffixing `-2`, `-3`, … if needed.

    Returns None if `base_slug` itself is free; otherwise returns the suggested
    suffixed slug. This separation lets the CLI surface the suggestion in its
    refusal message rather than silently renaming.
    """
    if not (posts_dir / f"{base_slug}.md").exists():
        return None
    for i in range(2, 100):
        candidate = f"{base_slug}-{i}"
        if not (posts_dir / f"{candidate}.md").exists():
            return candidate
    raise RuntimeError(f"Couldn't find a free slug after 100 tries from {base_slug!r}")


def copy_image_into_assets(image_path: Path, assets_dir: Path) -> Path:
    """Copy `image_path` into `assets_dir`, returning the destination path.

    If the destination filename collides, suffixes `-2`, `-3`, … on the stem.
    """
    image_path = Path(image_path).expanduser().resolve()
    if not image_path.is_file():
        raise FileNotFoundError(f"Image not found: {image_path}")
    assets_dir.mkdir(parents=True, exist_ok=True)
    dest = assets_dir / image_path.name
    if dest.exists():
        stem = image_path.stem
        suffix = image_path.suffix
        for i in range(2, 100):
            cand = assets_dir / f"{stem}-{i}{suffix}"
            if not cand.exists():
                dest = cand
                break
        else:
            raise RuntimeError(f"Too many collisions copying {image_path.name}")
    shutil.copy2(image_path, dest)
    return dest


def build_frontmatter(
    *,
    post_id: str,
    product: str,
    direction: Optional[str],
    channel: str,
    identity: Optional[str],
    kind: str,
    image_relpath: Optional[str],
) -> dict:
    """Assemble the canonical frontmatter dict for a brand-new draft."""
    fm: dict = {
        "id": post_id,
        "product": product,
        "direction": direction,
        "channel": channel,
        "identity": identity,
        "kind": kind,
        "status": "drafting",
        "url": None,
        "live_id": None,
        "posted_at": None,
        "metrics": {
            "score": 0,
            "comments": 0,
            "comments_real": 0,
            "last_checked": None,
        },
        "note": None,
    }
    if image_relpath:
        # Insert `image:` after `kind:` for readability
        new_fm = {}
        for k, v in fm.items():
            new_fm[k] = v
            if k == "kind":
                new_fm["image"] = image_relpath
        fm = new_fm
    return fm


def next_post_id(posts_dir: Path, prefix: str = "d") -> str:
    """Pick the next sequential id like `d1`, `d2`, … by scanning sibling posts.

    Falls back to `d1` if posts_dir is empty or unreadable. The id is just a
    short stable label for the dashboard — the slug is the real filename.
    """
    if not posts_dir.is_dir():
        return f"{prefix}1"
    used = set()
    for md in posts_dir.glob("*.md"):
        try:
            text = md.read_text()
        except OSError:
            continue
        m = re.search(r"^id:\s*(\S+)\s*$", text, re.MULTILINE)
        if m:
            used.add(m.group(1).strip())
    n = 1
    while f"{prefix}{n}" in used:
        n += 1
    return f"{prefix}{n}"
