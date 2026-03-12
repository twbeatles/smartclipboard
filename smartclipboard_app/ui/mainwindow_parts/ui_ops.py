"""Extracted MainWindow helper operations."""

from __future__ import annotations

from .ui_dragdrop_ops import event_filter_body, handle_drop_event_body
from .ui_init_sections import build_main_ui


def init_ui_impl(self, HAS_QRCODE):
    return build_main_ui(self, HAS_QRCODE)


def event_filter_impl(self, source, event, fallback_event_filter):
    return event_filter_body(self, source, event, fallback_event_filter)


def handle_drop_event_impl(self, event, THEMES, logger) -> bool:
    return handle_drop_event_body(self, event, THEMES, logger)
