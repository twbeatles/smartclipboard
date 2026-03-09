"""Application package for SmartClipboard refactor."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .bootstrap import run

__all__ = ["run"]


def __getattr__(name: str):
    if name == "run":
        from .bootstrap import run

        return run
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
