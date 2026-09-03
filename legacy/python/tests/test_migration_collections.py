import json
import os
import tempfile
import unittest

from smartclipboard_app.legacy_main_src import ExportImportManager
from smartclipboard_core.database import ClipboardDB


TEST_TMP_ROOT = os.path.join(os.getcwd(), ".tmp-unittest")
os.makedirs(TEST_TMP_ROOT, exist_ok=True)


def _workspace_tempdir():
    return tempfile.TemporaryDirectory(dir=TEST_TMP_ROOT)


class MigrationCollectionsTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = _workspace_tempdir()
        self.src_dir = os.path.join(self.tmpdir.name, "src")
        self.dst_dir = os.path.join(self.tmpdir.name, "dst")
        os.makedirs(self.src_dir, exist_ok=True)
        os.makedirs(self.dst_dir, exist_ok=True)

        self.src_db = ClipboardDB(
            db_file=os.path.join(self.src_dir, "clipboard_history_v6.db"),
            app_dir=self.src_dir,
        )
        self.dst_db = ClipboardDB(
            db_file=os.path.join(self.dst_dir, "clipboard_history_v6.db"),
            app_dir=self.dst_dir,
        )
        self.src_manager = ExportImportManager(self.src_db)
        self.dst_manager = ExportImportManager(self.dst_db)
        self.export_path = os.path.join(self.tmpdir.name, "clipboard_export.json")

    def tearDown(self):
        self.src_db.close()
        self.dst_db.close()
        self.tmpdir.cleanup()

    def test_export_json_includes_collections_metadata_in_migration_mode(self):
        collection_id = self.src_db.add_collection("work", "📁", "#123456")
        self.assertTrue(collection_id)

        item_id = self.src_db.add_item("collection-migrate-item", None, "TEXT")
        self.assertTrue(item_id)
        self.src_db.set_item_metadata(item_id, collection_id=collection_id, tags="alpha", note="memo")

        exported_count = self.src_manager.export_json(self.export_path, include_metadata=True)
        self.assertEqual(exported_count, 1)

        with open(self.export_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        self.assertTrue(payload.get("migration_mode"))
        self.assertIn("collections", payload)
        self.assertEqual(len(payload["collections"]), 1)
        self.assertEqual(payload["collections"][0]["legacy_id"], collection_id)
        self.assertEqual(payload["collections"][0]["name"], "work")

    def test_import_json_remaps_collection_ids_when_collections_payload_exists(self):
        collection_id = self.src_db.add_collection("project-x", "📂", "#abcdef")
        self.assertTrue(collection_id)

        item_id = self.src_db.add_item("remap-target", None, "TEXT")
        self.assertTrue(item_id)
        self.src_db.set_item_metadata(item_id, collection_id=collection_id, tags="migrate")
        self.assertEqual(self.src_manager.export_json(self.export_path, include_metadata=True), 1)

        imported = self.dst_manager.import_json(self.export_path)
        self.assertEqual(imported, 1)

        collections = self.dst_db.get_collections()
        self.assertTrue(collections)
        dst_collection_by_id = {row[0]: row[1] for row in collections}
        self.assertIn("project-x", dst_collection_by_id.values())

        with self.dst_db.lock:
            cursor = self.dst_db.conn.cursor()
            cursor.execute("SELECT collection_id FROM history WHERE content = ?", ("remap-target",))
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            restored_collection_id = row[0]
            self.assertIn(restored_collection_id, dst_collection_by_id)

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM history h
                LEFT JOIN collections c ON h.collection_id = c.id
                WHERE h.collection_id IS NOT NULL AND c.id IS NULL
                """
            )
            orphan_count = cursor.fetchone()[0]
        self.assertEqual(orphan_count, 0)

    def test_import_json_without_collections_payload_clears_orphan_collection_reference(self):
        old_payload = {
            "app": "SmartClipboard Pro",
            "version": "10.6",
            "migration_mode": True,
            "items": [
                {
                    "content": "legacy-item",
                    "type": "TEXT",
                    "timestamp": "2026-03-03 10:00:00",
                    "collection_id": 999,
                }
            ],
        }
        with open(self.export_path, "w", encoding="utf-8") as f:
            json.dump(old_payload, f, ensure_ascii=False, indent=2)

        imported = self.dst_manager.import_json(self.export_path)
        self.assertEqual(imported, 1)

        with self.dst_db.lock:
            cursor = self.dst_db.conn.cursor()
            cursor.execute("SELECT collection_id FROM history WHERE content = ?", ("legacy-item",))
            row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertIsNone(row[0])
        uncategorized = {item[1] for item in self.dst_db.get_items_uncategorized()}
        self.assertIn("legacy-item", uncategorized)


if __name__ == "__main__":
    unittest.main(verbosity=2)
