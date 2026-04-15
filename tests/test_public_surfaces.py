import inspect
import importlib
import json
import pathlib
import unittest

from scripts.refactor_symbol_inventory import build_inventory
import smartclipboard_app.legacy_main_src as legacy_main_src
from smartclipboard_core.database import ClipboardDB


class PublicSurfaceTests(unittest.TestCase):
    def test_clipboarddb_public_methods_match_baseline(self):
        baseline_path = pathlib.Path("tests/baseline/clipboarddb_public_methods.txt")
        baseline = [line.strip() for line in baseline_path.read_text(encoding="utf-8").splitlines() if line.strip()]

        current = sorted(
            {
                name
                for name, fn in inspect.getmembers(ClipboardDB, inspect.isfunction)
                if not name.startswith("_")
            }
        )
        self.assertEqual(current, baseline)

    def test_mainwindow_signatures_match_symbol_inventory_baseline(self):
        baseline_inventory_path = pathlib.Path("tests/baseline/symbol_inventory_v10_6.json")
        baseline_inventory = json.loads(baseline_inventory_path.read_text(encoding="utf-8"))
        current_inventory = build_inventory("smartclipboard_app/legacy_main_src.py")

        def _methods(inv: dict) -> dict[str, dict]:
            classes = {c["name"]: c for c in inv["classes"]}
            main_window = classes.get("MainWindow")
            self.assertIsNotNone(main_window, "MainWindow missing in inventory")
            return {m["name"]: m["signature"] for m in main_window["methods"]}

        self.assertEqual(_methods(current_inventory), _methods(baseline_inventory))

    def test_legacy_main_src_exposes_compatibility_aliases(self):
        expected = [
            "WorkerSignals",
            "Worker",
            "ClipboardDB",
            "SecureVaultManager",
            "ClipboardActionManager",
            "ExportImportManager",
            "ToastNotification",
            "SettingsDialog",
            "SecureVaultDialog",
            "ClipboardActionsDialog",
            "ExportDialog",
            "ImportDialog",
            "TrashDialog",
            "FloatingMiniWindow",
            "HotkeySettingsDialog",
            "SnippetDialog",
            "SnippetManagerDialog",
            "CollectionEditDialog",
            "CollectionManagerDialog",
            "TagEditDialog",
            "StatisticsDialog",
            "CopyRulesDialog",
            "MainWindow",
        ]
        for name in expected:
            self.assertTrue(hasattr(legacy_main_src, name), name)

    def test_refactor_facades_and_feature_modules_import(self):
        modules = [
            "smartclipboard_app.ui.mainwindow_parts.menu_ops",
            "smartclipboard_app.ui.mainwindow_parts.table_ops",
            "smartclipboard_app.ui.mainwindow_parts.tray_hotkey_ops",
            "smartclipboard_app.ui.mainwindow_parts.status_lifecycle_ops",
            "smartclipboard_app.ui.mainwindow_parts.clipboard_runtime_ops",
            "smartclipboard_app.ui.mainwindow_parts.ui_ops",
            "smartclipboard_app.ui.mainwindow_parts.theme_ops",
            "smartclipboard_app.features.history.controller",
            "smartclipboard_app.features.clipboard.controller",
            "smartclipboard_app.features.tray_hotkey.controller",
            "smartclipboard_app.features.shell.controller",
            "smartclipboard_app.features.shell_ui.controller",
            "smartclipboard_app.features.settings.controller",
            "smartclipboard_app.features.import_export.manager",
            "smartclipboard_app.features.vault.service",
            "smartclipboard_core.automation.manager",
            "smartclipboard_core.db_parts.search.queries",
            "smartclipboard_core.db_parts.automation.actions",
            "smartclipboard_core.db_parts.catalog.collections",
            "smartclipboard_core.db_parts.retention.trash",
        ]
        for module_name in modules:
            with self.subTest(module=module_name):
                importlib.import_module(module_name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
