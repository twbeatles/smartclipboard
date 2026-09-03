"""Automation feature package for clipboard actions."""

from .manager import ClipboardActionManager
from .fetch_title import HAS_WEB, extract_first_url

__all__ = ["ClipboardActionManager", "HAS_WEB", "extract_first_url"]
