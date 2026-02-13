"""Lifecycle and cleanup controller."""


class LifecycleController:
    def __init__(self, window):
        self.window = window

    def check_vault_timeout(self):
        return self.window.check_vault_timeout()

    def run_periodic_cleanup(self):
        return self.window.run_periodic_cleanup()

    def close_event(self, event):
        return self.window.closeEvent(event)

    def quit_app(self):
        return self.window.quit_app()
