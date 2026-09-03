"""Clipboard feature controller."""

from __future__ import annotations

from smartclipboard_app.features.shared.controller import FeatureController

from .services import (
    analyze_text_impl,
    apply_copy_rules_impl,
    on_clipboard_change_impl,
    process_actions_impl,
    process_clipboard_impl,
    process_image_clipboard_impl,
    process_text_clipboard_impl,
)


class ClipboardController(FeatureController):
    def on_clipboard_change(self, qtimer_cls):
        self.sync()
        return on_clipboard_change_impl(self.window, qtimer_cls)

    def process_clipboard(self, logger):
        self.sync()
        return process_clipboard_impl(self.window, logger)

    def process_image_clipboard(self, mime_data, logger, qbytearray_cls, qbuffer_cls, hashlib_mod, toast_cls):
        self.sync()
        return process_image_clipboard_impl(
            self.window,
            mime_data,
            logger,
            qbytearray_cls,
            qbuffer_cls,
            hashlib_mod,
            toast_cls,
        )

    def process_text_clipboard(self, mime_data, logger):
        self.sync()
        return process_text_clipboard_impl(self.window, mime_data, logger)

    def process_actions(self, text, item_id, logger, toast_cls):
        self.sync()
        return process_actions_impl(self.window, text, item_id, logger, toast_cls)

    def apply_copy_rules(self, text, logger, re_module):
        self.sync()
        return apply_copy_rules_impl(self.window, text, logger, re_module)

    def analyze_text(self, text, re_url, re_hex_color, re_rgb_color, re_hsl_color, code_indicators):
        return analyze_text_impl(text, re_url, re_hex_color, re_rgb_color, re_hsl_color, code_indicators)
