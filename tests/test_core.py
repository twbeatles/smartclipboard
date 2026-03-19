import datetime
import json
import os
import tempfile
import unittest

from PyQt6.QtWidgets import QApplication

from smartclipboard_app.managers.export_import import ExportImportManager
from smartclipboard_core.actions import ClipboardActionManager, extract_first_url
from smartclipboard_core.database import ClipboardDB


class FakeActionDB:
    def __init__(self, actions):
        self._actions = actions
        self.updated_titles = []

    def get_clipboard_actions(self):
        return self._actions

    def update_url_title(self, item_id, title):
        self.updated_titles.append((item_id, title))
        return True


class CoreActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_extract_first_url(self):
        text = "prefix https://example.com/path?q=1 suffix"
        self.assertEqual(extract_first_url(text), "https://example.com/path?q=1")

    def test_fetch_title_uses_extracted_url(self):
        db = FakeActionDB([(1, "fetch", r"https?://", "fetch_title", "{}", 1, 0)])
        manager = ClipboardActionManager(db)
        captured = {}

        def fake_fetch(url, item_id, action_name):
            captured["url"] = url
            captured["item_id"] = item_id
            captured["action_name"] = action_name

        manager.fetch_url_title_async = fake_fetch
        results = manager.process("링크: https://example.com/a?b=1 내용", item_id=7)

        self.assertEqual(results, [])
        self.assertEqual(captured["url"], "https://example.com/a?b=1")
        self.assertEqual(captured["item_id"], 7)

    def test_fetch_title_without_url_returns_notify(self):
        db = FakeActionDB([(1, "fetch", r".*", "fetch_title", "{}", 1, 0)])
        manager = ClipboardActionManager(db)
        results = manager.process("url 없음", item_id=11)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][1]["type"], "notify")
        self.assertIn("URL", results[0][1]["message"])


class CoreDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "clipboard_history_v6.db")
        self.db = ClipboardDB(db_file=self.db_path, app_dir=self.tmpdir.name)

    def tearDown(self):
        self.db.close()
        self.tmpdir.cleanup()

    def test_add_snippet_success(self):
        self.assertTrue(self.db.add_snippet("greeting", "hello world"))
        snippets = self.db.get_snippets()
        self.assertEqual(len(snippets), 1)
        self.assertEqual(snippets[0][1], "greeting")
        self.assertEqual(snippets[0][2], "hello world")

    def test_cleanup_respects_max_history_and_keeps_pinned(self):
        self.db.set_setting("max_history", 10)

        pinned_ids = []
        for i in range(2):
            item_id = self.db.add_item(f"pinned-{i}", None, "TEXT")
            pinned_ids.append(item_id)
            self.db.toggle_pin(item_id)

        for i in range(30):
            self.db.add_item(f"normal-{i}", None, "TEXT")

        self.db.cleanup()

        with self.db.lock:
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM history WHERE pinned = 0")
            unpinned_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM history WHERE pinned = 1")
            pinned_count = cursor.fetchone()[0]

        self.assertLessEqual(unpinned_count, 10)
        self.assertEqual(pinned_count, 2)

    def test_backup_db_creates_target_file(self):
        target_file = os.path.join(self.tmpdir.name, "manual_backup.db")
        ok = self.db.backup_db(target_path=target_file, force=True)

        self.assertTrue(ok)
        self.assertTrue(os.path.exists(target_file))

    def test_update_pin_orders_success(self):
        ids = []
        for i in range(3):
            item_id = self.db.add_item(f"pin-order-{i}", None, "TEXT")
            self.db.toggle_pin(item_id)
            ids.append(item_id)

        expected_order = [ids[2], ids[0], ids[1]]
        self.assertTrue(self.db.update_pin_orders(expected_order))

        pinned_items = self.db.get_items("", "📌 고정")
        self.assertEqual([row[0] for row in pinned_items], expected_order)

    def test_update_pin_orders_rollback_on_invalid_item(self):
        pinned_ids = []
        for i in range(2):
            item_id = self.db.add_item(f"rollback-pin-{i}", None, "TEXT")
            self.db.toggle_pin(item_id)
            pinned_ids.append(item_id)

        invalid_unpinned_id = self.db.add_item("rollback-normal", None, "TEXT")

        with self.db.lock:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT id, pin_order FROM history WHERE id IN (?, ?) ORDER BY id",
                (pinned_ids[0], pinned_ids[1]),
            )
            before = dict(cursor.fetchall())

        ok = self.db.update_pin_orders([pinned_ids[1], invalid_unpinned_id, pinned_ids[0]])
        self.assertFalse(ok)

        with self.db.lock:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT id, pin_order FROM history WHERE id IN (?, ?) ORDER BY id",
                (pinned_ids[0], pinned_ids[1]),
            )
            after = dict(cursor.fetchall())
        self.assertEqual(before, after)

    def test_get_items_by_tag_exact_match(self):
        only_a_id = self.db.add_item("tag-only-a", None, "TEXT")
        only_data_id = self.db.add_item("tag-only-data", None, "TEXT")
        both_id = self.db.add_item("tag-both", None, "TEXT")

        self.db.set_item_tags(only_a_id, "a")
        self.db.set_item_tags(only_data_id, "data")
        self.db.set_item_tags(both_id, "a, data")

        a_ids = {row[0] for row in self.db.get_items_by_tag("a")}
        data_ids = {row[0] for row in self.db.get_items_by_tag("data")}
        at_ids = {row[0] for row in self.db.get_items_by_tag("at")}

        self.assertEqual(a_ids, {only_a_id, both_id})
        self.assertEqual(data_ids, {only_data_id, both_id})
        self.assertEqual(at_ids, set())

    def test_get_items_keeps_pinned_first_with_custom_pin_order(self):
        normal_first = self.db.add_item("normal-first", None, "TEXT")
        pinned_a = self.db.add_item("pinned-a", None, "TEXT")
        pinned_b = self.db.add_item("pinned-b", None, "TEXT")
        pinned_c = self.db.add_item("pinned-c", None, "TEXT")
        normal_last = self.db.add_item("normal-last", None, "TEXT")

        self.db.toggle_pin(pinned_a)
        self.db.toggle_pin(pinned_b)
        self.db.toggle_pin(pinned_c)

        expected_pinned_order = [pinned_c, pinned_a, pinned_b]
        self.assertTrue(self.db.update_pin_orders(expected_pinned_order))

        items = self.db.get_items("", "전체")
        self.assertEqual([row[0] for row in items[:3]], expected_pinned_order)
        self.assertTrue(all(row[4] == 1 for row in items[:3]))
        self.assertTrue(all(row[4] == 0 for row in items[3:]))
        self.assertIn(normal_first, [row[0] for row in items[3:]])
        self.assertIn(normal_last, [row[0] for row in items[3:]])

    def test_soft_delete_restore_preserves_metadata(self):
        item_id = self.db.add_item("meta-item", None, "TEXT")
        self.db.set_item_tags(item_id, "alpha, beta")
        self.db.set_note(item_id, "important note")
        self.db.toggle_bookmark(item_id)
        collection_id = self.db.add_collection("work")
        self.assertTrue(collection_id)
        self.assertTrue(self.db.assign_to_collection(item_id, collection_id))
        self.db.toggle_pin(item_id)
        self.db.increment_use_count(item_id)
        self.db.increment_use_count(item_id)

        self.assertTrue(self.db.soft_delete(item_id))
        deleted_rows = self.db.get_deleted_items()
        self.assertEqual(len(deleted_rows), 1)
        deleted_id = deleted_rows[0][0]

        self.assertTrue(self.db.restore_item(deleted_id))

        with self.db.lock:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT tags, note, bookmark, collection_id, pinned, pin_order, use_count "
                "FROM history WHERE content = ?",
                ("meta-item",),
            )
            restored = cursor.fetchone()

        self.assertIsNotNone(restored)
        self.assertEqual(restored[0], "alpha, beta")
        self.assertEqual(restored[1], "important note")
        self.assertEqual(restored[2], 1)
        self.assertEqual(restored[3], collection_id)
        self.assertEqual(restored[4], 1)
        self.assertGreaterEqual(restored[5], 0)
        self.assertEqual(restored[6], 2)

    def test_cleanup_vacuum_uses_separate_counter(self):
        calls = {"vacuum": 0}

        def tracer(sql):
            if "VACUUM" in sql.upper():
                calls["vacuum"] += 1

        self.db.conn.set_trace_callback(tracer)
        try:
            for _ in range(50):
                self.db.cleanup(max_history=50)
        finally:
            self.db.conn.set_trace_callback(None)

        self.assertGreaterEqual(calls["vacuum"], 1)
        self.assertEqual(self.db.cleanup_count, 0)

    def test_duplicate_rule_helpers(self):
        self.assertFalse(self.db.is_duplicate_copy_rule(r"\s+", "trim", ""))
        self.assertTrue(self.db.add_copy_rule("trim-rule", r"\s+", "trim"))
        self.assertTrue(self.db.is_duplicate_copy_rule(r"\s+", "trim", ""))

        self.assertFalse(self.db.is_duplicate_clipboard_action(r"https?://", "fetch_title", "{}"))
        self.assertTrue(self.db.add_clipboard_action("fetch", r"https?://", "fetch_title", "{}"))
        self.assertTrue(self.db.is_duplicate_clipboard_action(r"https?://", "fetch_title", "{}"))

    def test_move_items_to_collection_bulk(self):
        item_a = self.db.add_item("bulk-a", None, "TEXT")
        item_b = self.db.add_item("bulk-b", None, "TEXT")
        item_c = self.db.add_item("bulk-c", None, "TEXT")
        collection_id = self.db.add_collection("bulk")
        self.assertTrue(collection_id)

        moved = self.db.move_items_to_collection([item_a, item_b, item_b, item_c], collection_id)
        self.assertEqual(moved, 3)

        with self.db.lock:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM history WHERE id IN (?, ?, ?) AND collection_id = ?",
                (item_a, item_b, item_c, collection_id),
            )
            assigned = cursor.fetchone()[0]
        self.assertEqual(assigned, 3)

    def test_duplicate_text_updates_existing_row_and_preserves_metadata(self):
        item_id = self.db.add_item("duplicate-text", None, "TEXT")
        other_id = self.db.add_item("other-text", None, "TEXT")
        collection_id = self.db.add_collection("duplicates")
        self.assertTrue(collection_id)

        self.db.set_item_tags(item_id, "alpha")
        self.db.set_note(item_id, "keep this note")
        self.db.toggle_bookmark(item_id)
        self.assertTrue(self.db.assign_to_collection(item_id, collection_id))
        self.db.increment_use_count(item_id)
        self.db.increment_use_count(item_id)
        self.assertTrue(self.db.set_item_metadata(item_id, timestamp="2000-01-01 00:00:00"))
        self.assertTrue(self.db.set_item_metadata(other_id, timestamp="2000-01-02 00:00:00"))

        updated_id = self.db.add_item("duplicate-text", None, "LINK")

        self.assertEqual(updated_id, item_id)
        with self.db.lock:
            cursor = self.db.conn.cursor()
            cursor.execute(
                "SELECT type, tags, note, bookmark, collection_id, use_count FROM history WHERE id = ?",
                (item_id,),
            )
            row = cursor.fetchone()
        self.assertEqual(row, ("LINK", "alpha", "keep this note", 1, collection_id, 2))

        items = self.db.get_items("", "전체")
        self.assertEqual(items[0][0], item_id)
        self.assertEqual(items[1][0], other_id)

    def test_export_import_json_round_trip_preserves_image_item(self):
        image_bytes = b"fake-image-payload"
        item_id = self.db.add_item("[이미지 캡처]", image_bytes, "IMAGE")
        self.assertTrue(item_id)

        export_manager = ExportImportManager(self.db)
        export_path = os.path.join(self.tmpdir.name, "clipboard_export.json")
        exported = export_manager.export_json(export_path, include_metadata=True)

        self.assertEqual(exported, 1)
        with open(export_path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        self.assertEqual(payload["items"][0]["type"], "IMAGE")
        self.assertIn("image_data_b64", payload["items"][0])

        dst_tmp = tempfile.TemporaryDirectory()
        dst_db = None
        try:
            dst_db = ClipboardDB(
                db_file=os.path.join(dst_tmp.name, "clipboard_history_v6.db"),
                app_dir=dst_tmp.name,
            )
            imported = ExportImportManager(dst_db).import_json(export_path)
            self.assertEqual(imported, 1)

            items = dst_db.get_items("", "전체")
            self.assertEqual(len(items), 1)
            restored = dst_db.get_content(items[0][0])
            if restored is None:
                self.fail("Imported image item could not be loaded from the destination DB")
            content, blob, ptype = restored
            self.assertEqual(content, "[이미지 캡처]")
            self.assertEqual(blob, image_bytes)
            self.assertEqual(ptype, "IMAGE")
        finally:
            if dst_db is not None:
                dst_db.close()
            dst_tmp.cleanup()


class CoreDatabaseSearchTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "clipboard_history_v6.db")
        self.db = ClipboardDB(db_file=self.db_path, app_dir=self.tmpdir.name)

    def tearDown(self):
        self.db.close()
        self.tmpdir.cleanup()

    def test_search_items_hits_tags_note_url_title(self):
        base_id = self.db.add_item("base-content", None, "TEXT")
        tags_only_id = self.db.add_item("tags-content", None, "TEXT")
        note_only_id = self.db.add_item("note-content", None, "TEXT")
        url_only_id = self.db.add_item("url-content", None, "LINK")

        self.db.set_item_tags(tags_only_id, "alpha, beta")
        self.db.set_note(note_only_id, "my-special-note")
        self.db.update_url_title(url_only_id, "example title keyword")

        by_tag = {row[0] for row in self.db.search_items("alpha")}
        by_note = {row[0] for row in self.db.search_items("special-note")}
        by_title = {row[0] for row in self.db.search_items("keyword")}

        self.assertIn(tags_only_id, by_tag)
        self.assertIn(note_only_id, by_note)
        self.assertIn(url_only_id, by_title)

        # Ensure punctuation-heavy queries do not crash (sanitized for FTS safety).
        weird = {row[0] for row in self.db.search_items('("alpha") -- !!')}
        self.assertIn(tags_only_id, weird)

    def test_search_items_keeps_pinned_first(self):
        pinned_a = self.db.add_item("pinned-a", None, "TEXT")
        pinned_b = self.db.add_item("pinned-b", None, "TEXT")
        normal = self.db.add_item("normal", None, "TEXT")

        self.db.toggle_pin(pinned_a)
        self.db.toggle_pin(pinned_b)
        self.db.update_pin_orders([pinned_b, pinned_a])

        items = self.db.search_items("pinned")
        self.assertEqual([row[0] for row in items[:2]], [pinned_b, pinned_a])
        self.assertNotIn(normal, [row[0] for row in items])

    def test_search_items_uncategorized_filter(self):
        uncategorized_id = self.db.add_item("uncategorized-only", None, "TEXT")
        categorized_id = self.db.add_item("categorized-only", None, "TEXT")
        collection_id = self.db.add_collection("project")
        self.assertTrue(collection_id)
        self.assertTrue(self.db.assign_to_collection(categorized_id, collection_id))

        uncategorized_items = {row[0] for row in self.db.search_items("", uncategorized=True)}
        self.assertIn(uncategorized_id, uncategorized_items)
        self.assertNotIn(categorized_id, uncategorized_items)

        uncategorized_search = {row[0] for row in self.db.search_items("only", uncategorized=True)}
        self.assertIn(uncategorized_id, uncategorized_search)
        self.assertNotIn(categorized_id, uncategorized_search)

    def test_search_items_empty_query_supports_tag_and_collection_filters_together(self):
        target_id = self.db.add_item("target-item", None, "TEXT")
        tag_only_id = self.db.add_item("tag-only", None, "TEXT")
        collection_only_id = self.db.add_item("collection-only", None, "TEXT")

        collection_id = self.db.add_collection("work")
        self.assertTrue(collection_id)

        self.db.set_item_tags(target_id, "alpha")
        self.db.assign_to_collection(target_id, collection_id)

        self.db.set_item_tags(tag_only_id, "alpha")
        self.db.assign_to_collection(collection_only_id, collection_id)

        rows = self.db.search_items("", tag_filter="alpha", collection_id=collection_id)
        ids = {row[0] for row in rows}

        self.assertIn(target_id, ids)
        self.assertNotIn(tag_only_id, ids)
        self.assertNotIn(collection_only_id, ids)

    def test_search_items_empty_query_supports_tag_and_uncategorized_filters_together(self):
        target_id = self.db.add_item("target-uncategorized", None, "TEXT")
        categorized_id = self.db.add_item("categorized", None, "TEXT")
        no_tag_id = self.db.add_item("no-tag", None, "TEXT")

        collection_id = self.db.add_collection("project")
        self.assertTrue(collection_id)

        self.db.set_item_tags(target_id, "alpha")
        self.db.set_item_tags(categorized_id, "alpha")
        self.db.assign_to_collection(categorized_id, collection_id)

        rows = self.db.search_items("", tag_filter="alpha", uncategorized=True)
        ids = {row[0] for row in rows}

        self.assertIn(target_id, ids)
        self.assertNotIn(categorized_id, ids)
        self.assertNotIn(no_tag_id, ids)

    def test_search_items_empty_query_supports_bookmark_and_tag_filters_together(self):
        target_id = self.db.add_item("bookmark-target", None, "TEXT")
        unbookmarked_id = self.db.add_item("unbookmarked", None, "TEXT")
        wrong_tag_id = self.db.add_item("wrong-tag", None, "TEXT")

        self.db.set_item_tags(target_id, "alpha")
        self.db.toggle_bookmark(target_id)

        self.db.set_item_tags(unbookmarked_id, "alpha")
        self.db.set_item_tags(wrong_tag_id, "beta")
        self.db.toggle_bookmark(wrong_tag_id)

        rows = self.db.search_items("", tag_filter="alpha", bookmarked=True)
        ids = {row[0] for row in rows}

        self.assertIn(target_id, ids)
        self.assertNotIn(unbookmarked_id, ids)
        self.assertNotIn(wrong_tag_id, ids)

    def test_search_items_empty_query_uses_updated_timestamp_order(self):
        target_id = self.db.add_item("search-duplicate", None, "TEXT")
        other_id = self.db.add_item("search-other", None, "TEXT")

        self.assertTrue(self.db.set_item_metadata(target_id, timestamp="2000-01-01 00:00:00"))
        self.assertTrue(self.db.set_item_metadata(other_id, timestamp="2000-01-02 00:00:00"))
        self.assertEqual(self.db.search_items("")[0][0], other_id)

        updated_id = self.db.add_item("search-duplicate", None, "TEXT")

        self.assertEqual(updated_id, target_id)
        self.assertEqual(self.db.search_items("")[0][0], target_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
