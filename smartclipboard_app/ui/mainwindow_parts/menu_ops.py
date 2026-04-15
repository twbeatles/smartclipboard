"""Compatibility shim for history menu operations."""

from __future__ import annotations

from smartclipboard_app.features.history.menu import (
    _sync_context_menu_selection,
    build_google_search_url,
    init_menu_impl,
    show_context_menu_impl,
)

__all__ = ["_sync_context_menu_selection", "build_google_search_url", "init_menu_impl", "show_context_menu_impl"]
