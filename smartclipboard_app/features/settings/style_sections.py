"""Compatibility facade for MainWindow theme QSS builders."""

from __future__ import annotations

from .styles import (
    _build_button_section,
    _build_misc_section,
    _build_window_input_table_section,
    build_theme_style,
)

__all__ = [
    "_build_button_section",
    "_build_misc_section",
    "_build_window_input_table_section",
    "build_theme_style",
]
