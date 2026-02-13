"""Main window orchestrator with controller composition."""

from smartclipboard_app.legacy_main import MainWindow as LegacyMainWindow

from .controllers.clipboard_controller import ClipboardController
from .controllers.lifecycle_controller import LifecycleController
from .controllers.table_controller import TableController
from .controllers.tray_hotkey_controller import TrayHotkeyController


class MainWindow(LegacyMainWindow):
    """Compatibility MainWindow that composes feature controllers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.clipboard_controller = ClipboardController(self)
        self.table_controller = TableController(self)
        self.tray_hotkey_controller = TrayHotkeyController(self)
        self.lifecycle_controller = LifecycleController(self)

    def get_controllers(self) -> dict[str, object]:
        return {
            "clipboard": self.clipboard_controller,
            "table": self.table_controller,
            "tray_hotkey": self.tray_hotkey_controller,
            "lifecycle": self.lifecycle_controller,
        }

