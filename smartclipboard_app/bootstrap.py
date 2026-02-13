"""Application bootstrap with preserved runtime behavior."""

from __future__ import annotations

import os
import sys
import traceback

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from .legacy_main import APP_DIR, logger
from .ui.main_window import MainWindow


def _global_exception_handler(exctype, value, tb):
    if issubclass(exctype, (KeyboardInterrupt, SystemExit)):
        sys.__excepthook__(exctype, value, tb)
        return

    logger.error("Uncaught exception", exc_info=(exctype, value, tb))
    error_msg = f"{exctype.__name__}: {value}"
    if QApplication.instance():
        QMessageBox.critical(None, "Critical Error", f"An unexpected error occurred:\n{error_msg}")
    sys.__excepthook__(exctype, value, tb)


def run(argv: list[str] | None = None) -> int:
    """Run SmartClipboard application."""
    argv = argv if argv is not None else sys.argv
    sys.excepthook = _global_exception_handler

    try:
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

        app = QApplication(argv)
        app.setQuitOnLastWindowClosed(False)
        font = QFont("Malgun Gothic", 10)
        font.setStyleHint(QFont.StyleHint.SansSerif)
        app.setFont(font)

        start_minimized = "--minimized" in argv
        window = MainWindow(start_minimized=start_minimized)

        if start_minimized:
            if window.tray_icon:
                window.tray_icon.showMessage(
                    "SmartClipboard Pro",
                    "백그라운드에서 실행 중입니다.",
                    QSystemTrayIcon.MessageIcon.Information,
                    2000,
                )
        else:
            window.show()

        error_log_path = os.path.join(APP_DIR, "debug_startup_error.log")
        if os.path.exists(error_log_path):
            try:
                os.remove(error_log_path)
                logger.info("이전 에러 로그 정리됨")
            except Exception:
                pass

        return app.exec()
    except Exception as exc:
        error_msg = traceback.format_exc()
        error_log_path = os.path.join(APP_DIR, "debug_startup_error.log")
        with open(error_log_path, "w", encoding="utf-8") as fh:
            fh.write(error_msg)
            fh.write(f"\nError: {exc}")

        try:
            if not QApplication.instance():
                _app = QApplication(argv)
            QMessageBox.critical(None, "Startup Error", f"An error occurred:\n{exc}\n\nSee {error_log_path} for details.")
        except Exception:
            print(f"Critical Error:\n{error_msg}")
        return 1

