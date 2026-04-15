"""Compatibility shim for clipboard runtime operations."""

from __future__ import annotations

from smartclipboard_app.features.clipboard import pipeline as _pipeline


def on_clipboard_change_impl(self, qtimer_cls):
    return _pipeline.on_clipboard_change_impl(self, qtimer_cls)


def process_file_clipboard_impl(self, mime_data, logger):
    return _pipeline.process_file_clipboard_impl(self, mime_data, logger)


def process_clipboard_impl(self, logger):
    if self.is_monitoring_paused:
        return

    try:
        mime_data = self.clipboard.mimeData()
        if mime_data.hasUrls() and process_file_clipboard_impl(self, mime_data, logger):
            return
        if mime_data.hasImage():
            self._process_image_clipboard(mime_data)
            return
        if mime_data.hasText():
            self._process_text_clipboard(mime_data)
    except Exception:
        logger.exception("Clipboard access error")


def process_image_clipboard_impl(self, mime_data, logger, qbytearray_cls, qbuffer_cls, hashlib_mod, toast_cls):
    return _pipeline.process_image_clipboard_impl(
        self,
        mime_data,
        logger,
        qbytearray_cls,
        qbuffer_cls,
        hashlib_mod,
        toast_cls,
    )


def process_text_clipboard_impl(self, mime_data, logger):
    return _pipeline.process_text_clipboard_impl(self, mime_data, logger)


def process_actions_impl(self, text, item_id, logger, toast_cls):
    return _pipeline.process_actions_impl(self, text, item_id, logger, toast_cls)


def apply_copy_rules_impl(self, text, logger, re_module):
    return _pipeline.apply_copy_rules_impl(self, text, logger, re_module)


def analyze_text_impl(text, re_url, re_hex_color, re_rgb_color, re_hsl_color, code_indicators):
    return _pipeline.analyze_text_impl(text, re_url, re_hex_color, re_rgb_color, re_hsl_color, code_indicators)


__all__ = [
    "analyze_text_impl",
    "apply_copy_rules_impl",
    "on_clipboard_change_impl",
    "process_actions_impl",
    "process_clipboard_impl",
    "process_file_clipboard_impl",
    "process_image_clipboard_impl",
    "process_text_clipboard_impl",
]
