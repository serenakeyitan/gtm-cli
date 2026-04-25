"""Identity → browser-session-dir resolver.

Browser-based platform clients (Reddit, Twitter) need a directory containing
storage_state.json. Each Identity stores its session under its identity_dir.

This module is the single point of resolution: given an identity name (or None
for default), return the absolute path to the directory where the browser
client should read/write storage_state.json.
"""

from __future__ import annotations


from gtm.identity.manager import IdentityManager


def session_dir_for_identity(name: str | None, platform: str) -> str:
    """Resolve identity name to its browser session directory.

    Args:
        name: identity name like "reddit:Pale_Stand5217" or just "Pale_Stand5217".
              If None, uses the default identity for the platform.
        platform: "reddit" or "twitter".

    Returns:
        Absolute string path to the directory holding storage_state.json.

    Raises:
        ValueError: identity not found.
    """
    mgr = IdentityManager()
    identity = mgr.resolve_as_flag(name, platform)
    return str(identity.identity_dir)


def session_dir_for_name(name: str) -> str:
    """Resolve a name (with or without platform prefix) to its session directory.

    Used when the platform can be inferred from the name format.
    """
    mgr = IdentityManager()
    identity = mgr.get(name)
    return str(identity.identity_dir)
