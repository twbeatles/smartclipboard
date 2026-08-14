"""선택 항목 한 건으로 ActionContext를 만든다."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping
from urllib.parse import urlparse

from smartclipboard_core.automation.fetch_title import extract_first_url
from smartclipboard_core.automation.formatters import format_phone

from .models import ActionContext

JSON_DETECT_MAX_CHARS = 256 * 1024

_SENSITIVE_WORD_RE = re.compile(
    r"(?i)(?<![a-z0-9_])(password|secret|api[_-]?key|비밀번호)(?![a-z0-9_])"
)
_SENSITIVE_BODY_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\."),
)


def _looks_like_json(text: str) -> bool:
    if not text or len(text) > JSON_DETECT_MAX_CHARS:
        return False
    try:
        json.loads(text)
    except (TypeError, ValueError):
        return False
    return True


def _looks_like_phone(text: str) -> bool:
    return format_phone(text) is not None


def _is_sensitive(tags: str, note: str, raw_text: str = "", explicit: bool | None = None) -> bool:
    if explicit is not None:
        return bool(explicit)
    metadata = f"{tags}\n{note}"
    if _SENSITIVE_WORD_RE.search(metadata):
        return True
    sample = raw_text if len(raw_text) <= 8192 else raw_text[:8192]
    return any(pattern.search(sample) for pattern in _SENSITIVE_BODY_PATTERNS)


def _infer_content_type(
    raw_text: str,
    stored_type: str,
    file_paths: tuple[str, ...],
    url: str | None,
    is_valid_json: bool,
) -> str:
    stored = (stored_type or "").upper()
    if stored == "IMAGE":
        return "image"
    if stored == "FILE":
        return "files" if len(file_paths) > 1 else "file"
    if url and (stored == "LINK" or re.match(r"^https?://", raw_text.strip())):
        return "url"
    if _looks_like_phone(raw_text):
        return "phone"
    if is_valid_json:
        return "json"
    if stored == "COLOR":
        return "color"
    if stored == "CODE":
        return "code"
    if url:
        return "url"
    return "text"


def build_context(
    *,
    item_id: int | str | None = None,
    raw_text: str = "",
    stored_type: str = "",
    file_paths: tuple[str, ...] | list[str] = (),
    tags: str = "",
    note: str = "",
    metadata: Mapping[str, Any] | None = None,
    is_sensitive: bool | None = None,
) -> ActionContext:
    text = raw_text if raw_text is not None else ""
    extra = dict(metadata or {})
    if tags and "tags" not in extra:
        extra["tags"] = tags
    if note and "note" not in extra:
        extra["note"] = note

    url = extract_first_url(text)
    domain = None
    if url:
        parsed = urlparse(url)
        domain = parsed.hostname or parsed.netloc or None
        if domain:
            extra.setdefault("url_title", extra.get("url_title"))

    paths = tuple(file_paths or ())
    valid_json = _looks_like_json(text.strip())
    content_type = _infer_content_type(text, stored_type, paths, url, valid_json)
    return ActionContext(
        item_id=item_id,
        raw_text=text,
        normalized_text=text.strip(),
        content_type=content_type,
        url=url,
        domain=domain,
        file_paths=paths,
        is_multiline=("\n" in text) or ("\r" in text),
        is_valid_json=valid_json,
        is_sensitive=_is_sensitive(
            str(extra.get("tags", tags) or ""),
            str(extra.get("note", note) or ""),
            text,
            is_sensitive,
        ),
        metadata=extra,
    )


__all__ = ["JSON_DETECT_MAX_CHARS", "build_context"]
