"""Updater controller and dialog handlers for SmartClipboard."""

from __future__ import annotations

import logging
import os
import sys
import threading
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QApplication, QMessageBox

from smartclipboard_core.config import Config
from smartclipboard_core.update_installer import (
    consume_update_result,
    launch_update_helper,
    prepare_staged_update,
    resolve_update_staging_root,
    stream_update_artifact,
    update_result_path,
)
from smartclipboard_core.update_manifest import (
    NoUpdateAvailableError,
    ReleaseManifest,
    download_release_manifest,
    verify_release_manifest,
)

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


def _open_latest_release_page() -> None:
    webbrowser.open(Config.UPDATE_RELEASES_URL)


class _UpdateWorkerSignals(QObject):
    manifest_ready = pyqtSignal(object, bool)  # manifest, interactive
    not_available = pyqtSignal(bool)  # interactive
    check_failed = pyqtSignal(str, bool)  # error, interactive
    download_ready = pyqtSignal(object, object, bool)  # manifest, staged_path, interactive
    download_failed = pyqtSignal(str, bool)  # error, interactive


class UpdaterController(QObject):
    """Manages update checking, downloading, and installation workflows."""

    def __init__(self, window: Any = None) -> None:
        super().__init__()
        self.window = window
        self._signals = _UpdateWorkerSignals()
        self._is_checking = False
        self._is_downloading = False
        self._last_notified_version: str | None = None

        self._signals.manifest_ready.connect(self._on_manifest_ready)
        self._signals.not_available.connect(self._on_not_available)
        self._signals.check_failed.connect(self._on_check_failed)
        self._signals.download_ready.connect(self._on_download_ready)
        self._signals.download_failed.connect(self._on_download_failed)

    def _get_dialog_parent(self) -> QWidget | None:
        from PyQt6.QtWidgets import QWidget

        return self.window if isinstance(self.window, QWidget) else None

    def _get_install_dir(self) -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parent.parent.parent.parent

    def notify_pending_update_result(self) -> None:
        staging_root = resolve_update_staging_root(install_dir=self._get_install_dir())
        payload = consume_update_result(update_result_path(staging_root))
        if not payload:
            return

        status = str(payload.get("status") or "")
        error = str(payload.get("error") or "")
        if status == "success":
            if self.window and hasattr(self.window, "statusBar"):
                status_bar = getattr(self.window, "statusBar")()
                if status_bar:
                    status_bar.showMessage("✅ 업데이트가 완료되었습니다.", 4000)
            return

        message = (
            "업데이트 후 원래 버전으로 복원했습니다."
            if status == "rolled_back"
            else "업데이트를 적용하지 못했습니다."
        )
        if error:
            message = f"{message}\n\n오류: {error}"
        logger.warning("Previous update failed: %s", error)
        dialog = QMessageBox(self._get_dialog_parent())
        dialog.setWindowTitle("업데이트 결과")
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText(f"{message}\n\n최신 버전은 GitHub 릴리스 페이지에서 직접 다운로드할 수 있습니다.")
        release_button = dialog.addButton("릴리스 페이지 열기", QMessageBox.ButtonRole.ActionRole)
        dialog.addButton("닫기", QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        if dialog.clickedButton() is release_button:
            _open_latest_release_page()

    def check_for_updates(self, interactive: bool = True) -> None:
        if self._is_checking or self._is_downloading:
            if interactive and self.window:
                QMessageBox.information(
                    self._get_dialog_parent(),
                    "업데이트",
                    "업데이트 작업이 이미 진행 중입니다.",
                )
            return

        manifest_url = str(Config.UPDATE_MANIFEST_URL or "").strip()
        public_key = str(Config.UPDATE_PUBLIC_KEY_B64 or "").strip()
        if not manifest_url or not public_key:
            if interactive and self.window:
                QMessageBox.information(
                    self._get_dialog_parent(),
                    "업데이트",
                    "서명된 업데이트 채널이 설정되지 않았습니다.",
                )
            return

        if interactive and self.window and hasattr(self.window, "statusBar"):
            status_bar = getattr(self.window, "statusBar")()
            if status_bar:
                status_bar.showMessage("🔄 업데이트 확인 중...", 3000)

        self._is_checking = True

        def worker_target() -> None:
            try:
                document = download_release_manifest(manifest_url)
                manifest = verify_release_manifest(
                    document,
                    public_key=public_key,
                    current_version=Config.VERSION,
                )
                self._signals.manifest_ready.emit(manifest, interactive)
            except NoUpdateAvailableError:
                self._signals.not_available.emit(interactive)
            except Exception as exc:
                self._signals.check_failed.emit(str(exc), interactive)

        thread = threading.Thread(target=worker_target, daemon=True, name="UpdateCheckThread")
        thread.start()

    @pyqtSlot(object, bool)
    def _on_manifest_ready(self, manifest: ReleaseManifest, interactive: bool) -> None:
        self._is_checking = False
        if not isinstance(manifest, ReleaseManifest):
            self._handle_failure("업데이트 응답 형식이 올바르지 않습니다.", interactive)
            return

        if not bool(getattr(sys, "frozen", False)):
            if interactive:
                dialog = QMessageBox(self._get_dialog_parent())
                dialog.setWindowTitle("업데이트 발견")
                dialog.setIcon(QMessageBox.Icon.Information)
                dialog.setText(
                    f"새 버전 {manifest.version}이 있습니다.\n\n"
                    f"현재 버전: v{Config.VERSION}\n"
                    f"최신 버전: v{manifest.version}\n\n"
                    "(개발 환경에서는 자동 설치가 비활성화됩니다)"
                )
                release_button = dialog.addButton("릴리스 페이지 열기", QMessageBox.ButtonRole.ActionRole)
                dialog.addButton("닫기", QMessageBox.ButtonRole.RejectRole)
                dialog.exec()
                if dialog.clickedButton() is release_button:
                    _open_latest_release_page()
            return

        if not interactive and self._last_notified_version == manifest.version:
            return
        self._last_notified_version = manifest.version

        dialog = QMessageBox(self._get_dialog_parent())
        dialog.setWindowTitle("업데이트 발견")
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setText(
            f"새 버전 v{manifest.version}이 있습니다.\n\n"
            f"현재 버전: v{Config.VERSION}\n"
            f"최신 버전: v{manifest.version}"
        )
        update_button = dialog.addButton("업데이트 다운로드", QMessageBox.ButtonRole.AcceptRole)
        release_button = dialog.addButton("릴리스 페이지 보기", QMessageBox.ButtonRole.ActionRole)
        dialog.addButton("나중에", QMessageBox.ButtonRole.RejectRole)
        dialog.exec()

        if dialog.clickedButton() is release_button:
            _open_latest_release_page()
            return
        if dialog.clickedButton() is not update_button:
            return

        self._start_download(manifest, interactive)

    def _start_download(self, manifest: ReleaseManifest, interactive: bool) -> None:
        self._is_downloading = True
        if self.window and hasattr(self.window, "statusBar"):
            status_bar = getattr(self.window, "statusBar")()
            if status_bar:
                status_bar.showMessage(f"📥 업데이트 v{manifest.version} 다운로드 중...", 5000)

        def download_worker() -> None:
            try:
                staging_root = resolve_update_staging_root(install_dir=self._get_install_dir())
                staged = prepare_staged_update(
                    manifest,
                    chunks=stream_update_artifact(manifest),
                    staging_root=staging_root,
                    approve=lambda _m, _p: True,
                )
                if staged is None:
                    return
                self._signals.download_ready.emit(manifest, staged, interactive)
            except Exception as exc:
                self._signals.download_failed.emit(str(exc), interactive)

        thread = threading.Thread(target=download_worker, daemon=True, name="UpdateDownloadThread")
        thread.start()

    @pyqtSlot(object, object, bool)
    def _on_download_ready(self, manifest: ReleaseManifest, staged_path: Path, interactive: bool) -> None:
        self._is_downloading = False
        target = Path(sys.executable).resolve()
        backup = target.with_name(f"{target.name}.v{Config.VERSION}.{uuid4().hex[:8]}.bak")
        staging_root = resolve_update_staging_root(install_dir=self._get_install_dir())
        result_file = update_result_path(staging_root)

        reply = QMessageBox.question(
            self._get_dialog_parent(),
            "업데이트 검증 완료",
            f"업데이트 v{manifest.version}의 디지털 서명과 파일 무결성을 확인했습니다.\n"
            "지금 설치를 진행하고 프로그램을 다시 시작하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            try:
                staged_path.unlink(missing_ok=True)
            except OSError:
                pass
            return

        try:
            launch_update_helper(
                target=target,
                staged=staged_path,
                backup=backup,
                parent_pid=os.getpid(),
                expected_sha256=manifest.artifact_sha256,
                expected_size=manifest.artifact_size,
                result_file=result_file,
            )
        except Exception as exc:
            try:
                staged_path.unlink(missing_ok=True)
            except OSError:
                pass
            self._handle_failure(f"업데이트 설치 시작 실패: {exc}", interactive)
            return

        if self.window and hasattr(self.window, "quit_app"):
            self.window.quit_app()
        else:
            QApplication.quit()

    @pyqtSlot(str, bool)
    def _on_download_failed(self, error: str, interactive: bool) -> None:
        self._is_downloading = False
        self._handle_failure(f"업데이트 다운로드 실패: {error}", interactive)

    @pyqtSlot(bool)
    def _on_not_available(self, interactive: bool) -> None:
        self._is_checking = False
        if not interactive:
            return
        if self.window and hasattr(self.window, "statusBar"):
            status_bar = getattr(self.window, "statusBar")()
            if status_bar:
                status_bar.showMessage("✅ 현재 최신 버전을 사용 중입니다.", 3000)
        QMessageBox.information(
            self._get_dialog_parent(),
            "업데이트",
            f"현재 최신 버전(v{Config.VERSION})을 사용 중입니다.",
        )

    @pyqtSlot(str, bool)
    def _on_check_failed(self, error: str, interactive: bool) -> None:
        self._is_checking = False
        self._handle_failure(error, interactive)

    def _handle_failure(self, error: str, interactive: bool) -> None:
        if not interactive:
            logger.warning("Background update check error: %s", error)
            return
        dialog = QMessageBox(self._get_dialog_parent())
        dialog.setWindowTitle("업데이트 확인 실패")
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText(
            "업데이트를 확인하지 못했습니다.\n\n"
            f"오류: {error}\n\n"
            "최신 버전은 GitHub 릴리스 페이지에서 직접 확인할 수 있습니다."
        )
        release_button = dialog.addButton("릴리스 페이지 열기", QMessageBox.ButtonRole.ActionRole)
        dialog.addButton("닫기", QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        if dialog.clickedButton() is release_button:
            _open_latest_release_page()


__all__ = ["UpdaterController"]
