"""Shell UI feature state models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ShellUiState:
    has_initialized_ui: bool = False
