"""Shell feature state models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LifecycleState:
    has_dirty_data: bool = False
