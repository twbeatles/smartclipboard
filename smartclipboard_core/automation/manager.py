"""Clipboard automation manager implementation."""

from __future__ import annotations

import json
import logging
import re

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from .cache import TITLE_FETCH_MAX_THREADS
from .fetch_title import (
    HAS_WEB,
    extract_first_url,
    fetch_title_logic,
    is_blocked_title_fetch_reason,
    validate_title_fetch_url,
)
from .formatters import format_email, format_phone, transform_text
from ..worker import Worker

logger = logging.getLogger(__name__)


class ClipboardActionManager(QObject):
    """복사된 내용에 따라 자동 액션을 수행하는 관리자."""

    action_completed = pyqtSignal(str, object)

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.actions_cache = []
        self._is_shutting_down = False
        self._title_cache: dict[str, str] = {}
        self._pending_by_url: dict[str, set[object]] = {}
        self._pending_action_name_by_url: dict[str, str] = {}
        self.reload_actions()
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(TITLE_FETCH_MAX_THREADS)

    def reload_actions(self):
        raw_actions = self.db.get_clipboard_actions()
        self.actions_cache = []
        for action in raw_actions:
            aid, name, pattern, action_type, params_json, enabled, priority = action
            if not pattern:
                continue
            try:
                compiled_pattern = re.compile(pattern)
                self.actions_cache.append(
                    {
                        "id": aid,
                        "name": name,
                        "pattern": pattern,
                        "compiled": compiled_pattern,
                        "type": action_type,
                        "params": params_json,
                        "enabled": enabled,
                        "priority": priority,
                    }
                )
            except re.error as exc:
                logger.warning("Invalid regex in action '%s': %s", name, exc)

    def process(self, text, item_id=None):
        results = []
        for action in self.actions_cache:
            if not action["enabled"]:
                continue
            try:
                if not action["compiled"].search(text):
                    continue
                params_json = action["params"]
                try:
                    params = json.loads(params_json) if params_json else {}
                except json.JSONDecodeError:
                    params = {}

                action_type = action["type"]
                name = action["name"]
                if action_type == "fetch_title":
                    url = extract_first_url(text)
                    if not url:
                        results.append((name, {"type": "notify", "message": "URL을 찾지 못해 제목 가져오기를 건너뛰었습니다."}))
                        continue
                    self.fetch_url_title_async(url, item_id, name)
                else:
                    result = self.execute_action(action_type, text, params, item_id)
                    if result:
                        results.append((name, result))
            except re.error as exc:
                logger.warning("Invalid regex in action '%s': %s", action["name"], exc)
            except Exception as exc:
                logger.warning("Action processing error '%s': %s", action["name"], exc)
        return results

    def execute_action(self, action_type, text, params, item_id):
        if action_type == "fetch_title":
            return None
        if action_type == "format_phone":
            return format_phone(text)
        if action_type == "format_email":
            return format_email(text)
        if action_type == "notify":
            return {"type": "notify", "message": params.get("message", "패턴 매칭됨")}
        if action_type == "transform":
            return transform_text(text, params.get("mode", "trim"))
        return None

    def fetch_url_title_async(self, url, item_id, action_name):
        if self._is_shutting_down:
            return
        if not HAS_WEB:
            self.action_completed.emit(action_name, {"type": "notify", "message": "웹 요청 라이브러리가 없어 URL 제목을 가져올 수 없습니다."})
            return
        is_safe, reason = validate_title_fetch_url(url)
        if not is_safe:
            logger.info("Title fetch precheck rejected %s: %s", url, reason)
            self.action_completed.emit(
                action_name,
                {
                    "type": "notify",
                    "message": (
                        "보안상 로컬/사설 주소의 제목 가져오기는 건너뜁니다."
                        if is_blocked_title_fetch_reason(reason)
                        else "URL 제목을 가져오기 전에 주소 검증에 실패했습니다."
                    ),
                },
            )
            return

        cached_title = self._title_cache.get(url)
        if cached_title:
            if item_id:
                if self._update_title_for_current_item(item_id, url, cached_title):
                    self.action_completed.emit(action_name, {"type": "title", "title": cached_title})
                else:
                    self.action_completed.emit(action_name, {"type": "notify", "message": "URL 제목을 저장하지 못했습니다."})
            else:
                self.action_completed.emit(action_name, {"type": "title", "title": cached_title})
            return

        pending_item_ids = self._pending_by_url.setdefault(url, set())
        if item_id is not None:
            pending_item_ids.add(item_id)
        if url in self._pending_action_name_by_url:
            return

        self._pending_action_name_by_url[url] = action_name
        worker = Worker(fetch_title_logic, url)
        worker.signals.result.connect(lambda res, request_url=url: self._handle_title_result(res, request_url))
        self.threadpool.start(worker)

    def _update_title_for_current_item(self, item_id: int, request_url: str, title: str) -> bool:
        if not item_id or not title:
            return False
        data = self.db.get_content(item_id)
        if not data:
            return False
        current_content, _blob, _type = data
        if extract_first_url(current_content or "") != request_url:
            return False
        return self.db.update_url_title(item_id, title)

    def _handle_title_result(self, result, request_url):
        url = result.get("url") or request_url
        action_name = self._pending_action_name_by_url.pop(url, "fetch_title")
        pending_item_ids = self._pending_by_url.pop(url, set())

        if self._is_shutting_down or not self._db_is_available():
            logger.debug("Ignoring title result after shutdown or DB close")
            return

        title = result.get("title")
        if title:
            self._title_cache[url] = title
            updated_any = False
            if pending_item_ids:
                for pending_item_id in pending_item_ids:
                    if isinstance(pending_item_id, int) and self._update_title_for_current_item(pending_item_id, url, title):
                        updated_any = True
                if updated_any:
                    self.action_completed.emit(action_name, {"type": "title", "title": title})
                else:
                    self.action_completed.emit(action_name, {"type": "notify", "message": "URL 제목을 저장하지 못했습니다."})
            else:
                self.action_completed.emit(action_name, {"type": "title", "title": title})
            return

        self.action_completed.emit(action_name, {"type": "notify", "message": "URL 제목을 가져오지 못했습니다."})

    def _db_is_available(self) -> bool:
        if self.db is None:
            return False
        if hasattr(self.db, "conn"):
            return getattr(self.db, "conn", None) is not None
        return True

    def shutdown(self, wait_timeout_ms: int = 2000) -> None:
        self._is_shutting_down = True
        try:
            self.threadpool.waitForDone(wait_timeout_ms)
        except TypeError:
            self.threadpool.waitForDone()


__all__ = ["ClipboardActionManager"]
