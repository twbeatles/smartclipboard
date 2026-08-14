"""URL Action. 제목 조회는 UI에서 Worker로 실행한다."""

from __future__ import annotations

from urllib.parse import urlparse

from ..models import ActionContext, ActionResult
from ..registry import FunctionAction

QR_MAX_CHARS = 2048


def _has_url(context: ActionContext) -> bool:
    return bool(context.url) and context.content_type not in {"image", "file", "files"}


def _has_text(context: ActionContext) -> bool:
    return bool(context.raw_text) and context.content_type not in {"image", "file", "files"}


def qr_text_is_supported(text: str) -> bool:
    return bool(text) and len(text) <= QR_MAX_CHARS


def _qr_supported(context: ActionContext) -> bool:
    return _has_text(context) and qr_text_is_supported(context.raw_text)


def _domain_of(url: str) -> str:
    parsed = urlparse(url)
    return parsed.hostname or parsed.netloc or ""


def _open(context: ActionContext) -> ActionResult:
    url = context.url or context.raw_text
    mixed = bool(context.url and context.raw_text.strip() != context.url)
    return ActionResult(
        kind="url",
        value=url,
        copy_to_clipboard=False,
        metadata={"open_browser": True, "confirm_open": mixed},
    )


def _copy_domain(context: ActionContext) -> ActionResult:
    return ActionResult(
        kind="text",
        value=context.domain or _domain_of(context.url or ""),
        copy_to_clipboard=True,
        preview=False,
    )


def _markdown_link(context: ActionContext) -> ActionResult:
    url = context.url or context.raw_text
    title = str(context.metadata.get("url_title") or "").strip() or (context.domain or _domain_of(url) or url)
    return ActionResult(
        kind="text",
        value=f"[{title}]({url})",
        copy_to_clipboard=True,
        preview=False,
    )


def _fetch_title(context: ActionContext) -> ActionResult:
    url = context.url or ""
    return ActionResult(
        kind="info",
        value=url,
        preview=True,
        copy_to_clipboard=False,
        metadata={"async": "fetch_title", "url": url, "item_id": context.item_id},
    )


def _qr(context: ActionContext) -> ActionResult:
    return ActionResult(
        kind="qr",
        value=context.raw_text,
        preview=True,
        copy_to_clipboard=False,
    )


def register_url_actions(registry) -> None:
    registry.register(
        FunctionAction(
            id="url.open",
            title="페이지 열기",
            category="url",
            description="기본 브라우저에서 URL을 엽니다.",
            priority=110,
            network_required=False,
            applicable=lambda context: _has_url(context) and not context.is_sensitive,
            execute=_open,
        )
    )
    registry.register(
        FunctionAction(
            id="url.copy_domain",
            title="도메인 복사",
            category="url",
            description="호스트 이름만 복사합니다.",
            priority=105,
            network_required=False,
            applicable=_has_url,
            execute=_copy_domain,
        )
    )
    registry.register(
        FunctionAction(
            id="url.markdown_link",
            title="Markdown 링크 만들기",
            category="url",
            description="제목과 URL로 마크다운 링크를 만듭니다.",
            priority=100,
            network_required=False,
            applicable=_has_url,
            execute=_markdown_link,
        )
    )
    registry.register(
        FunctionAction(
            id="url.fetch_title",
            title="페이지 제목 가져오기",
            category="url",
            description="페이지 제목을 조회합니다.",
            priority=95,
            network_required=True,
            applicable=_has_url,
            execute=_fetch_title,
        )
    )
    registry.register(
        FunctionAction(
            id="url.qr",
            title="QR 코드",
            category="url",
            description="현재 내용으로 QR 코드를 만듭니다.",
            priority=50,
            network_required=False,
            applicable=_qr_supported,
            execute=_qr,
        )
    )


__all__ = ["QR_MAX_CHARS", "qr_text_is_supported", "register_url_actions"]
