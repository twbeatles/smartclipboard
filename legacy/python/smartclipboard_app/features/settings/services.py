"""Settings feature services."""

from __future__ import annotations

from .style_sections import build_theme_style


def apply_theme_impl(self, THEMES, GLASS_STYLES):
    theme = THEMES.get(self.current_theme, THEMES["dark"])
    glass = GLASS_STYLES.get(self.current_theme, GLASS_STYLES["dark"])
    self.setStyleSheet(build_theme_style(theme, glass))
