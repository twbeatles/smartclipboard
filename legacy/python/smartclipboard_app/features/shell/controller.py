"""Shell/lifecycle feature controller."""

from __future__ import annotations

from smartclipboard_app.features.shared.controller import FeatureController

from .services import (
    check_vault_timeout_impl,
    quit_app_impl,
    run_periodic_cleanup_impl,
    update_status_bar_impl,
    update_tray_theme_impl,
)


class LifecycleController(FeatureController):
    def update_tray_theme(self, THEMES):
        self.sync()
        return update_tray_theme_impl(self.window, THEMES)

    def update_status_bar(self, selection_count, qt_module):
        self.sync()
        return update_status_bar_impl(self.window, selection_count, qt_module)

    def check_vault_timeout(self, logger):
        self.sync()
        return check_vault_timeout_impl(self.window, logger)

    def run_periodic_cleanup(self, logger):
        self.sync()
        return run_periodic_cleanup_impl(self.window, logger)

    def quit_app(self, logger, keyboard, qapplication_cls):
        self.sync()
        return quit_app_impl(self.window, logger, keyboard, qapplication_cls)
