"""Settings feature state models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SettingsViewState:
    current_theme: str = "dark"
