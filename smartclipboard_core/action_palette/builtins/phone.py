"""전화번호 Action. 기존 format_phone을 재사용한다."""

from __future__ import annotations

import re

from smartclipboard_core.automation.formatters import format_phone, replacement_text_from_result

from ..models import ActionContext, ActionResult
from ..registry import FunctionAction

_DIGITS = re.compile(r"\D")


def _is_phone_like(context: ActionContext) -> bool:
    if context.content_type in {"image", "file", "files"}:
        return False
    return format_phone(context.raw_text) is not None


def _format_kr(context: ActionContext) -> ActionResult:
    payload = format_phone(context.raw_text)
    formatted = replacement_text_from_result(payload) or context.raw_text
    return ActionResult(kind="text", value=formatted, copy_to_clipboard=True, preview=False)


def _digits_only(context: ActionContext) -> ActionResult:
    return ActionResult(
        kind="text",
        value=_DIGITS.sub("", context.raw_text),
        copy_to_clipboard=True,
        preview=False,
    )


def register_phone_actions(registry) -> None:
    registry.register(
        FunctionAction(
            id="phone.format_kr",
            title="한국 전화번호 형식",
            category="phone",
            description="010-1234-5678 형식으로 맞춥니다.",
            priority=100,
            network_required=False,
            applicable=_is_phone_like,
            execute=_format_kr,
        )
    )
    registry.register(
        FunctionAction(
            id="phone.digits_only",
            title="숫자만 남기기",
            category="phone",
            description="전화번호에서 숫자만 남깁니다.",
            priority=90,
            network_required=False,
            applicable=lambda context: _is_phone_like(context) and bool(_DIGITS.search(context.raw_text)),
            execute=_digits_only,
        )
    )


__all__ = ["register_phone_actions"]
