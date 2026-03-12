"""MainWindow tray and hotkey helper operations."""

from __future__ import annotations


def register_hotkeys_impl(self, logger, keyboard, json, default_hotkeys):
    """Register global hotkeys from persisted settings."""
    try:
        raw_hotkeys = self.db.get_setting("hotkeys", json.dumps(default_hotkeys))
        try:
            hotkeys = json.loads(raw_hotkeys)
            if not isinstance(hotkeys, dict):
                raise ValueError("hotkeys must be a JSON object")
        except Exception as parse_exc:
            logger.warning(f"Invalid hotkeys setting; resetting to defaults: {parse_exc}")
            hotkeys = dict(default_hotkeys)
            self.db.set_setting("hotkeys", json.dumps(hotkeys))

        if hasattr(self, "_registered_hotkeys") and self._registered_hotkeys:
            for hk in self._registered_hotkeys:
                try:
                    keyboard.remove_hotkey(hk)
                except Exception:
                    pass
        self._registered_hotkeys = []

        main_key = hotkeys.get("show_main", "ctrl+shift+v")
        hk1 = keyboard.add_hotkey(main_key, lambda: self.show_main_signal.emit())
        self._registered_hotkeys.append(hk1)

        mini_enabled = self.db.get_setting("mini_window_enabled", "true").lower() == "true"
        if mini_enabled:
            mini_key = hotkeys.get("show_mini", "alt+v")
            hk2 = keyboard.add_hotkey(mini_key, lambda: self.toggle_mini_signal.emit())
            self._registered_hotkeys.append(hk2)
            logger.info(f"Mini window hotkey registered: {mini_key}")
        else:
            mini_key = "(비활성화)"
            logger.info("Mini window hotkey disabled by user setting")

        paste_key = hotkeys.get("paste_last", "ctrl+shift+z")
        hk3 = keyboard.add_hotkey(paste_key, lambda: self.paste_last_signal.emit())
        self._registered_hotkeys.append(hk3)

        logger.info(f"Hotkeys registered: {main_key}, {mini_key}, {paste_key}")
    except Exception as hotkey_exc:
        logger.warning(f"Hotkey registration error: {hotkey_exc}")


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

        pid, content, ptype, *_ = items[0]
        data = self.db.get_content(pid)
        if not data:
            return

        content, blob, ptype = data
        self.is_internal_copy = True
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
