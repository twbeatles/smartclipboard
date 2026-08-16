from smartclipboard_app.features.shared import bind_window_facets
from smartclipboard_app.features.updater import UpdaterController
from smartclipboard_app.legacy_main import MainWindow as LegacyMainWindow

from .controllers.clipboard_controller import ClipboardController
from .controllers.lifecycle_controller import LifecycleController
from .controllers.table_controller import TableController
from .controllers.tray_hotkey_controller import TrayHotkeyController


class MainWindow(LegacyMainWindow):
    """Compatibility MainWindow that composes feature controllers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        bind_window_facets(self)
        self.clipboard_controller = getattr(self, "clipboard_controller", ClipboardController(self))
        self.table_controller = getattr(self, "table_controller", TableController(self))
        self.tray_hotkey_controller = getattr(self, "tray_hotkey_controller", TrayHotkeyController(self))
        self.lifecycle_controller = getattr(self, "lifecycle_controller", LifecycleController(self))
        self.updater_controller = getattr(self, "updater_controller", UpdaterController(self))
        self.updater_controller.notify_pending_update_result()
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(3000, lambda: self.check_for_updates(interactive=False))

    def check_for_updates(self, interactive: bool = True) -> None:
        """Check for application updates."""
        self.updater_controller.check_for_updates(interactive=interactive)

    def get_controllers(self) -> dict[str, object]:
        return {
            "clipboard": self.clipboard_controller,
            "table": self.table_controller,
            "tray_hotkey": self.tray_hotkey_controller,
            "lifecycle": self.lifecycle_controller,
            "updater": self.updater_controller,
        }

