"""수동 Contextual Action Palette 코어."""

from .builtins import register_builtin_actions
from .context import build_context
from .executor import ActionExecutor
from .models import ActionContext, ActionResult, ClipboardPaletteAction
from .registry import ActionRegistry, FunctionAction


def create_default_registry() -> ActionRegistry:
    registry = ActionRegistry()
    register_builtin_actions(registry)
    return registry


__all__ = [
    "ActionContext",
    "ActionExecutor",
    "ActionRegistry",
    "ActionResult",
    "ClipboardPaletteAction",
    "FunctionAction",
    "build_context",
    "create_default_registry",
]
