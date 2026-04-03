"""Migration from the old openclaw growth pipeline.

Copies existing credentials to the new growth-cli identity format.
No re-authentication needed.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import stat
from pathlib import Path

from growth.config import IDENTITIES_DIR
from growth.identity.manager import Identity

log = logging.getLogger(__name__)

OLD_SECRETS_DIR = Path("~/.openclaw-growth-pipeline/secrets").expanduser()


def migrate_from_openclaw() -> list[str]:
    """Migrate all credentials from the old pipeline.

    Returns list of migrated identity names.
    """
    migrated = []

    # Twitter cookies
    old_twitter = OLD_SECRETS_DIR / "twitter_cookies.json"
    if old_twitter.exists():
        name = _migrate_twitter(old_twitter)
        if name:
            migrated.append(name)

    # Reddit session
    old_reddit = OLD_SECRETS_DIR / "reddit_session" / "storage_state.json"
    if old_reddit.exists():
        name = _migrate_reddit(old_reddit)
        if name:
            migrated.append(name)

    # HN cookie
    old_hn = OLD_SECRETS_DIR / "hn_session" / "hn_cookie.json"
    if old_hn.exists():
        name = _migrate_hn(old_hn)
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


def _migrate_reddit(old_path: Path) -> str | None:
    """Migrate Reddit Playwright session."""
    try:
        username = "openclaw_migrated"
        identity_dir = IDENTITIES_DIR / "reddit" / username
        session_dir = identity_dir / "session"
        session_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(old_path, session_dir / "storage_state.json")
        _secure_dir(identity_dir)
        _secure_dir(session_dir)

        Identity(
            name=f"reddit:{username}",
            platform="reddit",
            username=username,
            auth_method="browser",
            notes="Migrated from openclaw pipeline",
        ).save()

        log.info("Migrated Reddit session → reddit:%s", username)
        return f"reddit:{username}"
    except Exception as e:
        log.error("Failed to migrate Reddit: %s", e)
        return None


def _migrate_hn(old_path: Path) -> str | None:
    """Migrate HN cookie."""
    try:
        username = "openclaw_migrated"
        identity_dir = IDENTITIES_DIR / "hn" / username
        session_dir = identity_dir / "session"
        session_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(old_path, session_dir / "hn_cookie.json")
        _secure_dir(identity_dir)
        _secure_dir(session_dir)

        Identity(
            name=f"hn:{username}",
            platform="hn",
            username=username,
            auth_method="browser",
            notes="Migrated from openclaw pipeline",
        ).save()

        log.info("Migrated HN cookie → hn:%s", username)
        return f"hn:{username}"
    except Exception as e:
        log.error("Failed to migrate HN: %s", e)
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
