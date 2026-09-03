"""Compatibility shim for UI operations."""

from __future__ import annotations

from smartclipboard_app.features.shell_ui.view import event_filter_impl, handle_drop_event_impl, init_ui_impl

__all__ = ["event_filter_impl", "handle_drop_event_impl", "init_ui_impl"]
