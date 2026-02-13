"""Compatibility facade for SmartClipboard modular layout."""

from __future__ import annotations

import sys

from smartclipboard_app.bootstrap import run
from smartclipboard_app.legacy_main import *  # noqa: F401,F403
from smartclipboard_app.managers.export_import import ExportImportManager
from smartclipboard_app.managers.secure_vault import SecureVaultManager
from smartclipboard_app.ui.dialogs.clipboard_actions import ClipboardActionsDialog
from smartclipboard_app.ui.dialogs.copy_rules import CopyRulesDialog
from smartclipboard_app.ui.dialogs.export_dialog import ExportDialog
from smartclipboard_app.ui.dialogs.hotkeys import HotkeySettingsDialog
from smartclipboard_app.ui.dialogs.import_dialog import ImportDialog
from smartclipboard_app.ui.dialogs.secure_vault import SecureVaultDialog
from smartclipboard_app.ui.dialogs.settings import SettingsDialog
from smartclipboard_app.ui.dialogs.snippets import SnippetDialog, SnippetManagerDialog
from smartclipboard_app.ui.dialogs.statistics import StatisticsDialog
from smartclipboard_app.ui.dialogs.tags import TagEditDialog
from smartclipboard_app.ui.dialogs.trash_dialog import TrashDialog
from smartclipboard_app.ui.main_window import MainWindow
from smartclipboard_app.ui.widgets.floating_mini_window import FloatingMiniWindow
from smartclipboard_app.ui.widgets.toast import ToastNotification
from smartclipboard_core.actions import ClipboardActionManager
from smartclipboard_core.database import ClipboardDB
from smartclipboard_core.worker import Worker, WorkerSignals

__all__ = [
    "MainWindow",
    "SettingsDialog",
    "SecureVaultDialog",
    "ClipboardActionsDialog",
    "ExportDialog",
    "ImportDialog",
    "TrashDialog",
    "HotkeySettingsDialog",
    "SnippetDialog",
    "SnippetManagerDialog",
    "TagEditDialog",
    "StatisticsDialog",
    "CopyRulesDialog",
    "FloatingMiniWindow",
    "ToastNotification",
    "SecureVaultManager",
    "ExportImportManager",
    "ClipboardDB",
    "ClipboardActionManager",
    "Worker",
    "WorkerSignals",
    "run",
]

if __name__ == "__main__":
    sys.exit(run())
