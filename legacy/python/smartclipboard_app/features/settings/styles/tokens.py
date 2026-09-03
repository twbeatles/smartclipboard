"""Derived design tokens for the MainWindow theme system.

The base palettes live in ``THEMES``/``GLASS_STYLES`` (legacy_main). This module
layers a small, consistent design-token system on top of those palettes so the
QSS section builders can share the same spacing, radius, elevation and colour
language across every theme without each palette having to spell out every
shade by hand.
"""

from __future__ import annotations

from typing import Any

# --- Shared geometry scale (px) -------------------------------------------------
# A single radius/spacing scale keeps corners and gaps consistent app-wide.
RADIUS_CARD = 18
RADIUS_CONTROL = 12
RADIUS_PILL = 22
RADIUS_CHIP = 10
RADIUS_SMALL = 8


def _clamp(value: float, low: float = 0.0, high: float = 255.0) -> float:
    return max(low, min(high, value))


def _parse_hex(color: str) -> tuple[int, int, int] | None:
    text = color.strip()
    if not text.startswith("#"):
        return None
    text = text[1:]
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        return None
    try:
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    except ValueError:
        return None


def with_alpha(color: str, alpha: float) -> str:
    """Return ``color`` as an ``rgba(...)`` string with the given alpha (0..1).

    Falls back to the original string when ``color`` is not a plain hex value
    (e.g. it is already an ``rgba(...)`` token), so callers can pass any palette
    value safely.
    """

    rgb = _parse_hex(color)
    if rgb is None:
        return color
    r, g, b = rgb
    return f"rgba({r}, {g}, {b}, {alpha:.3f})"


def mix(color: str, other: str, weight: float) -> str:
    """Blend ``color`` toward ``other`` by ``weight`` (0..1). Hex-only inputs."""

    base = _parse_hex(color)
    target = _parse_hex(other)
    if base is None or target is None:
        return color
    weight = max(0.0, min(1.0, weight))
    mixed = tuple(
        int(round(_clamp(b * (1.0 - weight) + t * weight)))
        for b, t in zip(base, target)
    )
    return "#{:02x}{:02x}{:02x}".format(*mixed)


def _is_dark(theme: dict[str, Any]) -> bool:
    rgb = _parse_hex(str(theme.get("background", "#000000")))
    if rgb is None:
        return True
    r, g, b = rgb
    # Perceived luminance (Rec. 601). Low value -> dark theme.
    return (0.299 * r + 0.587 * g + 0.114 * b) < 128


def derive_tokens(theme: dict[str, Any], glass: dict[str, Any]) -> dict[str, str]:
    """Compute consistent derived tokens from a base palette + glass entry.

    Every theme gets the same set of semantic surfaces/overlays regardless of
    whether the underlying palette spelled them out, which is what makes the
    redesigned QSS render uniformly across the five themes.
    """

    dark = _is_dark(theme)
    text = str(theme.get("text", "#ffffff"))
    surface = str(theme.get("surface", "#1a1a24"))
    surface_variant = str(theme.get("surface_variant", surface))
    primary = str(theme.get("primary", "#6366f1"))
    border = str(theme.get("border", "#334155"))
    glass_bg = str(glass.get("glass_bg", with_alpha(surface, 0.85)))
    shadow = str(glass.get("shadow", "rgba(0, 0, 0, 0.4)"))

    # Tone the app brightens toward (white) on dark themes and darkens toward
    # (near-black) on light themes, so overlays read correctly either way.
    lift = "#ffffff" if dark else "#0f172a"

    return {
        # Elevated card / panel surface (one step above the base surface).
        "surface_high": mix(surface, lift, 0.06 if dark else 0.0) if dark else "#ffffff",
        # Subtle hairline divider, softer than the structural border.
        "divider": with_alpha(border, 0.55),
        # Hover/press overlays usable on top of any surface.
        "overlay_hover": with_alpha(lift, 0.06),
        "overlay_press": with_alpha(lift, 0.12),
        # Translucent brand tints for selection backgrounds and chips.
        "primary_soft": with_alpha(primary, 0.16),
        "primary_softer": with_alpha(primary, 0.10),
        "chip_bg": with_alpha(primary, 0.14),
        "chip_border": with_alpha(primary, 0.35),
        # Text on top of a solid primary fill.
        "on_primary": str(theme.get("selected_text", "#ffffff")) if not dark else "#ffffff",
        # Focus ring colour (slightly translucent brand).
        "focus_ring": with_alpha(primary, 0.45),
        "glass_bg": glass_bg,
        "shadow": shadow,
        # Geometry tokens exposed as strings for f-string interpolation.
        "radius_card": str(RADIUS_CARD),
        "radius_control": str(RADIUS_CONTROL),
        "radius_pill": str(RADIUS_PILL),
        "radius_chip": str(RADIUS_CHIP),
        "radius_small": str(RADIUS_SMALL),
    }


__all__ = [
    "RADIUS_CARD",
    "RADIUS_CHIP",
    "RADIUS_CONTROL",
    "RADIUS_PILL",
    "RADIUS_SMALL",
    "derive_tokens",
    "mix",
    "with_alpha",
]
