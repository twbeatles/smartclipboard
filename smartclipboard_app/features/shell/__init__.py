"""Shell and lifecycle feature package."""

from .controller import LifecycleController
from .services import (
    check_vault_timeout_impl,
    quit_app_impl,
    run_periodic_cleanup_impl,
    update_status_bar_impl,
    update_tray_theme_impl,
)

__all__ = [
    "LifecycleController",
    "check_vault_timeout_impl",
    "quit_app_impl",
    "run_periodic_cleanup_impl",
    "update_status_bar_impl",
    "update_tray_theme_impl",
]
