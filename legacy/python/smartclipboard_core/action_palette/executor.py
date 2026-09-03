"""Action 실행을 격리하고 결과를 정규화한다."""

from __future__ import annotations

from .models import ActionContext, ActionResult, ClipboardPaletteAction

_PREVIEW_LENGTH = 300


class ActionExecutor:
    def execute(self, action: ClipboardPaletteAction, context: ActionContext) -> ActionResult:
        try:
            if context.is_sensitive and getattr(action, "network_required", False):
                return ActionResult(
                    kind="error",
                    value="민감한 항목에는 네트워크 작업을 실행할 수 없습니다.",
                    title=action.title,
                )
            result = action.execute(context)
            return self._normalize(result, action, context)
        except Exception as exc:
            return ActionResult(
                kind="error",
                value=f"{action.title}에 실패했습니다.",
                title=action.title,
                metadata={"error": str(exc)},
            )

    def _normalize(
        self,
        result: ActionResult,
        action: ClipboardPaletteAction,
        context: ActionContext,
    ) -> ActionResult:
        if not isinstance(result, ActionResult):
            result = ActionResult(kind="text", value=str(result), title=action.title)
        preview = bool(result.preview)
        if result.kind in {"qr"}:
            preview = True
        if result.kind == "info" and (result.metadata or {}).get("async") == "fetch_title":
            preview = True
        if result.kind == "text" and len(result.value or "") >= _PREVIEW_LENGTH:
            preview = True
        if result.kind == "error":
            preview = False
        title = result.title or action.title
        return ActionResult(
            kind=result.kind,
            value=result.value,
            title=title,
            preview=preview,
            copy_to_clipboard=bool(result.copy_to_clipboard) and result.kind != "error",
            metadata=dict(result.metadata or {}),
        )


__all__ = ["ActionExecutor"]
