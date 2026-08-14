"""텍스트 변환 Action."""

from __future__ import annotations

import re

from ..models import ActionContext, ActionResult
from ..registry import FunctionAction

_HORIZONTAL_WS = re.compile(r"[^\S\n\r]+")
_NEWLINES = re.compile(r"\r\n|\r|\n")


def _text_result(value: str, *, preview: bool = False, copy: bool = True) -> ActionResult:
    return ActionResult(kind="text", value=value, preview=preview, copy_to_clipboard=copy)


def _has_text(context: ActionContext) -> bool:
    return bool(context.raw_text) and context.content_type not in {"image", "file", "files"}


def _trim(context: ActionContext) -> ActionResult:
    return _text_result(context.raw_text.strip())


def _collapse(context: ActionContext) -> ActionResult:
    return _text_result(_HORIZONTAL_WS.sub(" ", context.raw_text))


def _single_line(context: ActionContext) -> ActionResult:
    collapsed = _NEWLINES.sub(" ", context.raw_text)
    return _text_result(_HORIZONTAL_WS.sub(" ", collapsed), preview=True)


def _remove_blank_lines(context: ActionContext) -> ActionResult:
    lines = context.raw_text.split("\n")
    kept = [line for line in lines if line.strip() != ""]
    return _text_result("\n".join(kept), preview=True)


def _dedupe_lines(context: ActionContext) -> ActionResult:
    seen: set[str] = set()
    kept: list[str] = []
    for line in context.raw_text.split("\n"):
        if line in seen:
            continue
        seen.add(line)
        kept.append(line)
    return _text_result("\n".join(kept), preview=True)


def _sort_lines(context: ActionContext) -> ActionResult:
    lines = context.raw_text.split("\n")
    lines.sort(key=lambda item: item.casefold())
    return _text_result("\n".join(lines), preview=True)


def _lowercase(context: ActionContext) -> ActionResult:
    return _text_result(context.raw_text.lower())


def _uppercase(context: ActionContext) -> ActionResult:
    return _text_result(context.raw_text.upper())


def _normalize_newlines(context: ActionContext) -> ActionResult:
    return _text_result(_NEWLINES.sub("\n", context.raw_text))


def register_text_actions(registry) -> None:
    specs = (
        ("text.trim", "앞뒤 공백 제거", "앞뒤 whitespace를 제거합니다.", 80, _trim, lambda c: _has_text(c) and c.raw_text != c.raw_text.strip()),
        (
            "text.collapse_spaces",
            "연속 공백 줄이기",
            "가로 공백을 하나로 줄이고 줄바꿈은 유지합니다.",
            70,
            _collapse,
            lambda c: _has_text(c) and _HORIZONTAL_WS.search(c.raw_text) is not None,
        ),
        (
            "text.single_line",
            "한 줄로 만들기",
            "줄바꿈을 공백으로 바꿉니다.",
            75,
            _single_line,
            lambda c: _has_text(c) and bool(_NEWLINES.search(c.raw_text)),
        ),
        (
            "text.remove_blank_lines",
            "빈 줄 제거",
            "비어 있는 줄을 삭제합니다.",
            65,
            _remove_blank_lines,
            lambda c: _has_text(c) and any(line.strip() == "" for line in c.raw_text.split("\n")),
        ),
        (
            "text.dedupe_lines",
            "중복 줄 제거",
            "순서를 유지한 채 같은 줄을 제거합니다.",
            60,
            _dedupe_lines,
            lambda c: _has_text(c) and len(c.raw_text.split("\n")) != len(set(c.raw_text.split("\n"))),
        ),
        (
            "text.sort_lines",
            "줄 정렬",
            "대소문자 구분 없이 줄을 정렬합니다.",
            55,
            _sort_lines,
            lambda c: _has_text(c) and c.is_multiline,
        ),
        (
            "text.lowercase",
            "소문자로",
            "모든 문자를 소문자로 바꿉니다.",
            40,
            _lowercase,
            lambda c: _has_text(c) and c.raw_text != c.raw_text.lower(),
        ),
        (
            "text.uppercase",
            "대문자로",
            "모든 문자를 대문자로 바꿉니다.",
            40,
            _uppercase,
            lambda c: _has_text(c) and c.raw_text != c.raw_text.upper(),
        ),
        (
            "text.normalize_newlines",
            "줄바꿈 정규화",
            "CRLF/CR을 LF로 맞춥니다.",
            50,
            _normalize_newlines,
            lambda c: _has_text(c) and ("\r" in c.raw_text),
        ),
    )
    for action_id, title, description, priority, execute, applicable in specs:
        registry.register(
            FunctionAction(
                id=action_id,
                title=title,
                category="text",
                description=description,
                priority=priority,
                network_required=False,
                applicable=applicable,
                execute=execute,
            )
        )


__all__ = ["register_text_actions"]
