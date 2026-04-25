"""Warm-up list registry — handles to ping right before a launch.

A "warm-up" handle is someone who agreed to engage with a launch within
the first algorithmic window (first 30-60 min on Twitter, first hour on
Reddit). Stored per launch slug so multiple launches can be tracked.

Layout::

    ~/.config/gtm/warmup.json
    {
      "first-tree": [
        {"handle": "alice", "platform": "twitter", "added_at": "...",
         "notes": "DM'd, said yes"}
      ]
    }
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from gtm.config import CONFIG_DIR

REGISTRY_PATH = CONFIG_DIR / "warmup.json"


def _load() -> dict[str, list[dict[str, Any]]]:
    if not REGISTRY_PATH.exists():
        return {}
    try:
        return json.loads(REGISTRY_PATH.read_text())
    except json.JSONDecodeError:
        return {}


def _save(data: dict[str, list[dict[str, Any]]]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(data, indent=2))


def list_for_launch(launch: str) -> list[dict[str, Any]]:
    return _load().get(launch, [])


def add(launch: str, handle: str, platform: str, notes: str = "") -> None:
    data = _load()
    bucket = data.setdefault(launch, [])
    for entry in bucket:
        if entry["handle"] == handle and entry["platform"] == platform:
            entry["notes"] = notes or entry.get("notes", "")
            entry["added_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            _save(data)
            return
    bucket.append({
        "handle": handle,
        "platform": platform,
        "added_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "notes": notes,
    })
    _save(data)


def remove(launch: str, handle: str, platform: str) -> bool:
    data = _load()
    bucket = data.get(launch, [])
    new_bucket = [e for e in bucket if not (e["handle"] == handle and e["platform"] == platform)]
    if len(new_bucket) == len(bucket):
        return False
    if new_bucket:
        data[launch] = new_bucket
    else:
        del data[launch]
    _save(data)
    return True


def all_launches() -> list[str]:
    return list(_load().keys())
