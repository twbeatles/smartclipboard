import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication, QDialog

from smartclipboard_app.features.action_palette.dialog import ActionPaletteDialog
from smartclipboard_app.features.action_palette.preview import ActionPreviewDialog
from smartclipboard_app.features.action_palette.services import (
    apply_result,
    context_from_item,
    start_fetch_title,
    shutdown_palette_workers,
)
from smartclipboard_core.action_palette import ActionResult, build_context, create_default_registry
from smartclipboard_core.database import ClipboardDB
from smartclipboard_app.ui.dialogs.snippets import APP_LOCAL_SHORTCUTS
from smartclipboard_app.features.history.menu import show_context_menu_impl

TEST_TMP_ROOT = os.path.join(os.getcwd(), ".tmp-unittest")
os.makedirs(TEST_TMP_ROOT, exist_ok=True)


class _FakeClipboard:
    def __init__(self):
        self.text_value = ""

    def setText(self, text):
        self.text_value = text


class ActionPaletteUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.registry = create_default_registry()

    def _dialog(self, text="https://github.com/twbeatles/smartclipboard"):
        context = build_context(raw_text=text, metadata={"url_title": "SmartClipboard"})
        dialog = ActionPaletteDialog(None, context, self.registry, themes={})
        return dialog

    def test_dialog_lists_url_actions_and_autofocuses_search(self):
        dialog = self._dialog()
        dialog.show()
        QApplication.processEvents()
        self.assertTrue(dialog.search_input.isVisible())
        ids = []
        for row in range(dialog.list_widget.count()):
            item = dialog.list_widget.item(row)
            self.assertIsNotNone(item)
            assert item is not None
            action_id = item.data(Qt.ItemDataRole.UserRole)
            if action_id:
                ids.append(action_id)
        self.assertIn("url.markdown_link", ids)
        self.assertIn("url.copy_domain", ids)
        dialog.close()

    def test_search_filters_and_empty_state(self):
        dialog = self._dialog()
        dialog.search_input.setText("도메인")
        QApplication.processEvents()
        visible = []
        for row in range(dialog.list_widget.count()):
            item = dialog.list_widget.item(row)
            self.assertIsNotNone(item)
            assert item is not None
            action_id = item.data(Qt.ItemDataRole.UserRole)
            if action_id:
                visible.append(action_id)
        self.assertEqual(visible, ["url.copy_domain"])
        dialog.search_input.setText("없는작업xyz")
        QApplication.processEvents()
        empty_item = dialog.list_widget.item(0)
        self.assertIsNotNone(empty_item)
        assert empty_item is not None
        self.assertIn("없습니다", empty_item.text())
        dialog.close()

    def test_enter_accepts_current_action_and_escape_closes(self):
        dialog = self._dialog()
        dialog.show()
        QApplication.processEvents()
        QApplication.sendEvent(
            dialog,
            QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier),
        )
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertIsNotNone(dialog.selected_action)
        dialog.close()

        dialog = self._dialog()
        dialog.show()
        QApplication.processEvents()
        QApplication.sendEvent(
            dialog,
            QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier),
        )
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        dialog.close()

    def test_preview_dialog_copy_sets_flag(self):
        context = build_context(raw_text='{"a":1}')
        result = ActionResult(kind="text", value='{\n  "a": 1\n}', title="JSON 정리", preview=True)
        preview = ActionPreviewDialog(None, result, context, themes={})
        preview._copy()
        self.assertTrue(preview.copied)
        preview.close()

    def test_apply_result_marks_internal_copy_and_writes_back(self):
        clipboard = _FakeClipboard()
        db = SimpleNamespace(replace_text_item_or_merge=mock.Mock(return_value=1), conn=object())
        window = SimpleNamespace(
            clipboard=clipboard,
            is_internal_copy=False,
            db=db,
            analyze_text=lambda text: "TEXT",
            isVisible=lambda: True,
            load_data=mock.Mock(),
        )
        context = build_context(item_id=9, raw_text="  hi  ")
        result = ActionResult(kind="text", value="hi", title="앞뒤 공백 제거", copy_to_clipboard=True)
        with mock.patch("smartclipboard_app.features.action_palette.services.ToastNotification.show_toast"):
            apply_result(window, result, context)
        self.assertEqual(clipboard.text_value, "hi")
        self.assertTrue(window.is_internal_copy)
        db.replace_text_item_or_merge.assert_called_once_with(9, "hi", "TEXT")
        window.load_data.assert_called_once()

    def test_context_from_item_reads_history_metadata(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP_ROOT) as tmp:
            db = ClipboardDB(db_file=os.path.join(tmp, "palette.db"), app_dir=tmp)
            item_id = db.add_item("https://example.com/x", None, "LINK")
            db.set_item_metadata(item_id, tags="secret", note="", url_title="Example")
            context = context_from_item(db, item_id)
            self.assertIsNotNone(context)
            assert context is not None
            self.assertEqual(context.content_type, "url")
            self.assertTrue(context.is_sensitive)
            self.assertEqual(context.metadata.get("url_title"), "Example")
            db.close()

    def test_context_menu_includes_palette_action(self):
        captured = {}

        class _Menu:
            def __init__(self, *_args, **_kwargs):
                self.actions = []

            def setStyleSheet(self, *_args, **_kwargs):
                return None

            def addAction(self, text):
                action = SimpleNamespace(
                    text=text,
                    enabled=True,
                    triggered=SimpleNamespace(connect=lambda *_a: None),
                    setEnabled=lambda value: None,
                )
                action.setEnabled = lambda value: setattr(action, "enabled", bool(value))
                self.actions.append(action)
                return action

            def addMenu(self, text):
                return self

            def addSeparator(self):
                return None

            def exec(self, *_args, **_kwargs):
                captured["actions"] = [action.text for action in self.actions]
                return None

        window = SimpleNamespace(
            table=SimpleNamespace(
                itemAt=lambda pos: object(),
                row=lambda item: 0,
                selectionModel=lambda: SimpleNamespace(selectedRows=lambda: [SimpleNamespace(row=lambda: 0)]),
                selectRow=lambda row: None,
                clearSelection=lambda: None,
                viewport=lambda: SimpleNamespace(mapToGlobal=lambda pos: pos),
            ),
            current_theme="dark",
            get_selected_id=lambda: 1,
            db=SimpleNamespace(get_content=lambda pid: ("hello", None, "TEXT"), get_collections=lambda: []),
            copy_item=lambda: None,
            paste_selected=lambda: None,
            open_action_palette=lambda: None,
            toggle_pin=lambda: None,
            toggle_bookmark=lambda: None,
            edit_tag=lambda: None,
            edit_note=lambda: None,
            move_to_collection=lambda *_a: None,
            create_collection=lambda: None,
            show_collection_manager=lambda: None,
            merge_selected=lambda: None,
            delete_item=lambda: None,
            transform_text=lambda *_a: None,
        )
        with mock.patch("smartclipboard_app.features.history.menu.QMenu", _Menu):
            show_context_menu_impl(window, object(), {"dark": {"surface": "#000", "text": "#fff", "border": "#111", "primary": "#00f"}}, mock.Mock())
        self.assertIn("⚡ 작업 실행...", captured.get("actions", []))

    def test_alt_a_is_reserved_app_local_shortcut(self):
        self.assertEqual(APP_LOCAL_SHORTCUTS["action_palette"], "Alt+A")

    def test_fetch_title_blocks_private_url_without_worker(self):
        window = SimpleNamespace(
            _action_palette_shutting_down=False,
            db=SimpleNamespace(conn=object()),
            action_manager=None,
        )
        context = build_context(item_id=1, raw_text="http://127.0.0.1/admin")
        with mock.patch("smartclipboard_app.features.action_palette.services.ToastNotification.show_toast") as toast:
            with mock.patch("smartclipboard_app.features.action_palette.services.Worker") as worker_cls:
                start_fetch_title(window, context, "http://127.0.0.1/admin")
        worker_cls.assert_not_called()
        toast.assert_called()
        self.assertIn("사설", toast.call_args.args[1])

    def test_fetch_title_ignores_callback_after_shutdown(self):
        db = SimpleNamespace(conn=None, get_content=mock.Mock(), update_url_title=mock.Mock())
        window = SimpleNamespace(db=db, action_manager=None, isVisible=lambda: True)
        shutdown_palette_workers(window)
        context = build_context(item_id=1, raw_text="https://example.com")
        with mock.patch("smartclipboard_app.features.action_palette.services.ToastNotification.show_toast") as toast:
            from smartclipboard_app.features.action_palette import services as palette_services

            palette_services._handle_title_result(
                window,
                context,
                "https://example.com",
                {"title": "Example", "url": "https://example.com"},
            )
        db.get_content.assert_not_called()
        db.update_url_title.assert_not_called()
        toast.assert_not_called()

    def test_preview_qr_copy_button_uses_source_label(self):
        from PyQt6.QtWidgets import QPushButton

        context = build_context(raw_text="https://example.com")
        result = ActionResult(kind="qr", value="https://example.com", title="QR 코드", preview=True)
        preview = ActionPreviewDialog(None, result, context, themes={})
        texts = [btn.text() for btn in preview.findChildren(QPushButton)]
        self.assertIn("원문 복사", texts)
        preview.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
