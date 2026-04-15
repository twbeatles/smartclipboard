"""History context-menu feature helpers."""

from __future__ import annotations

from typing import TypeVar
from urllib.parse import quote

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMenu

from smartclipboard_app.ui.clipboard_guard import mark_internal_copy

T = TypeVar("T")


def _ensure(value: T | None) -> T:
    assert value is not None
    return value


def _copy_text(self, text: str) -> None:
    mark_internal_copy(self)
    self.clipboard.setText(text)


def build_google_search_url(text: str) -> str:
    query = str(text or "").strip()
    if not query:
        return "https://www.google.com/search"
    return f"https://www.google.com/search?q={quote(query, safe='')}"


def _sync_context_menu_selection(self, pos):
    item = self.table.itemAt(pos)
    if item is None:
        return None

    row_getter = getattr(self.table, "row", None)
    row = row_getter(item) if callable(row_getter) else None
    if row is None:
        return item

    selection_model = self.table.selectionModel()
    if selection_model is None:
        return item

    selected_rows = {index.row() for index in selection_model.selectedRows()}
    if row not in selected_rows:
        clear_selection = getattr(self.table, "clearSelection", None)
        if callable(clear_selection):
            clear_selection()
        self.table.selectRow(row)
    return item


def init_menu_impl(self, THEMES):
    menubar = _ensure(self.menuBar())
    file_menu = _ensure(menubar.addMenu("파일"))
    action_export = QAction("💾 텍스트 내보내기", self)
    action_export.triggered.connect(self.export_history)
    file_menu.addAction(action_export)
    file_menu.addSeparator()
    action_backup = QAction("📦 데이터 백업...", self)
    action_backup.triggered.connect(self.backup_data)
    file_menu.addAction(action_backup)
    action_restore = QAction("♻️ 데이터 복원...", self)
    action_restore.triggered.connect(self.restore_data)
    file_menu.addAction(action_restore)
    file_menu.addSeparator()
    action_quit = QAction("❌ 종료", self)
    action_quit.setShortcut("Ctrl+Q")
    action_quit.triggered.connect(self.quit_app)
    file_menu.addAction(action_quit)

    edit_menu = _ensure(menubar.addMenu("편집"))
    action_clear = QAction("🗑️ 기록 전체 삭제", self)
    action_clear.triggered.connect(self.clear_all_history)
    edit_menu.addAction(action_clear)
    edit_menu.addSeparator()
    action_snippets = QAction("📝 스니펫 관리...", self)
    action_snippets.triggered.connect(self.show_snippet_manager)
    edit_menu.addAction(action_snippets)
    edit_menu.addSeparator()
    action_export_adv = QAction("📤 고급 내보내기...", self)
    action_export_adv.triggered.connect(self.show_export_dialog)
    edit_menu.addAction(action_export_adv)
    action_import = QAction("📥 가져오기...", self)
    action_import.triggered.connect(self.show_import_dialog)
    edit_menu.addAction(action_import)
    edit_menu.addSeparator()
    action_trash = QAction("🗑️ 휴지통...", self)
    action_trash.triggered.connect(self.show_trash)
    edit_menu.addAction(action_trash)

    view_menu = _ensure(menubar.addMenu("보기"))
    action_stats = QAction("📊 히스토리 통계...", self)
    action_stats.triggered.connect(self.show_statistics)
    view_menu.addAction(action_stats)
    action_mini = QAction("📋 빠른 클립보드 (미니 창)", self)
    action_mini.setShortcut("Alt+V")
    action_mini.triggered.connect(self.toggle_mini_window)
    view_menu.addAction(action_mini)
    view_menu.addSeparator()
    self.action_ontop = QAction("📌 항상 위 고정", self)
    self.action_ontop.setCheckable(True)
    self.action_ontop.setChecked(bool(getattr(self, "always_on_top", False)))
    self.action_ontop.triggered.connect(self.toggle_always_on_top)
    view_menu.addAction(self.action_ontop)
    view_menu.addSeparator()
    theme_menu = _ensure(view_menu.addMenu("🎨 테마"))
    for key, theme in THEMES.items():
        action = QAction(theme["name"], self)
        action.setData(key)
        action.triggered.connect(lambda checked, k=key: self.change_theme(k))
        theme_menu.addAction(action)

    settings_menu = _ensure(menubar.addMenu("설정"))
    self.action_startup = QAction("🚀 시작 시 자동 실행", self)
    self.action_startup.setCheckable(True)
    self.action_startup.setChecked(self.check_startup_registry())
    self.action_startup.triggered.connect(self.toggle_startup)
    settings_menu.addAction(self.action_startup)
    settings_menu.addSeparator()
    action_rules = QAction("⚙️ 복사 규칙 관리...", self)
    action_rules.triggered.connect(self.show_copy_rules)
    settings_menu.addAction(action_rules)
    action_collections = QAction("📁 컬렉션 관리...", self)
    action_collections.triggered.connect(self.show_collection_manager)
    settings_menu.addAction(action_collections)
    action_actions = QAction("⚡ 액션 자동화...", self)
    action_actions.triggered.connect(self.show_clipboard_actions)
    settings_menu.addAction(action_actions)
    action_hotkeys = QAction("⌨️ 핫키 설정...", self)
    action_hotkeys.triggered.connect(self.show_hotkey_settings)
    settings_menu.addAction(action_hotkeys)
    action_settings = QAction("⚙️ 설정...", self)
    action_settings.triggered.connect(self.show_settings)
    settings_menu.addAction(action_settings)
    settings_menu.addSeparator()
    action_vault = QAction("🔒 보안 보관함...", self)
    action_vault.triggered.connect(self.show_secure_vault)
    settings_menu.addAction(action_vault)
    settings_menu.addSeparator()
    self.action_privacy = QAction("🔒 프라이버시 모드 (기록 중지)", self)
    self.action_privacy.setCheckable(True)
    self.action_privacy.triggered.connect(self.toggle_privacy_mode)
    settings_menu.addAction(self.action_privacy)
    self.action_debug = QAction("🐛 디버그 모드", self)
    self.action_debug.setCheckable(True)
    self.action_debug.triggered.connect(self.toggle_debug_mode)
    settings_menu.addAction(self.action_debug)

    help_menu = _ensure(menubar.addMenu("도움말"))
    action_shortcuts = QAction("⌨️ 키보드 단축키", self)
    action_shortcuts.triggered.connect(self.show_shortcuts_dialog)
    help_menu.addAction(action_shortcuts)
    help_menu.addSeparator()
    action_about = QAction("ℹ️ 정보", self)
    action_about.triggered.connect(self.show_about_dialog)
    help_menu.addAction(action_about)


def show_context_menu_impl(self, pos, THEMES, webbrowser):
    item = _sync_context_menu_selection(self, pos)
    if not item:
        return

    theme = THEMES.get(self.current_theme, THEMES["dark"])
    menu = QMenu(self)
    menu.setStyleSheet(
        f"""
        QMenu {{ background-color: {theme["surface"]}; color: {theme["text"]}; border: 1px solid {theme["border"]}; padding: 5px; }}
        QMenu::item {{ padding: 8px 20px; }}
        QMenu::item:selected {{ background-color: {theme["primary"]}; }}
    """
    )

    copy_action = _ensure(menu.addAction("📄 복사"))
    copy_action.triggered.connect(self.copy_item)
    paste_action = _ensure(menu.addAction("📋 붙여넣기"))
    paste_action.triggered.connect(self.paste_selected)
    menu.addSeparator()

    pid = self.get_selected_id()
    if pid:
        data = self.db.get_content(pid)
        if data and data[2] == "LINK":
            url = data[0]
            open_menu = _ensure(menu.addMenu("🌐 링크 열기"))
            open_default = _ensure(open_menu.addAction("🔗 기본 브라우저로 열기"))
            open_default.triggered.connect(lambda: webbrowser.open(url))
            open_menu.addSeparator()
            copy_url = _ensure(open_menu.addAction("📋 URL 복사"))
            copy_url.triggered.connect(lambda: _copy_text(self, url))
            search_action = _ensure(open_menu.addAction("🔍 Google에서 검색"))
            search_action.triggered.connect(lambda: webbrowser.open(build_google_search_url(url)))
            menu.addSeparator()

    pin_action = _ensure(menu.addAction("📌 고정/해제"))
    pin_action.triggered.connect(self.toggle_pin)
    bookmark_action = _ensure(menu.addAction("⭐ 북마크 토글"))
    bookmark_action.triggered.connect(self.toggle_bookmark)
    tag_action = _ensure(menu.addAction("🏷️ 태그 편집"))
    tag_action.triggered.connect(self.edit_tag)
    note_action = _ensure(menu.addAction("📝 메모 추가/편집"))
    note_action.triggered.connect(self.edit_note)

    collection_menu = _ensure(menu.addMenu("📁 컬렉션으로 이동"))
    collections = self.db.get_collections()
    if collections:
        for cid, cname, cicon, ccolor, _ in collections:
            c_action = _ensure(collection_menu.addAction(f"{cicon} {cname}"))
            c_action.triggered.connect(lambda checked, col_id=cid: self.move_to_collection(col_id))
        collection_menu.addSeparator()
    new_col_action = _ensure(collection_menu.addAction("➕ 새 컬렉션 만들기"))
    new_col_action.triggered.connect(self.create_collection)
    manage_col_action = _ensure(collection_menu.addAction("⚙️ 컬렉션 관리..."))
    manage_col_action.triggered.connect(self.show_collection_manager)
    remove_col_action = _ensure(collection_menu.addAction("🚫 컬렉션에서 제거"))
    remove_col_action.triggered.connect(lambda: self.move_to_collection(None))
    menu.addSeparator()

    selection_model = self.table.selectionModel()
    selected_count = len(selection_model.selectedRows()) if selection_model is not None else 0
    if selected_count >= 2:
        merge_action = _ensure(menu.addAction(f"🔗 {selected_count}개 병합"))
        merge_action.triggered.connect(self.merge_selected)
        menu.addSeparator()

    delete_action = _ensure(menu.addAction("🗑️ 삭제 (휴지통)"))
    delete_action.triggered.connect(self.delete_item)
    if pid:
        data = self.db.get_content(pid)
        if data and data[2] not in ["IMAGE"]:
            menu.addSeparator()
            transform_menu = _ensure(menu.addMenu("✍️ 텍스트 변환"))
            upper_action = _ensure(transform_menu.addAction("ABC 대문자 변환"))
            upper_action.triggered.connect(lambda: self.transform_text("upper"))
            lower_action = _ensure(transform_menu.addAction("abc 소문자 변환"))
            lower_action.triggered.connect(lambda: self.transform_text("lower"))
            strip_action = _ensure(transform_menu.addAction("✂️ 공백 제거"))
            strip_action.triggered.connect(lambda: self.transform_text("strip"))
            normalize_action = _ensure(transform_menu.addAction("📋 줄바꿈 정리"))
            normalize_action.triggered.connect(lambda: self.transform_text("normalize"))
            json_action = _ensure(transform_menu.addAction("{ } JSON 포맷팅"))
            json_action.triggered.connect(lambda: self.transform_text("json"))

    menu.exec(_ensure(self.table.viewport()).mapToGlobal(pos))
