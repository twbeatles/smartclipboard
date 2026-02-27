import hashlib
import importlib
import inspect
import marshal
import os
import pathlib
import unittest

from scripts.refactor_symbol_inventory import build_inventory


class PayloadSyncTests(unittest.TestCase):
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

    def test_payload_matches_compiled_source(self):
        src = pathlib.Path("smartclipboard_app/legacy_main_src.py")
        payload = pathlib.Path("smartclipboard_app/legacy_main_payload.marshal")
        self.assertTrue(src.exists(), "missing source file")
        self.assertTrue(payload.exists(), "missing payload file")
        self.assertGreater(payload.stat().st_size, 0, "empty payload file")
        marshal.loads(payload.read_bytes())  # parse guard

        source_inventory = build_inventory(src)
        source_classes = {
            c["name"]: {m["name"]: m["signature"] for m in c["methods"]}
            for c in source_inventory["classes"]
        }
        source_functions = {f["name"]: f["signature"] for f in source_inventory["top_functions"]}
        source_constants = set(source_inventory["constants"])

        old_impl = os.environ.get("SMARTCLIPBOARD_LEGACY_IMPL")
        try:
            os.environ["SMARTCLIPBOARD_LEGACY_IMPL"] = "payload"
            module = importlib.import_module("smartclipboard_app.legacy_main")
            module = importlib.reload(module)
        finally:
            if old_impl is None:
                os.environ.pop("SMARTCLIPBOARD_LEGACY_IMPL", None)
            else:
                os.environ["SMARTCLIPBOARD_LEGACY_IMPL"] = old_impl

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
        old_impl = os.environ.get("SMARTCLIPBOARD_LEGACY_IMPL")
        try:
            os.environ["SMARTCLIPBOARD_LEGACY_IMPL"] = "payload"
            module = importlib.import_module("smartclipboard_app.legacy_main")
            module = importlib.reload(module)

            method = module.SnippetManagerDialog.use_snippet
            params = list(inspect.signature(method).parameters.values())
            has_varargs = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params)
            self.assertTrue(has_varargs, "payload SnippetManagerDialog.use_snippet must accept signal args")
        finally:
            if old_impl is None:
                os.environ.pop("SMARTCLIPBOARD_LEGACY_IMPL", None)
            else:
                os.environ["SMARTCLIPBOARD_LEGACY_IMPL"] = old_impl


if __name__ == "__main__":
    unittest.main(verbosity=2)
