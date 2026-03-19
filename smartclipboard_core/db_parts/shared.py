from __future__ import annotations

import logging
import os


def get_app_directory() -> str:
    """Return base directory for app data and database files."""
    import sys

    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    # In source mode this file lives in smartclipboard_core/db_parts/, so use two parents.
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


APP_DIR = get_app_directory()
DEFAULT_MAX_HISTORY = 100
CLEANUP_INTERVAL = 10
FILTER_TAG_MAP = {
    "?? ???": "TEXT",
    "??? ???": "IMAGE",
    "?? ??": "LINK",
    "?? ??": "CODE",
    "?? ??": "COLOR",
}

logger = logging.getLogger(__name__)


def history_order_by(alias: str = "") -> str:
    prefix = f"{alias}." if alias else ""
    return (
        f"ORDER BY {prefix}pinned DESC, {prefix}pin_order ASC, "
        f"{prefix}timestamp DESC, {prefix}id DESC"
    )
