"""Timeout helpers for the secure vault."""

from __future__ import annotations

import time


def has_timed_out(last_activity: float, lock_timeout: int) -> bool:
    return time.time() - last_activity > lock_timeout


__all__ = ["has_timed_out"]
