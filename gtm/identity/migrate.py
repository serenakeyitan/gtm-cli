"""Migration from the old openclaw growth pipeline.

Copies existing credentials to the new gtm-cli identity format.
No re-authentication needed.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import stat
from pathlib import Path

from gtm.config import IDENTITIES_DIR
from gtm.identity.manager import Identity

log = logging.getLogger(__name__)

OLD_SECRETS_DIR = Path("~/.openclaw-growth-pipeline/secrets").expanduser()


def migrate_from_openclaw() -> list[str]:
    """Migrate all credentials from the old pipeline.

    Returns list of migrated identity names.

    Discovers per-account session dirs by scanning OLD_SECRETS_DIR for any
    directory named `reddit_session*` or `hn_session*`. Each is migrated as
    a separate identity. Username is taken from the suffix after `_session_`,
    or "openclaw_migrated" if none.
    """
    migrated = []

    # Twitter cookies (single file, single account)
    old_twitter = OLD_SECRETS_DIR / "twitter_cookies.json"
    if old_twitter.exists():
        name = _migrate_twitter(old_twitter)
        if name:
            migrated.append(name)

    # Reddit sessions (one or more dirs: reddit_session, reddit_session_pale, ...)
    if OLD_SECRETS_DIR.exists():
        for d in sorted(OLD_SECRETS_DIR.iterdir()):
            if not d.is_dir() or not d.name.startswith("reddit_session"):
                continue
            storage = d / "storage_state.json"
            if not storage.exists():
                continue
            suffix = d.name.removeprefix("reddit_session").lstrip("_")
            username = suffix or "openclaw_migrated"
            name = _migrate_reddit(storage, username=username)
            if name:
                migrated.append(name)

    # HN sessions (same shape)
    if OLD_SECRETS_DIR.exists():
        for d in sorted(OLD_SECRETS_DIR.iterdir()):
            if not d.is_dir() or not d.name.startswith("hn_session"):
                continue
            cookie = d / "hn_cookie.json"
            if not cookie.exists():
                continue
            suffix = d.name.removeprefix("hn_session").lstrip("_")
            username = suffix or "openclaw_migrated"
            name = _migrate_hn(cookie, username=username)
            if name:
                migrated.append(name)

    return migrated


def _migrate_twitter(old_path: Path) -> str | None:
    """Migrate Twitter cookies."""
    try:
        username = "openclaw_migrated"
        # Try to extract username from cookies
        with open(old_path) as f:
            cookies = json.load(f)
        # twid contains user ID but not username — use generic name
        if isinstance(cookies, dict) and "twid" in cookies:
            import urllib.parse
            twid = urllib.parse.unquote(cookies.get("twid", ""))
            username = f"twitter_user_{twid.replace('u=', '')[:8]}"

        identity_dir = IDENTITIES_DIR / "twitter" / username
        identity_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(old_path, identity_dir / "cookies.json")
        _secure_dir(identity_dir)

        Identity(
            name=f"twitter:{username}",
            platform="twitter",
            username=username,
            auth_method="cookies_manual",
            notes="Migrated from openclaw pipeline",
        ).save()

        log.info("Migrated Twitter cookies → twitter:%s", username)
        return f"twitter:{username}"
    except Exception as e:
        log.error("Failed to migrate Twitter: %s", e)
        return None


def _migrate_reddit(old_path: Path, username: str = "openclaw_migrated") -> str | None:
    """Migrate Reddit Playwright session.

    storage_state.json is placed directly under identity_dir (not session/), to
    match what gtm.platforms.reddit.client.PlaywrightRedditClient reads.
    """
    try:
        identity_dir = IDENTITIES_DIR / "reddit" / username
        identity_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(old_path, identity_dir / "storage_state.json")
        _secure_dir(identity_dir)

        Identity(
            name=f"reddit:{username}",
            platform="reddit",
            username=username,
            auth_method="browser",
            notes=f"Migrated from openclaw pipeline ({old_path.parent.name})",
        ).save()

        log.info("Migrated Reddit session → reddit:%s", username)
        return f"reddit:{username}"
    except Exception as e:
        log.error("Failed to migrate Reddit %s: %s", username, e)
        return None


def _migrate_hn(old_path: Path, username: str = "openclaw_migrated") -> str | None:
    """Migrate HN cookie. Stored directly under identity_dir."""
    try:
        identity_dir = IDENTITIES_DIR / "hn" / username
        identity_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(old_path, identity_dir / "hn_cookie.json")
        _secure_dir(identity_dir)

        Identity(
            name=f"hn:{username}",
            platform="hn",
            username=username,
            auth_method="browser",
            notes=f"Migrated from openclaw pipeline ({old_path.parent.name})",
        ).save()

        log.info("Migrated HN cookie → hn:%s", username)
        return f"hn:{username}"
    except Exception as e:
        log.error("Failed to migrate HN %s: %s", username, e)
        return None


def _secure_dir(d: Path) -> None:
    """Set secure permissions on a directory and its files."""
    try:
        os.chmod(d, stat.S_IRWXU)
        for f in d.iterdir():
            if f.is_file():
                os.chmod(f, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
