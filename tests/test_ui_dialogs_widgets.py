import json
import re
import unittest
from unittest import mock

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QListWidgetItem, QMessageBox, QPushButton, QWidget

from smartclipboard_app.ui.dialogs.clipboard_actions import ClipboardActionsDialog
from smartclipboard_app.ui.dialogs.collections import CollectionManagerDialog
from smartclipboard_app.ui.dialogs.hotkeys import DEFAULT_HOTKEYS, HotkeySettingsDialog
from smartclipboard_app.ui.dialogs.secure_vault import SecureVaultDialog
from smartclipboard_app.ui.dialogs.settings import FALLBACK_THEMES, SettingsDialog
from smartclipboard_app.ui.dialogs.snippets import SnippetDialog, SnippetManagerDialog, validate_snippet_shortcut
from smartclipboard_app.ui.mainwindow_parts.table_ops import get_display_items_impl
from smartclipboard_app.ui.mainwindow_parts.tray_hotkey_ops import paste_last_item_slot_impl
from smartclipboard_app.ui.mainwindow_parts.tray_hotkey_ops import register_hotkeys_impl
from smartclipboard_app.ui.mainwindow_parts.ui_dragdrop_ops import handle_drop_event_body
from smartclipboard_app.ui.widgets.floating_mini_window import FloatingMiniWindow


class _FakeSettingsDB:
    def __init__(self, values=None):
        self.values = dict(values or {})
        self.saved = {}

    def get_setting(self, key, default=None):
        return self.values.get(key, default)

    def set_setting(self, key, value):
        self.saved[key] = value
        self.values[key] = value


class _FakeActionDB:
    def __init__(self, duplicate=False):
        self.duplicate = duplicate
        self.added = []

    def get_clipboard_actions(self):
        return []

    def is_duplicate_clipboard_action(self, pattern, action_type, action_params="{}"):
        return self.duplicate

    def add_clipboard_action(self, name, pattern, action_type, action_params="{}"):
        self.added.append((name, pattern, action_type, action_params))
        return True

    def toggle_clipboard_action(self, action_id, enabled):
        return None

    def delete_clipboard_action(self, action_id):
        return None


class _FakeActionManager:
    def reload_actions(self):
        return None


class _FakeMiniDB:
    def __init__(self):
        self.incremented = []

    def get_items(self, _q, _filter):
        return []

    def get_content(self, _pid):
        return ("mini-copy-text", None, "TEXT")

    def increment_use_count(self, pid):
        self.incremented.append(pid)


class _FakeMiniParent(QWidget):
    current_theme = "dark"

    def __init__(self):
        super().__init__()
        self.is_internal_copy = False

    def show(self):
        return None

    def activateWindow(self):
        return None

    def statusBar(self):
        return None


class _FakeVaultDB:
    def get_vault_items(self):
        return []


class _FakeVaultManager:
    is_unlocked = True

    def decrypt(self, _encrypted_data):
        return "vault-secret"

    def has_master_password(self):
        return True

    def lock(self):
        return None


class _FakeSnippetDB:
    def get_snippets(self, category=""):
        return [(1, "welcome", "snippet-text", "", "일반")]


class _FakeSnippetSaveDB(_FakeSettingsDB):
    def __init__(self):
        super().__init__({"hotkeys": json.dumps(DEFAULT_HOTKEYS)})
        self.snippets = [(1, "existing", "text", "Ctrl+Alt+2", "일반")]
        self.added = []

    def get_snippets(self, category=""):
        return list(self.snippets)

    def add_snippet(self, name, content, shortcut="", category="일반"):
        self.added.append((name, content, shortcut, category))
        return True

    def update_snippet(self, snippet_id, name, content, shortcut="", category="일반"):
        self.added.append((snippet_id, name, content, shortcut, category))
        return True


class _FakeCollectionParent(QWidget):
    def __init__(self):
        super().__init__()
        self.refresh_calls = 0
        self.load_calls = 0

    def refresh_collection_filter_options(self):
        self.refresh_calls += 1

    def load_data(self):
        self.load_calls += 1


class _FakeCollectionsDB:
    def __init__(self):
        self.collections = [
            (10, "Work", "📁", "#123456", "2026-03-25 10:00:00"),
            (11, "Ideas", "💡", "#654321", "2026-03-25 11:00:00"),
        ]
        self.deleted = []

    def get_collections(self):
        return list(self.collections)

    def delete_collection(self, collection_id):
        self.deleted.append(collection_id)
        self.collections = [row for row in self.collections if row[0] != collection_id]
        return True


class _FakeSignal:
    def __init__(self):
        self.calls = 0

    def emit(self):
        self.calls += 1


class _FakeHotkeyWindow:
    def __init__(self):
        self.db = _FakeSettingsDB({"hotkeys": json.dumps(DEFAULT_HOTKEYS), "mini_window_enabled": "true"})
        self.show_main_signal = _FakeSignal()
        self.toggle_mini_signal = _FakeSignal()
        self.paste_last_signal = _FakeSignal()
        self._registered_hotkeys = ["old-main", "old-mini", "old-paste"]
        self._last_hotkey_error = ""


class _FakeClipboardWriter:
    def __init__(self):
        self.text_value = None
        self.pixmap_value = None

    def setText(self, text):
        self.text_value = text

    def setPixmap(self, pixmap):
        self.pixmap_value = pixmap


class _ImmediateTimer:
    calls = []

    @classmethod
    def reset(cls):
        cls.calls = []

    @classmethod
    def singleShot(cls, delay, callback):
        cls.calls.append(delay)
        callback()


class _FakePasteKeyboard:
    def __init__(self):
        self.sent = []

    def send(self, keys):
        self.sent.append(keys)


class _FakePasteLastDB:
    def __init__(self):
        self.incremented = []
        self.contents = {
            10: ("pinned-old", None, "TEXT"),
            11: ("latest-normal", None, "TEXT"),
        }

    def get_items(self, _query, _filter_type):
        return [
            (10, "pinned-old", "TEXT", "2026-04-01 09:00:00", 1, 0, 0),
            (11, "latest-normal", "TEXT", "2026-04-01 10:00:00", 0, 0, 0),
        ]

    def get_content(self, pid):
        return self.contents.get(pid)

    def increment_use_count(self, pid):
        self.incremented.append(pid)


class _StaticTextControl:
    def __init__(self, value):
        self.value = value

    def text(self):
        return self.value

    def currentText(self):
        return self.value


class _FakeSortedSearchDB:
    def search_items(self, *_args, **_kwargs):
        return [
            (1, "alpha", "TEXT", "2026-04-01 09:00:00", 1, 0, 0),
            (2, "bravo", "TEXT", "2026-04-01 09:01:00", 1, 0, 1),
            (3, "omega", "TEXT", "2026-04-01 09:02:00", 0, 0, 0),
        ]


class _FakeTableWindow:
    def __init__(self):
        self.db = _FakeSortedSearchDB()
        self.search_input = _StaticTextControl("")
        self.filter_combo = _StaticTextControl("전체")
        self.current_tag_filter = None
        self.current_collection_filter = "__all__"
        self.sort_column = 2
        self.sort_order = Qt.SortOrder.DescendingOrder


class _PasswordRotatingVaultDB:
    def __init__(self):
        self.rows = [(1, b"enc-old", "secret", "2026-04-01 10:00:00")]

    def get_vault_items(self):
        return list(self.rows)


class _PasswordRotatingVaultManager:
    is_unlocked = True

    def __init__(self, db):
        self.db = db

    def decrypt(self, encrypted_data):
        return "vault-secret" if encrypted_data == self.db.rows[0][1] else None

    def has_master_password(self):
        return True

    def lock(self):
        return None

    def change_master_password(self, current_password, new_password):
        if current_password != "old-pass" or new_password != "new-pass!1":
            return False
        self.db.rows[0] = (1, b"enc-new", "secret", "2026-04-01 10:00:00")
        return True


class _FailingKeyboard:
    def __init__(self):
        self.handles = []
        self.removed = []

    def add_hotkey(self, hotkey, callback):
        if hotkey == "bad-hotkey":
            raise RuntimeError("registration failed")
        handle = f"handle:{hotkey}:{len(self.handles)}"
        self.handles.append((hotkey, callback, handle))
        return handle

    def remove_hotkey(self, handle):
        self.removed.append(handle)


class _FakeDragItem:
    def __init__(self, text, item_id):
        self._text = text
        self._item_id = item_id

    def text(self):
        return self._text

    def data(self, _role):
        return self._item_id


class _FakeDragIndex:
    def __init__(self, row):
        self._row = row

    def row(self):
        return self._row


class _FakeDragSelectionModel:
    def __init__(self, selected_row):
        self._selected_row = selected_row

    def selectedRows(self):
        return [_FakeDragIndex(self._selected_row)]


class _FakeDragTable:
    def __init__(self):
        self._items = {
            0: _FakeDragItem("📌", 100),
            1: _FakeDragItem("📌", 101),
        }

    def rowAt(self, _y):
        return 0

    def selectionModel(self):
        return _FakeDragSelectionModel(1)

    def item(self, row, _column):
        return self._items.get(row)

    def rowCount(self):
        return len(self._items)


class _FakeDragDB:
    def __init__(self):
        self.ordered_ids = None

    def update_pin_orders(self, ordered_ids):
        self.ordered_ids = list(ordered_ids)
        return True


class _FakeDragStatusBar:
    def __init__(self):
        self.messages = []

    def showMessage(self, message, _duration):
        self.messages.append(message)


class _FakeDragPosition:
    def y(self):
        return 0


class _FakeDragEvent:
    def __init__(self):
        self.accepted = False
        self.ignored = False

    def position(self):
        return _FakeDragPosition()

    def accept(self):
        self.accepted = True

    def ignore(self):
        self.ignored = True


class _FakeDragWindow:
    def __init__(self):
        self.table = _FakeDragTable()
        self.db = _FakeDragDB()
        self._status_bar = _FakeDragStatusBar()
        self.load_calls = 0

    def statusBar(self):
        return self._status_bar

    def load_data(self):
        self.load_calls += 1


class UiDialogsWidgetsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_settings_dialog_handles_invalid_settings_values(self):
        db = _FakeSettingsDB(
            {
                "max_history": "not-a-number",
                "mini_window_enabled": "invalid-bool",
                "log_level": "not-a-level",
            }
        )
        dialog = SettingsDialog(None, db, current_theme="unknown-theme", themes=FALLBACK_THEMES, max_history=123)
        try:
            self.assertEqual(dialog.max_history_spin.value(), 123)
            self.assertTrue(dialog.mini_window_enabled.isChecked())
            self.assertEqual(dialog.log_level_combo.currentData(), "INFO")
        finally:
            dialog.close()

    def test_hotkey_dialog_recovers_from_invalid_json(self):
        db = _FakeSettingsDB({"hotkeys": "{bad-json"})
        dialog = HotkeySettingsDialog(None, db, default_hotkeys=DEFAULT_HOTKEYS)
        try:
            self.assertEqual(dialog.input_main.text(), DEFAULT_HOTKEYS["show_main"])
            self.assertEqual(dialog.input_mini.text(), DEFAULT_HOTKEYS["show_mini"])
            self.assertEqual(dialog.input_paste.text(), DEFAULT_HOTKEYS["paste_last"])
            self.assertIn("hotkeys", db.saved)
        finally:
            dialog.close()

    def test_default_actions_use_correct_phone_regex(self):
        db = _FakeActionDB(duplicate=False)
        manager = _FakeActionManager()
        dialog = ClipboardActionsDialog(None, db, manager)
        try:
            with mock.patch("PyQt6.QtWidgets.QMessageBox.information"):
                dialog.add_default_actions()
            phone_action = [entry for entry in db.added if entry[2] == "format_phone"]
            self.assertEqual(len(phone_action), 1)
            pattern = phone_action[0][1]
            self.assertEqual(pattern, r"^0\d{9,10}$")
            self.assertTrue(re.search(pattern, "01012345678"))
        finally:
            dialog.close()

    def test_default_actions_skip_duplicates(self):
        db = _FakeActionDB(duplicate=True)
        manager = _FakeActionManager()
        dialog = ClipboardActionsDialog(None, db, manager)
        try:
            with mock.patch("PyQt6.QtWidgets.QMessageBox.information") as info_mock:
                dialog.add_default_actions()
            self.assertEqual(db.added, [])
            self.assertTrue(info_mock.called)
            self.assertIn("중복 건너뜀: 2개", info_mock.call_args[0][2])
        finally:
            dialog.close()

    def test_floating_mini_window_sets_internal_copy_flag(self):
        db = _FakeMiniDB()
        parent = _FakeMiniParent()
        window = FloatingMiniWindow(db, parent=parent)
        try:
            item = QListWidgetItem("row")
            item.setData(Qt.ItemDataRole.UserRole, 7)
            window.on_item_double_clicked(item)
            self.assertTrue(parent.is_internal_copy)
            self.assertEqual(db.incremented, [7])
        finally:
            window.close()

    def test_paste_last_hotkey_uses_most_recent_item_not_pinned_sort_order(self):
        window = _FakeMiniParent()
        window.db = _FakePasteLastDB()
        window.clipboard = _FakeClipboardWriter()
        keyboard = _FakePasteKeyboard()
        _ImmediateTimer.reset()

        paste_last_item_slot_impl(window, mock.Mock(), mock.Mock(), _ImmediateTimer, keyboard)

        self.assertEqual(window.clipboard.text_value, "latest-normal")
        self.assertEqual(window.db.incremented, [11])
        self.assertTrue(window.is_internal_copy)
        self.assertEqual(_ImmediateTimer.calls, [100])
        self.assertEqual(keyboard.sent, ["ctrl+v"])

    def test_display_sort_keeps_pinned_rows_above_unpinned_in_descending_order(self):
        window = _FakeTableWindow()

        items = get_display_items_impl(window)

        self.assertEqual([row[0] for row in items], [2, 1, 3])

    def test_secure_vault_copy_marks_internal_copy_flag(self):
        parent = _FakeMiniParent()
        dialog = SecureVaultDialog(parent, _FakeVaultDB(), _FakeVaultManager())
        try:
            dialog.copy_item(1, b"encrypted")
            self.assertTrue(parent.is_internal_copy)
        finally:
            dialog.close()
            parent.close()

    def test_secure_vault_copy_button_uses_latest_encrypted_payload_after_password_change(self):
        parent = _FakeMiniParent()
        db = _PasswordRotatingVaultDB()
        manager = _PasswordRotatingVaultManager(db)
        dialog = SecureVaultDialog(parent, db, manager)
        clipboard = QApplication.clipboard()
        try:
            clipboard.setText("")
            button_widget = dialog.table.cellWidget(0, 2)
            copy_buttons = [btn for btn in button_widget.findChildren(QPushButton) if btn.toolTip() == "복호화하여 복사"]
            old_copy_button = copy_buttons[0]

            with mock.patch(
                "PyQt6.QtWidgets.QInputDialog.getText",
                side_effect=[("old-pass", True), ("new-pass!1", True), ("new-pass!1", True)],
            ), mock.patch("PyQt6.QtWidgets.QMessageBox.information"), mock.patch(
                "smartclipboard_app.ui.dialogs.secure_vault.QTimer.singleShot"
            ):
                dialog.change_master_password()
                old_copy_button.click()

            self.assertEqual(clipboard.text(), "vault-secret")
            self.assertTrue(parent.is_internal_copy)
        finally:
            dialog.close()
            parent.close()

    def test_snippet_manager_use_snippet_marks_internal_copy_flag(self):
        parent = _FakeMiniParent()
        dialog = SnippetManagerDialog(parent, _FakeSnippetDB())
        try:
            dialog.table.selectRow(0)
            dialog.use_snippet()
            self.assertTrue(parent.is_internal_copy)
        finally:
            dialog.close()
            parent.close()

    def test_dragdrop_helper_updates_pin_order_without_qt_name_error(self):
        window = _FakeDragWindow()
        event = _FakeDragEvent()
        with mock.patch("smartclipboard_app.ui.mainwindow_parts.ui_dragdrop_ops.QTimer.singleShot") as single_shot:
            result = handle_drop_event_body(window, event, {}, mock.Mock())

        self.assertTrue(result)
        self.assertEqual(window.db.ordered_ids, [101, 100])
        self.assertTrue(event.accepted)
        single_shot.assert_called_once_with(50, window.load_data)

    def test_register_hotkeys_impl_restores_previous_handles_on_failure(self):
        window = _FakeHotkeyWindow()
        keyboard = _FailingKeyboard()
        logger = mock.Mock()

        ok = register_hotkeys_impl(
            window,
            logger,
            keyboard,
            json,
            DEFAULT_HOTKEYS,
            hotkeys_override={
                "show_main": "ctrl+alt+1",
                "show_mini": "bad-hotkey",
                "paste_last": "ctrl+alt+3",
            },
            persist=True,
        )

        self.assertFalse(ok)
        self.assertIn("registration failed", window._last_hotkey_error)
        self.assertEqual(len(window._registered_hotkeys), 3)
        self.assertTrue(window._registered_hotkeys[0].startswith("handle:ctrl+shift+v"))
        self.assertIn("old-main", keyboard.removed)
        self.assertIn("old-mini", keyboard.removed)
        self.assertIn("old-paste", keyboard.removed)
        self.assertNotIn("hotkeys", window.db.saved)

    def test_snippet_shortcut_validation_and_save_uses_canonical_text(self):
        db = _FakeSnippetSaveDB()
        self.assertIsNotNone(validate_snippet_shortcut(db, "Ctrl+F"))
        self.assertIsNone(validate_snippet_shortcut(db, "ctrl+alt+1"))

        dialog = SnippetDialog(None, db)
        try:
            dialog.name_input.setText("greeting")
            dialog.content_input.setPlainText("hello")
            dialog.shortcut_input.setText("ctrl+alt+1")
            dialog.save_snippet()
            self.assertEqual(db.added, [("greeting", "hello", "Ctrl+Alt+1", "일반")])
        finally:
            dialog.close()

    def test_collection_manager_delete_refreshes_parent_filters(self):
        parent = _FakeCollectionParent()
        db = _FakeCollectionsDB()
        dialog = CollectionManagerDialog(parent, db)
        try:
            dialog.table.selectRow(0)
            with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
                dialog.delete_collection()
            self.assertEqual(db.deleted, [10])
            self.assertEqual(parent.refresh_calls, 1)
            self.assertEqual(parent.load_calls, 1)
        finally:
            dialog.close()
            parent.close()

    def test_secure_vault_clipboard_clear_is_delayed_and_conditional(self):
        parent = _FakeMiniParent()
        dialog = SecureVaultDialog(parent, _FakeVaultDB(), _FakeVaultManager())
        clipboard = QApplication.clipboard()
        try:
            with mock.patch("smartclipboard_app.ui.dialogs.secure_vault.QTimer.singleShot") as single_shot:
                dialog.copy_item(1, b"encrypted")
            single_shot.assert_called_once()
            self.assertEqual(single_shot.call_args[0][0], 30000)

            clipboard.setText("different-text")
            dialog._clear_clipboard_if_unchanged("vault-secret")
            self.assertEqual(clipboard.text(), "different-text")

            clipboard.setText("vault-secret")
            dialog._clear_clipboard_if_unchanged("vault-secret")
            self.assertEqual(clipboard.text(), "")
        finally:
            dialog.close()
            parent.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
