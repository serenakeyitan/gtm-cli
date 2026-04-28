"""Render the launch dashboard HTML from a LaunchDir + its posts.

CP6 turns the previously hand-edited `atf-launch/dashboard.html` into a
generated artifact. The React component, recommender, TODOS, and styles all
live in `dashboard_template.html` unchanged. We only inject four blobs:

* ``{{TODAY}}``           — today's date in YYYY-MM-DD (UTC).
* ``{{DIRECTIONS_JSON}}`` — JSON array of ``{key,label}`` from ``.gtm-launch.yaml``.
* ``{{PRODUCTS_JSON}}``   — JSON array of products from ``.gtm-launch.yaml``.
* ``{{POSTS_JSON}}``      — JSON array of post records, one per .md file.

Substitution is plain string ``.replace()`` — no Jinja, no template engine, so
the only dependency is what the launch package already pulls in (PyYAML).
"""

from __future__ import annotations

import datetime as _datetime_mod
import json
from datetime import datetime, timezone

# Local aliases so the formatter doesn't drop them as "unused" — see usage in
# _post_to_dict and _json_default below for date/timedelta handling of YAML
# timestamps.
_date = _datetime_mod.date
_timedelta = _datetime_mod.timedelta
from pathlib import Path
from typing import Any, Optional

from gtm.launch.dir import LaunchDir
from gtm.launch.post import Post


TEMPLATE_PATH = Path(__file__).parent / "dashboard_template.html"

# Fallback data — used when `.gtm-launch.yaml` doesn't define products /
# directions. Empty arrays keep the React component happy (the recommender
# never traverses these without checking length).
_DEFAULT_DIRECTIONS: list[dict] = []
_DEFAULT_PRODUCTS: list[dict] = []

# Frontmatter keys we drop into the per-post JSON record verbatim. Anything
# under `metrics` is hoisted to top-level (the React component reads
# `post.score` / `post.comments`, NOT `post.metrics.score`).
_PASSTHROUGH_FM_KEYS = (
    "id",
    "product",
    "direction",
    "channel",
    "identity",
    "kind",
    "image",
    "status",
    "url",
    "live_id",
    "posted_at",
    "note",
    "draft",
)


def _today_utc() -> str:
    """YYYY-MM-DD in UTC. Isolated for test monkeypatching."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _channel_account(post: Post) -> Optional[str]:
    """Render the `account` field the dashboard shows (e.g. ``u/foo``).

    The atf-launch dashboard wrote ``u/<identity>`` literally. We mirror that
    so the React component renders the same string. ``None`` if no identity.
    """
    ident = post.identity
    if not ident:
        return None
    return f"u/{ident}"


def _post_to_dict(post: Post) -> dict[str, Any]:
    """Convert a Post into the flat dict the React component expects.

    Field map (frontmatter → rendered):
      * ``id, product, direction, channel, identity, kind, image, status,
        url, live_id, posted_at, note, draft`` → top-level passthrough.
      * ``metrics.score`` → ``score``
      * ``metrics.comments`` → ``comments``
      * ``metrics.comments_real`` → ``comments_real`` (only if present)
      * ``metrics.last_checked`` → ``last_checked`` (only if present)
      * ``account`` synthesized as ``u/<identity>``.
      * ``date`` derived from ``posted_at[:10]`` else frontmatter
        ``target_date``/``date`` else "".
      * For ``status == 'removed'``: include ``reason`` if frontmatter has one
        (either top-level ``reason`` or fall back to ``note``).
    """
    fm = post.frontmatter or {}
    out: dict[str, Any] = {}
    for k in _PASSTHROUGH_FM_KEYS:
        if k in fm and fm[k] is not None:
            out[k] = fm[k]

    # Metrics → flat top-level keys.
    metrics = fm.get("metrics") or {}
    if isinstance(metrics, dict):
        if metrics.get("score") is not None:
            out["score"] = metrics["score"]
        if metrics.get("comments") is not None:
            out["comments"] = metrics["comments"]
        if metrics.get("comments_real") is not None:
            out["comments_real"] = metrics["comments_real"]
        if metrics.get("last_checked") is not None:
            out["last_checked"] = metrics["last_checked"]

    # account synthesized from identity.
    acct = _channel_account(post)
    if acct:
        out["account"] = acct

    # date — the React component sorts/labels by `date`. Prefer YYYY-MM-DD
    # prefix of posted_at; fall back to explicit target_date/date in fm.
    posted_at = fm.get("posted_at")
    if isinstance(posted_at, datetime):
        out["date"] = posted_at.strftime("%Y-%m-%d")
    elif isinstance(posted_at, _date):
        out["date"] = posted_at.isoformat()
    elif posted_at and isinstance(posted_at, str) and len(posted_at) >= 10:
        out["date"] = posted_at[:10]
    elif fm.get("target_date"):
        td = fm["target_date"]
        out["date"] = td.isoformat() if isinstance(td, _date) else td
    elif fm.get("date"):
        d = fm["date"]
        out["date"] = d.isoformat() if isinstance(d, _date) else d

    # reason — surface for removed posts. atf-launch's hand-rolled JSON had a
    # top-level `reason`; on Post.frontmatter it might live as `reason` or
    # bleed through `note`. Prefer explicit `reason`.
    if out.get("status") == "removed":
        reason = fm.get("reason")
        if reason:
            out["reason"] = reason
        elif fm.get("note") and "reason" not in out:
            # Don't overwrite note (already passed through); just expose as
            # reason too so the dashboard's removed-row formatter shows it.
            out["reason"] = fm["note"]

    return out


def _json_dump(value: Any) -> str:
    """JSON dump tuned for embedding in a <script> tag.

    * ``ensure_ascii=False`` so unicode body text stays readable.
    * No trailing newline; the template provides its own ``;`` after.
    * Defensive escape of ``</`` to avoid breaking out of the script tag if
      a post body or note contains literal ``</script>`` (unlikely but cheap).
    """
    s = json.dumps(value, ensure_ascii=False, indent=2, default=_json_default)
    return s.replace("</", "<\\/")


def _json_default(obj: Any) -> Any:
    """JSON fallback for non-native types we encounter via PyYAML.

    PyYAML decodes bare ISO timestamps (e.g. ``2026-04-25T10:00:00Z``) as
    ``datetime`` and bare ``YYYY-MM-DD`` as ``date``. Render both as ISO
    strings so the dashboard's recommender (which does ``new Date(p.posted_at)``)
    keeps working.
    """
    if isinstance(obj, datetime):
        # Round-trip with explicit Z suffix when UTC, isoformat otherwise.
        if obj.tzinfo is not None and obj.utcoffset() == _timedelta(0):
            return obj.strftime("%Y-%m-%dT%H:%M:%SZ")
        return obj.isoformat()
    if isinstance(obj, _date):
        return obj.isoformat()
    raise TypeError(f"not JSON-serializable: {type(obj).__name__}")


def build_dashboard(launch: LaunchDir, today: Optional[str] = None) -> str:
    """Return the full rendered dashboard HTML string.

    Pure function: doesn't touch disk for output (caller writes the file). The
    template path itself IS read from disk on every call — fine, it's tiny and
    we want template edits to be picked up live during dev.

    Parameters
    ----------
    launch: the LaunchDir to render. Posts are discovered via ``Post.find_all``.
    today:  optional override (mainly for tests). Defaults to UTC today.
    """
    template = TEMPLATE_PATH.read_text()

    posts = Post.find_all(launch)
    posts_json = _json_dump([_post_to_dict(p) for p in posts])

    directions = launch.directions or _DEFAULT_DIRECTIONS
    products = launch.products or _DEFAULT_PRODUCTS

    out = template
    out = out.replace("{{TODAY}}", today or _today_utc())
    out = out.replace("{{DIRECTIONS_JSON}}", _json_dump(directions))
    out = out.replace("{{PRODUCTS_JSON}}", _json_dump(products))
    out = out.replace("{{POSTS_JSON}}", posts_json)
    return out


def write_dashboard(
    launch: LaunchDir,
    out_path: Optional[Path] = None,
    today: Optional[str] = None,
) -> tuple[Path, int]:
    """Build + write to disk. Returns ``(path, bytes_written)``.

    Default output is ``<launch.path>/dashboard.html`` — overwriting is
    expected (the file is generated). Caller is responsible for ``mkdir`` of
    any non-default ``out_path`` parent.
    """
    html = build_dashboard(launch, today=today)
    target = Path(out_path).expanduser().resolve() if out_path else (launch.path / "dashboard.html")
    target.parent.mkdir(parents=True, exist_ok=True)
    data = html.encode("utf-8")
    target.write_bytes(data)
    return target, len(data)
