from __future__ import annotations

from .automation import ClipboardActionsMixin, CopyRulesMixin, SnippetSettingsMixin


class RulesSnippetsActionsMixin(SnippetSettingsMixin, CopyRulesMixin, ClipboardActionsMixin):
    """Compatibility facade for rules/snippets/actions mixins."""


__all__ = ["RulesSnippetsActionsMixin"]
