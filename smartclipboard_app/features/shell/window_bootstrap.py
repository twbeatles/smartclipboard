"""MainWindow bootstrap orchestration.

This module keeps the legacy MainWindow constructor thin while preserving the
legacy runtime namespace used by the public compatibility facade.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def bootstrap_main_window(self: Any, start_minimized: bool, namespace: Mapping[str, Any]) -> None:
    ClipboardDB = namespace["ClipboardDB"]
    QApplication = namespace["QApplication"]
    SecureVaultManager = namespace["SecureVaultManager"]
    ClipboardActionManager = namespace["ClipboardActionManager"]
    ExportImportManager = namespace["ExportImportManager"]
    QSettings = namespace["QSettings"]
    ORG_NAME = namespace["ORG_NAME"]
    APP_NAME = namespace["APP_NAME"]
    VERSION = namespace["VERSION"]
    Qt = namespace["Qt"]
    bind_window_facets = namespace["bind_window_facets"]
    ClipboardController = namespace["ClipboardController"]
    HistoryController = namespace["HistoryController"]
    TrayHotkeyController = namespace["TrayHotkeyController"]
    LifecycleController = namespace["LifecycleController"]
    SettingsController = namespace["SettingsController"]
    ShellUiController = namespace["ShellUiController"]
    FloatingMiniWindow = namespace["FloatingMiniWindow"]
    QTimer = namespace["QTimer"]
    logger = namespace["logger"]

    self.start_minimized = start_minimized
    self.is_data_dirty = True  # v10.4: Lazy loading flag
    self.is_monitoring_paused = False  # v10.6: 모니터링 일시정지 플래그
    try:
        self.db = ClipboardDB()
        self.apply_saved_log_level()
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_change)
        self.is_internal_copy = False
        self.is_privacy_mode = False  # 프라이버시 모드 (모니터링 중지)

        # v8.0: 새 매니저들 초기화
        self.vault_manager = SecureVaultManager(self.db)
        self.action_manager = ClipboardActionManager(self.db)
        self.export_manager = ExportImportManager(self.db)

        # v10.5: 비동기 액션 시그널 연결
        self.action_manager.action_completed.connect(self.on_action_completed)

        self.settings = QSettings(ORG_NAME, APP_NAME)
        self.current_theme = self.db.get_setting("theme", "dark")

        self.setWindowTitle(f"스마트 클립보드 프로 v{VERSION}")
        self.restore_window_state()

        self.app_icon = self.create_app_icon()
        self.setWindowIcon(self.app_icon)

        # v10.5: 기본값 변경 - 항상 위 해제
        self.always_on_top = False
        self.current_tag_filter = None  # 태그 필터
        self.current_collection_filter = "__all__"  # 컬렉션 필터
        self.sort_column = 3  # 기본 정렬: 시간 컨럼
        self.sort_order = Qt.SortOrder.DescendingOrder  # 기본: 내림차순
        self._search_sort_override = False
        bind_window_facets(self)
        self.clipboard_controller = ClipboardController(self)
        self.history_controller = HistoryController(self)
        self.table_controller = self.history_controller
        self.tray_hotkey_controller = TrayHotkeyController(self)
        self.lifecycle_controller = LifecycleController(self)
        self.settings_controller = SettingsController(self)
        self.shell_ui_controller = ShellUiController(self)

        # v10.0: 복사 규칙 캐싱 (성능 최적화)
        self._rules_cache = None
        self._rules_cache_dirty = True
        self._last_hotkey_error = ""
        self._base_shortcuts = []
        self._snippet_shortcuts = []

        # v10.3: 클립보드 디바운스 타이머 (중복 호출 방지)
        self._clipboard_debounce_timer = None

        self.apply_theme()
        self.init_menu()
        self.init_ui()
        self.init_tray()
        self.init_shortcuts()
        bind_window_facets(self)

        # v8.0: 핫키 시그널 연결 (스레드 안전)
        self.toggle_mini_signal.connect(self._toggle_mini_window_slot)
        self.paste_last_signal.connect(self._paste_last_item_slot)
        self.show_main_signal.connect(self.show_window_from_tray)

        # v8.0: 플로팅 미니 창
        self.mini_window = FloatingMiniWindow(self.db, self)

        # 핫키 설정 로드 및 등록 (안정성을 위해 지연 초기화)
        QTimer.singleShot(1000, self.register_hotkeys_at_startup)

        self.update_always_on_top()

        # v10.4: Lazy loading - started minimized면 로드 지연
        if not self.start_minimized:
            self.load_data()

        self.update_status_bar()

        # v8.0: 보관함 자동 잠금 타이머
        self.vault_timer = QTimer(self)
        self.vault_timer.timeout.connect(self.check_vault_timeout)
        self.vault_timer.start(60000)  # 1분마다 타임아웃 체크

        # v10.2: 만료 항목 정리 타이머 (1시간마다)
        self.cleanup_timer = QTimer(self)
        self.cleanup_timer.timeout.connect(self.run_periodic_cleanup)
        self.cleanup_timer.start(3600000)  # 1시간 = 3600000ms

        # v10.7: 일일 자동 백업 (실행 중 날짜 변경 포함)
        self.backup_timer = QTimer(self)
        self.backup_timer.timeout.connect(self.run_daily_backup_if_needed)
        self.backup_timer.start(3600000)  # 1시간마다 확인
        QTimer.singleShot(3000, self.run_daily_backup_if_needed)

        # v10.2: 등록된 핫키 추적 (안전한 해제를 위해)
        self._registered_hotkeys = []

        # 앱 시작 시 5초 후 정리 작업 실행
        QTimer.singleShot(5000, self.run_periodic_cleanup)

        logger.info("SmartClipboard Pro v10.3 started")
    except Exception as e:
        logger.error(f"MainWindow Init Error: {e}", exc_info=True)
        raise e


__all__ = ["bootstrap_main_window"]
