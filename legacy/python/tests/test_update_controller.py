import datetime
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication

from smartclipboard_app.features.updater.controller import UpdaterController
from smartclipboard_core.update_manifest import ReleaseManifest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
app = QApplication.instance() or QApplication([])


class TestUpdaterController(unittest.TestCase):
    def setUp(self):
        self.mock_window = MagicMock()
        self.controller = UpdaterController(window=self.mock_window)

    def test_init_and_properties(self):
        self.assertIsNotNone(self.controller._signals)
        self.assertFalse(self.controller._is_checking)
        self.assertFalse(self.controller._is_downloading)

    @patch("smartclipboard_app.features.updater.controller.consume_update_result")
    @patch("smartclipboard_app.features.updater.controller.QMessageBox.exec")
    def test_notify_pending_update_result_success(self, mock_exec, mock_consume):
        mock_consume.return_value = {
            "status": "success",
            "version": "10.7",
            "error": "",
        }
        self.controller.notify_pending_update_result()
        # Status bar should be notified for success
        self.mock_window.statusBar().showMessage.assert_called()

    @patch("smartclipboard_app.features.updater.controller.consume_update_result")
    @patch("smartclipboard_app.features.updater.controller.QMessageBox.exec")
    def test_notify_pending_update_result_rollback(self, mock_exec, mock_consume):
        mock_consume.return_value = {
            "status": "rollback",
            "version": "10.7",
            "error": "smoke check failed",
        }
        self.controller.notify_pending_update_result()
        mock_exec.assert_called_once()

    @patch("smartclipboard_app.features.updater.controller.QMessageBox.information")
    def test_on_not_available_non_interactive_does_not_show_dialog(self, mock_msg):
        self.controller._on_not_available(interactive=False)
        mock_msg.assert_not_called()

    @patch("smartclipboard_app.features.updater.controller.QMessageBox.information")
    def test_on_not_available_interactive_shows_dialog(self, mock_msg):
        self.controller._on_not_available(interactive=True)
        mock_msg.assert_called_once()

    @patch("smartclipboard_app.features.updater.controller.QMessageBox.exec")
    def test_on_check_failed_non_interactive_does_not_show_dialog(self, mock_exec):
        self.controller._on_check_failed("Network Error", interactive=False)
        mock_exec.assert_not_called()

    @patch("smartclipboard_app.features.updater.controller.QMessageBox.exec")
    def test_on_check_failed_interactive_shows_dialog(self, mock_exec):
        self.controller._on_check_failed("Network Error", interactive=True)
        mock_exec.assert_called_once()

    @patch("smartclipboard_app.features.updater.controller.UpdaterController._start_download")
    def test_on_manifest_ready_triggers_download_when_selected(self, mock_download):
        manifest = ReleaseManifest(
            version="10.7",
            artifact_url="https://github.com/twbeatles/smartclipboard/releases/download/v10.7/SmartClipboard.exe",
            artifact_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            artifact_size=1024,
            expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30),
            signature="c2lnbmF0dXJl",
        )

        with patch("sys.frozen", True, create=True):
            mock_dialog = MagicMock()
            btn_update = MagicMock()
            btn_release = MagicMock()
            btn_cancel = MagicMock()
            mock_dialog.addButton.side_effect = [btn_update, btn_release, btn_cancel]
            mock_dialog.clickedButton.return_value = btn_update

            with patch("smartclipboard_app.features.updater.controller.QMessageBox", return_value=mock_dialog):
                self.controller._on_manifest_ready(manifest, interactive=True)
                mock_download.assert_called_once_with(manifest, True)


if __name__ == "__main__":
    unittest.main()
