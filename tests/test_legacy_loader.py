import importlib
import os
import sys
import unittest
from pathlib import Path


class LegacyLoaderTests(unittest.TestCase):
    def _reload_legacy_main(self, impl: str):
        old_impl = os.environ.get("SMARTCLIPBOARD_LEGACY_IMPL")
        try:
            os.environ["SMARTCLIPBOARD_LEGACY_IMPL"] = impl
            sys.modules.pop("smartclipboard_app.legacy_main", None)
            module = importlib.import_module("smartclipboard_app.legacy_main")
            return importlib.reload(module)
        finally:
            if old_impl is None:
                os.environ.pop("SMARTCLIPBOARD_LEGACY_IMPL", None)
            else:
                os.environ["SMARTCLIPBOARD_LEGACY_IMPL"] = old_impl

    def test_source_mode_sets_active_impl(self):
        module = self._reload_legacy_main("src")
        self.assertEqual(module.LEGACY_IMPL_REQUESTED, "src")
        self.assertEqual(module.LEGACY_IMPL_ACTIVE, "src")
        self.assertIsNone(module.LEGACY_IMPL_FALLBACK_REASON)

    def test_payload_failure_falls_back_to_src(self):
        payload_path = Path("smartclipboard_app/legacy_main_payload.marshal")
        original = payload_path.read_bytes()
        try:
            payload_path.write_bytes(b"invalid-marshal-payload")
            module = self._reload_legacy_main("payload")
        finally:
            payload_path.write_bytes(original)

        self.assertEqual(module.LEGACY_IMPL_REQUESTED, "payload")
        self.assertEqual(module.LEGACY_IMPL_ACTIVE, "src")
        self.assertIsNotNone(module.LEGACY_IMPL_FALLBACK_REASON)
        reason = (module.LEGACY_IMPL_FALLBACK_REASON or "").lower()
        self.assertTrue("marshal" in reason or "typeerror" in reason)
        self.assertTrue(hasattr(module, "MainWindow"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
