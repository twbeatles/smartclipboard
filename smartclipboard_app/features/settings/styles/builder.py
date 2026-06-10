"""Theme QSS composition."""

from __future__ import annotations

from .buttons import _build_button_section
from .misc import _build_misc_section
from .window_inputs import _build_window_input_table_section

def build_theme_style(theme, glass) -> str:
    return "\n".join(
        (
            _build_window_input_table_section(theme, glass),
            _build_button_section(theme, glass),
            _build_misc_section(theme, glass),
        )
    )

__all__ = ["build_theme_style"]
