"""MainWindow dialog launcher operations."""

from __future__ import annotations


def show_settings_impl(self, settings_dialog_cls, qdialog_cls):
    dialog = settings_dialog_cls(self, self.db, self.current_theme)
    if dialog.exec() == qdialog_cls.DialogCode.Accepted:
        new_theme = dialog.get_selected_theme()
        if new_theme != self.current_theme:
            self.change_theme(new_theme)
        self.statusBar().showMessage("✅ 설정이 저장되었습니다.", 2000)


def show_snippet_manager_impl(self, snippet_manager_dialog_cls):
    dialog = snippet_manager_dialog_cls(self, self.db)
    dialog.exec()


def show_collection_manager_impl(self, collection_manager_dialog_cls):
    dialog = collection_manager_dialog_cls(self, self.db)
    dialog.exec()


def show_statistics_impl(self, statistics_dialog_cls):
    dialog = statistics_dialog_cls(self, self.db)
    dialog.exec()


def show_copy_rules_impl(self, copy_rules_dialog_cls):
    dialog = copy_rules_dialog_cls(self, self.db)
    dialog.exec()


def show_secure_vault_impl(self, has_crypto, message_box_cls, secure_vault_dialog_cls):
    if not has_crypto:
        message_box_cls.warning(
            self,
            "라이브러리 필요",
            "암호화 기능을 사용하려면 cryptography 라이브러리가 필요합니다.\n\npip install cryptography",
        )
        return
    dialog = secure_vault_dialog_cls(self, self.db, self.vault_manager)
    dialog.exec()


def show_clipboard_actions_impl(self, clipboard_actions_dialog_cls):
    dialog = clipboard_actions_dialog_cls(self, self.db, self.action_manager)
    dialog.exec()


def show_export_dialog_impl(self, export_dialog_cls, qdialog_cls):
    dialog = export_dialog_cls(self, self.export_manager)
    if dialog.exec() == qdialog_cls.DialogCode.Accepted:
        self.statusBar().showMessage("✅ 내보내기 완료", 3000)


def show_import_dialog_impl(self, import_dialog_cls, qdialog_cls):
    dialog = import_dialog_cls(self, self.export_manager)
    if dialog.exec() == qdialog_cls.DialogCode.Accepted:
        self.refresh_collection_filter_options()
        self.load_data()
        self.statusBar().showMessage("✅ 가져오기 완료", 3000)


def show_trash_impl(self, trash_dialog_cls):
    dialog = trash_dialog_cls(self, self.db)
    dialog.exec()


def show_hotkey_settings_impl(self, hotkey_settings_dialog_cls):
    dialog = hotkey_settings_dialog_cls(self, self.db)
    dialog.exec()


def show_shortcuts_dialog_impl(self, message_box_cls):
    shortcuts_text = """
<h2>⌨️ 키보드 단축키</h2>
<table cellspacing="8">
<tr><td><b>Ctrl+Shift+V</b></td><td>창 표시/숨기기 (글로벌)</td></tr>
<tr><td><b>Ctrl+C</b></td><td>선택 항목 복사</td></tr>
<tr><td><b>Enter</b></td><td>복사 후 붙여넣기</td></tr>
<tr><td><b>Delete</b></td><td>선택 항목 삭제</td></tr>
<tr><td><b>Ctrl+P</b></td><td>고정/해제 토글</td></tr>
<tr><td><b>Ctrl+F</b></td><td>검색창 포커스</td></tr>
<tr><td><b>Alt+A</b></td><td>선택 항목 작업 실행</td></tr>
<tr><td><b>Ctrl/Shift+클릭</b></td><td>다중 선택</td></tr>
<tr><td><b>Escape</b></td><td>검색 클리어 / 창 숨기기</td></tr>
<tr><td><b>↑↓</b></td><td>테이블 네비게이션</td></tr>
<tr><td><b>Ctrl+Q</b></td><td>프로그램 종료</td></tr>
</table>
<br>
<p><b>💡 Tip:</b> 헤더를 클릭하면 정렬할 수 있습니다!</p>
"""
    message_box_cls.information(self, "키보드 단축키", shortcuts_text)


def show_about_dialog_impl(self, message_box_cls, version: str):
    about_text = f"""
<h2>📋 스마트 클립보드 프로 v{version}</h2>
<p>고급 클립보드 매니저 - PyQt6 기반</p>
<br>
<p><b>주요 기능:</b></p>
<ul>
<li>클립보드 히스토리 자동 저장</li>
<li>텍스트, 이미지, 링크, 코드 분류</li>
<li>태그 시스템 및 스니펫 관리</li>
<li>복사 규칙 자동화</li>
<li>다크/라이트/오션 테마</li>
</ul>
<br>
<p>© 2025-2026 MySmartTools</p>
"""
    message_box_cls.about(self, f"스마트 클립보드 프로 v{version}", about_text)
