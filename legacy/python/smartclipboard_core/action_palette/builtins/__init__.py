"""Built-in Action Palette actions."""

from .developer import register_developer_actions
from .phone import register_phone_actions
from .search import register_search_actions
from .text import register_text_actions
from .url import register_url_actions


def register_builtin_actions(registry) -> None:
    register_text_actions(registry)
    register_phone_actions(registry)
    register_url_actions(registry)
    register_developer_actions(registry)
    register_search_actions(registry)


__all__ = ["register_builtin_actions"]
