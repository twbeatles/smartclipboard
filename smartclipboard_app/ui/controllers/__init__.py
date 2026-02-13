__all__ = [
    "ClipboardController",
    "TableController",
    "TrayHotkeyController",
    "LifecycleController",
]


def __getattr__(name):
    if name == "ClipboardController":
        from .clipboard_controller import ClipboardController

        return ClipboardController
    if name == "TableController":
        from .table_controller import TableController

        return TableController
    if name == "TrayHotkeyController":
        from .tray_hotkey_controller import TrayHotkeyController

        return TrayHotkeyController
    if name == "LifecycleController":
        from .lifecycle_controller import LifecycleController

        return LifecycleController
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
