import hashlib
import importlib
import inspect
import json
import marshal
import os
import pathlib
import unittest

from PyQt6.QtWidgets import QApplication

from smartclipboard_app.legacy_payload import compute_source_sha256
from scripts.refactor_symbol_inventory import build_inventory


class PayloadSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def _sig_dict(func):
        signature = inspect.signature(func)
        params = list(signature.parameters.values())
        posonly = [p.name for p in params if p.kind == inspect.Parameter.POSITIONAL_ONLY]
        args = [p.name for p in params if p.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD]
        kwonly = [p.name for p in params if p.kind == inspect.Parameter.KEYWORD_ONLY]
        vararg = next((p.name for p in params if p.kind == inspect.Parameter.VAR_POSITIONAL), None)
        kwarg = next((p.name for p in params if p.kind == inspect.Parameter.VAR_KEYWORD), None)
        defaults_count = sum(1 for p in params if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD) and p.default is not inspect.Parameter.empty)
        kw_defaults_count = sum(1 for p in params if p.kind == inspect.Parameter.KEYWORD_ONLY and p.default is not inspect.Parameter.empty)
        return {
            "posonly": posonly,
            "args": args,
            "vararg": vararg,
            "kwonly": kwonly,
            "kwarg": kwarg,
            "defaults_count": defaults_count,
            "kw_defaults_count": kw_defaults_count,
        }

    def _reload_payload_module(self):
        old_impl = os.environ.get("SMARTCLIPBOARD_LEGACY_IMPL")
        try:
            os.environ["SMARTCLIPBOARD_LEGACY_IMPL"] = "payload"
            importlib.invalidate_caches()
            module = importlib.import_module("smartclipboard_app.legacy_main")
            module = importlib.reload(module)
        finally:
            if old_impl is None:
                os.environ.pop("SMARTCLIPBOARD_LEGACY_IMPL", None)
            else:
                os.environ["SMARTCLIPBOARD_LEGACY_IMPL"] = old_impl

        self.assertEqual(module.LEGACY_IMPL_ACTIVE, "payload", getattr(module, "LEGACY_IMPL_FALLBACK_REASON", None))
        return module

    def test_payload_matches_compiled_source(self):
        src = pathlib.Path("smartclipboard_app/legacy_main_src.py")
        payload = pathlib.Path("smartclipboard_app/legacy_main_payload.marshal")
        manifest_path = pathlib.Path("smartclipboard_app/legacy_main_payload.manifest.json")
        self.assertTrue(src.exists(), "missing source file")
        self.assertTrue(payload.exists(), "missing payload file")
        self.assertTrue(manifest_path.exists(), "missing payload manifest")
        self.assertGreater(payload.stat().st_size, 0, "empty payload file")
        marshal.loads(payload.read_bytes())  # parse guard
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest.get("source_sha256"), compute_source_sha256(src))

        source_inventory = build_inventory(src)
        source_classes = {
            c["name"]: {m["name"]: m["signature"] for m in c["methods"]}
            for c in source_inventory["classes"]
        }
        source_functions = {f["name"]: f["signature"] for f in source_inventory["top_functions"]}
        source_constants = set(source_inventory["constants"])

        module = self._reload_payload_module()

        payload_classes = {}
        for cls_name, cls_obj in inspect.getmembers(module, inspect.isclass):
            if cls_obj.__module__ != module.__name__:
                continue
            methods = {}
            for method_name, attr in cls_obj.__dict__.items():
                if isinstance(attr, classmethod):
                    method = attr.__func__
                elif isinstance(attr, staticmethod):
                    method = attr.__func__
                elif inspect.isfunction(attr):
                    method = attr
                else:
                    continue
                if method.__module__ != module.__name__:
                    continue
                methods[method_name] = self._sig_dict(method)
            payload_classes[cls_name] = methods

        payload_functions = {}
        for fn_name, fn_obj in inspect.getmembers(module, inspect.isfunction):
            if fn_obj.__module__ != module.__name__:
                continue
            payload_functions[fn_name] = self._sig_dict(fn_obj)

        payload_constants = {
            name
            for name, value in module.__dict__.items()
            if name.isupper() and not callable(value)
        }

        source_class_set = set(source_classes.keys())
        payload_class_set = set(payload_classes.keys())
        self.assertTrue(source_class_set.issubset(payload_class_set), "payload missing source classes")

        for class_name, source_methods in source_classes.items():
            payload_methods = payload_classes.get(class_name, {})
            self.assertTrue(set(source_methods.keys()).issubset(set(payload_methods.keys())), f"payload missing methods in {class_name}")
            for method_name, source_sig in source_methods.items():
                self.assertEqual(
                    payload_methods[method_name],
                    source_sig,
                    f"payload signature mismatch: {class_name}.{method_name}",
                )

        self.assertTrue(set(source_functions.keys()).issubset(set(payload_functions.keys())), "payload missing top-level functions")
        for fn_name, source_sig in source_functions.items():
            self.assertEqual(payload_functions[fn_name], source_sig, f"payload signature mismatch: {fn_name}")

        self.assertTrue(source_constants.issubset(payload_constants), "payload missing source constants")

    def test_payload_mode_snippet_signature_accepts_signal_args(self):
        module = self._reload_payload_module()

        method = module.SnippetManagerDialog.use_snippet
        params = list(inspect.signature(method).parameters.values())
        has_varargs = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params)
        self.assertTrue(has_varargs, "payload SnippetManagerDialog.use_snippet must accept signal args")

    def test_payload_fetch_title_uses_first_extracted_url(self):
        class FakeActionDB:
            def get_clipboard_actions(self):
                return [(1, "fetch", r".*", "fetch_title", "{}", 1, 0)]

            def update_url_title(self, item_id, title):
                return True

        module = self._reload_payload_module()

        manager = module.ClipboardActionManager(FakeActionDB())
        captured = {}

        def fake_fetch(url, item_id, action_name):
            captured["url"] = url
            captured["item_id"] = item_id
            captured["action_name"] = action_name

        manager.fetch_url_title_async = fake_fetch
        results = manager.process("prefix https://example.com/path?q=1 suffix", item_id=9)

        self.assertEqual(captured.get("url"), "https://example.com/path?q=1")
        self.assertEqual(captured.get("item_id"), 9)
        self.assertEqual(captured.get("action_name"), "fetch")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][1]["type"], "notify")

    def test_payload_fetch_title_without_url_returns_notify(self):
        class FakeActionDB:
            def get_clipboard_actions(self):
                return [(1, "fetch", r".*", "fetch_title", "{}", 1, 0)]

            def update_url_title(self, item_id, title):
                return True

        module = self._reload_payload_module()

        manager = module.ClipboardActionManager(FakeActionDB())
        called = {"count": 0}

        def fake_fetch(url, item_id, action_name):
            called["count"] += 1

        manager.fetch_url_title_async = fake_fetch
        results = manager.process("url 없음", item_id=3)

        self.assertEqual(called["count"], 0)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][1]["type"], "notify")
        self.assertIn("URL", results[0][1]["message"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

