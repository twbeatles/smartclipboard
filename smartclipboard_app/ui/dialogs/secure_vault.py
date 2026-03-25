"""Secure vault dialog module."""

from __future__ import annotations

from typing import Protocol, TypeVar, cast

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from smartclipboard_app.ui.clipboard_guard import mark_internal_copy

T = TypeVar("T")


class _VaultParent(Protocol):
    def statusBar(self) -> QStatusBar | None: ...


def _ensure(value: T | None) -> T:
    assert value is not None
    return value


def _vault_parent(value: object | None) -> _VaultParent | None:
    if value is not None and hasattr(value, "statusBar"):
        return cast(_VaultParent, value)
    return None


class SecureVaultDialog(QDialog):
    """Encrypted secure-vault UI."""

    def __init__(self, parent, db, vault_manager):
        super().__init__(parent)
        self.db = db
        self.vault = vault_manager
        self.parent_window = parent
        self.setWindowTitle("🔒 보안 보관함")
        self.setMinimumSize(500, 450)
        self.init_ui()

        if self.vault.is_unlocked:
            self.load_items()
        else:
            self.show_lock_ui()

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(12)

        self.status_label = QLabel("🔒 보관함이 잠겨 있습니다")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.main_layout.addWidget(self.status_label)

        self.password_widget = QWidget()
        pw_layout = QVBoxLayout(self.password_widget)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("마스터 비밀번호 입력...")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self.unlock_vault)
        pw_layout.addWidget(self.password_input)

        btn_unlock = QPushButton("🔓 잠금 해제")
        btn_unlock.clicked.connect(self.unlock_vault)
        pw_layout.addWidget(btn_unlock)

        self.main_layout.addWidget(self.password_widget)

        self.items_widget = QWidget()
        items_layout = QVBoxLayout(self.items_widget)
        items_layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        btn_add = QPushButton("➕ 새 항목")
        btn_add.clicked.connect(self.add_item)
        btn_change_password = QPushButton("🔁 비밀번호 변경")
        btn_change_password.clicked.connect(self.change_master_password)
        btn_lock = QPushButton("🔒 잠금")
        btn_lock.clicked.connect(self.lock_vault)
        toolbar.addWidget(btn_add)
        toolbar.addWidget(btn_change_password)
        toolbar.addStretch()
        toolbar.addWidget(btn_lock)
        items_layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["레이블", "생성일", "동작"])
        header = _ensure(self.table.horizontalHeader())
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 100)
        vertical_header = self.table.verticalHeader()
        if vertical_header is not None:
            vertical_header.setVisible(False)
        items_layout.addWidget(self.table)

        self.items_widget.setVisible(False)
        self.main_layout.addWidget(self.items_widget)

        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.close)
        self.main_layout.addWidget(btn_close)

    def show_lock_ui(self):
        self.status_label.setText("🔒 보관함이 잠겨 있습니다")
        self.password_widget.setVisible(True)
        self.items_widget.setVisible(False)
        if not self.vault.has_master_password():
            self.status_label.setText("🔐 마스터 비밀번호를 설정해주세요 (최초 설정)")

    def unlock_vault(self):
        password = self.password_input.text()
        if not password:
            QMessageBox.warning(self, "경고", "비밀번호를 입력하세요.")
            return

        if not self.vault.has_master_password():
            is_valid, error_msg = self.validate_password_strength(password)
            if not is_valid:
                QMessageBox.warning(self, "비밀번호 강도 부족", error_msg)
                return
            if self.vault.set_master_password(password):
                QMessageBox.information(self, "설정 완료", "마스터 비밀번호가 설정되었습니다.")
                self.load_items()
            else:
                QMessageBox.critical(self, "오류", "암호화 라이브러리가 없습니다.\npip install cryptography")
        else:
            if self.vault.unlock(password):
                self.load_items()
            else:
                QMessageBox.warning(self, "실패", "비밀번호가 일치하지 않습니다.")

        self.password_input.clear()

    def lock_vault(self):
        self.vault.lock()
        self.show_lock_ui()

    def load_items(self):
        self.status_label.setText("🔓 보관함이 열려 있습니다")
        self.password_widget.setVisible(False)
        self.items_widget.setVisible(True)

        items = self.db.get_vault_items()
        self.table.setRowCount(0)
        for row_idx, (vid, encrypted, label, created_at) in enumerate(items):
            self.table.insertRow(row_idx)

            label_item = QTableWidgetItem(label or "[레이블 없음]")
            label_item.setData(Qt.ItemDataRole.UserRole, vid)
            self.table.setItem(row_idx, 0, label_item)
            self.table.setItem(row_idx, 1, QTableWidgetItem(created_at[:10] if created_at else ""))

            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(2, 2, 2, 2)

            btn_copy = QPushButton("📋")
            btn_copy.setToolTip("복호화하여 복사")
            btn_copy.clicked.connect(lambda checked, v=vid, e=encrypted: self.copy_item(v, e))
            btn_delete = QPushButton("🗑")
            btn_delete.setToolTip("삭제")
            btn_delete.clicked.connect(lambda checked, v=vid: self.delete_item(v))

            btn_layout.addWidget(btn_copy)
            btn_layout.addWidget(btn_delete)
            self.table.setCellWidget(row_idx, 2, btn_widget)

    def add_item(self):
        label, ok1 = QInputDialog.getText(self, "새 항목", "레이블 (선택사항):")
        if not ok1:
            return
        content, ok2 = QInputDialog.getMultiLineText(self, "새 항목", "저장할 내용:")
        if ok2 and content:
            encrypted = self.vault.encrypt(content)
            if encrypted:
                self.db.add_vault_item(encrypted, label)
                self.load_items()
            else:
                QMessageBox.warning(self, "오류", "암호화에 실패했습니다.")

    def copy_item(self, _vid, encrypted_data):
        decrypted = self.vault.decrypt(encrypted_data)
        if decrypted:
            clipboard = QApplication.clipboard()
            if clipboard is None:
                QMessageBox.warning(self, "오류", "클립보드에 접근할 수 없습니다.")
                return
            mark_internal_copy(self.parent_window)
            clipboard.setText(decrypted)
            parent = _vault_parent(self.parent_window)
            if parent is not None:
                status_bar = parent.statusBar()
                if status_bar is not None:
                    status_bar.showMessage("✅ 복호화된 내용이 클립보드에 복사되었습니다.", 3000)
            self._schedule_clipboard_clear(decrypted)
        else:
            QMessageBox.warning(self, "오류", "복호화에 실패했습니다. 보관함을 다시 열어주세요.")

    def _schedule_clipboard_clear(self, text):
        QTimer.singleShot(30000, lambda expected=text: self._clear_clipboard_if_unchanged(expected))

    def _clear_clipboard_if_unchanged(self, expected_text):
        clipboard = QApplication.clipboard()
        if clipboard is None:
            return
        try:
            if clipboard.text() != expected_text:
                return
        except Exception:
            return
        mark_internal_copy(self.parent_window)
        clipboard.setText("")

    def change_master_password(self):
        if not self.vault.is_unlocked:
            QMessageBox.warning(self, "경고", "보관함을 먼저 잠금 해제하세요.")
            return

        current_password, ok = QInputDialog.getText(
            self,
            "현재 비밀번호 확인",
            "현재 마스터 비밀번호:",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return
        new_password, ok = QInputDialog.getText(
            self,
            "새 비밀번호",
            "새 마스터 비밀번호:",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return
        is_valid, error_msg = self.validate_password_strength(new_password)
        if not is_valid:
            QMessageBox.warning(self, "비밀번호 강도 부족", error_msg)
            return
        confirm_password, ok = QInputDialog.getText(
            self,
            "새 비밀번호 확인",
            "새 마스터 비밀번호 확인:",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return
        if new_password != confirm_password:
            QMessageBox.warning(self, "경고", "새 비밀번호 확인이 일치하지 않습니다.")
            return
        if not self.vault.change_master_password(current_password, new_password):
            QMessageBox.warning(self, "오류", "마스터 비밀번호 변경에 실패했습니다.")
            return
        QMessageBox.information(self, "완료", "마스터 비밀번호가 변경되었습니다.")

    def delete_item(self, vid):
        reply = QMessageBox.question(
            self,
            "삭제 확인",
            "이 항목을 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.db.delete_vault_item(vid)
            self.load_items()

    def validate_password_strength(self, password):
        if len(password) < 8:
            return False, "비밀번호는 최소 8자 이상이어야 합니다."
        if not any(c.isdigit() for c in password):
            return False, "비밀번호에 숫자가 포함되어야 합니다."
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            return False, "비밀번호에 특수문자가 포함되어야 합니다."
        return True, ""


__all__ = ["SecureVaultDialog"]
