"""Theme QSS composition."""

from __future__ import annotations

from .buttons import _build_button_section
from .misc import _build_misc_section
from .tokens import derive_tokens
from .window_inputs import _build_window_input_table_section


def build_theme_style(theme, glass) -> str:
    tokens = derive_tokens(theme, glass)
    return "\n".join(
        (
            _build_window_input_table_section(theme, glass, tokens),
            _build_button_section(theme, glass, tokens),
            _build_misc_section(theme, glass, tokens),
        )
    )


__all__ = ["build_theme_style"]
