"""Reddit preflight: check (identity, subreddit) compatibility against per-sub rules.

Workflow:
  1. Fetch the identity's public karma + age via reddit's about.json endpoint.
  2. Look up the sub's rule from gtm/data/reddit_sub_rules.yaml.
  3. Evaluate stats against the rule and return a verdict:
       PASS       — comfortably above all minimums
       BORDERLINE — passes by <=20% margin on any rule
       FAIL       — at least one rule violated

Used by `gtm reddit preflight` and by the Promoter agent's Phase C to drop
under-qualified identities before they burn a post slot.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml

DEFAULT_RULES_PATH = Path(__file__).parent.parent / "data" / "reddit_sub_rules.yaml"

_USER_AGENT = "gtm-cli-preflight/0.1 (by u/gtm-cli)"
_TIMEOUT = 10


class PreflightError(Exception):
    """Raised when we can't fetch user stats (404, timeout, network)."""


# ── Reddit user fetch ─────────────────────────────────────────────────


def fetch_reddit_user(username: str) -> dict[str, Any]:
    """Fetch public karma + age for a reddit user.

    Returns ``{link_karma, comment_karma, total_karma, age_days, verified}``.
    Raises PreflightError on 404, timeout, or malformed payload.
    """
    name = username.strip().lstrip("u/").lstrip("/")
    url = f"https://www.reddit.com/user/{name}/about.json"
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise PreflightError(f"reddit returned HTTP {e.code} for u/{name}") from e
    except urllib.error.URLError as e:
        raise PreflightError(f"network error fetching u/{name}: {e.reason}") from e
    except (TimeoutError, OSError) as e:
        raise PreflightError(f"timeout fetching u/{name}: {e}") from e
    except json.JSONDecodeError as e:
        raise PreflightError(f"bad JSON for u/{name}: {e}") from e

    data = payload.get("data") or {}
    if not data:
        raise PreflightError(f"no data field in payload for u/{name}")

    link_karma = int(data.get("link_karma", 0))
    comment_karma = int(data.get("comment_karma", 0))
    total_karma = int(data.get("total_karma", link_karma + comment_karma))
    created_utc = float(data.get("created_utc", 0))
    age_days = int((time.time() - created_utc) / 86400) if created_utc else 0
    verified = bool(data.get("verified", False))

    return {
        "username": name,
        "link_karma": link_karma,
        "comment_karma": comment_karma,
        "total_karma": total_karma,
        "age_days": age_days,
        "verified": verified,
    }


# ── Rules loading ─────────────────────────────────────────────────────


def load_sub_rules(path: Path | None = None) -> dict[str, Any]:
    """Load reddit_sub_rules.yaml. Returns the parsed dict."""
    rules_path = Path(path) if path else DEFAULT_RULES_PATH
    if not rules_path.exists():
        raise PreflightError(f"sub rules file not found: {rules_path}")
    with rules_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def _lookup_sub_rule(sub: str, rules: dict[str, Any]) -> dict[str, Any] | None:
    """Case-insensitive sub lookup. Strips r/ prefix."""
    name = sub.strip().lstrip("r/").lstrip("/")
    subs = rules.get("subs") or {}
    for key, val in subs.items():
        if key.lower() == name.lower():
            return val or {}
    return None


# ── Verdict evaluation ────────────────────────────────────────────────

# Rules of the form (rule_key_in_yaml, stats_key)
_NUMERIC_RULES = (
    ("min_total_karma", "total_karma"),
    ("min_link_karma", "link_karma"),
    ("min_comment_karma", "comment_karma"),
    ("min_age_days", "age_days"),
)

_BORDERLINE_MARGIN = 0.20  # within 20% over the floor counts as borderline


def evaluate(stats: dict[str, Any], rule: dict[str, Any]) -> dict[str, Any]:
    """Evaluate stats against a single sub rule.

    Returns ``{verdict, reasons}``. Reasons is a list of dicts describing each
    rule check. ``verdict`` is one of PASS / BORDERLINE / FAIL.
    """
    reasons: list[dict[str, Any]] = []
    has_fail = False
    has_borderline = False

    rule = rule or {}

    for rule_key, stat_key in _NUMERIC_RULES:
        floor = rule.get(rule_key)
        if floor is None:
            continue
        actual = int(stats.get(stat_key, 0))
        floor = int(floor)
        if actual < floor:
            has_fail = True
            reasons.append({
                "rule": rule_key,
                "floor": floor,
                "actual": actual,
                "status": "fail",
                "detail": f"{stat_key}={actual} < required {floor}",
            })
            continue
        # Pass — measure margin to detect borderline.
        if floor > 0:
            margin = (actual - floor) / floor
        else:
            margin = float("inf")
        if margin <= _BORDERLINE_MARGIN:
            has_borderline = True
            pct = int(round(margin * 100))
            reasons.append({
                "rule": rule_key,
                "floor": floor,
                "actual": actual,
                "margin_pct": pct,
                "status": "borderline",
                "detail": f"{stat_key}={actual} only {pct}% over floor {floor}",
            })
        else:
            pct = int(round(margin * 100))
            reasons.append({
                "rule": rule_key,
                "floor": floor,
                "actual": actual,
                "margin_pct": pct,
                "status": "pass",
                "detail": f"{stat_key}={actual} comfortably over floor {floor}",
            })

    if has_fail:
        verdict = "FAIL"
    elif has_borderline:
        verdict = "BORDERLINE"
    else:
        verdict = "PASS"

    return {"verdict": verdict, "reasons": reasons}


# ── Top-level entry point ─────────────────────────────────────────────


def preflight(
    identity: str,
    sub: str,
    *,
    rules: dict[str, Any] | None = None,
    stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Preflight an (identity, sub) pair.

    Returns ``{identity, sub, stats, verdict, reasons, notes, permanent_skip,
    rule_found}``. ``stats`` may be passed in to skip the network fetch
    (useful for tests).
    """
    if rules is None:
        rules = load_sub_rules()
    if stats is None:
        stats = fetch_reddit_user(identity)

    rule = _lookup_sub_rule(sub, rules)
    if rule is None:
        # No rule for this sub → treat as PASS but flag rule_found=False.
        return {
            "identity": identity,
            "sub": sub,
            "stats": stats,
            "verdict": "PASS",
            "reasons": [{"status": "pass", "detail": f"no rule on file for r/{sub}"}],
            "notes": None,
            "permanent_skip": False,
            "rule_found": False,
        }

    eval_result = evaluate(stats, rule)
    permanent_skip = bool(rule.get("permanent_skip", False))
    verdict = eval_result["verdict"]
    if permanent_skip and verdict != "FAIL":
        # Permanent skip overrides — treat as FAIL with explicit reason.
        eval_result["reasons"].append({
            "rule": "permanent_skip",
            "status": "fail",
            "detail": "sub is marked permanent_skip in rules file",
        })
        verdict = "FAIL"

    return {
        "identity": identity,
        "sub": sub,
        "stats": stats,
        "verdict": verdict,
        "reasons": eval_result["reasons"],
        "notes": rule.get("notes"),
        "permanent_skip": permanent_skip,
        "rule_found": True,
    }
