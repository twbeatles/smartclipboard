"""Tray/hotkey feature state models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HotkeyRuntimeState:
    registered_hotkeys: list[object] = field(default_factory=list)
    last_hotkey_error: str = ""
