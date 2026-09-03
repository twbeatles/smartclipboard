"""Shell UI feature controller."""

from __future__ import annotations

from smartclipboard_app.features.shared.controller import FeatureController

from .view import event_filter_impl, handle_drop_event_impl, init_ui_impl


class ShellUiController(FeatureController):
    def init_ui(self, has_qrcode):
        self.sync()
        result = init_ui_impl(self.window, has_qrcode)
        self.sync()
        return result

    def event_filter(self, source, event, fallback_event_filter):
        self.sync()
        return event_filter_impl(self.window, source, event, fallback_event_filter)

    def handle_drop_event(self, event, THEMES, logger):
        self.sync()
        return handle_drop_event_impl(self.window, event, THEMES, logger)
