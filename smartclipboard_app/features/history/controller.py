"""History feature controller."""

from __future__ import annotations

from smartclipboard_app.features.shared.controller import FeatureController

from .services import (
    get_display_items_impl,
    init_menu_impl,
    load_data_impl,
    on_selection_changed_impl,
    populate_table_impl,
    show_context_menu_impl,
    show_empty_state_impl,
)


class HistoryController(FeatureController):
    def init_menu(self, THEMES):
        self.sync()
        return init_menu_impl(self.window, THEMES)

    def show_context_menu(self, pos, THEMES, webbrowser):
        self.sync()
        return show_context_menu_impl(self.window, pos, THEMES, webbrowser)

    def load_data(self, THEMES, logger):
        self.sync()
        return load_data_impl(self.window, THEMES, logger)

    def get_display_items(self):
        self.sync()
        return get_display_items_impl(self.window)

    def show_empty_state(self, theme):
        self.sync()
        return show_empty_state_impl(self.window, theme)

    def populate_table(self, items, theme, TYPE_ICONS):
        self.sync()
        return populate_table_impl(self.window, items, theme, TYPE_ICONS)

    def on_selection_changed(self, HAS_QRCODE, THEMES):
        self.sync()
        return on_selection_changed_impl(self.window, HAS_QRCODE, THEMES)
