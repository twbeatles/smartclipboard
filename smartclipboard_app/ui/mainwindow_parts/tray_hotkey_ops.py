"""MainWindow tray and hotkey helper operations."""

from __future__ import annotations

from smartclipboard_app.ui.clipboard_guard import mark_internal_copy


def _normalized_hotkey_value(value, fallback: str) -> str:
    normalized = str(value or fallback).strip().lower()
    return normalized or fallback


def _load_hotkeys(self, logger, json, default_hotkeys, hotkeys_override=None):
    if hotkeys_override is not None:
        raw_hotkeys = hotkeys_override
    else:
        raw_hotkeys = self.db.get_setting("hotkeys", json.dumps(default_hotkeys))

    if isinstance(raw_hotkeys, dict):
        hotkeys = dict(raw_hotkeys)
    else:
        try:
            hotkeys = json.loads(raw_hotkeys)
            if not isinstance(hotkeys, dict):
                raise ValueError("hotkeys must be a JSON object")
        except Exception as parse_exc:
            logger.warning(f"Invalid hotkeys setting; resetting to defaults: {parse_exc}")
            hotkeys = dict(default_hotkeys)
            if hotkeys_override is None:
                self.db.set_setting("hotkeys", json.dumps(hotkeys))

    return {
        "show_main": _normalized_hotkey_value(hotkeys.get("show_main"), default_hotkeys["show_main"]),
        "show_mini": _normalized_hotkey_value(hotkeys.get("show_mini"), default_hotkeys["show_mini"]),
        "paste_last": _normalized_hotkey_value(hotkeys.get("paste_last"), default_hotkeys["paste_last"]),
    }


def _validate_hotkeys(hotkeys: dict[str, str]) -> str | None:
    for label, value in hotkeys.items():
        if not value.strip():
            return f"'{label}' 단축키가 비어 있습니다."

    values = list(hotkeys.values())
    if len(values) != len(set(values)):
        return "단축키 조합이 서로 중복됩니다."

    return None


def _remove_hotkeys(keyboard, handles):
    for hk in handles:
        try:
            keyboard.remove_hotkey(hk)
        except Exception:
            pass


def _register_hotkey_handles(self, keyboard, hotkeys, mini_enabled):
    handles = []
    handles.append(keyboard.add_hotkey(hotkeys["show_main"], lambda: self.show_main_signal.emit()))
    if mini_enabled:
        handles.append(keyboard.add_hotkey(hotkeys["show_mini"], lambda: self.toggle_mini_signal.emit()))
    handles.append(keyboard.add_hotkey(hotkeys["paste_last"], lambda: self.paste_last_signal.emit()))
    return handles


def register_hotkeys_impl(
    self,
    logger,
    keyboard,
    json,
    default_hotkeys,
    hotkeys_override=None,
    persist=False,
):
    """Register global hotkeys from persisted settings."""
    self._last_hotkey_error = ""
    mini_enabled = self.db.get_setting("mini_window_enabled", "true").lower() == "true"
    old_handles = list(getattr(self, "_registered_hotkeys", []) or [])
    old_hotkeys = _load_hotkeys(self, logger, json, default_hotkeys)
    hotkeys = _load_hotkeys(self, logger, json, default_hotkeys, hotkeys_override=hotkeys_override)

    validation_error = _validate_hotkeys(hotkeys)
    if validation_error:
        self._last_hotkey_error = validation_error
        logger.warning("Hotkey validation error: %s", validation_error)
        return False

    _remove_hotkeys(keyboard, old_handles)
    new_handles = []
    try:
        new_handles = _register_hotkey_handles(self, keyboard, hotkeys, mini_enabled)
        self._registered_hotkeys = new_handles
        if persist:
            self.db.set_setting("hotkeys", json.dumps(hotkeys))

        mini_label = hotkeys["show_mini"] if mini_enabled else "(비활성화)"
        if mini_enabled:
            logger.info(f"Mini window hotkey registered: {hotkeys['show_mini']}")
        else:
            logger.info("Mini window hotkey disabled by user setting")
        logger.info(
            "Hotkeys registered: %s, %s, %s",
            hotkeys["show_main"],
            mini_label,
            hotkeys["paste_last"],
        )
        return True
    except Exception as hotkey_exc:
        _remove_hotkeys(keyboard, new_handles)
        try:
            restored_handles = _register_hotkey_handles(self, keyboard, old_hotkeys, mini_enabled)
        except Exception as restore_exc:
            restored_handles = []
            logger.warning(f"Hotkey restore error: {restore_exc}")
        self._registered_hotkeys = restored_handles
        self._last_hotkey_error = str(hotkey_exc)
        logger.warning(f"Hotkey registration error: {hotkey_exc}")
        return False


def toggle_mini_window_slot_impl(self, logger):
    try:
        if self.db.get_setting("mini_window_enabled", "true").lower() != "true":
            return

        if self.mini_window.isVisible():
            self.mini_window.hide()
        else:
            from PyQt6.QtGui import QCursor

            cursor_pos = QCursor.pos()
            self.mini_window.move(cursor_pos.x() - 150, cursor_pos.y() - 200)
            self.mini_window.show()
            self.mini_window.activateWindow()
    except Exception as mini_exc:
        logger.error(f"Toggle mini window error: {mini_exc}")


def paste_last_item_slot_impl(self, logger, qpixmap_cls, qtimer_cls, keyboard):
    try:
        items = self.db.get_items("", "전체")
        if not items:
            return

        pid, content, ptype, *_ = max(items, key=lambda item: (item[3] or "", item[0]))
        data = self.db.get_content(pid)
        if not data:
            return

        content, blob, ptype = data
        mark_internal_copy(self)
        if ptype == "IMAGE" and blob:
            pixmap = qpixmap_cls()
            pixmap.loadFromData(blob)
            self.clipboard.setPixmap(pixmap)
        else:
            self.clipboard.setText(content)
        self.db.increment_use_count(pid)
        qtimer_cls.singleShot(100, lambda: keyboard.send("ctrl+v"))
    except Exception as paste_exc:
        logger.error(f"Paste last item error: {paste_exc}")


def init_tray_impl(self, version, qaction_cls, qmenu_cls, qsystem_tray_icon_cls):
    self.tray_icon = qsystem_tray_icon_cls(self)
    self.tray_icon.setIcon(self.app_icon)
    self.tray_icon.setToolTip(f"스마트 클립보드 프로 v{version}")

    self.tray_menu = qmenu_cls()
    self.update_tray_theme()

    show_action = qaction_cls("보기", self)
    show_action.triggered.connect(self.show_window_from_tray)

    self.tray_privacy_action = qaction_cls("프라이버시 모드", self, checkable=True)
    self.tray_privacy_action.triggered.connect(self.toggle_privacy_mode)

    self.tray_pause_action = qaction_cls("⏸ 모니터링 일시정지", self, checkable=True)
    self.tray_pause_action.triggered.connect(self.toggle_monitoring_pause)

    quit_action = qaction_cls("앱 종료", self)
    quit_action.triggered.connect(self.quit_app)

    adv_menu = qmenu_cls("고급")
    adv_menu.addAction("설정 초기화", self.reset_settings)
    adv_menu.addAction("클립보드 모니터 재시작", self.reset_clipboard_monitor)

    self.tray_menu.addAction(show_action)
    self.tray_menu.addSeparator()
    self.tray_menu.addAction(self.tray_privacy_action)
    self.tray_menu.addAction(self.tray_pause_action)
    self.tray_menu.addSeparator()
    self.tray_menu.addMenu(adv_menu)
    self.tray_menu.addSeparator()
    self.tray_menu.addAction(quit_action)

    self.tray_icon.setContextMenu(self.tray_menu)
    self.tray_icon.activated.connect(self.on_tray_activated)
    self.tray_icon.show()


def on_tray_activated_impl(self, reason, qsystem_tray_icon_cls):
    if reason in (
        qsystem_tray_icon_cls.ActivationReason.Trigger,
        qsystem_tray_icon_cls.ActivationReason.DoubleClick,
    ):
        if self.isVisible():
            self.hide()
        else:
            self.show_window_from_tray()


def show_window_from_tray_impl(self):
    self.show()
    self.activateWindow()
    self.raise_()
    self.search_input.setFocus()
    self.update_status_bar()
