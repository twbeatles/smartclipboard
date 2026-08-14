"""Action Palette feature controller."""

from __future__ import annotations

from smartclipboard_app.features.shared.controller import FeatureController

from .integration import open_palette_impl, show_preview_impl


class ActionPaletteController(FeatureController):
    def open_palette(self):
        self.sync()
        return open_palette_impl(self.window)

    def show_preview(self, result, context):
        self.sync()
        return show_preview_impl(self.window, result, context)
