"""MainWindow status and lifecycle feature operations."""

from __future__ import annotations

from smartclipboard_app.ui.clipboard_guard import mark_internal_copy


def update_tray_theme_impl(self, THEMES):
    theme = THEMES.get(self.current_theme, THEMES["dark"])
    self.tray_menu.setStyleSheet(
        f"""
            QMenu {{
                background-color: {theme["surface"]};
                color: {theme["text"]};
                border: 1px solid {theme["border"]};
                padding: 5px;
            }}
            QMenu::item {{ padding: 8px 20px; }}
            QMenu::item:selected {{ background-color: {theme["primary"]}; }}
        """
    )


def update_status_bar_impl(self, selection_count, qt_module):
    if hasattr(self, "privacy_indicator"):
        if self.is_privacy_mode:
            self.privacy_indicator.setText("🔒 프라이버시")
        elif self.is_monitoring_paused:
            self.privacy_indicator.setText("⏸ 일시정지")
        else:
            self.privacy_indicator.setText("")

    if self.is_privacy_mode:
        self.statusBar().showMessage("🔒 프라이버시 모드 활성화됨 (클립보드 기록 중지)")
        return

    stats = self.db.get_statistics()
    today_count = self.db.get_today_count()

    status_parts = [
        f"📋 총 {stats['total']}개",
        f"📌 고정 {stats['pinned']}개",
        f"📟 오늘 {today_count}개",
    ]

    if self.is_monitoring_paused:
        status_parts.append("⏸ [일시정지]")

    current_filter = self.filter_combo.currentText() if hasattr(self, "filter_combo") else "전체"
    if current_filter != "전체":
        status_parts.append(f"🔇 {current_filter}")

    collection_filter = getattr(self, "current_collection_filter", "__all__")
    if collection_filter == "__uncategorized__":
        status_parts.append("🗂 미분류")
    elif isinstance(collection_filter, int) and hasattr(self, "collection_filter_combo"):
        label = self.collection_filter_combo.currentText()
        if label:
            status_parts.append(f"🗂 {label}")

    search_query = self.search_input.text() if hasattr(self, "search_input") else ""
    if search_query.strip():
        shown = getattr(self, "_last_display_count", None)
        if shown is not None:
            status_parts.append(f"🔊 검색 {shown}개")

    if selection_count > 0:
        status_parts.append(f"✅ {selection_count}개 선택")

    if hasattr(self, "sort_column") and self.sort_column > 0:
        sort_names = {1: "유형", 2: "내용", 3: "시간", 4: "사용"}
        order = "↑" if self.sort_order == qt_module.SortOrder.AscendingOrder else "↓"
        status_parts.append(f"{sort_names.get(self.sort_column, '')}{order}")

    self.statusBar().showMessage(" | ".join(status_parts))


def check_vault_timeout_impl(self, logger):
    if self.vault_manager.check_timeout():
        logger.info("Vault auto-locked due to inactivity")


def run_periodic_cleanup_impl(self, logger):
    try:
        expired_count = self.db.cleanup_expired_items()
        self.db.cleanup_expired_trash()
        history_deleted = int(self.db.cleanup() or 0)
        if expired_count > 0:
            logger.info(f"주기적 정리: 만료 항목 {expired_count}개 삭제")

        should_refresh = expired_count > 0 or history_deleted > 0
        if not should_refresh:
            return

        is_visible_getter = getattr(self, "isVisible", None)
        is_visible = is_visible_getter() if callable(is_visible_getter) else True
        if is_visible:
            self.load_data()
            self.update_status_bar()
        elif hasattr(self, "is_data_dirty"):
            self.is_data_dirty = True
    except Exception as cleanup_exc:
        logger.debug(f"Periodic cleanup error: {cleanup_exc}")


def quit_app_impl(self, logger, keyboard, qapplication_cls):
    logger.info("앱 종료 시작...")
    try:
        armed_vault_text = getattr(self, "_vault_clipboard_expected_text", None)
        if armed_vault_text:
            clipboard = qapplication_cls.clipboard()
            if clipboard is not None:
                try:
                    if clipboard.text() == armed_vault_text:
                        mark_internal_copy(self)
                        clipboard.setText("")
                        logger.debug("Cleared armed vault clipboard during shutdown")
                except Exception as clipboard_exc:
                    logger.debug(f"Vault clipboard cleanup skipped during shutdown: {clipboard_exc}")
            self._vault_clipboard_expected_text = None
            self._vault_clipboard_expires_at = None

        if hasattr(self, "settings"):
            self.settings.setValue("geometry", self.saveGeometry())

        if hasattr(self, "_registered_hotkeys") and self._registered_hotkeys:
            for hk in self._registered_hotkeys:
                try:
                    keyboard.remove_hotkey(hk)
                except Exception:
                    pass
            self._registered_hotkeys = []
        logger.debug("핫키 모두 해제됨")

        if hasattr(self, "vault_timer") and self.vault_timer.isActive():
            self.vault_timer.stop()
            logger.debug("보관함 타이머 중지됨")

        if hasattr(self, "cleanup_timer") and self.cleanup_timer.isActive():
            self.cleanup_timer.stop()
            logger.debug("정리 타이머 중지됨")

        if hasattr(self, "backup_timer") and self.backup_timer.isActive():
            self.backup_timer.stop()
            logger.debug("백업 타이머 중지됨")

        if hasattr(self, "mini_window") and self.mini_window:
            self.mini_window.close()
            logger.debug("미니 창 종료")

        if hasattr(self, "action_manager") and self.action_manager:
            try:
                self.action_manager.action_completed.disconnect(self.on_action_completed)
            except Exception:
                pass
            self.action_manager.shutdown()
            logger.debug("비동기 액션 정리 완료")
    except Exception as cleanup_exc:
        logger.warning(f"Cleanup warning: {cleanup_exc}")

    try:
        self.db.close()
        logger.debug("DB 연결 종료됨")
    except Exception:
        pass

    logger.info("앱 종료 완료")
    qapplication_cls.quit()
