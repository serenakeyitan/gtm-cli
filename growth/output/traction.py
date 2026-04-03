"""Traction tracker — fetch live engagement data for posted content.

Reads posts from the output repo, then hits each platform's public API
to get current engagement metrics (likes, comments, score, views).

No auth needed for reading public engagement data.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from growth.config import GrowthConfig

log = logging.getLogger(__name__)


async def fetch_twitter_engagement(tweet_id: str, identity_dir: Path | None = None) -> dict[str, Any]:
    """Fetch engagement for a tweet. Uses twikit if identity available, else returns cached."""
    if not identity_dir:
        return {"error": "No Twitter identity for live fetch"}

    try:
        from growth.platforms.twitter.client import TwitterClient
        cookie_path = identity_dir / "cookies.json"
        if not cookie_path.exists():
            return {"error": "No cookies"}

        client = TwitterClient(cookie_path=cookie_path)
        tweet = await client.get_tweet(tweet_id)
        return {
            "platform": "twitter",
            "post_id": tweet_id,
            "likes": tweet.get("favorite_count", 0),
            "retweets": tweet.get("retweet_count", 0),
            "replies": tweet.get("reply_count", 0),
            "views": tweet.get("view_count", 0),
            "fetched_at": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"platform": "twitter", "post_id": tweet_id, "error": str(e)}


async def fetch_reddit_engagement(post_url: str) -> dict[str, Any]:
    """Fetch engagement for a Reddit post via public JSON API."""
    try:
        # Convert to .json endpoint
        json_url = post_url.rstrip("/") + ".json"
        if "reddit.com" not in json_url:
            json_url = f"https://www.reddit.com{post_url}.json"

        async with httpx.AsyncClient() as http:
            resp = await http.get(json_url, headers={"User-Agent": "growth-cli/0.1"}, follow_redirects=True)
            data = resp.json()

        if isinstance(data, list) and len(data) > 0:
            post_data = data[0]["data"]["children"][0]["data"]
            return {
                "platform": "reddit",
                "post_id": post_data.get("id", ""),
                "score": post_data.get("score", 0),
                "upvote_ratio": post_data.get("upvote_ratio", 0),
                "comments": post_data.get("num_comments", 0),
                "url": post_url,
                "fetched_at": datetime.now().isoformat(),
            }
        return {"platform": "reddit", "url": post_url, "error": "Could not parse response"}
    except Exception as e:
        return {"platform": "reddit", "url": post_url, "error": str(e)}


async def fetch_hn_engagement(item_id: str) -> dict[str, Any]:
    """Fetch engagement for an HN post via Algolia API."""
    try:
        async with httpx.AsyncClient() as http:
            resp = await http.get(f"https://hn.algolia.com/api/v1/items/{item_id}")
            data = resp.json()

        return {
            "platform": "hn",
            "post_id": item_id,
            "points": data.get("points", 0),
            "comments": len(data.get("children", [])),
            "title": data.get("title", ""),
            "url": f"https://news.ycombinator.com/item?id={item_id}",
            "fetched_at": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"platform": "hn", "post_id": item_id, "error": str(e)}


async def fetch_all_traction(refresh: bool = True) -> list[dict[str, Any]]:
    """Fetch traction data for all posts in the output repo.

    Reads posted/*.md files, extracts platform/post_id/url,
    then fetches live engagement data from each platform.
    """
    import yaml
    from growth.config import IDENTITIES_DIR

    output_dir = Path(GrowthConfig.load().output_dir).expanduser()
    posted_dir = output_dir / "posted"

    if not posted_dir.exists():
        return []

    results = []

    for f in sorted(posted_dir.glob("*.md"), reverse=True):
        text = f.read_text()
        if not text.startswith("---"):
            continue

        parts = text.split("---", 2)
        if len(parts) < 3:
            continue

        try:
            meta = yaml.safe_load(parts[1])
        except Exception:
            continue

        platform = meta.get("platform", "")
        post_id = meta.get("post_id", "")
        url = meta.get("url", "")
        content = parts[2].strip()[:80]
        posted_at = meta.get("posted_at", "")

        entry = {
            "platform": platform,
            "post_id": post_id,
            "url": url,
            "content": content,
            "posted_at": posted_at,
            "file": f.name,
        }

        if refresh:
            if platform == "twitter" and post_id:
                # Find a Twitter identity for fetching
                twitter_dir = IDENTITIES_DIR / "twitter"
                identity_dir = None
                if twitter_dir.exists():
                    for d in twitter_dir.iterdir():
                        if d.is_dir() and not d.name.startswith("_"):
                            identity_dir = d
                            break
                engagement = await fetch_twitter_engagement(post_id, identity_dir)
                entry.update(engagement)

            elif platform == "reddit" and url:
                engagement = await fetch_reddit_engagement(url)
                entry.update(engagement)

            elif platform == "hn" and post_id:
                engagement = await fetch_hn_engagement(post_id)
                entry.update(engagement)

        results.append(entry)

    # Save snapshot to output repo
    if refresh and results:
        traction_dir = output_dir / "traction"
        traction_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = traction_dir / f"{datetime.now().strftime('%Y-%m-%d_%H%M')}.json"
        with open(snapshot_path, "w") as fp:
            json.dump(results, fp, indent=2)

    return results
