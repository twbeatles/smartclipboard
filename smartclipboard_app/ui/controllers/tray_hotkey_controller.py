"""Tray and hotkey controller."""


class TrayHotkeyController:
    def __init__(self, window):
        self.window = window

    def init_tray(self):
        return self.window.init_tray()

    def register_hotkeys(self):
        return self.window.register_hotkeys()

    def on_tray_activated(self, reason):
        return self.window.on_tray_activated(reason)

    def show_window_from_tray(self):
        return self.window.show_window_from_tray()

    def toggle_mini_window(self):
        return self.window.toggle_mini_window()

    def toggle_mini_window_slot(self):
        return self.window._toggle_mini_window_slot()

    def paste_last_item(self):
        return self.window.paste_last_item()

    def paste_last_item_slot(self):
        return self.window._paste_last_item_slot()
