"""Shared preflight gate for any reddit submit path.

Both `gtm reddit submit` and `gtm post submit` (when CP1-8 land) must call
this before letting a post go live. The gate:

  1. Runs preflight (which auto-fetches sub rules via CP9 if missing/stale).
  2. Always echoes the sub's notes — operator should see "flair required",
     "10% rule", "permanent_skip", etc. before the post lands.
  3. Returns a verdict + an `allowed` boolean. PASS allows. BORDERLINE
     allows unless `strict=True`. FAIL blocks unless `override_reason` is set
     (which gets recorded for later audit).

Pure logic. CLI prints + sys.exit live in cli.py. Tests can call this
directly with stubbed preflight() via dependency injection.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from .preflight import preflight as default_preflight


GateResult = dict[str, Any]


def evaluate_submit(
    identity: str,
    sub: str,
    *,
    strict: bool = False,
    override_reason: Optional[str] = None,
    auto_fetch: bool = True,
    preflight_fn: Callable[..., dict[str, Any]] = default_preflight,
) -> GateResult:
    """Decide whether a submit should proceed.

    Returns:
        {
          "allowed": bool,
          "verdict": "PASS" | "BORDERLINE" | "FAIL",
          "reason": short human string,
          "preflight": <the full preflight result dict>,
          "override_used": bool,
          "override_reason": str | None,
        }

    The override field is only honored when verdict is FAIL — it lets a human
    operator bypass with a written justification that the caller should
    record in the post's frontmatter / dashboard.
    """
    pf = preflight_fn(identity, sub, auto_fetch=auto_fetch)
    verdict = pf["verdict"]
    permanent_skip = pf.get("permanent_skip", False)

    if permanent_skip:
        if override_reason:
            return _result(True, verdict, "permanent_skip overridden", pf,
                           override_used=True, override_reason=override_reason)
        return _result(False, verdict,
                       f"r/{sub} is marked permanent_skip in rules", pf)

    if verdict == "PASS":
        return _result(True, verdict, "preflight PASS", pf)

    if verdict == "BORDERLINE":
        if strict:
            if override_reason:
                return _result(True, verdict, "borderline overridden under strict",
                               pf, override_used=True, override_reason=override_reason)
            return _result(False, verdict,
                           "BORDERLINE blocked by --strict (use --override)", pf)
        return _result(True, verdict, "borderline accepted (non-strict)", pf)

    # verdict == "FAIL"
    if override_reason:
        return _result(True, verdict, "FAIL overridden", pf,
                       override_used=True, override_reason=override_reason)
    failing = [r for r in pf.get("reasons", []) if r.get("status") == "fail"]
    detail = "; ".join(r.get("detail", "?") for r in failing) or "preflight FAIL"
    return _result(False, verdict, detail, pf)


def _result(allowed: bool, verdict: str, reason: str,
            preflight_result: dict[str, Any], *,
            override_used: bool = False,
            override_reason: Optional[str] = None) -> GateResult:
    return {
        "allowed": allowed,
        "verdict": verdict,
        "reason": reason,
        "preflight": preflight_result,
        "override_used": override_used,
        "override_reason": override_reason,
    }


def format_gate_summary(result: GateResult) -> list[str]:
    """Render a gate result as printable lines for the CLI."""
    pf = result["preflight"]
    sub = pf.get("sub", "?")
    lines = [f"── preflight gate for r/{sub} ──"]

    fa = pf.get("fetch_action")
    if fa and fa != "not_attempted":
        lines.append(f"  fetch: {fa}")

    notes = pf.get("notes")
    if notes:
        lines.append(f"  notes: {notes}")
    if pf.get("permanent_skip"):
        lines.append("  permanent_skip: TRUE")

    for r in pf.get("reasons", []):
        if r.get("status") in ("fail", "borderline"):
            lines.append(f"  {r['status']}: {r.get('detail', '')}")

    verdict = result["verdict"]
    lines.append(f"  verdict: {verdict}")
    if result["override_used"]:
        lines.append(f"  override: \"{result['override_reason']}\"")
    lines.append(f"  decision: {'ALLOW' if result['allowed'] else 'BLOCK'} — {result['reason']}")
    return lines
