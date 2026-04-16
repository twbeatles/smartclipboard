"""MainWindow clipboard runtime feature operations."""

from __future__ import annotations

from smartclipboard_app.ui.clipboard_guard import extract_local_file_paths, mark_internal_copy
from smartclipboard_core.automation.formatters import replacement_text_from_result
from smartclipboard_core.file_paths import describe_file_paths, file_content_from_paths


def on_clipboard_change_impl(self, qtimer_cls):
    if self.is_privacy_mode or self.is_internal_copy:
        self.is_internal_copy = False
        return

    if self._clipboard_debounce_timer is not None:
        self._clipboard_debounce_timer.stop()
        self._clipboard_debounce_timer.deleteLater()

    self._clipboard_debounce_timer = qtimer_cls(self)
    self._clipboard_debounce_timer.setSingleShot(True)
    self._clipboard_debounce_timer.timeout.connect(self.process_clipboard)
    self._clipboard_debounce_timer.start(100)


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
    try:
        image = self.clipboard.image()
        if image.isNull():
            return

        ba = qbytearray_cls()
        buffer = qbuffer_cls(ba)
        buffer.open(qbuffer_cls.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        blob_data = ba.data()

        max_image_size = 5 * 1024 * 1024
        if len(blob_data) > max_image_size:
            logger.warning(f"Image too large ({len(blob_data)} bytes), skipping")
            toast_cls.show_toast(self, "이미지가 너무 큽니다(최대 5MB)", duration=2500, toast_type="warning")
            return

        img_hash = hashlib_mod.md5(blob_data).hexdigest()
        if hasattr(self, "_last_image_hash") and self._last_image_hash == img_hash:
            logger.debug("Duplicate image skipped")
            return
        self._last_image_hash = img_hash

        if self.db.add_item("[이미지 캡처]", blob_data, "IMAGE"):
            if self.isVisible():
                self.load_data()
                self.update_status_bar()
            else:
                self.is_data_dirty = True
    except Exception:
        logger.exception("Image processing error")


def process_text_clipboard_impl(self, mime_data, logger):
    try:
        raw_text = mime_data.text()
        if not raw_text:
            return

        text = self.apply_copy_rules(raw_text)
        normalized_text = text.strip()
        if not normalized_text:
            return

        tag = self.analyze_text(normalized_text)
        item_id = self.db.add_item(text, None, tag)
        if item_id:
            self._process_actions(normalized_text, item_id)
            if self.isVisible():
                self.load_data()
                self.update_status_bar()
            else:
                self.is_data_dirty = True
    except Exception:
        logger.exception("Text processing error")


def process_file_clipboard_impl(self, mime_data, logger):
    try:
        file_paths = extract_local_file_paths(mime_data)
        if not file_paths:
            return False

        content = file_content_from_paths(file_paths)
        if not content:
            return False

        item_id = self.db.add_item(content, None, "FILE")
        if not item_id:
            return False

        logger.debug("File clipboard captured: %s", describe_file_paths(file_paths))
        if self.isVisible():
            self.load_data()
            self.update_status_bar()
        else:
            self.is_data_dirty = True
        return True
    except Exception:
        logger.exception("File clipboard processing error")
        return False


def _update_text_item_after_actions(self, item_id, new_text, logger):
    normalized_text = str(new_text or "")
    if not normalized_text:
        return False

    item_type = self.analyze_text(normalized_text.strip()) if normalized_text.strip() else "TEXT"
    with self.db.lock:
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT 1 FROM history WHERE id = ? LIMIT 1", (item_id,))
            if cursor.fetchone() is None:
                return False
            cursor.execute(
                "UPDATE history SET content = ?, image_data = NULL, type = ?, file_path = '', file_signature = '', url_title = '' "
                "WHERE id = ?",
                (normalized_text, item_type, item_id),
            )
            self.db.conn.commit()
            return cursor.rowcount == 1
        except Exception as exc:
            self.db.conn.rollback()
            logger.debug("Action text update error: %s", exc)
            return False


def process_actions_impl(self, text, item_id, logger, toast_cls):
    try:
        action_results = self.action_manager.process(text, item_id)
        updated_text = text
        updated_by_actions: list[str] = []
        for action_name, result in action_results:
            if not isinstance(result, dict):
                continue
            result_type = result.get("type")
            if result_type == "notify":
                toast_cls.show_toast(
                    self,
                    f"⚡{action_name}: {result.get('message', '')}",
                    duration=3000,
                    toast_type="info",
                )
            elif result_type == "title":
                title = result.get("title")
                if title:
                    toast_cls.show_toast(self, f"🔗 {title[:50]}...", duration=2500, toast_type="info")
            elif result_type == "replace_text":
                replacement_text = replacement_text_from_result(result)
                if replacement_text is None or replacement_text == updated_text:
                    continue
                updated_text = replacement_text
                updated_by_actions.append(action_name)

        if updated_by_actions and updated_text != text:
            if _update_text_item_after_actions(self, item_id, updated_text, logger):
                mark_internal_copy(self)
                self.clipboard.setText(updated_text)
                logger.info("Applied clipboard action text replacement: %s", ", ".join(updated_by_actions))
            else:
                logger.warning("Clipboard action text replacement skipped; item %s is unavailable", item_id)
    except Exception as action_err:
        logger.debug(f"Action processing error: {action_err}")


def apply_copy_rules_impl(self, text, logger, re_module):
    if self._rules_cache_dirty or self._rules_cache is None:
        self._rules_cache = self.db.get_copy_rules()
        self._rules_cache_dirty = False
        logger.debug("Copy rules cache refreshed")

    for rule in self._rules_cache:
        rid, name, pattern, action, replacement, enabled, priority = rule
        if not enabled:
            continue
        if not pattern:
            logger.warning(f"Empty pattern in copy rule '{name}' (id={rid}), skipping")
            continue
        try:
            if re_module.search(pattern, text):
                if action == "trim":
                    text = text.strip()
                elif action == "lowercase":
                    text = text.lower()
                elif action == "uppercase":
                    text = text.upper()
                elif action == "remove_newlines":
                    text = text.replace("\n", " ").replace("\r", "")
                elif action == "custom_replace":
                    text = re_module.sub(pattern, replacement or "", text)
                logger.debug(f"Rule '{name}' applied")
        except re_module.error as regex_exc:
            logger.warning(f"Invalid regex in rule '{name}': {regex_exc}")
    return text


def analyze_text_impl(text, re_url, re_hex_color, re_rgb_color, re_hsl_color, code_indicators):
    if re_url.match(text):
        return "LINK"
    if re_hex_color.match(text):
        return "COLOR"
    if re_rgb_color.match(text):
        return "COLOR"
    if re_hsl_color.match(text):
        return "COLOR"
    if any(x in text for x in code_indicators):
        return "CODE"
    return "TEXT"
