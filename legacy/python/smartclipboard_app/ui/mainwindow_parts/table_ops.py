"""Compatibility shim for history table operations."""

from __future__ import annotations

from smartclipboard_app.features.history.view import (
    get_display_items_impl,
    load_data_impl,
    on_selection_changed_impl,
    populate_table_impl,
    show_empty_state_impl,
)

__all__ = [
    "get_display_items_impl",
    "load_data_impl",
    "on_selection_changed_impl",
    "populate_table_impl",
    "show_empty_state_impl",
]
