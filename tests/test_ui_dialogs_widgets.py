import re
import unittest
from unittest import mock

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QListWidgetItem, QWidget

from smartclipboard_app.ui.dialogs.clipboard_actions import ClipboardActionsDialog
from smartclipboard_app.ui.dialogs.hotkeys import DEFAULT_HOTKEYS, HotkeySettingsDialog
from smartclipboard_app.ui.dialogs.secure_vault import SecureVaultDialog
from smartclipboard_app.ui.dialogs.settings import FALLBACK_THEMES, SettingsDialog
from smartclipboard_app.ui.dialogs.snippets import SnippetManagerDialog
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

    def test_secure_vault_copy_marks_internal_copy_flag(self):
        parent = _FakeMiniParent()
        dialog = SecureVaultDialog(parent, _FakeVaultDB(), _FakeVaultManager())
        try:
            dialog.copy_item(1, b"encrypted")
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
