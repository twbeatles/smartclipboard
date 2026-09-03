"""Clipboard feature state models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ClipboardFeatureState:
    debounce_active: bool = False
