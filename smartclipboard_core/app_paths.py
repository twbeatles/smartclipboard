from __future__ import annotations

import os
import sys


def get_app_directory() -> str:
    """Return the canonical directory for app data files."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(repo_root, "smartclipboard_app")


__all__ = ["get_app_directory"]
