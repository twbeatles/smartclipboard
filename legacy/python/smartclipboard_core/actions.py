"""Compatibility facade for clipboard automation."""

from __future__ import annotations

import socket

from .automation.fetch_title import HAS_WEB, extract_first_url, fetch_title_logic, requests
from .automation.formatters import format_email, format_phone, transform_text
from .automation.manager import ClipboardActionManager as _ClipboardActionManager


class ClipboardActionManager(_ClipboardActionManager):
    """Public compatibility class that preserves legacy helper entrypoints."""

    format_phone = staticmethod(format_phone)
    format_email = staticmethod(format_email)
    transform_text = staticmethod(transform_text)
    _fetch_title_logic = staticmethod(fetch_title_logic)


__all__ = [
    "ClipboardActionManager",
    "HAS_WEB",
    "extract_first_url",
    "fetch_title_logic",
    "requests",
    "socket",
]
