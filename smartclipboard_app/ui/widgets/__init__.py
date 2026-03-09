from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .floating_mini_window import FloatingMiniWindow
    from .toast import ToastNotification

__all__ = ["ToastNotification", "FloatingMiniWindow"]


def __getattr__(name: str):
    if name == "ToastNotification":
        from .toast import ToastNotification

        return ToastNotification
    if name == "FloatingMiniWindow":
        from .floating_mini_window import FloatingMiniWindow

        return FloatingMiniWindow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
