"""Tray/hotkey feature controller."""

from __future__ import annotations

from smartclipboard_app.features.shared.controller import FeatureController

from .services import (
    init_tray_impl,
    on_tray_activated_impl,
    paste_last_item_slot_impl,
    register_hotkeys_impl,
    show_window_from_tray_impl,
    toggle_mini_window_slot_impl,
)


class TrayHotkeyController(FeatureController):
    def register_hotkeys(self, logger, keyboard, json, default_hotkeys, hotkeys_override=None, persist=False):
        self.sync()
        return register_hotkeys_impl(
            self.window,
            logger,
            keyboard,
            json,
            default_hotkeys,
            hotkeys_override=hotkeys_override,
            persist=persist,
        )

    def toggle_mini_window_slot(self, logger):
        self.sync()
        return toggle_mini_window_slot_impl(self.window, logger)

    def paste_last_item_slot(self, logger, qpixmap_cls, qtimer_cls, keyboard):
        self.sync()
        return paste_last_item_slot_impl(self.window, logger, qpixmap_cls, qtimer_cls, keyboard)

    def init_tray(self, version, qaction_cls, qmenu_cls, qsystem_tray_icon_cls):
        self.sync()
        result = init_tray_impl(self.window, version, qaction_cls, qmenu_cls, qsystem_tray_icon_cls)
        self.sync()
        return result

    def on_tray_activated(self, reason, qsystem_tray_icon_cls):
        self.sync()
        return on_tray_activated_impl(self.window, reason, qsystem_tray_icon_cls)

    def show_window_from_tray(self):
        self.sync()
        return show_window_from_tray_impl(self.window)
