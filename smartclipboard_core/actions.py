"""Core clipboard action processing for SmartClipboard."""

from __future__ import annotations

import ipaddress
import json
import logging
import re
import socket
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

requests: Any | None
BeautifulSoup: Any | None

try:
    import requests as _requests
    from bs4 import BeautifulSoup as _BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None
    HAS_WEB = False
else:
    requests = _requests
    BeautifulSoup = _BeautifulSoup
    HAS_WEB = True

from .worker import Worker

logger = logging.getLogger(__name__)
TITLE_FETCH_MAX_BYTES = 1024 * 1024
TITLE_FETCH_MAX_THREADS = 4
TITLE_FETCH_MAX_REDIRECTS = 5
URL_TRAILING_PUNCTUATION = ".,!?:;"
BLOCKED_TITLE_HOSTS = {
    "localhost",
    "metadata.google.internal",
    "metadata.google.internal.",
}


def _normalize_extracted_url(url: str) -> str:
    return url.rstrip(URL_TRAILING_PUNCTUATION)


def _resolve_title_fetch_host_ips(hostname: str, scheme: str) -> list[ipaddress._BaseAddress]:
    try:
        return [ipaddress.ip_address(hostname)]
    except ValueError:
        pass

    default_port = 443 if scheme == "https" else 80
    resolved_ips: list[ipaddress._BaseAddress] = []
    seen: set[str] = set()
    addrinfo = socket.getaddrinfo(hostname, default_port, type=socket.SOCK_STREAM)
    for _family, _socktype, _proto, _canonname, sockaddr in addrinfo:
        if not sockaddr:
            continue
        host_value = str(sockaddr[0] or "").strip()
        if not host_value or host_value in seen:
            continue
        seen.add(host_value)
        resolved_ips.append(ipaddress.ip_address(host_value))
    return resolved_ips


def _validate_title_fetch_url(url: str) -> tuple[bool, str]:
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "invalid url"

    if parsed.scheme not in {"http", "https"}:
        return False, "invalid scheme"

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        return False, "missing hostname"
    if hostname in BLOCKED_TITLE_HOSTS:
        return False, f"blocked metadata hostname: {hostname}"

    try:
        resolved_ips = _resolve_title_fetch_host_ips(hostname, parsed.scheme)
    except (socket.gaierror, TypeError, ValueError) as exc:
        return False, f"dns resolution failed: {exc}"

    if not resolved_ips:
        return False, "dns resolution returned no addresses"

    for host_ip in resolved_ips:
        if not host_ip.is_global:
            return False, f"blocked non-global address: {host_ip}"

    return True, "ok"


def _is_safe_title_fetch_url(url: str) -> bool:
    return _validate_title_fetch_url(url)[0]


def _is_blocked_title_fetch_reason(reason: str) -> bool:
    return str(reason or "").startswith("blocked")


def extract_first_url(text: str) -> Optional[str]:
    """Extract the first HTTP(S) URL from a text blob."""
    if not text:
        return None
    match = re.search(r"https?://[^\s<>'\"\]\)]+", text)
    return _normalize_extracted_url(match.group(0)) if match else None


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
        if self._is_shutting_down:
            return
        if not HAS_WEB:
            self.action_completed.emit(action_name, {"type": "notify", "message": "웹 요청 라이브러리가 없어 URL 제목을 가져올 수 없습니다."})
            return
        is_safe, reason = _validate_title_fetch_url(url)
        if not is_safe:
            logger.info("Title fetch precheck rejected %s: %s", url, reason)
            self.action_completed.emit(
                action_name,
                {
                    "type": "notify",
                    "message": (
                        "보안상 로컬/사설 주소의 제목 가져오기는 건너뜁니다."
                        if _is_blocked_title_fetch_reason(reason)
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
        worker = Worker(self._fetch_title_logic, url)
        worker.signals.result.connect(lambda res, request_url=url: self._handle_title_result(res, request_url))
        self.threadpool.start(worker)

    @staticmethod
    def _fetch_title_logic(url, item_id=None):
        """작업 스레드에서 실행될 로직."""
        response = None
        try:
            if requests is None or BeautifulSoup is None:
                return {"title": None, "item_id": item_id, "url": url, "error": "web libraries unavailable"}
            current_url = url
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            for _redirect_index in range(TITLE_FETCH_MAX_REDIRECTS + 1):
                is_safe, reason = _validate_title_fetch_url(current_url)
                if not is_safe:
                    logger.info("Title fetch blocked for %s: %s", current_url, reason)
                    return {"title": None, "item_id": item_id, "url": url, "error": reason}

                response = requests.get(
                    current_url,
                    headers=headers,
                    timeout=(3, 5),
                    verify=True,
                    stream=True,
                    allow_redirects=False,
                )
                if 300 <= response.status_code < 400:
                    location = str(response.headers.get("Location", "") or "").strip()
                    if not location:
                        return {"title": None, "item_id": item_id, "url": url, "error": "redirect missing location"}
                    next_url = _normalize_extracted_url(urljoin(current_url, location))
                    response.close()
                    response = None
                    current_url = next_url
                    continue

                response.raise_for_status()
                content_type = str(response.headers.get("Content-Type", "") or "").lower()
                if content_type and "html" not in content_type:
                    return {"title": None, "item_id": item_id, "url": url, "error": f"unsupported content type: {content_type}"}

                html_chunks: list[bytes] = []
                bytes_read = 0
                for chunk in response.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    remaining = TITLE_FETCH_MAX_BYTES - bytes_read
                    if remaining <= 0:
                        break
                    limited_chunk = chunk[:remaining]
                    html_chunks.append(limited_chunk)
                    bytes_read += len(limited_chunk)
                    if bytes_read >= TITLE_FETCH_MAX_BYTES:
                        break

                html_text = b"".join(html_chunks).decode(response.encoding or "utf-8", errors="replace")
                soup = BeautifulSoup(html_text, "html.parser")
                title = soup.title.string if soup.title else None
                return {"title": title.strip() if title else None, "item_id": item_id, "url": url, "final_url": current_url}

            return {"title": None, "item_id": item_id, "url": url, "error": "too many redirects"}
        except Exception as exc:
            logger.debug("Fetch title error: %s", exc)
            return {"title": None, "item_id": item_id, "url": url, "error": str(exc)}
        finally:
            if response is not None and hasattr(response, "close"):
                try:
                    response.close()
                except Exception:
                    pass

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
        """비동기 결과 처리 (메인 스레드)."""
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

    def format_phone(self, text):
        """전화번호 포맷팅."""
        digits = re.sub(r"\D", "", text)
        if digits.startswith("02") and len(digits) == 9:
            formatted = f"{digits[:2]}-{digits[2:5]}-{digits[5:]}"
            return {"type": "format", "original": text, "formatted": formatted}
        if digits.startswith("02") and len(digits) == 10:
            formatted = f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
            return {"type": "format", "original": text, "formatted": formatted}
        if len(digits) == 8 and digits.startswith(("15", "16", "18")):
            formatted = f"{digits[:4]}-{digits[4:]}"
            return {"type": "format", "original": text, "formatted": formatted}
        if digits.startswith("0505") and len(digits) == 11:
            formatted = f"{digits[:4]}-{digits[4:7]}-{digits[7:]}"
            return {"type": "format", "original": text, "formatted": formatted}
        if len(digits) == 11 and digits.startswith("0"):
            formatted = f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
            return {"type": "format", "original": text, "formatted": formatted}
        if len(digits) == 10 and digits.startswith("0"):
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
