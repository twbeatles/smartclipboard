"""Settings feature controller."""

from __future__ import annotations

from smartclipboard_app.features.shared.controller import FeatureController

from .services import apply_theme_impl


class SettingsController(FeatureController):
    def apply_theme(self, THEMES, GLASS_STYLES):
        self.sync()
        return apply_theme_impl(self.window, THEMES, GLASS_STYLES)
