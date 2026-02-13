"""Core clipboard action processing for SmartClipboard."""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

try:
    import requests
    from bs4 import BeautifulSoup

    HAS_WEB = True
except ImportError:
    HAS_WEB = False

from .worker import Worker

logger = logging.getLogger(__name__)


def extract_first_url(text: str) -> Optional[str]:
    """Extract the first HTTP(S) URL from a text blob."""
    if not text:
        return None
    match = re.search(r"https?://[^\s<>'\"\]\)]+", text)
    return match.group(0) if match else None


class ClipboardActionManager(QObject):
    """복사된 내용에 따라 자동 액션을 수행하는 관리자."""

    action_completed = pyqtSignal(str, object)

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.actions_cache = []
        self.reload_actions()
        self.threadpool = QThreadPool.globalInstance()

    def reload_actions(self):
        """액션 규칙 캐시 갱신 - 정규식 사전 컴파일 최적화."""
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
        """텍스트에 매칭되는 액션 실행."""
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
        """동기 액션 실행."""
        if action_type == "fetch_title":
            return None
        if action_type == "format_phone":
            return self.format_phone(text)
        if action_type == "format_email":
            return self.format_email(text)
        if action_type == "notify":
            return {"type": "notify", "message": params.get("message", "패턴 매칭됨")}
        if action_type == "transform":
            return self.transform_text(text, params.get("mode", "trim"))
        return None

    def fetch_url_title_async(self, url, item_id, action_name):
        """URL 제목 비동기 요청."""
        if not HAS_WEB:
            self.action_completed.emit(action_name, {"type": "notify", "message": "웹 요청 라이브러리가 없어 URL 제목을 가져올 수 없습니다."})
            return

        worker = Worker(self._fetch_title_logic, url, item_id)
        worker.signals.result.connect(lambda res: self._handle_title_result(res, action_name))
        self.threadpool.start(worker)

    @staticmethod
    def _fetch_title_logic(url, item_id):
        """작업 스레드에서 실행될 로직."""
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(url, headers=headers, timeout=(3, 5), verify=True)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            title = soup.title.string if soup.title else None
            return {"title": title.strip() if title else None, "item_id": item_id, "url": url}
        except Exception as exc:
            logger.debug("Fetch title error: %s", exc)
            return {"title": None, "item_id": item_id, "url": url, "error": str(exc)}

    def _handle_title_result(self, result, action_name):
        """비동기 결과 처리 (메인 스레드)."""
        title = result.get("title")
        item_id = result.get("item_id")

        if title and item_id:
            self.db.update_url_title(item_id, title)
            self.action_completed.emit(action_name, {"type": "title", "title": title})
            return

        self.action_completed.emit(action_name, {"type": "notify", "message": "URL 제목을 가져오지 못했습니다."})

    def format_phone(self, text):
        """전화번호 포맷팅."""
        digits = re.sub(r"\D", "", text)
        if len(digits) == 11 and digits.startswith("010"):
            formatted = f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
            return {"type": "format", "original": text, "formatted": formatted}
        if len(digits) == 10:
            formatted = f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
            return {"type": "format", "original": text, "formatted": formatted}
        return None

    def format_email(self, text):
        """이메일 정규화."""
        email = text.strip().lower()
        return {"type": "format", "original": text, "formatted": email}

    def transform_text(self, text, mode):
        """텍스트 변환."""
        if mode == "trim":
            return {"type": "transform", "result": text.strip()}
        if mode == "upper":
            return {"type": "transform", "result": text.upper()}
        if mode == "lower":
            return {"type": "transform", "result": text.lower()}
        return None
