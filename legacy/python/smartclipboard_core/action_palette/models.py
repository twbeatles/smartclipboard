"""Action Palette 계약 모델."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class ActionContext:
    item_id: int | str | None
    raw_text: str
    normalized_text: str
    content_type: str

    url: str | None = None
    domain: str | None = None
    file_paths: tuple[str, ...] = ()

    is_multiline: bool = False
    is_valid_json: bool = False
    is_sensitive: bool = False

    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionResult:
    kind: str
    value: str
    title: str | None = None
    preview: bool = False
    copy_to_clipboard: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class ClipboardPaletteAction(Protocol):
    id: str
    title: str
    category: str
    description: str
    priority: int
    network_required: bool

    def is_applicable(self, context: ActionContext) -> bool:
        ...

    def execute(self, context: ActionContext) -> ActionResult:
        ...


__all__ = ["ActionContext", "ActionResult", "ClipboardPaletteAction"]
