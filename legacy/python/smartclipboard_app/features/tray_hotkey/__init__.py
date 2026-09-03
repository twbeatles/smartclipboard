"""Tray/hotkey feature package."""

from .controller import TrayHotkeyController
from .services import (
    init_tray_impl,
    on_tray_activated_impl,
    paste_last_item_slot_impl,
    register_hotkeys_impl,
    show_window_from_tray_impl,
    toggle_mini_window_slot_impl,
)

__all__ = [
    "TrayHotkeyController",
    "init_tray_impl",
    "on_tray_activated_impl",
    "paste_last_item_slot_impl",
    "register_hotkeys_impl",
    "show_window_from_tray_impl",
    "toggle_mini_window_slot_impl",
]
