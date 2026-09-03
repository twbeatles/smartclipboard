"""Action Palette 서비스: context 조립과 결과 반영."""

from __future__ import annotations

import logging
import webbrowser
from typing import Any

from smartclipboard_core.action_palette import ActionContext, ActionResult, build_context
from smartclipboard_core.automation.fetch_title import (
    extract_first_url,
    fetch_title_logic,
    is_blocked_title_fetch_reason,
    validate_title_fetch_url,
)
from smartclipboard_core.file_paths import file_paths_from_content
from smartclipboard_core.worker import Worker
from smartclipboard_app.ui.clipboard_guard import mark_internal_copy
from smartclipboard_app.ui.widgets.toast import ToastNotification

logger = logging.getLogger(__name__)


def _history_fields(db, item_id: int) -> tuple[str, str, str]:
    getter = getattr(db, "get_item_annotations", None)
    if callable(getter):
        try:
            row = getter(item_id)
        except Exception:
            logger.debug("Action palette metadata lookup failed", exc_info=True)
            return "", "", ""
        if not isinstance(row, (tuple, list)) or len(row) < 3:
            return "", "", ""
        return str(row[0] or ""), str(row[1] or ""), str(row[2] or "")
    return "", "", ""


def context_from_item(db, item_id) -> ActionContext | None:
    data = db.get_content(item_id)
    if not data:
        return None
    content, _blob, stored_type = data
    tags, note, url_title = _history_fields(db, int(item_id)) if item_id is not None else ("", "", "")
    file_paths = ()
    if stored_type == "FILE":
        file_paths = tuple(file_paths_from_content(content or ""))
    return build_context(
        item_id=item_id,
        raw_text=content or "",
        stored_type=str(stored_type or ""),
        file_paths=file_paths,
        tags=tags,
        note=note,
        metadata={"url_title": url_title, "tags": tags, "note": note},
    )


def _palette_is_shutting_down(window) -> bool:
    return bool(getattr(window, "_action_palette_shutting_down", False))


def _db_is_available(window) -> bool:
    db = getattr(window, "db", None)
    if db is None:
        return False
    return getattr(db, "conn", None) is not None


def _refresh_history(window) -> None:
    visible = True
    is_visible = getattr(window, "isVisible", None)
    if callable(is_visible):
        try:
            visible = bool(is_visible())
        except Exception:
            visible = False
    load_data = getattr(window, "load_data", None)
    if visible and callable(load_data):
        load_data()
        return
    if hasattr(window, "is_data_dirty"):
        window.is_data_dirty = True


def _write_back_selected_item(window, context: ActionContext, new_text: str) -> None:
    if not new_text or context.item_id is None or new_text == context.raw_text:
        return
    db = getattr(window, "db", None)
    if db is None or not hasattr(db, "replace_text_item_or_merge"):
        return
    analyzer = getattr(window, "analyze_text", None)
    item_type = "TEXT"
    if callable(analyzer):
        try:
            stripped = new_text.strip()
            item_type = analyzer(stripped) if stripped else "TEXT"
        except Exception:
            item_type = "TEXT"
    try:
        db.replace_text_item_or_merge(int(context.item_id), new_text, item_type)
    except Exception:
        logger.debug("Action palette writeback failed", exc_info=True)
        return
    _refresh_history(window)


def apply_result(window, result: ActionResult, context: ActionContext) -> None:
    if result.kind == "error":
        ToastNotification.show_toast(window, result.value, duration=2500, toast_type="warning")
        return
    if result.kind == "info" and (result.metadata or {}).get("async") == "fetch_title":
        start_fetch_title(window, context, str(result.metadata.get("url") or context.url or ""))
        return
    if result.kind in {"url"} and (result.metadata or {}).get("open_browser"):
        if context.is_sensitive and not str(result.value).startswith("https://www.google.com/search"):
            ToastNotification.show_toast(window, "민감한 항목의 외부 열기는 건너뜁니다.", duration=2500, toast_type="warning")
            return
        if (result.metadata or {}).get("confirm_open"):
            from PyQt6.QtWidgets import QMessageBox

            parent = window if hasattr(window, "windowTitle") else None
            reply = QMessageBox.question(
                parent,
                "페이지 열기",
                f"다음 주소를 열까요?\n{result.value}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        webbrowser.open(result.value)
        ToastNotification.show_toast(window, "브라우저에서 열었습니다.", duration=2000, toast_type="info")
        return
    if result.copy_to_clipboard and result.kind in {"text", "url", "info"}:
        clipboard = getattr(window, "clipboard", None)
        if clipboard is not None and hasattr(clipboard, "setText"):
            mark_internal_copy(window)
            clipboard.setText(result.value)
            if not (result.metadata or {}).get("skip_writeback"):
                _write_back_selected_item(window, context, result.value)
        ToastNotification.show_toast(window, f"✅ {result.title or '작업'} 결과가 복사되었습니다.", duration=2000, toast_type="success")


def _disconnect_title_worker(window) -> None:
    worker = getattr(window, "_action_palette_title_worker", None)
    if worker is None:
        return
    try:
        worker.signals.result.disconnect()
    except Exception:
        pass
    window._action_palette_title_worker = None
    window._action_palette_title_pending_url = None


def start_fetch_title(window, context: ActionContext, url: str) -> None:
    if _palette_is_shutting_down(window) or not _db_is_available(window):
        return
    if not url:
        ToastNotification.show_toast(window, "URL을 찾지 못했습니다.", duration=2000, toast_type="warning")
        return
    is_safe, reason = validate_title_fetch_url(url)
    if not is_safe:
        message = (
            "보안상 로컬/사설 주소의 제목 가져오기는 건너뜁니다."
            if is_blocked_title_fetch_reason(reason)
            else "URL 제목을 가져오기 전에 주소 검증에 실패했습니다."
        )
        ToastNotification.show_toast(window, message, duration=2500, toast_type="warning")
        return

    manager = getattr(window, "action_manager", None)
    cached_title = None
    getter = getattr(manager, "_get_cached_title", None)
    if callable(getter):
        try:
            cached_title = getter(url)
        except Exception:
            cached_title = None
    if cached_title:
        _handle_title_result(window, context, url, {"title": cached_title, "url": url})
        return

    pending = getattr(window, "_action_palette_title_pending_url", None)
    if pending == url:
        ToastNotification.show_toast(window, "같은 URL 제목을 이미 가져오는 중입니다.", duration=2000, toast_type="info")
        return

    _disconnect_title_worker(window)
    ToastNotification.show_toast(window, "제목을 가져오는 중...", duration=2000, toast_type="info")
    worker = Worker(fetch_title_logic, url, context.item_id)
    worker.signals.result.connect(lambda res: _handle_title_result(window, context, url, res))
    pool = getattr(manager, "threadpool", None)
    if pool is None:
        from PyQt6.QtCore import QThreadPool

        pool = QThreadPool.globalInstance()
    if pool is None:
        ToastNotification.show_toast(window, "제목을 가져올 스레드풀이 없습니다.", duration=2000, toast_type="warning")
        return
    window._action_palette_title_worker = worker
    window._action_palette_title_pending_url = url
    pool.start(worker)


def _handle_title_result(window, context: ActionContext, request_url: str, result: dict[str, Any]) -> None:
    window._action_palette_title_pending_url = None
    if _palette_is_shutting_down(window) or not _db_is_available(window):
        return
    title = (result or {}).get("title")
    item_id = context.item_id
    db = getattr(window, "db", None)
    if item_id and db is not None:
        current = db.get_content(item_id)
        if not current:
            ToastNotification.show_toast(window, "항목이 삭제되어 제목을 저장하지 못했습니다.", duration=2500, toast_type="warning")
            return
        current_url = extract_first_url(current[0] or "")
        if current_url != request_url:
            ToastNotification.show_toast(window, "URL이 바뀌어 제목을 저장하지 않았습니다.", duration=2500, toast_type="warning")
            return
        if title and hasattr(db, "update_url_title"):
            db.update_url_title(item_id, title)
            setter = getattr(getattr(window, "action_manager", None), "_set_cached_title", None)
            if callable(setter):
                try:
                    setter(request_url, title)
                except Exception:
                    pass
            _refresh_history(window)
    if not title:
        ToastNotification.show_toast(window, "URL 제목을 가져오지 못했습니다.", duration=2500, toast_type="warning")
        return
    visible = True
    is_visible = getattr(window, "isVisible", None)
    if callable(is_visible):
        try:
            visible = bool(is_visible())
        except Exception:
            visible = False
    if not visible:
        ToastNotification.show_toast(window, f"🔗 {title[:50]}", duration=2500, toast_type="info")
        return
    show_preview = getattr(window, "_show_action_palette_preview", None)
    preview_result = ActionResult(kind="text", value=title, title="페이지 제목", preview=True, copy_to_clipboard=True)
    if callable(show_preview):
        show_preview(preview_result, context)
        return
    apply_result(window, preview_result, context)


def shutdown_palette_workers(window) -> None:
    window._action_palette_shutting_down = True
    _disconnect_title_worker(window)


__all__ = ["apply_result", "context_from_item", "shutdown_palette_workers", "start_fetch_title"]
