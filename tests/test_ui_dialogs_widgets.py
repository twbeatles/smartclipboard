import json
import os
import re
import tempfile
import unittest
from contextlib import contextmanager
from unittest import mock

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QTableWidget, QWidget

import smartclipboard_app.legacy_main_src as legacy_main_src
import smartclipboard_app.ui.mainwindow_parts.menu_ops as menu_ops
from smartclipboard_core.file_paths import file_content_from_paths
from smartclipboard_core.database import ClipboardDB
from smartclipboard_app.ui.dialogs.clipboard_actions import ClipboardActionsDialog
from smartclipboard_app.ui.dialogs.collections import CollectionManagerDialog
from smartclipboard_app.ui.dialogs.copy_rules import CopyRuleEditDialog
from smartclipboard_app.ui.dialogs.export_dialog import ExportDialog
from smartclipboard_app.ui.dialogs.hotkeys import DEFAULT_HOTKEYS, HotkeySettingsDialog
from smartclipboard_app.ui.dialogs.import_dialog import ImportDialog
from smartclipboard_app.ui.dialogs.secure_vault import SecureVaultDialog
from smartclipboard_app.ui.dialogs.settings import FALLBACK_THEMES, SettingsDialog
from smartclipboard_app.ui.mainwindow_parts.clipboard_runtime_ops import process_actions_impl, process_clipboard_impl
from smartclipboard_app.ui.mainwindow_parts.status_lifecycle_ops import quit_app_impl, run_periodic_cleanup_impl
from smartclipboard_app.ui.dialogs.snippets import SnippetDialog, SnippetManagerDialog, validate_snippet_shortcut
from smartclipboard_app.ui.mainwindow_parts.table_ops import get_display_items_impl, load_data_impl, populate_table_impl
from smartclipboard_app.ui.mainwindow_parts.tray_hotkey_ops import paste_last_item_slot_impl
from smartclipboard_app.ui.mainwindow_parts.tray_hotkey_ops import register_hotkeys_impl
from smartclipboard_app.ui.mainwindow_parts.ui_dragdrop_ops import handle_drop_event_body
from smartclipboard_app.ui.widgets.floating_mini_window import FloatingMiniWindow


class _FakeSettingsDB:
    def __init__(self, values=None):
        self.values = dict(values or {})
        self.saved = {}
        self.cleanup_calls = 0

    def get_setting(self, key, default=None):
        return self.values.get(key, default)

    def set_setting(self, key, value):
        self.saved[key] = value
        self.values[key] = value

    def cleanup(self):
        self.cleanup_calls += 1

    def _get_max_history(self):
        return int(self.values.get("max_history", 100))


class _FakeImportExportManager:
    def __init__(self):
        self.last_import_report = {}
        self.last_export_report = {}

    def import_json(self, path):
        self.last_import_report = {
            "success": True,
            "format": "json",
            "path": path,
            "imported": 2,
            "skipped": 0,
            "warnings": [],
            "backup_path": os.path.join(os.getcwd(), "backups", "pre_import_20260412_120000.db"),
            "collection_summary": {"created": 0, "reused": 0, "remapped": 0, "cleared": 0},
        }
        return 2

    def import_csv(self, path):
        self.last_import_report = {
            "success": True,
            "format": "csv",
            "path": path,
            "imported": 1,
            "skipped": 2,
            "warnings": ["CSV import warning"],
            "backup_path": os.path.join(os.getcwd(), "backups", "pre_import_20260412_120001.db"),
            "collection_summary": {"created": 0, "reused": 0, "remapped": 0, "cleared": 1},
        }
        return 1

    def export_json(self, path, *_args, **_kwargs):
        self.last_export_report = {
            "success": True,
            "format": "json",
            "path": path,
            "exported": 3,
            "skipped": 0,
            "warnings": [],
        }
        return 3

    def export_csv(self, path, *_args, **_kwargs):
        self.last_export_report = {
            "success": True,
            "format": "csv",
            "path": path,
            "exported": 2,
            "skipped": 1,
            "warnings": ["CSV export warning"],
        }
        return 2

    def export_markdown(self, path, *_args, **_kwargs):
        self.last_export_report = {
            "success": True,
            "format": "markdown",
            "path": path,
            "exported": 2,
            "skipped": 0,
            "warnings": ["Markdown export warning"],
        }
        return 2


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


class _FakeCopyRuleDB:
    def __init__(self):
        self.added = []

    def is_duplicate_copy_rule(self, pattern, action, replacement="", exclude_id=None):
        return False

    def add_copy_rule(self, name, pattern, action, replacement=""):
        self.added.append((name, pattern, action, replacement))
        return True

    def update_copy_rule(self, *_args, **_kwargs):
        return True


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

    def is_configuration_corrupted(self):
        return False

    def lock(self):
        return None

    def reset_vault(self):
        return True


class _CorruptedVaultManager:
    def __init__(self):
        self.is_unlocked = False
        self.reset_calls = 0
        self._corrupted = True

    def has_master_password(self):
        return False

    def is_configuration_corrupted(self):
        return self._corrupted

    def reset_vault(self):
        self.reset_calls += 1
        self._corrupted = False
        return True

    def lock(self):
        return None


class _FakeMiniListDB:
    def __init__(self, items):
        self._items = items

    def get_items(self, _q, _filter):
        return list(self._items)


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


class _FakeSettingsParent(QWidget):
    def __init__(self):
        super().__init__()
        self._last_hotkey_error = "mini registration failed"
        self.register_calls = 0
        self.theme_changes = []
        self.load_calls = 0
        self.status_updates = 0

    def register_hotkeys(self):
        self.register_calls += 1
        return False if self.register_calls == 1 else True

    def change_theme(self, theme_name: str):
        self.theme_changes.append(theme_name)

    def load_data(self):
        self.load_calls += 1

    def update_status_bar(self):
        self.status_updates += 1


class _FakeClipboardWriter:
    def __init__(self):
        self.text_value = None
        self.pixmap_value = None
        self.mime_data = None

    def setText(self, text):
        self.text_value = text

    def setPixmap(self, pixmap):
        self.pixmap_value = pixmap

    def setMimeData(self, mime_data):
        self.mime_data = mime_data

    def text(self):
        return self.text_value or ""

    def mimeData(self):
        return self.mime_data


class _FakeActionProcessManager:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def process(self, text, item_id=None):
        self.calls.append((text, item_id))
        return list(self.results)


class _FakeActionProcessWindow:
    def __init__(self, db, results):
        self.db = db
        self.action_manager = _FakeActionProcessManager(results)
        self.clipboard = _FakeClipboardWriter()
        self.is_internal_copy = False

    def analyze_text(self, _text):
        return "TEXT"


class _FakeQuitDB:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _FakeQuitApp:
    clipboard_instance = None
    quit_called = False

    @classmethod
    def clipboard(cls):
        return cls.clipboard_instance

    @classmethod
    def quit(cls):
        cls.quit_called = True


class _FakeQuitWindow:
    def __init__(self, clipboard_text):
        self.db = _FakeQuitDB()
        self._vault_clipboard_expected_text = clipboard_text
        self._vault_clipboard_expires_at = 123.0
        self.is_internal_copy = False


class _FakeQuitKeyboard:
    def remove_hotkey(self, _handle):
        return None


@contextmanager
def _workspace_tempdir():
    root = os.path.join(os.getcwd(), ".tmp-unittest")
    os.makedirs(root, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root) as tmpdir:
        yield tmpdir


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


class _FakeMimeData:
    def __init__(self, has_urls=False, has_image=False, has_text=False):
        self._has_urls = has_urls
        self._has_image = has_image
        self._has_text = has_text

    def hasUrls(self):
        return self._has_urls

    def hasImage(self):
        return self._has_image

    def hasText(self):
        return self._has_text


class _FakeRuntimeClipboard:
    def __init__(self, mime_data):
        self._mime_data = mime_data

    def mimeData(self):
        return self._mime_data


class _FakeClipboardRuntimeWindow:
    def __init__(self, mime_data):
        self.is_monitoring_paused = False
        self.clipboard = _FakeRuntimeClipboard(mime_data)
        self.image_calls = 0
        self.text_calls = 0

    def _process_image_clipboard(self, _mime_data):
        self.image_calls += 1

    def _process_text_clipboard(self, _mime_data):
        self.text_calls += 1

    def increment_use_count(self, pid):
        self.incremented.append(pid)


class _FakeFilePasteLastDB:
    def __init__(self, content):
        self.incremented = []
        self.contents = {
            20: (content, None, "FILE"),
        }

    def get_items(self, _query, _filter_type):
        return [
            (20, "files", "FILE", "2026-04-01 10:00:00", 0, 0, 0),
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


class _FakeRelevantSearchDB:
    def search_items(self, *_args, **_kwargs):
        return [
            (1, "high-relevance", "TEXT", "2026-04-01 09:00:00", 1, 0, 0),
            (2, "low-relevance", "TEXT", "2026-04-01 10:00:00", 1, 0, 1),
            (3, "normal-row", "TEXT", "2026-04-01 08:00:00", 0, 0, 0),
        ]


class _FakeSearchWindow:
    def __init__(self, override=False):
        self.db = _FakeRelevantSearchDB()
        self.search_input = _StaticTextControl("relevance")
        self.filter_combo = _StaticTextControl("전체")
        self.current_tag_filter = None
        self.current_collection_filter = "__all__"
        self.sort_column = 3
        self.sort_order = Qt.SortOrder.DescendingOrder
        self._search_sort_override = override


class _FakeStatusLoadWindow:
    def __init__(self):
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.search_input = _StaticTextControl("")
        self.current_tag_filter = None
        self.current_collection_filter = "__all__"
        self.current_theme = "dark"
        self.is_data_dirty = True
        self.status_calls = []

    def _get_display_items(self):
        return []

    def _show_empty_state(self, _theme):
        self.table.setRowCount(1)

    def update_status_bar(self, selection_count=0):
        self.status_calls.append(selection_count)


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


class _FakeMenuWindow(QMainWindow):
    def __init__(self, always_on_top=False):
        super().__init__()
        self.current_theme = "dark"
        self.always_on_top = always_on_top

    def export_history(self):
        return None

    def backup_data(self):
        return None

    def restore_data(self):
        return None

    def quit_app(self):
        return None

    def clear_all_history(self):
        return None

    def show_snippet_manager(self):
        return None

    def show_export_dialog(self):
        return None

    def show_import_dialog(self):
        return None

    def show_trash(self):
        return None

    def show_statistics(self):
        return None

    def toggle_mini_window(self):
        return None

    def toggle_always_on_top(self):
        return None

    def change_theme(self, _theme_key):
        return None

    def check_startup_registry(self):
        return False

    def toggle_startup(self):
        return None

    def show_copy_rules(self):
        return None

    def show_collection_manager(self):
        return None

    def show_clipboard_actions(self):
        return None

    def show_hotkey_settings(self):
        return None

    def show_settings(self):
        return None

    def show_secure_vault(self):
        return None

    def toggle_privacy_mode(self):
        return None

    def toggle_debug_mode(self):
        return None

    def show_shortcuts_dialog(self):
        return None

    def show_about_dialog(self):
        return None


class _FakeShowImportStatusBar:
    def __init__(self):
        self.messages = []

    def showMessage(self, message, duration):
        self.messages.append((message, duration))


class _AcceptedImportDialog:
    def __init__(self, *_args, **_kwargs):
        pass

    def exec(self):
        from PyQt6.QtWidgets import QDialog

        return QDialog.DialogCode.Accepted


class _FakeShowImportWindow:
    def __init__(self):
        self.export_manager = object()
        self.status_bar = _FakeShowImportStatusBar()
        self.calls = []

    def refresh_collection_filter_options(self):
        self.calls.append("refresh")

    def load_data(self):
        self.calls.append("load")

    def statusBar(self):
        return self.status_bar


class _FakeContextIndex:
    def __init__(self, row):
        self._row = row

    def row(self):
        return self._row


class _FakeContextSelectionModel:
    def __init__(self, table):
        self._table = table

    def selectedRows(self):
        return [_FakeContextIndex(row) for row in self._table.selected_rows]


class _FakeContextItem:
    def __init__(self, row):
        self._row = row


class _FakeContextTable:
    def __init__(self, clicked_row, selected_rows):
        self.clicked_row = clicked_row
        self.selected_rows = list(selected_rows)
        self.clear_calls = 0
        self.selected_via_click = []

    def itemAt(self, _pos):
        if self.clicked_row is None:
            return None
        return _FakeContextItem(self.clicked_row)

    def row(self, item):
        return item._row

    def selectionModel(self):
        return _FakeContextSelectionModel(self)

    def clearSelection(self):
        self.clear_calls += 1
        self.selected_rows = []

    def selectRow(self, row):
        self.selected_rows = [row]
        self.selected_via_click.append(row)


class _FakeCleanupDB:
    def __init__(self, expired_count=0, history_deleted=0):
        self.expired_count = expired_count
        self.history_deleted = history_deleted
        self.trash_cleanup_calls = 0

    def cleanup_expired_items(self):
        return self.expired_count

    def cleanup_expired_trash(self):
        self.trash_cleanup_calls += 1

    def cleanup(self):
        return self.history_deleted


class _FakeCleanupWindow:
    def __init__(self, db, visible=True):
        self.db = db
        self._visible = visible
        self.load_calls = 0
        self.status_calls = 0
        self.is_data_dirty = False

    def isVisible(self):
        return self._visible

    def load_data(self):
        self.load_calls += 1

    def update_status_bar(self):
        self.status_calls += 1


class _FakeResetWindow:
    def __init__(self, db, fail_hotkeys=False):
        self.db = db
        self.current_theme = str(db.get_setting("theme", "dark"))
        self.fail_hotkeys = fail_hotkeys
        self.register_calls = 0
        self.theme_apply_calls = 0
        self.log_apply_calls = 0
        self.load_calls = 0
        self.status_calls = 0
        self._last_hotkey_error = "reset hotkey registration failed"

    def apply_theme(self):
        self.theme_apply_calls += 1

    def apply_saved_log_level(self):
        self.log_apply_calls += 1

    def register_hotkeys(self):
        self.register_calls += 1
        if self.fail_hotkeys and self.register_calls == 1:
            return False
        self._last_hotkey_error = ""
        return True

    def load_data(self):
        self.load_calls += 1

    def update_status_bar(self):
        self.status_calls += 1


class _FakeRestoreSignal:
    def __init__(self):
        self.disconnect_calls = 0
        self.connect_calls = 0

    def disconnect(self, _slot):
        self.disconnect_calls += 1

    def connect(self, _slot):
        self.connect_calls += 1


class _FakeRestoreActionManager:
    def __init__(self):
        self.action_completed = _FakeRestoreSignal()
        self.shutdown_calls = 0

    def shutdown(self):
        self.shutdown_calls += 1


class _FakeRestoreDB:
    def __init__(self, db_file, app_dir):
        self.db_file = db_file
        self.app_dir = app_dir
        self.closed = False

    def close(self):
        self.closed = True


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

    def test_settings_dialog_rolls_back_only_mini_window_on_hotkey_failure(self):
        db = _FakeSettingsDB({"mini_window_enabled": "false", "log_level": "INFO"})
        parent = _FakeSettingsParent()
        dialog = SettingsDialog(parent, db, current_theme="dark", themes=FALLBACK_THEMES, max_history=100)
        try:
            dialog.mini_window_enabled.setChecked(True)
            dialog.max_history_spin.setValue(222)
            dialog.log_level_combo.setCurrentIndex(dialog.log_level_combo.findData("DEBUG"))
            with mock.patch.object(QMessageBox, "warning") as warning_mock:
                dialog.save_settings()
            self.assertEqual(db.values["mini_window_enabled"], "false")
            self.assertEqual(db.values["max_history"], 222)
            self.assertEqual(db.values["log_level"], "DEBUG")
            self.assertEqual(parent.register_calls, 2)
            self.assertTrue(warning_mock.called)
            self.assertIn("미니 창", warning_mock.call_args[0][2])
            self.assertTrue(dialog.result())
        finally:
            dialog.close()
            parent.close()

    def test_settings_dialog_runs_cleanup_immediately_when_max_history_decreases(self):
        db = _FakeSettingsDB({"max_history": 200, "mini_window_enabled": "true", "log_level": "INFO"})
        parent = _FakeSettingsParent()
        dialog = SettingsDialog(parent, db, current_theme="dark", themes=FALLBACK_THEMES, max_history=200)
        try:
            dialog.max_history_spin.setValue(120)
            dialog.save_settings()
            self.assertEqual(db.cleanup_calls, 1)
            self.assertEqual(parent.load_calls, 1)
            self.assertEqual(parent.status_updates, 1)
        finally:
            dialog.close()
            parent.close()

    def test_reset_settings_resets_only_core_settings(self):
        db = _FakeSettingsDB(
            {
                "theme": "ocean",
                "max_history": 200,
                "mini_window_enabled": "false",
                "hotkeys": json.dumps(
                    {
                        "show_main": "ctrl+alt+1",
                        "show_mini": "ctrl+alt+2",
                        "paste_last": "ctrl+alt+3",
                    }
                ),
                "log_level": "DEBUG",
                "last_auto_backup_date": "20260415",
            }
        )
        window = _FakeResetWindow(db)

        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), mock.patch.object(
            QMessageBox, "information"
        ) as info_mock, mock.patch.object(QMessageBox, "warning") as warning_mock:
            legacy_main_src.MainWindow.reset_settings(window)

        self.assertEqual(db.values["theme"], "dark")
        self.assertEqual(db.values["max_history"], legacy_main_src.MAX_HISTORY)
        self.assertEqual(db.values["mini_window_enabled"], "true")
        self.assertEqual(json.loads(db.values["hotkeys"]), DEFAULT_HOTKEYS)
        self.assertEqual(db.values["log_level"], "INFO")
        self.assertEqual(db.values["last_auto_backup_date"], "20260415")
        self.assertNotIn("opacity", db.saved)
        self.assertEqual(db.cleanup_calls, 1)
        self.assertEqual(window.theme_apply_calls, 1)
        self.assertEqual(window.log_apply_calls, 1)
        self.assertEqual(window.register_calls, 1)
        self.assertEqual(window.load_calls, 1)
        self.assertEqual(window.status_calls, 1)
        self.assertTrue(info_mock.called)
        self.assertFalse(warning_mock.called)

    def test_reset_settings_rolls_back_only_hotkey_related_values_on_failure(self):
        original_hotkeys = json.dumps(
            {
                "show_main": "ctrl+alt+1",
                "show_mini": "ctrl+alt+2",
                "paste_last": "ctrl+alt+3",
            }
        )
        db = _FakeSettingsDB(
            {
                "theme": "ocean",
                "max_history": 200,
                "mini_window_enabled": "false",
                "hotkeys": original_hotkeys,
                "log_level": "DEBUG",
            }
        )
        window = _FakeResetWindow(db, fail_hotkeys=True)

        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), mock.patch.object(
            QMessageBox, "warning"
        ) as warning_mock, mock.patch.object(QMessageBox, "information") as info_mock:
            legacy_main_src.MainWindow.reset_settings(window)

        self.assertEqual(db.values["theme"], "dark")
        self.assertEqual(db.values["max_history"], legacy_main_src.MAX_HISTORY)
        self.assertEqual(db.values["log_level"], "INFO")
        self.assertEqual(db.values["mini_window_enabled"], "false")
        self.assertEqual(db.values["hotkeys"], original_hotkeys)
        self.assertEqual(db.cleanup_calls, 1)
        self.assertEqual(window.register_calls, 2)
        self.assertTrue(warning_mock.called)
        self.assertFalse(info_mock.called)

    def test_init_menu_syncs_always_on_top_check_state_with_runtime_flag(self):
        window = _FakeMenuWindow(always_on_top=False)
        try:
            menu_ops.init_menu_impl(window, FALLBACK_THEMES)
            self.assertFalse(window.action_ontop.isChecked())
        finally:
            window.close()

    def test_context_menu_selection_replaces_external_selection(self):
        window = mock.Mock()
        window.table = _FakeContextTable(clicked_row=4, selected_rows=[1, 2])

        item = menu_ops._sync_context_menu_selection(window, object())

        self.assertIsNotNone(item)
        self.assertEqual(window.table.selected_rows, [4])
        self.assertEqual(window.table.clear_calls, 1)
        self.assertEqual(window.table.selected_via_click, [4])

    def test_context_menu_selection_keeps_existing_multi_selection_for_clicked_row(self):
        window = mock.Mock()
        window.table = _FakeContextTable(clicked_row=2, selected_rows=[1, 2])

        item = menu_ops._sync_context_menu_selection(window, object())

        self.assertIsNotNone(item)
        self.assertEqual(window.table.selected_rows, [1, 2])
        self.assertEqual(window.table.clear_calls, 0)
        self.assertEqual(window.table.selected_via_click, [])

    def test_google_search_helper_encodes_reserved_characters(self):
        url = menu_ops.build_google_search_url("https://example.com/a b?x=1&y=한글")

        self.assertTrue(url.startswith("https://www.google.com/search?q="))
        self.assertIn("%2F%2Fexample.com%2Fa%20b%3Fx%3D1%26y%3D", url)
        self.assertIn("%ED%95%9C%EA%B8%80", url)

    def test_import_dialog_csv_warns_and_shows_summary(self):
        dialog = ImportDialog(None, _FakeImportExportManager())
        try:
            dialog.file_path.setText("sample.csv")
            dialog._set_format_hint("sample.csv")
            self.assertIn("CSV", dialog.format_hint.text())
            with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), mock.patch.object(
                QMessageBox, "information"
            ) as info_mock:
                dialog.do_import()
            self.assertTrue(info_mock.called)
            summary = info_mock.call_args[0][2]
            self.assertIn("가져온 항목", summary)
            self.assertIn("사전 백업", summary)
            self.assertIn("컬렉션 처리", summary)
            self.assertTrue(dialog.result())
        finally:
            dialog.close()

    def test_show_import_dialog_refreshes_collection_filters_before_reload(self):
        window = _FakeShowImportWindow()

        with mock.patch.object(legacy_main_src, "ImportDialog", _AcceptedImportDialog):
            legacy_main_src.MainWindow.show_import_dialog(window)

        self.assertEqual(window.calls, ["refresh", "load"])
        self.assertEqual(window.status_bar.messages, [("✅ 가져오기 완료", 3000)])

    def test_export_dialog_shows_report_summary_for_multiple_formats(self):
        dialog = ExportDialog(None, _FakeImportExportManager())
        try:
            dialog.format_json.setChecked(True)
            dialog.format_csv.setChecked(True)
            dialog.format_md.setChecked(False)
            with mock.patch(
                "PyQt6.QtWidgets.QFileDialog.getSaveFileName",
                side_effect=[("out.json", "JSON"), ("out.csv", "CSV")],
            ), mock.patch.object(QMessageBox, "information") as info_mock:
                dialog.do_export()
            self.assertTrue(info_mock.called)
            summary = info_mock.call_args[0][2]
            self.assertIn("JSON", summary)
            self.assertIn("CSV", summary)
            self.assertIn("내보냄 3개", summary)
            self.assertIn("CSV export warning", summary)
            self.assertTrue(dialog.result())
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
            self.assertEqual(pattern, r"^(?:02\d{7,8}|0\d{9,10}|1[568]\d{6})$")
            self.assertTrue(re.search(pattern, "01012345678"))
            self.assertTrue(re.search(pattern, "021234567"))
            self.assertTrue(re.search(pattern, "15881234"))
        finally:
            dialog.close()

    def test_copy_rule_dialog_allows_empty_custom_replace(self):
        db = _FakeCopyRuleDB()
        dialog = CopyRuleEditDialog(None, db)
        try:
            dialog.name_input.setText("remove-foo")
            dialog.pattern_input.setText("foo")
            dialog.action_combo.setCurrentIndex(dialog.action_combo.findData("custom_replace"))
            dialog.replacement_input.setText("")
            with mock.patch.object(dialog, "accept") as accept_mock:
                dialog.save_rule()
            self.assertEqual(db.added, [("remove-foo", "foo", "custom_replace", "")])
            accept_mock.assert_called_once()
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

    def test_floating_mini_window_restores_file_clipboard(self):
        with _workspace_tempdir() as tmpdir:
            file_a = os.path.join(tmpdir, "note.txt")
            with open(file_a, "w", encoding="utf-8") as fh:
                fh.write("note")

            class _FakeMiniFileDB(_FakeMiniDB):
                def get_content(self, _pid):
                    return (file_content_from_paths([file_a]), None, "FILE")

            parent = _FakeMiniParent()
            window = FloatingMiniWindow(_FakeMiniFileDB(), parent=parent)
            clipboard = _FakeClipboardWriter()
            try:
                with mock.patch("smartclipboard_app.ui.widgets.floating_mini_window.QApplication.clipboard", return_value=clipboard):
                    item = QListWidgetItem("row")
                    item.setData(Qt.ItemDataRole.UserRole, 7)
                    window.on_item_double_clicked(item)
                restored_paths = [os.path.normcase(os.path.normpath(url.toLocalFile())) for url in clipboard.mimeData().urls()]
                self.assertEqual(restored_paths, [os.path.normcase(os.path.normpath(file_a))])
                self.assertTrue(parent.is_internal_copy)
            finally:
                window.close()
                parent.close()

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

    def test_paste_last_hotkey_restores_file_clipboard_urls(self):
        with _workspace_tempdir() as tmpdir:
            file_a = os.path.join(tmpdir, "alpha.txt")
            file_b = os.path.join(tmpdir, "beta.txt")
            with open(file_a, "w", encoding="utf-8") as fh:
                fh.write("alpha")
            with open(file_b, "w", encoding="utf-8") as fh:
                fh.write("beta")

            window = _FakeMiniParent()
            window.db = _FakeFilePasteLastDB(file_content_from_paths([file_a, file_b]))
            window.clipboard = _FakeClipboardWriter()
            keyboard = _FakePasteKeyboard()
            _ImmediateTimer.reset()

            paste_last_item_slot_impl(window, mock.Mock(), mock.Mock(), _ImmediateTimer, keyboard)

            self.assertIsNotNone(window.clipboard.mime_data)
            restored_paths = [os.path.normcase(os.path.normpath(url.toLocalFile())) for url in window.clipboard.mime_data.urls()]
            self.assertEqual(
                restored_paths,
                [os.path.normcase(os.path.normpath(file_a)), os.path.normcase(os.path.normpath(file_b))],
            )
            self.assertEqual(window.db.incremented, [20])
            self.assertTrue(window.is_internal_copy)
            self.assertEqual(keyboard.sent, ["ctrl+v"])

    def test_paste_last_hotkey_skips_missing_file_clipboard(self):
        missing_path = os.path.join(os.getcwd(), ".tmp-unittest", "does-not-exist.txt")
        window = _FakeMiniParent()
        window.db = _FakeFilePasteLastDB(file_content_from_paths([missing_path]))
        window.clipboard = _FakeClipboardWriter()
        keyboard = _FakePasteKeyboard()
        _ImmediateTimer.reset()

        paste_last_item_slot_impl(window, mock.Mock(), mock.Mock(), _ImmediateTimer, keyboard)

        self.assertIsNone(window.clipboard.mime_data)
        self.assertEqual(window.db.incremented, [])
        self.assertEqual(keyboard.sent, [])

    def test_paste_last_hotkey_restores_available_file_paths_when_some_missing(self):
        with _workspace_tempdir() as tmpdir:
            file_a = os.path.join(tmpdir, "alpha.txt")
            missing_path = os.path.join(tmpdir, "missing.txt")
            with open(file_a, "w", encoding="utf-8") as fh:
                fh.write("alpha")

            window = _FakeMiniParent()
            window.db = _FakeFilePasteLastDB(file_content_from_paths([file_a, missing_path]))
            window.clipboard = _FakeClipboardWriter()
            keyboard = _FakePasteKeyboard()
            _ImmediateTimer.reset()

            paste_last_item_slot_impl(window, mock.Mock(), mock.Mock(), _ImmediateTimer, keyboard)

            self.assertIsNotNone(window.clipboard.mime_data)
            restored_paths = [os.path.normcase(os.path.normpath(url.toLocalFile())) for url in window.clipboard.mime_data.urls()]
            self.assertEqual(restored_paths, [os.path.normcase(os.path.normpath(file_a))])
            self.assertEqual(window.db.incremented, [20])
            self.assertEqual(keyboard.sent, ["ctrl+v"])

    def test_process_clipboard_prefers_file_urls_over_image_payload(self):
        window = _FakeClipboardRuntimeWindow(_FakeMimeData(has_urls=True, has_image=True, has_text=True))

        with mock.patch(
            "smartclipboard_app.ui.mainwindow_parts.clipboard_runtime_ops.process_file_clipboard_impl",
            return_value=True,
        ) as file_mock:
            process_clipboard_impl(window, mock.Mock())

        self.assertTrue(file_mock.called)
        self.assertEqual(window.image_calls, 0)
        self.assertEqual(window.text_calls, 0)

    def test_process_clipboard_falls_back_to_image_when_urls_do_not_restore_files(self):
        window = _FakeClipboardRuntimeWindow(_FakeMimeData(has_urls=True, has_image=True, has_text=True))

        with mock.patch(
            "smartclipboard_app.ui.mainwindow_parts.clipboard_runtime_ops.process_file_clipboard_impl",
            return_value=False,
        ) as file_mock:
            process_clipboard_impl(window, mock.Mock())

        self.assertTrue(file_mock.called)
        self.assertEqual(window.image_calls, 1)
        self.assertEqual(window.text_calls, 0)

    def test_process_actions_impl_updates_history_and_clipboard_for_replace_text(self):
        with _workspace_tempdir() as tmpdir:
            db = ClipboardDB(
                db_file=os.path.join(tmpdir, "clipboard_history_v6.db"),
                app_dir=tmpdir,
            )
            try:
                item_id = db.add_item("01012345678", None, "TEXT")
                window = _FakeActionProcessWindow(
                    db,
                    [
                        ("format_phone", {"type": "replace_text", "text": "010-1234-5678", "formatted": "010-1234-5678"}),
                    ],
                )

                process_actions_impl(window, "01012345678", item_id, mock.Mock(), mock.Mock())

                self.assertEqual(db.get_content(item_id), ("010-1234-5678", None, "TEXT"))
                self.assertEqual(window.clipboard.text_value, "010-1234-5678")
                self.assertTrue(window.is_internal_copy)
            finally:
                db.close()

    def test_display_sort_keeps_pinned_rows_above_unpinned_in_descending_order(self):
        window = _FakeTableWindow()

        items = get_display_items_impl(window)

        self.assertEqual([row[0] for row in items], [2, 1, 3])

    def test_search_results_keep_db_relevance_order_without_user_sort_override(self):
        window = _FakeSearchWindow(override=False)

        items = get_display_items_impl(window)

        self.assertEqual([row[0] for row in items], [1, 2, 3])

    def test_search_results_apply_client_sort_after_user_override(self):
        window = _FakeSearchWindow(override=True)

        items = get_display_items_impl(window)

        self.assertEqual([row[0] for row in items], [2, 1, 3])

    def test_load_data_updates_status_bar_for_empty_state(self):
        window = _FakeStatusLoadWindow()

        load_data_impl(
            window,
            {
                "dark": {
                    "text_secondary": "#888888",
                }
            },
            mock.Mock(),
        )

        self.assertEqual(window.status_calls, [0])
        self.assertEqual(window.table.rowCount(), 1)

    def test_table_ops_file_rows_show_missing_status_before_restore(self):
        with _workspace_tempdir() as tmpdir:
            file_a = os.path.join(tmpdir, "alpha.txt")
            missing_path = os.path.join(tmpdir, "missing.txt")
            with open(file_a, "w", encoding="utf-8") as fh:
                fh.write("alpha")

            class _FakePopulateWindow:
                def __init__(self):
                    self.table = QTableWidget()
                    self.table.setColumnCount(5)

            window = _FakePopulateWindow()
            populate_table_impl(
                window,
                [(1, file_content_from_paths([file_a, missing_path]), "FILE", "2026-04-01 10:00:00", 0, 0, 0)],
                {
                    "primary": "#3366ff",
                    "text_secondary": "#888888",
                    "secondary": "#22aa99",
                    "success": "#22aa55",
                    "warning": "#ffaa33",
                },
                {"FILE": "📎"},
            )

            content_item = window.table.item(0, 2)
            self.assertIsNotNone(content_item)
            self.assertTrue(content_item.text().startswith("[누락 1]"))
            self.assertIn("사용 가능 1개, 누락 1개", content_item.toolTip())

    def test_floating_mini_window_marks_stale_file_items_in_tooltip(self):
        with _workspace_tempdir() as tmpdir:
            file_a = os.path.join(tmpdir, "note.txt")
            missing_path = os.path.join(tmpdir, "missing.txt")
            with open(file_a, "w", encoding="utf-8") as fh:
                fh.write("note")

            db = _FakeMiniListDB(
                [(1, file_content_from_paths([file_a, missing_path]), "FILE", "2026-04-01 10:00:00", 0, 0, 0)]
            )
            parent = _FakeMiniParent()
            window = FloatingMiniWindow(db, parent=parent)
            try:
                window.load_items()
                item = window.list_widget.item(0)
                self.assertIn("[누락 1]", item.text())
                self.assertIn("사용 가능 1개, 누락 1개", item.toolTip())
            finally:
                window.close()
                parent.close()

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
        clipboard = _FakeClipboardWriter()
        try:
            clipboard.setText("")
            with mock.patch("smartclipboard_app.ui.dialogs.secure_vault.QApplication.clipboard", return_value=clipboard):
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

    def test_secure_vault_corruption_reset_returns_to_first_time_setup(self):
        parent = _FakeMiniParent()
        manager = _CorruptedVaultManager()
        dialog = SecureVaultDialog(parent, _FakeVaultDB(), manager)
        try:
            self.assertFalse(dialog.btn_reset.isHidden())
            self.assertIn("손상", dialog.status_label.text())
            with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), mock.patch.object(
                QMessageBox, "information"
            ):
                dialog.reset_vault()
            self.assertEqual(manager.reset_calls, 1)
            self.assertTrue(dialog.btn_reset.isHidden())
            self.assertIn("최초 설정", dialog.status_label.text())
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
        clipboard = _FakeClipboardWriter()
        try:
            with mock.patch("smartclipboard_app.ui.dialogs.secure_vault.QApplication.clipboard", return_value=clipboard):
                with mock.patch("smartclipboard_app.ui.dialogs.secure_vault.QTimer.singleShot") as single_shot:
                    dialog.copy_item(1, b"encrypted")
                single_shot.assert_called_once()
                self.assertEqual(single_shot.call_args[0][0], 30000)
                self.assertEqual(getattr(parent, "_vault_clipboard_expected_text", None), "vault-secret")

                clipboard.setText("different-text")
                dialog._clear_clipboard_if_unchanged("vault-secret")
                self.assertEqual(clipboard.text(), "different-text")
                self.assertIsNone(getattr(parent, "_vault_clipboard_expected_text", None))

                clipboard.setText("vault-secret")
                setattr(parent, "_vault_clipboard_expected_text", "vault-secret")
                dialog._clear_clipboard_if_unchanged("vault-secret")
                self.assertEqual(clipboard.text(), "")
                self.assertIsNone(getattr(parent, "_vault_clipboard_expected_text", None))
        finally:
            dialog.close()
            parent.close()

    def test_quit_app_impl_clears_armed_vault_clipboard(self):
        clipboard = _FakeClipboardWriter()
        clipboard.setText("vault-secret")
        _FakeQuitApp.clipboard_instance = clipboard
        _FakeQuitApp.quit_called = False
        window = _FakeQuitWindow("vault-secret")

        quit_app_impl(window, mock.Mock(), _FakeQuitKeyboard(), _FakeQuitApp)

        self.assertEqual(clipboard.text(), "")
        self.assertTrue(window.is_internal_copy)
        self.assertTrue(window.db.closed)
        self.assertIsNone(window._vault_clipboard_expected_text)
        self.assertTrue(_FakeQuitApp.quit_called)

    def test_quit_app_impl_leaves_non_matching_clipboard_text_untouched(self):
        clipboard = _FakeClipboardWriter()
        clipboard.setText("different-text")
        _FakeQuitApp.clipboard_instance = clipboard
        _FakeQuitApp.quit_called = False
        window = _FakeQuitWindow("vault-secret")

        quit_app_impl(window, mock.Mock(), _FakeQuitKeyboard(), _FakeQuitApp)

        self.assertEqual(clipboard.text(), "different-text")
        self.assertTrue(window.db.closed)
        self.assertIsNone(window._vault_clipboard_expected_text)

    def test_run_periodic_cleanup_refreshes_visible_window_when_history_rows_deleted(self):
        window = _FakeCleanupWindow(_FakeCleanupDB(expired_count=0, history_deleted=2), visible=True)

        run_periodic_cleanup_impl(window, mock.Mock())

        self.assertEqual(window.load_calls, 1)
        self.assertEqual(window.status_calls, 1)
        self.assertFalse(window.is_data_dirty)

    def test_run_periodic_cleanup_marks_hidden_window_dirty_when_history_rows_deleted(self):
        window = _FakeCleanupWindow(_FakeCleanupDB(expired_count=0, history_deleted=1), visible=False)

        run_periodic_cleanup_impl(window, mock.Mock())

        self.assertEqual(window.load_calls, 0)
        self.assertEqual(window.status_calls, 0)
        self.assertTrue(window.is_data_dirty)

    def test_restore_data_failure_reuses_runtime_db_path(self):
        current_db = _FakeRestoreDB(db_file="D:/runtime/custom.db", app_dir="D:/runtime")
        current_action_manager = _FakeRestoreActionManager()
        new_db = _FakeRestoreDB(db_file=current_db.db_file, app_dir=current_db.app_dir)
        new_action_manager = _FakeRestoreActionManager()
        new_vault_manager = object()
        new_export_manager = object()
        window = mock.Mock()
        window.db = current_db
        window.action_manager = current_action_manager
        window.on_action_completed = object()

        with mock.patch.object(
            legacy_main_src.QMessageBox,
            "warning",
            return_value=QMessageBox.StandardButton.Yes,
        ), mock.patch.object(
            legacy_main_src.QFileDialog,
            "getOpenFileName",
            return_value=("backup.db", "SQLite DB Files (*.db)"),
        ), mock.patch.object(
            legacy_main_src.QMessageBox,
            "critical",
        ) as critical_mock, mock.patch.object(
            legacy_main_src,
            "ClipboardDB",
            return_value=new_db,
        ) as db_ctor, mock.patch.object(
            legacy_main_src,
            "SecureVaultManager",
            return_value=new_vault_manager,
        ), mock.patch.object(
            legacy_main_src,
            "ClipboardActionManager",
            return_value=new_action_manager,
        ), mock.patch.object(
            legacy_main_src,
            "ExportImportManager",
            return_value=new_export_manager,
        ), mock.patch.object(
            legacy_main_src.shutil,
            "copy2",
            side_effect=RuntimeError("copy failed"),
        ):
            legacy_main_src.MainWindow.restore_data(window)

        self.assertTrue(current_db.closed)
        self.assertEqual(current_action_manager.shutdown_calls, 1)
        self.assertEqual(current_action_manager.action_completed.disconnect_calls, 1)
        db_ctor.assert_called_once_with(db_file="D:/runtime/custom.db", app_dir="D:/runtime")
        self.assertIs(window.db, new_db)
        self.assertIs(window.vault_manager, new_vault_manager)
        self.assertIs(window.action_manager, new_action_manager)
        self.assertIs(window.export_manager, new_export_manager)
        self.assertEqual(new_action_manager.action_completed.connect_calls, 1)
        self.assertTrue(critical_mock.called)


if __name__ == "__main__":
    unittest.main(verbosity=2)
