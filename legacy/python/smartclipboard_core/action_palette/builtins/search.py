"""검색 Action."""

from __future__ import annotations

from urllib.parse import quote

from ..models import ActionContext, ActionResult
from ..registry import FunctionAction

_MAX_QUERY = 500


def build_google_search_url(text: str) -> str:
    query = str(text or "").strip()[:_MAX_QUERY]
    if not query:
        return "https://www.google.com/search"
    return f"https://www.google.com/search?q={quote(query, safe='')}"


def _has_query(context: ActionContext) -> bool:
    return bool(context.normalized_text) and context.content_type not in {"image", "file", "files"}


def _google(context: ActionContext) -> ActionResult:
    query = context.raw_text.strip()[:_MAX_QUERY]
    return ActionResult(
        kind="url",
        value=build_google_search_url(query),
        copy_to_clipboard=False,
        metadata={"open_browser": True, "query": query},
    )


def register_search_actions(registry) -> None:
    registry.register(
        FunctionAction(
            id="search.google",
            title="Google에서 검색",
            category="search",
            description="현재 내용으로 Google 검색을 엽니다.",
            priority=20,
            network_required=True,
            applicable=_has_query,
            execute=_google,
        )
    )


__all__ = ["build_google_search_url", "register_search_actions"]
