"""적용 가능한 Action 목록을 모은다."""

from __future__ import annotations

from .models import ActionContext, ClipboardPaletteAction

_CONTENT_SPECIFIC_CATEGORIES = {
    "phone": {"phone"},
    "url": {"url"},
    "json": {"developer"},
    "code": {"developer"},
    "color": {"url", "developer"},
}


class FunctionAction:
    """Protocol을 만족하는 얇은 함수 래퍼."""

    def __init__(
        self,
        *,
        id: str,
        title: str,
        category: str,
        description: str,
        priority: int,
        network_required: bool,
        applicable,
        execute,
    ) -> None:
        self.id = id
        self.title = title
        self.category = category
        self.description = description
        self.priority = priority
        self.network_required = network_required
        self._applicable = applicable
        self._execute = execute

    def is_applicable(self, context: ActionContext) -> bool:
        try:
            return bool(self._applicable(context))
        except Exception:
            return False

    def execute(self, context: ActionContext):
        return self._execute(context)


class ActionRegistry:
    def __init__(self) -> None:
        self._actions: dict[str, ClipboardPaletteAction] = {}

    def register(self, action: ClipboardPaletteAction) -> None:
        self._actions[action.id] = action

    def get(self, action_id: str):
        return self._actions.get(action_id)

    def all(self) -> list[ClipboardPaletteAction]:
        return list(self._actions.values())

    def get_applicable(self, context: ActionContext, query: str = "") -> list[ClipboardPaletteAction]:
        needle = (query or "").strip().casefold()
        matched: list[ClipboardPaletteAction] = []
        for action in self._actions.values():
            if context.is_sensitive and getattr(action, "network_required", False):
                continue
            if not action.is_applicable(context):
                continue
            if needle and not _matches_query(action, needle):
                continue
            matched.append(action)

        specific = _CONTENT_SPECIFIC_CATEGORIES.get(context.content_type, set())

        def sort_key(action: ClipboardPaletteAction):
            content_rank = 0 if action.category in specific else 1
            return (content_rank, -int(action.priority), action.title.casefold())

        matched.sort(key=sort_key)
        return matched


def _matches_query(action: ClipboardPaletteAction, needle: str) -> bool:
    haystack = " ".join(
        (
            action.id,
            action.title,
            action.description,
            action.category,
        )
    ).casefold()
    return needle in haystack


__all__ = ["ActionRegistry", "FunctionAction"]
