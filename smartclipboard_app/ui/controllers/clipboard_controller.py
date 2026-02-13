"""Clipboard behavior controller."""


class ClipboardController:
    def __init__(self, window):
        self.window = window

    def on_clipboard_change(self):
        return self.window.on_clipboard_change()

    def process_clipboard(self):
        return self.window.process_clipboard()

    def process_image_clipboard(self, mime_data):
        return self.window._process_image_clipboard(mime_data)

    def process_text_clipboard(self, mime_data):
        return self.window._process_text_clipboard(mime_data)

    def process_actions(self, text, item_id):
        return self.window._process_actions(text, item_id)

    def apply_copy_rules(self, text):
        return self.window.apply_copy_rules(text)

    def analyze_text(self, text):
        return self.window.analyze_text(text)

    def reset_clipboard_monitor(self):
        return self.window.reset_clipboard_monitor()
