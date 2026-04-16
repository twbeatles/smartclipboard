import pathlib
import re
import unittest
from unittest import mock

import smartclipboard_app.legacy_main_src as legacy_main_src


LEGACY_SRC = pathlib.Path("smartclipboard_app/legacy_main_src.py")


class LegacyUiContractsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = LEGACY_SRC.read_text(encoding="utf-8-sig")

    def _method_block(self, method_name: str) -> str:
        pattern = rf"^    def {re.escape(method_name)}\(self[^\n]*\):\n((?:        .*\n)*)"
        match = re.search(pattern, self.source, flags=re.MULTILINE)
        if match is None:
            self.fail(f"missing method: {method_name}")
        return match.group(1)

    def test_show_toast_calls_are_not_bound_to_mainwindow(self):
        self.assertNotIn("self.show_toast(", self.source)
        self.assertIn("ToastNotification.show_toast(self,", self.source)

    def test_trash_dialog_supports_extended_selection(self):
        self.assertIn(
            "self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)",
            self.source,
        )

    def test_update_always_on_top_preserves_visibility(self):
        block = self._method_block("update_always_on_top")
        self.assertIn("was_visible = self.isVisible()", block)
        self.assertIn("if was_visible:", block)
        self.assertIn("self.show()", block)

    def test_restore_data_uses_runtime_db_path_and_reconnects_action_signal(self):
        block = self._method_block("restore_data")
        self.assertIn("target_db_file = getattr(self.db, \"db_file\", DB_FILE)", block)
        self.assertIn("self.action_manager.action_completed.connect(self.on_action_completed)", block)

    def test_move_to_collection_uses_multi_selection(self):
        block = self._method_block("move_to_collection")
        self.assertIn("item_ids = self.get_selected_ids()", block)
        self.assertIn("move_items_to_collection", block)

    def test_get_selected_ids_exists(self):
        self.assertIn("def get_selected_ids(self):", self.source)


class _FakeClipboardSignal:
    def __init__(self):
        self.disconnected = []
        self.connected = []

    def disconnect(self, callback):
        self.disconnected.append(callback)

    def connect(self, callback):
        self.connected.append(callback)


class _FakeClipboard:
    def __init__(self):
        self.dataChanged = _FakeClipboardSignal()


class _FakeSearchInput:
    def hasFocus(self):
        return False


class LegacyUiRuntimeSafetyTests(unittest.TestCase):
    def test_on_action_completed_shows_notify_toast(self):
        fake_window = type("FakeWindow", (), {})()

        with mock.patch.object(legacy_main_src.ToastNotification, "show_toast") as toast_mock:
            legacy_main_src.MainWindow.on_action_completed(
                fake_window,
                "fetch",
                {"type": "notify", "message": "blocked"},
            )

        toast_mock.assert_called_once()
        self.assertEqual(toast_mock.call_args[0][1], "⚡fetch")
        self.assertEqual(toast_mock.call_args.kwargs["detail"], "blocked")

    def test_on_action_completed_reconnects_clipboard_when_toast_raises(self):
        fake_window = type("FakeWindow", (), {})()
        fake_window.clipboard = _FakeClipboard()
        fake_window.search_input = _FakeSearchInput()
        fake_window.on_clipboard_change = object()
        fake_window.load_data = lambda: None

        with mock.patch.object(legacy_main_src.ToastNotification, "show_toast", side_effect=RuntimeError("toast boom")):
            legacy_main_src.MainWindow.on_action_completed(
                fake_window,
                "fetch",
                {"type": "title", "title": "Example Title"},
            )

        self.assertEqual(fake_window.clipboard.dataChanged.disconnected, [fake_window.on_clipboard_change])
        self.assertEqual(fake_window.clipboard.dataChanged.connected, [fake_window.on_clipboard_change])


if __name__ == "__main__":
    unittest.main(verbosity=2)
