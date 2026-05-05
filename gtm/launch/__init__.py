"""Launch directory model and commands.

A "launch directory" is any directory containing a `.gtm-launch.yaml` marker.
See docs/PLAN-launch-workflow.md for the full convention.
"""

from gtm.launch.dir import LaunchDir, LAUNCH_MARKER, LaunchDirError
from gtm.launch.post import Post, PostError
from gtm.launch import draft  # re-export module for `from gtm.launch import draft`

__all__ = [
    "LaunchDir",
    "LAUNCH_MARKER",
    "LaunchDirError",
    "Post",
    "PostError",
    "draft",
]
