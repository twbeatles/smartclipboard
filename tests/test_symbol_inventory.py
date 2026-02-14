import importlib.util
import inspect
import json
import pathlib
import unittest

from scripts.refactor_symbol_inventory import build_inventory


class SymbolInventoryTests(unittest.TestCase):
    def test_legacy_main_matches_baseline_inventory(self):
        baseline_path = pathlib.Path("tests/baseline/symbol_inventory_v10_6.json")
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        current = build_inventory("smartclipboard_app/legacy_main.py")
        self.assertEqual(current, baseline)

    def test_entrypoint_and_export_compatibility(self):
        facade_path = pathlib.Path("클립모드 매니저.py")
        text = facade_path.read_text(encoding="utf-8")
        self.assertIn('if __name__ == "__main__":', text)
        self.assertIn("run(", text)

        spec = importlib.util.spec_from_file_location("smartclipboard_facade", facade_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        expected = [
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
        ]
        for name in expected:
            self.assertTrue(hasattr(module, name), f"missing export: {name}")

    def test_lazy_package_exports_available(self):
        import smartclipboard_app as app_pkg
        import smartclipboard_app.managers as managers_pkg
        import smartclipboard_app.ui as ui_pkg
        import smartclipboard_app.ui.dialogs as dialogs_pkg
        import smartclipboard_app.ui.widgets as widgets_pkg

        self.assertTrue(callable(app_pkg.run))
        self.assertTrue(hasattr(managers_pkg, "SecureVaultManager"))
        self.assertTrue(hasattr(ui_pkg, "MainWindow"))
        self.assertTrue(hasattr(dialogs_pkg, "SnippetDialog"))
        self.assertTrue(hasattr(dialogs_pkg, "SnippetManagerDialog"))
        self.assertTrue(hasattr(widgets_pkg, "ToastNotification"))

    def test_snippet_manager_use_snippet_accepts_signal_args(self):
        import smartclipboard_app.ui.dialogs as dialogs_pkg

        method = dialogs_pkg.SnippetManagerDialog.use_snippet
        params = list(inspect.signature(method).parameters.values())
        has_varargs = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params)
        self.assertTrue(has_varargs, "use_snippet should accept extra signal args")


if __name__ == "__main__":
    unittest.main(verbosity=2)
