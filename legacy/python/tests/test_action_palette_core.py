import base64
import json
import time
import unittest
from urllib.parse import quote

from smartclipboard_core.action_palette import (
    ActionContext,
    ActionExecutor,
    ActionRegistry,
    ActionResult,
    build_context,
    create_default_registry,
)


def _ids(actions):
    return [action.id for action in actions]


class ActionPaletteCoreTests(unittest.TestCase):
    def setUp(self):
        self.registry = create_default_registry()
        self.executor = ActionExecutor()

    def _action(self, action_id: str):
        action = self.registry.get(action_id)
        self.assertIsNotNone(action, action_id)
        assert action is not None
        return action

    def test_trim_collapses_outer_whitespace_only(self):
        context = build_context(raw_text="  hello  \n")
        action = self._action("text.trim")
        self.assertTrue(action.is_applicable(context))
        result = self.executor.execute(action, context)
        self.assertEqual(result.kind, "text")
        self.assertEqual(result.value, "hello")
        self.assertTrue(result.copy_to_clipboard)
        self.assertFalse(result.preview)

    def test_collapse_spaces_keeps_newlines(self):
        context = build_context(raw_text="a   b\n\tc\t\td")
        result = self.executor.execute(self._action("text.collapse_spaces"), context)
        self.assertEqual(result.value, "a b\n c d")

    def test_single_line_replaces_newlines_with_space(self):
        context = build_context(raw_text="a\nb\r\nc")
        result = self.executor.execute(self._action("text.single_line"), context)
        self.assertEqual(result.value, "a b c")
        self.assertTrue(result.preview)

    def test_remove_blank_lines_and_dedupe_and_sort(self):
        raw = "Banana\n\napple\nBanana\nCherry\n"
        context = build_context(raw_text=raw)
        self.assertEqual(
            self.executor.execute(self._action("text.remove_blank_lines"), context).value,
            "Banana\napple\nBanana\nCherry",
        )
        self.assertEqual(
            self.executor.execute(self._action("text.dedupe_lines"), context).value,
            "Banana\n\napple\nCherry",
        )
        self.assertEqual(
            self.executor.execute(self._action("text.sort_lines"), context).value,
            "\n\napple\nBanana\nBanana\nCherry",
        )

    def test_sort_lines_is_case_insensitive_and_stable(self):
        context = build_context(raw_text="b\nA\na\nB")
        result = self.executor.execute(self._action("text.sort_lines"), context)
        self.assertEqual(result.value, "A\na\nb\nB")

    def test_case_and_newline_normalization(self):
        context = build_context(raw_text="Hello\r\nWorld\r!")
        self.assertEqual(
            self.executor.execute(self._action("text.lowercase"), context).value,
            "hello\r\nworld\r!",
        )
        self.assertEqual(
            self.executor.execute(self._action("text.uppercase"), context).value,
            "HELLO\r\nWORLD\r!",
        )
        self.assertEqual(
            self.executor.execute(self._action("text.normalize_newlines"), context).value,
            "Hello\nWorld\n!",
        )

    def test_hangul_and_emoji_are_preserved(self):
        context = build_context(raw_text="  안녕 🙂\n안녕 🙂  ")
        result = self.executor.execute(self._action("text.trim"), context)
        self.assertEqual(result.value, "안녕 🙂\n안녕 🙂")
        deduped = self.executor.execute(self._action("text.dedupe_lines"), context)
        self.assertEqual(deduped.value, "  안녕 🙂\n안녕 🙂  ")

    def test_phone_format_reuses_existing_formatter(self):
        context = build_context(raw_text="01012345678")
        self.assertEqual(context.content_type, "phone")
        ids = _ids(self.registry.get_applicable(context))
        self.assertIn("phone.format_kr", ids)
        result = self.executor.execute(self._action("phone.format_kr"), context)
        self.assertEqual(result.value, "010-1234-5678")
        self.assertTrue(result.copy_to_clipboard)

        seoul = build_context(raw_text="021234567")
        self.assertEqual(
            self.executor.execute(self._action("phone.format_kr"), seoul).value,
            "02-123-4567",
        )

    def test_phone_digits_only_and_invalid_phone_hidden(self):
        formatted = build_context(raw_text="010-1234-5678")
        self.assertEqual(
            self.executor.execute(self._action("phone.digits_only"), formatted).value,
            "01012345678",
        )
        invalid = build_context(raw_text="not-a-phone")
        self.assertNotIn("phone.format_kr", _ids(self.registry.get_applicable(invalid)))

    def test_url_domain_and_markdown_link(self):
        context = build_context(
            raw_text="https://github.com/a/b?x=1",
            metadata={"url_title": "SmartClipboard"},
        )
        self.assertEqual(context.content_type, "url")
        self.assertEqual(context.domain, "github.com")
        self.assertEqual(
            self.executor.execute(self._action("url.copy_domain"), context).value,
            "github.com",
        )
        self.assertEqual(
            self.executor.execute(self._action("url.markdown_link"), context).value,
            "[SmartClipboard](https://github.com/a/b?x=1)",
        )
        untitled = build_context(raw_text="https://example.com/path")
        self.assertEqual(
            self.executor.execute(self._action("url.markdown_link"), untitled).value,
            "[example.com](https://example.com/path)",
        )

    def test_url_open_and_fetch_title_are_not_clipboard_writes(self):
        context = build_context(raw_text="https://example.com")
        opened = self.executor.execute(self._action("url.open"), context)
        self.assertEqual(opened.kind, "url")
        self.assertTrue(opened.metadata.get("open_browser"))
        self.assertFalse(opened.copy_to_clipboard)
        title = self.executor.execute(self._action("url.fetch_title"), context)
        self.assertEqual(title.kind, "info")
        self.assertEqual(title.metadata.get("async"), "fetch_title")

    def test_json_pretty_minify_and_invalid_hidden(self):
        context = build_context(raw_text='{"b":1,"a":2}')
        self.assertEqual(context.content_type, "json")
        self.assertTrue(context.is_valid_json)
        pretty = self.executor.execute(self._action("dev.json_pretty"), context)
        self.assertEqual(pretty.value, '{\n  "b": 1,\n  "a": 2\n}')
        self.assertTrue(pretty.preview)
        compact = self.executor.execute(self._action("dev.json_minify"), context)
        self.assertEqual(compact.value, '{"b":1,"a":2}')
        primitive = build_context(raw_text="1")
        self.assertTrue(primitive.is_valid_json)
        self.assertIn("dev.json_pretty", _ids(self.registry.get_applicable(primitive)))
        invalid = build_context(raw_text="{not json")
        self.assertFalse(invalid.is_valid_json)
        self.assertNotIn("dev.json_pretty", _ids(self.registry.get_applicable(invalid)))

    def test_encode_decode_and_json_escape(self):
        context = build_context(raw_text="안녕 path/x")
        encoded = self.executor.execute(self._action("dev.url_encode"), context)
        self.assertEqual(encoded.value, quote("안녕 path/x", safe=""))
        decoded = self.executor.execute(
            self._action("dev.url_decode"),
            build_context(raw_text=encoded.value),
        )
        self.assertEqual(decoded.value, "안녕 path/x")
        escaped = self.executor.execute(self._action("dev.json_escape_string"), context)
        self.assertEqual(json.loads(escaped.value), "안녕 path/x")

    def test_base64_roundtrip_and_binary_not_applicable(self):
        context = build_context(raw_text="hello")
        encoded = self.executor.execute(self._action("dev.base64_encode"), context)
        self.assertEqual(encoded.value, base64.b64encode(b"hello").decode("ascii"))
        decoded = self.executor.execute(
            self._action("dev.base64_decode"),
            build_context(raw_text=encoded.value),
        )
        self.assertEqual(decoded.value, "hello")
        binary = base64.b64encode(b"\xff\xfe").decode("ascii")
        self.assertFalse(self._action("dev.base64_decode").is_applicable(build_context(raw_text=binary)))

    def test_google_search_limits_query_and_hides_when_sensitive(self):
        context = build_context(raw_text="find me")
        result = self.executor.execute(self._action("search.google"), context)
        self.assertEqual(result.kind, "url")
        self.assertIn("google.com/search?q=", result.value)
        long_text = "x" * 800
        limited = self.executor.execute(self._action("search.google"), build_context(raw_text=long_text))
        self.assertLessEqual(len(limited.metadata.get("query", long_text[:500])), 500)
        sensitive = build_context(raw_text="find me", tags="password")
        self.assertTrue(sensitive.is_sensitive)
        ids = _ids(self.registry.get_applicable(sensitive))
        self.assertNotIn("search.google", ids)
        self.assertNotIn("url.fetch_title", ids)

    def test_image_and_file_have_no_actions(self):
        image = build_context(raw_text="[이미지]", stored_type="IMAGE")
        self.assertEqual(image.content_type, "image")
        self.assertEqual(self.registry.get_applicable(image), [])
        file_ctx = build_context(
            raw_text="C:\\a.txt\nC:\\b.txt",
            stored_type="FILE",
            file_paths=("C:\\a.txt", "C:\\b.txt"),
        )
        self.assertEqual(file_ctx.content_type, "files")
        self.assertEqual(self.registry.get_applicable(file_ctx), [])

    def test_search_filters_titles_and_content_specific_sort(self):
        context = build_context(raw_text="https://example.com")
        matches = self.registry.get_applicable(context, query="도메인")
        self.assertEqual(_ids(matches)[0], "url.copy_domain")
        none = self.registry.get_applicable(context, query="없는작업xyz")
        self.assertEqual(none, [])
        url_ids = _ids(self.registry.get_applicable(context))
        specific = [action_id for action_id in url_ids if action_id.startswith("url.")]
        generic = [action_id for action_id in url_ids if action_id.startswith("text.")]
        if specific and generic:
            self.assertLess(url_ids.index(specific[0]), url_ids.index(generic[0]))

    def test_executor_isolates_action_exceptions(self):
        class Boom:
            id = "boom"
            title = "JSON 정리"
            category = "developer"
            description = "boom"
            priority = 0
            network_required = False

            def is_applicable(self, context):
                return True

            def execute(self, context):
                raise RuntimeError("bad json")

        result = self.executor.execute(Boom(), build_context(raw_text="{}"))
        self.assertEqual(result.kind, "error")
        self.assertIn("JSON 정리에 실패했습니다.", result.value)

    def test_sensitive_network_guard_blocks_execution(self):
        context = build_context(raw_text="https://example.com", tags="api_key")
        result = self.executor.execute(self._action("url.fetch_title"), context)
        self.assertEqual(result.kind, "error")
        self.assertIn("민감", result.value)

    def test_sensitive_body_hides_google_and_open(self):
        secret = build_context(raw_text="AKIAIOSFODNN7EXAMPLE")
        self.assertTrue(secret.is_sensitive)
        ids = _ids(self.registry.get_applicable(secret))
        self.assertNotIn("search.google", ids)
        self.assertNotIn("url.open", ids)
        docs = build_context(raw_text="hello", note="documentation")
        self.assertFalse(docs.is_sensitive)

    def test_long_text_hides_qr(self):
        long_text = "a" * 3000
        context = build_context(raw_text=long_text)
        self.assertFalse(self._action("url.qr").is_applicable(context))
        self.assertTrue(self._action("url.qr").is_applicable(build_context(raw_text="short")))

    def test_empty_and_whitespace_only_have_limited_actions(self):
        empty = build_context(raw_text="")
        self.assertEqual(self.registry.get_applicable(empty), [])
        spaces = build_context(raw_text="   \n")
        ids = _ids(self.registry.get_applicable(spaces))
        self.assertIn("text.trim", ids)
        self.assertNotIn("search.google", ids)
        self.assertNotIn("phone.format_kr", ids)

    def test_large_text_context_stays_local_and_fast(self):
        raw = ("hello world\n" * 20000)
        started = time.perf_counter()
        context = build_context(raw_text=raw)
        actions = self.registry.get_applicable(context)
        elapsed_ms = (time.perf_counter() - started) * 1000
        self.assertGreater(len(actions), 0)
        self.assertLess(elapsed_ms, 250)

    def test_preview_policy_for_long_results(self):
        context = build_context(raw_text="A" * 400)
        result = self.executor.execute(self._action("text.lowercase"), context)
        self.assertTrue(result.preview)

    def test_registry_get_unknown_returns_none(self):
        self.assertIsNone(self.registry.get("missing.action"))
        self.assertGreaterEqual(len(self.registry.all()), 15)


if __name__ == "__main__":
    unittest.main(verbosity=2)
