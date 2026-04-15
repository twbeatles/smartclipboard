"""Clipboard feature package."""

from .controller import ClipboardController
from .pipeline import (
    analyze_text_impl,
    apply_copy_rules_impl,
    on_clipboard_change_impl,
    process_actions_impl,
    process_clipboard_impl,
    process_file_clipboard_impl,
    process_image_clipboard_impl,
    process_text_clipboard_impl,
)

__all__ = [
    "ClipboardController",
    "analyze_text_impl",
    "apply_copy_rules_impl",
    "on_clipboard_change_impl",
    "process_actions_impl",
    "process_clipboard_impl",
    "process_file_clipboard_impl",
    "process_image_clipboard_impl",
    "process_text_clipboard_impl",
]
