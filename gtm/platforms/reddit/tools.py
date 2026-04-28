"""Reddit MCP tools — for agents via Claude SDK."""

from __future__ import annotations

import json

from claude_agent_sdk import tool
import httpx


@tool("reddit_search_subreddits", "Search for subreddits", {"query": str})
async def reddit_search_subreddits(args):
    query = args.get("query", "")
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"https://www.reddit.com/subreddits/search.json?q={query}&limit=10",
                              headers={"User-Agent": "gtm-cli/0.1"})
        return {"content": [{"type": "text", "text": json.dumps([s["data"] for s in resp.json().get("data", {}).get("children", [])], indent=2)}]}


@tool("reddit_top_posts", "Get top posts from a subreddit", {"subreddit": str, "count": int})
async def reddit_top_posts(args):
    subreddit = args["subreddit"]
    count = args.get("count", 10)
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"https://www.reddit.com/r/{subreddit}/top.json?t=week&limit={count}",
                              headers={"User-Agent": "gtm-cli/0.1"})
        return {"content": [{"type": "text", "text": json.dumps([p["data"] for p in resp.json().get("data", {}).get("children", [])], indent=2)}]}


@tool("reddit_subreddit_rules", "Get subreddit rules", {"subreddit": str})
async def reddit_subreddit_rules(args):
    subreddit = args["subreddit"]
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"https://www.reddit.com/r/{subreddit}/about/rules.json",
                              headers={"User-Agent": "gtm-cli/0.1"})
        return {"content": [{"type": "text", "text": json.dumps(resp.json(), indent=2)}]}


@tool("reddit_user_posts", "Get a user's recent posts", {"username": str})
async def reddit_user_posts(args):
    username = args["username"]
    async with httpx.AsyncClient() as http:
        resp = await http.get(f"https://www.reddit.com/user/{username}/submitted.json?limit=10",
                              headers={"User-Agent": "gtm-cli/0.1"})
        return {"content": [{"type": "text", "text": json.dumps([p["data"] for p in resp.json().get("data", {}).get("children", [])], indent=2)}]}


@tool("reddit_check_post", "Check a Reddit post's score and status", {"url": str})
async def reddit_check_post(args):
    url = args["url"]
    async with httpx.AsyncClient() as http:
        resp = await http.get(url.rstrip("/") + ".json", headers={"User-Agent": "gtm-cli/0.1"}, follow_redirects=True)
        data = resp.json()
        if isinstance(data, list) and data:
            post = data[0]["data"]["children"][0]["data"]
            return {"content": [{"type": "text", "text": json.dumps({"score": post.get("score"), "comments": post.get("num_comments")}, indent=2)}]}
        return {"content": [{"type": "text", "text": "{}"}]}


@tool(
    "reddit_browser_submit",
    (
        "Post to a subreddit using browser-based API. Supports text posts "
        "(kind='self') and link posts (kind='link'). Pass `identity` to choose "
        "which registered account posts (resolved via IdentityManager); omit "
        "to use the default reddit identity. Always wait at least 15 seconds "
        "between consecutive posts."
    ),
    {
        "subreddit": str,
        "title": str,
        "selftext": str,
        "url": str,
        "kind": str,
        "identity": str,
    },
)
async def reddit_browser_submit(args):
    from gtm.platforms.reddit.client import (
        get_reddit_browser_client,
        get_reddit_browser_client_for_identity,
    )

    identity = args.get("identity") or ""
    try:
        client = (
            get_reddit_browser_client_for_identity(identity)
            if identity
            else get_reddit_browser_client()
        )
        result = await client.submit_api_post(
            subreddit=args["subreddit"],
            title=args["title"],
            selftext=args.get("selftext", ""),
            url=args.get("url", ""),
            kind=args.get("kind", "self"),
        )
        if identity:
            result["identity"] = identity
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}


@tool("reddit_browser_check_post", "Check a Reddit post via browser", {"url": str})
async def reddit_browser_check_post(args):
    return await reddit_check_post(args)


@tool("reddit_browser_subreddit_rules", "Get subreddit rules via browser", {"subreddit": str})
async def reddit_browser_subreddit_rules(args):
    return await reddit_subreddit_rules(args)


# ── Cross-post anti-spam lint ────────────────────────────────────────

_OPENER_ARCHETYPES = {
    "personal_pain": ("i kept hitting", "i was running into", "i ran into",
                      "i kept running", "the problem i kept", "i hit"),
    "observation": ("something nobody talks about", "nobody talks about",
                    "everyone has this problem", "this is one of those"),
    "experiment": ("quick experiment", "tried using", "ran an experiment",
                   "did a small experiment", "tried doing"),
    "announcement": ("shipping this", "shipped this", "just shipped",
                     "released today", "launching", "going public",
                     "i built", "i made", "i created", "i wrote",
                     "i open sourced", "i open-sourced", "i just made"),
    "third_person": ("an interesting", "stumbled across", "documentation drift is",
                     "this problem", "there's an interesting"),
    "question": ("anyone else", "has anyone", "how do you", "what do you",
                 "is anyone running"),
}


def _classify_opener(text: str) -> str:
    """Pick the opener archetype for a post body. Returns 'unknown' if none match."""
    head = text.strip().lower()[:120]
    for archetype, prefixes in _OPENER_ARCHETYPES.items():
        for p in prefixes:
            if p in head:
                return archetype
    return "unknown"


def _longest_common_substring_len(a: str, b: str) -> tuple[int, str]:
    """Word-level longest common substring length and the substring itself."""
    aw = a.lower().split()
    bw = b.lower().split()
    if not aw or not bw:
        return 0, ""
    best_len = 0
    best_run: list[str] = []
    n, m = len(aw), len(bw)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if aw[i - 1] == bw[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
                if dp[i][j] > best_len:
                    best_len = dp[i][j]
                    best_run = aw[i - best_len:i]
    return best_len, " ".join(best_run)


@tool(
    "reddit_cross_post_lint",
    (
        "Lint a batch of cross-posts for anti-spam violations BEFORE submitting. "
        "Pass a list of {subreddit, title, body} drafts. Returns violations: "
        "shared opener archetype, repeated phrasing (8+ identical words in a row), "
        "identical title. The Promoter agent MUST run this and fix all violations "
        "before calling submit."
    ),
    {"posts": list},
)
async def reddit_cross_post_lint(args):
    try:
        posts = args.get("posts", [])
        if len(posts) < 2:
            return {"content": [{"type": "text", "text": json.dumps({
                "pass": True,
                "violations": [],
                "note": "fewer than 2 posts, no cross-comparison needed",
            })}]}

        violations: list[dict] = []

        archetypes = [(p.get("subreddit", f"#{i}"), _classify_opener(p.get("body", "")))
                      for i, p in enumerate(posts)]
        seen_archetypes: dict[str, list[str]] = {}
        for sub, arch in archetypes:
            if arch == "unknown":
                continue
            seen_archetypes.setdefault(arch, []).append(sub)
        for arch, subs in seen_archetypes.items():
            if len(subs) > 1:
                violations.append({
                    "kind": "duplicate_opener_archetype",
                    "archetype": arch,
                    "affected_subs": subs,
                    "fix": f"rewrite the opener of all but one of: {subs} to use a different archetype",
                })

        for i in range(len(posts)):
            for j in range(i + 1, len(posts)):
                a_body = posts[i].get("body", "")
                b_body = posts[j].get("body", "")
                run_len, run_text = _longest_common_substring_len(a_body, b_body)
                if run_len >= 8:
                    violations.append({
                        "kind": "long_repeated_phrase",
                        "between": [posts[i].get("subreddit", f"#{i}"),
                                    posts[j].get("subreddit", f"#{j}")],
                        "word_count": run_len,
                        "phrase": run_text[:200],
                        "fix": "rewrite one side to break the repetition",
                    })

        title_seen: dict[str, list[str]] = {}
        for p in posts:
            t = (p.get("title", "") or "").strip().lower()
            if t:
                title_seen.setdefault(t, []).append(p.get("subreddit", "?"))
        for t, subs in title_seen.items():
            if len(subs) > 1:
                violations.append({
                    "kind": "identical_title",
                    "title": t,
                    "affected_subs": subs,
                    "fix": "every cross-post must have a distinct title",
                })

        return {"content": [{"type": "text", "text": json.dumps({
            "pass": len(violations) == 0,
            "violations": violations,
            "post_count": len(posts),
        }, indent=2)}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}


# ── Multi-identity routing tools ─────────────────────────────────────


@tool(
    "reddit_list_identities",
    "List Reddit identities registered via `gtm auth reddit`. Returns names + status.",
    {},
)
async def reddit_list_identities(args):
    try:
        from gtm.identity.manager import IdentityManager
        identities = IdentityManager().list_platform("reddit")
        return {"content": [{"type": "text", "text": json.dumps({
            "identities": [
                {"name": i.name, "username": i.username, "status": i.status,
                 "role": i.role, "notes": i.notes}
                for i in identities
            ],
        }, indent=2)}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}


@tool(
    "reddit_identity_affinity",
    (
        "Show identity×subreddit history (post count, avg score, last post date, "
        "removal flag) from past runs. Use to pick the safest identity for a sub. "
        "Pass optional `subreddit` to filter to one sub."
    ),
    {"subreddit": str},
)
async def reddit_identity_affinity(args):
    try:
        from gtm.modules.filters.identity_affinity import compute_affinity
        sub = (args.get("subreddit") or "").strip().lower()
        table = compute_affinity()
        if sub:
            filtered = {a: {s: v for s, v in subs.items() if s.lower() == sub}
                        for a, subs in table.items()}
            table = {a: subs for a, subs in filtered.items() if subs}
        return {"content": [{"type": "text", "text": json.dumps(table, indent=2)}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}


@tool(
    "reddit_preflight",
    (
        "Preflight a (reddit identity, sub) pair against per-sub karma/age "
        "rules from gtm/data/reddit_sub_rules.yaml. Returns "
        "{verdict: PASS|BORDERLINE|FAIL, reasons, notes, permanent_skip, stats}. "
        "FAIL means do NOT post from this identity to this sub. BORDERLINE means "
        "post is allowed but the identity barely qualifies — log a warning."
    ),
    {"identity": str, "sub": str},
)
async def reddit_preflight(args):
    try:
        from gtm.modules.preflight import preflight as _preflight, PreflightError
        identity = (args.get("identity") or "").strip()
        sub = (args.get("sub") or "").strip()
        if not identity or not sub:
            return {"content": [{"type": "text", "text": "identity and sub required"}],
                    "isError": True}
        try:
            result = _preflight(identity, sub)
        except PreflightError as e:
            return {"content": [{"type": "text", "text": json.dumps({
                "error": str(e),
                "identity": identity,
                "sub": sub,
            })}], "isError": True}
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}


def filter_identities_by_preflight(
    sub: str,
    candidates: list[str],
    *,
    rules: dict | None = None,
) -> tuple[list[str], list[dict]]:
    """Drop FAIL identities from candidates; flag BORDERLINE in returned log.

    Returns ``(safe_candidates, log)`` where ``log`` is a list of preflight
    result dicts (one per candidate, including FAILs that were dropped).
    Used by the Promoter agent's Phase C before picking an identity.
    """
    from gtm.modules.preflight import preflight as _preflight, PreflightError

    safe: list[str] = []
    log: list[dict] = []
    for ident in candidates:
        try:
            result = _preflight(ident, sub, rules=rules)
        except PreflightError as e:
            log.append({"identity": ident, "sub": sub, "verdict": "ERROR",
                        "error": str(e)})
            # On fetch error, leave the identity in the candidate pool but
            # flag it — we don't want a transient 429 to nuke routing.
            safe.append(ident)
            continue
        log.append(result)
        if result["verdict"] != "FAIL":
            safe.append(ident)
    return safe, log


@tool(
    "reddit_pick_identity_for_sub",
    (
        "Recommend the best registered identity for posting to a subreddit, "
        "based on affinity. Skips identities with prior removals in that sub. "
        "Returns a single identity name."
    ),
    {"subreddit": str},
)
async def reddit_pick_identity_for_sub(args):
    try:
        from gtm.identity.manager import IdentityManager
        from gtm.modules.filters.identity_affinity import (
            compute_affinity, best_identity_for_sub,
        )
        sub = (args.get("subreddit") or "").strip().lower()
        if not sub:
            return {"content": [{"type": "text", "text": "subreddit required"}],
                    "isError": True}
        candidates = [i.name for i in IdentityManager().list_platform("reddit")]
        if not candidates:
            return {"content": [{"type": "text", "text": json.dumps({
                "error": "no reddit identities registered",
                "fix": "gtm auth reddit",
            })}]}
        pick = best_identity_for_sub(sub, candidates, compute_affinity())
        return {"content": [{"type": "text", "text": json.dumps({
            "subreddit": sub,
            "recommended_identity": pick,
            "candidates": candidates,
        }, indent=2)}]}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}
