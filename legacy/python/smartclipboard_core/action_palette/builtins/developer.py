"""개발자용 변환 Action."""

from __future__ import annotations

import base64
import json
from urllib.parse import quote, unquote

from ..models import ActionContext, ActionResult
from ..registry import FunctionAction


def _has_text(context: ActionContext) -> bool:
    return bool(context.raw_text) and context.content_type not in {"image", "file", "files"}


def _json_pretty(context: ActionContext) -> ActionResult:
    parsed = json.loads(context.raw_text)
    return ActionResult(
        kind="text",
        value=json.dumps(parsed, ensure_ascii=False, indent=2),
        preview=True,
        copy_to_clipboard=True,
    )


def _json_minify(context: ActionContext) -> ActionResult:
    parsed = json.loads(context.raw_text)
    return ActionResult(
        kind="text",
        value=json.dumps(parsed, ensure_ascii=False, separators=(",", ":")),
        preview=True,
        copy_to_clipboard=True,
    )


def _url_encode(context: ActionContext) -> ActionResult:
    return ActionResult(
        kind="text",
        value=quote(context.raw_text, safe=""),
        copy_to_clipboard=True,
        preview=len(context.raw_text) >= 300,
    )


def _url_decode(context: ActionContext) -> ActionResult:
    return ActionResult(
        kind="text",
        value=unquote(context.raw_text),
        copy_to_clipboard=True,
        preview=len(context.raw_text) >= 300,
    )


def _json_escape(context: ActionContext) -> ActionResult:
    return ActionResult(
        kind="text",
        value=json.dumps(context.raw_text, ensure_ascii=False),
        preview=True,
        copy_to_clipboard=True,
    )


def _b64_encode(context: ActionContext) -> ActionResult:
    encoded = base64.b64encode(context.raw_text.encode("utf-8")).decode("ascii")
    return ActionResult(kind="text", value=encoded, preview=True, copy_to_clipboard=True)


def _b64_decode(context: ActionContext) -> ActionResult:
    raw = "".join(context.raw_text.split())
    decoded = base64.b64decode(raw, validate=True)
    return ActionResult(kind="text", value=decoded.decode("utf-8"), preview=True, copy_to_clipboard=True)


def _can_decode_base64(context: ActionContext) -> bool:
    if not _has_text(context):
        return False
    raw = "".join(context.raw_text.split())
    if not raw:
        return False
    try:
        decoded = base64.b64decode(raw, validate=True)
        decoded.decode("utf-8")
    except Exception:
        return False
    return True


def _looks_urlencoded(context: ActionContext) -> bool:
    return _has_text(context) and ("%" in context.raw_text or "+" in context.raw_text)


def register_developer_actions(registry) -> None:
    registry.register(
        FunctionAction(
            id="dev.json_pretty",
            title="JSON 정리",
            category="developer",
            description="JSON을 들여쓰기해 읽기 쉽게 만듭니다.",
            priority=100,
            network_required=False,
            applicable=lambda context: _has_text(context) and context.is_valid_json,
            execute=_json_pretty,
        )
    )
    registry.register(
        FunctionAction(
            id="dev.json_minify",
            title="JSON 압축",
            category="developer",
            description="JSON을 한 줄로 압축합니다.",
            priority=90,
            network_required=False,
            applicable=lambda context: _has_text(context) and context.is_valid_json,
            execute=_json_minify,
        )
    )
    registry.register(
        FunctionAction(
            id="dev.url_encode",
            title="URL 인코드",
            category="developer",
            description="텍스트를 percent-encoding 합니다.",
            priority=50,
            network_required=False,
            applicable=_has_text,
            execute=_url_encode,
        )
    )
    registry.register(
        FunctionAction(
            id="dev.url_decode",
            title="URL 디코드",
            category="developer",
            description="percent-encoding을 되돌립니다.",
            priority=50,
            network_required=False,
            applicable=_looks_urlencoded,
            execute=_url_decode,
        )
    )
    registry.register(
        FunctionAction(
            id="dev.json_escape_string",
            title="JSON 문자열 이스케이프",
            category="developer",
            description="텍스트를 JSON 문자열로 감쌉니다.",
            priority=45,
            network_required=False,
            applicable=_has_text,
            execute=_json_escape,
        )
    )
    registry.register(
        FunctionAction(
            id="dev.base64_encode",
            title="Base64 인코드",
            category="developer",
            description="UTF-8 텍스트를 Base64로 만듭니다.",
            priority=30,
            network_required=False,
            applicable=_has_text,
            execute=_b64_encode,
        )
    )
    registry.register(
        FunctionAction(
            id="dev.base64_decode",
            title="Base64 디코드",
            category="developer",
            description="Base64를 UTF-8 텍스트로 되돌립니다.",
            priority=30,
            network_required=False,
            applicable=_can_decode_base64,
            execute=_b64_decode,
        )
    )


__all__ = ["register_developer_actions"]
