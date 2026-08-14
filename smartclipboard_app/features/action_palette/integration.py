"""메인 창과 Palette를 연결한다."""

from __future__ import annotations

from smartclipboard_core.action_palette import ActionExecutor, create_default_registry
from smartclipboard_app.ui.widgets.toast import ToastNotification

from .dialog import ActionPaletteDialog
from .preview import ActionPreviewDialog
from .services import apply_result, context_from_item

_executor = ActionExecutor()
_registry = None


def default_registry():
    global _registry
    if _registry is None:
        _registry = create_default_registry()
    return _registry


def open_palette_impl(window) -> None:
    item_id = None
    getter = getattr(window, "get_selected_id", None)
    if callable(getter):
        item_id = getter()
    if not item_id:
        ToastNotification.show_toast(window, "항목을 먼저 선택하세요.", duration=2000, toast_type="warning")
        return

    context = context_from_item(window.db, item_id)
    if context is None:
        ToastNotification.show_toast(window, "선택한 항목을 찾을 수 없습니다.", duration=2000, toast_type="warning")
        return

    themes = _themes_from(window)
    dialog = ActionPaletteDialog(window, context, default_registry(), themes=themes)
    if dialog.exec() != dialog.DialogCode.Accepted or dialog.selected_action is None:
        return
    result = _executor.execute(dialog.selected_action, context)
    if result.kind == "error":
        apply_result(window, result, context)
        return
    if result.preview or result.kind == "qr":
        show_preview_impl(window, result, context)
        return
    apply_result(window, result, context)


def show_preview_impl(window, result, context) -> None:
    dialog = ActionPreviewDialog(window, result, context, themes=_themes_from(window))
    if dialog.exec() == dialog.DialogCode.Accepted and dialog.copied:
        copied = result
        if result.kind == "qr":
            from smartclipboard_core.action_palette import ActionResult

            copied = ActionResult(
                kind="text",
                value=context.raw_text,
                title="원문 복사",
                preview=False,
                copy_to_clipboard=True,
                metadata={"skip_writeback": True},
            )
        elif not copied.copy_to_clipboard:
            from smartclipboard_core.action_palette import ActionResult

            copied = ActionResult(
                kind=result.kind,
                value=result.value,
                title=result.title,
                preview=False,
                copy_to_clipboard=True,
                metadata=dict(result.metadata or {}),
            )
        apply_result(window, copied, context)


def _themes_from(window):
    themes = getattr(window, "THEMES", None)
    if themes:
        return themes
    try:
        import smartclipboard_app.legacy_main_src as legacy_main_src

        return getattr(legacy_main_src, "THEMES", {}) or {}
    except Exception:
        return {}


__all__ = ["default_registry", "open_palette_impl", "show_preview_impl"]
