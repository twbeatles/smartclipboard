"""Compatibility shim for lifecycle operations."""

from __future__ import annotations

from smartclipboard_app.features.shell.services import (
    check_vault_timeout_impl,
    quit_app_impl,
    run_periodic_cleanup_impl,
    update_status_bar_impl,
    update_tray_theme_impl,
)

__all__ = [
    "check_vault_timeout_impl",
    "quit_app_impl",
    "run_periodic_cleanup_impl",
    "update_status_bar_impl",
    "update_tray_theme_impl",
]
