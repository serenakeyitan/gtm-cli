"""Auto-fetch Reddit subreddit posting rules and merge into reddit_sub_rules.yaml.

The yaml is part-human, part-machine. Humans set min_*, permanent_skip, and any
note that captures lived experience (e.g. "flair UI bug 2026-04-27"). The
machine fills the rest from reddit's about.json + rules.json: subscribers,
public_description, rule short_names, submission_type, last_fetched.

Every entry written by this module carries source: 'auto' so future merges
won't clobber human edits.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

DEFAULT_RULES_PATH = Path(__file__).parent.parent / "data" / "reddit_sub_rules.yaml"

_USER_AGENT = "gtm-cli-sub-rules/0.1 (by u/gtm-cli)"
_TIMEOUT = 10
DEFAULT_MAX_AGE_DAYS = 30


class FetchError(Exception):
    """Raised when reddit's API can't be reached or returns garbage."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw, strict=False)
    except urllib.error.HTTPError as e:
        raise FetchError(f"reddit HTTP {e.code} for {url}") from e
    except urllib.error.URLError as e:
        raise FetchError(f"network error {url}: {e.reason}") from e
    except (TimeoutError, OSError) as e:
        raise FetchError(f"timeout {url}: {e}") from e
    except json.JSONDecodeError as e:
        raise FetchError(f"bad JSON {url}: {e}") from e


def fetch_sub_meta(sub: str) -> dict[str, Any]:
    """Pull about.json + rules.json for a subreddit.

    Returns a dict with: subscribers, public_description, submission_type,
    rules (list of {short_name, description}), created_utc, fetched_at.
    """
    name = sub.strip().lstrip("r/").lstrip("/")
    if not name:
        raise FetchError("empty sub name")

    about = _get_json(f"https://www.reddit.com/r/{name}/about.json")
    about_data = (about or {}).get("data") or {}
    if not about_data:
        raise FetchError(f"no data for r/{name} (sub may not exist)")

    rules_payload = _get_json(f"https://www.reddit.com/r/{name}/about/rules.json")
    rules_list = (rules_payload or {}).get("rules") or []

    return {
        "sub": name,
        "subscribers": int(about_data.get("subscribers") or 0),
        "public_description": (about_data.get("public_description") or "").strip(),
        "submission_type": about_data.get("submission_type") or "any",
        "created_utc": float(about_data.get("created_utc") or 0),
        "rules": [
            {
                "short_name": (r.get("short_name") or "").strip(),
                "description": (r.get("description") or "").strip(),
            }
            for r in rules_list if isinstance(r, dict)
        ],
        "fetched_at": _now_iso(),
    }


def _looks_flair_required(meta: dict[str, Any]) -> bool:
    """Best-effort scan of rules + about for flair requirements."""
    desc_blob = " ".join(
        (r.get("short_name", "") + " " + r.get("description", ""))
        for r in meta.get("rules", [])
    ).lower()
    if "flair" in desc_blob and ("required" in desc_blob or "must" in desc_blob):
        return True
    return False


def _condense_notes(meta: dict[str, Any]) -> str:
    """Build a one-line note from fetched meta."""
    parts: list[str] = []
    subs = meta.get("subscribers") or 0
    if subs:
        if subs >= 1_000_000:
            parts.append(f"{subs/1_000_000:.1f}M subs")
        elif subs >= 1_000:
            parts.append(f"{subs/1_000:.0f}k subs")
        else:
            parts.append(f"{subs} subs")

    sub_type = meta.get("submission_type") or "any"
    if sub_type and sub_type != "any":
        parts.append(f"submission_type={sub_type}")

    if _looks_flair_required(meta):
        parts.append("flair required (auto-detected)")

    rule_names = [
        r["short_name"] for r in meta.get("rules", [])
        if r.get("short_name")
    ][:5]
    if rule_names:
        parts.append("rules: " + "; ".join(rule_names))

    desc = meta.get("public_description") or ""
    if desc:
        snippet = desc.split("\n")[0].strip()[:160]
        if snippet:
            parts.append(f"about: {snippet}")

    return " · ".join(parts) or "auto-fetched, no description"


def derive_yaml_entry(meta: dict[str, Any]) -> dict[str, Any]:
    """Translate fetched meta into a YAML row.

    All min_* fields default to null — humans add karma/age gates after a
    removal. permanent_skip defaults to false. source='auto'.
    """
    return {
        "min_total_karma": None,
        "min_link_karma": None,
        "min_comment_karma": None,
        "min_age_days": None,
        "notes": _condense_notes(meta),
        "permanent_skip": False,
        "last_fetched": meta["fetched_at"],
        "source": "auto",
        "subscribers": meta.get("subscribers") or 0,
        "submission_type": meta.get("submission_type") or "any",
        "flair_required_auto": _looks_flair_required(meta),
    }


# ── YAML I/O ──────────────────────────────────────────────────────────


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"subs": {}}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"subs": {}}


def _dump_yaml(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False,
                       allow_unicode=True, width=100)


def _find_existing_key(name: str, subs: dict[str, Any]) -> str | None:
    for key in subs:
        if key.lower() == name.lower():
            return key
    return None


def upsert_sub_rule(sub: str, entry: dict[str, Any], *,
                    path: Path | None = None) -> dict[str, Any]:
    """Merge entry into yaml. Preserves human-set fields.

    Rules:
      - If existing entry has source='manual' (or no source field): only
        update last_fetched + auto-only fields (subscribers, submission_type,
        flair_required_auto). Notes/permanent_skip/min_* stay as the human set.
      - If existing entry has source='auto': overwrite wholesale.
      - If no existing entry: insert new.

    Returns the final merged entry that ended up in the file.
    """
    p = Path(path) if path else DEFAULT_RULES_PATH
    data = _load_yaml(p)
    if "subs" not in data or data["subs"] is None:
        data["subs"] = {}
    subs = data["subs"]
    name = sub.strip().lstrip("r/").lstrip("/")
    existing_key = _find_existing_key(name, subs)

    if existing_key is None:
        subs[name] = entry
        final = entry
    else:
        existing = subs[existing_key] or {}
        source = existing.get("source", "manual")
        if source == "auto":
            subs[existing_key] = entry
            final = entry
        else:
            merged = dict(existing)
            merged["last_fetched"] = entry["last_fetched"]
            for k in ("subscribers", "submission_type", "flair_required_auto"):
                if k in entry:
                    merged[k] = entry[k]
            if "source" not in merged:
                merged["source"] = "manual"
            subs[existing_key] = merged
            final = merged

    _dump_yaml(p, data)
    return final


# ── Staleness ─────────────────────────────────────────────────────────


def is_stale(entry: dict[str, Any] | None, *,
             max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> bool:
    """Entry is stale if it has no last_fetched, or last_fetched is older
    than max_age_days. Manual entries with no last_fetched are NOT stale —
    a human curated them, leave them alone.
    """
    if entry is None:
        return True
    last = entry.get("last_fetched")
    if not last:
        if entry.get("source") == "auto":
            return True
        return False
    try:
        ts = datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return True
    age_days = (datetime.now(timezone.utc) - ts).days
    return age_days >= max_age_days


# ── Top-level entry point ────────────────────────────────────────────


def ensure_sub_rule(sub: str, *,
                    path: Path | None = None,
                    force: bool = False,
                    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
                    fetch: bool = True) -> dict[str, Any]:
    """Ensure the YAML has an up-to-date entry for `sub`.

    Returns a dict: {sub, action, entry, fetched}
      action ∈ {'used_cached', 'fetched_new', 'refetched_stale', 'skipped_no_fetch'}
    """
    p = Path(path) if path else DEFAULT_RULES_PATH
    data = _load_yaml(p)
    subs = (data.get("subs") or {})
    name = sub.strip().lstrip("r/").lstrip("/")
    existing_key = _find_existing_key(name, subs)
    existing = subs.get(existing_key) if existing_key else None

    needs_fetch = force or existing is None or is_stale(existing, max_age_days=max_age_days)

    if not needs_fetch:
        return {"sub": name, "action": "used_cached", "entry": existing, "fetched": False}

    if not fetch:
        return {"sub": name, "action": "skipped_no_fetch", "entry": existing, "fetched": False}

    meta = fetch_sub_meta(name)
    entry = derive_yaml_entry(meta)
    final = upsert_sub_rule(name, entry, path=p)
    action = "fetched_new" if existing is None else "refetched_stale"
    return {"sub": name, "action": action, "entry": final, "fetched": True}
