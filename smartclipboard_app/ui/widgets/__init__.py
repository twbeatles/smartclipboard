__all__ = ["ToastNotification", "FloatingMiniWindow"]


def __getattr__(name):
    if name == "ToastNotification":
        from .toast import ToastNotification

        return ToastNotification
    if name == "FloatingMiniWindow":
        from .floating_mini_window import FloatingMiniWindow

        return FloatingMiniWindow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
