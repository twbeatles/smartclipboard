"""Compatibility shim for tray/hotkey operations."""

from __future__ import annotations

from smartclipboard_app.features.tray_hotkey.services import (
    init_tray_impl,
    on_tray_activated_impl,
    paste_last_item_slot_impl,
    register_hotkeys_impl,
    show_window_from_tray_impl,
    toggle_mini_window_slot_impl,
)

__all__ = [
    "init_tray_impl",
    "on_tray_activated_impl",
    "paste_last_item_slot_impl",
    "register_hotkeys_impl",
    "show_window_from_tray_impl",
    "toggle_mini_window_slot_impl",
]
