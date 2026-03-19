"""Helpers for clipboard writes initiated by the application itself."""

from __future__ import annotations


def mark_internal_copy(parent: object | None) -> None:
    if parent is None or not hasattr(parent, "is_internal_copy"):
        return
    try:
        setattr(parent, "is_internal_copy", True)
    except Exception:
        pass
