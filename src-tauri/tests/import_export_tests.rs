use std::fs;
use std::path::PathBuf;
use tempfile::NamedTempFile;

use smartclipboard_native_lib::database::Database;
use smartclipboard_native_lib::import_export::{export_to_csv, export_to_json, import_from_json};
use smartclipboard_native_lib::paths::resolve_app_data_dir;

fn get_source_db() -> Database {
    let fixture_path = PathBuf::from("fixtures/synthetic_test_v6.db");
    assert!(fixture_path.exists());
    Database::open_read_only(&fixture_path).expect("open read only")
}

fn create_temp_db_copy() -> (NamedTempFile, Database) {
    let fixture_path = PathBuf::from("fixtures/synthetic_test_v6.db");
    assert!(fixture_path.exists());
    let temp = NamedTempFile::new().expect("create temp file");
    fs::copy(&fixture_path, temp.path()).expect("copy fixture db");
    let db = Database::open_read_write(temp.path()).expect("open read write");
    (temp, db)
}

#[test]
fn test_json_export_and_import_roundtrip() {
    let src_db = get_source_db();

    // 1. Export from source DB
    let json_str = export_to_json(&src_db).expect("export to json");
    assert!(json_str.contains("\"version\": 1"));
    assert!(json_str.contains("\"app_version\": \"10.7.0\""));
    assert!(json_str.contains("\"history\":"));
    assert!(json_str.contains("\"collections\":"));
    assert!(json_str.contains("\"snippets\":"));

    // 2. Create fresh target DB
    let fixture_path = PathBuf::from("fixtures/synthetic_test_v6.db");
    let target_temp = NamedTempFile::new().expect("create temp");
    fs::copy(&fixture_path, target_temp.path()).expect("copy schema");

    let target_db = Database::open_read_write(target_temp.path()).expect("open target");
    // Clear existing history to test pure import
    target_db
        .with_conn(|c| {
            c.execute("DELETE FROM history", [])?;
            c.execute("DELETE FROM snippets", [])?;
            c.execute("DELETE FROM collections", [])?;
            Ok(())
        })
        .expect("clear target");

    // 3. Import JSON
    let (imported_hist, imported_snip) =
        import_from_json(&json_str, &target_db).expect("import from json");
    assert!(imported_hist > 0, "Should import history rows");
    assert!(imported_snip > 0, "Should import snippets");

    // 4. Verify roundtrip equality
    let imported_items = target_db.list_history(100).expect("list imported");
    assert_eq!(imported_items.len(), imported_hist);

    let imported_snippets = target_db.get_snippets().expect("list snippets");
    assert_eq!(imported_snippets.len(), imported_snip);
}

#[test]
fn test_csv_export() {
    let src_db = get_source_db();
    let csv_str = export_to_csv(&src_db).expect("export to csv");

    assert!(csv_str.starts_with("id,type,timestamp,content,tags,note,bookmark"));
    assert!(csv_str.contains("TEXT"));
}

#[test]
fn test_paths_resolution() {
    let app_dir = resolve_app_data_dir();
    assert!(!app_dir.to_string_lossy().is_empty());
}

#[test]
fn test_python_migration_format_import() {
    use smartclipboard_native_lib::import_export::import_from_json;

    let (_temp, db) = create_temp_db_copy();
    let before = db.list_history(1000).expect("list").len();

    let png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==";
    let payload = serde_json::json!({
        "app": "SmartClipboard Pro",
        "version": "10.6",
        "migration_mode": true,
        "items": [
            {"content": "audit probe text alpha", "type": "TEXT",
             "timestamp": "2026-09-20 10:00:00", "pinned": false,
             "use_count": 0, "pin_order": 0, "tags": "audit",
             "note": "", "bookmark": 0, "collection_id": 9001, "url_title": ""},
            {"content": "C:\\audit\\a.txt\nC:\\audit\\b.txt", "type": "FILE",
             "timestamp": "2026-09-20 10:01:00", "pinned": false,
             "use_count": 0, "pin_order": 0,
             "file_paths": ["C:\\audit\\a.txt", "C:\\audit\\b.txt"],
             "file_path": "C:\\audit\\a.txt"},
            {"content": "[이미지 캡처]", "type": "IMAGE",
             "timestamp": "2026-09-20 10:02:00", "pinned": false,
             "use_count": 0, "pin_order": 0, "image_data_b64": png_b64}
        ],
        "collections": [
            {"legacy_id": 9001, "name": "AuditCol", "icon": "📁", "color": "#6366f1"}
        ]
    })
    .to_string();

    let (hist, _snip) = import_from_json(&payload, &db).expect("python-format import");
    assert_eq!(hist, 3);

    // Collection remapped by name: item references the created collection.
    let cols = db.get_collections().expect("collections");
    let audit = cols
        .iter()
        .find(|c| c.name == "AuditCol")
        .expect("AuditCol created");
    let items = db.list_history(1000).expect("list");
    let text = items
        .iter()
        .find(|i| i.content == "audit probe text alpha")
        .expect("text row");
    assert_eq!(text.collection_id, Some(audit.id));
    assert_eq!(text.tags, "audit");

    // FILE signature rebuilt and stored.
    let file_row = items
        .iter()
        .find(|i| i.r#type == "FILE" && i.content.contains("a.txt"))
        .expect("file row");
    let detail = db.get_history_detail(file_row.id).expect("detail");
    assert!(!detail.file_signature.is_empty());
    assert_eq!(detail.file_path, "C:\\audit\\a.txt");

    // Re-import merges TEXT/FILE rows; IMAGE rows are always inserted,
    // matching the Python capture path (no image dedupe).
    let (hist2, _) = import_from_json(&payload, &db).expect("reimport");
    assert_eq!(hist2, 3);
    assert_eq!(db.list_history(1000).expect("list").len(), before + 4);
}

#[test]
fn test_csv_import_layouts_and_markdown_export() {
    use smartclipboard_native_lib::import_export::{export_to_markdown, import_from_csv};

    let (_temp, db) = create_temp_db_copy();
    let before = db.list_history(10000).expect("list").len();

    let csv_py = "내용,유형,시간,고정,사용횟수\ncsv probe one,TEXT,2026-09-20 11:00:00,아니오,0\n[이미지 항목],IMAGE,2026-09-20 11:00:00,아니오,0\nC:\\csv\\f.txt,FILE,2026-09-20 11:00:00,예,2\n";
    let (imported, _) = import_from_csv(csv_py, &db).expect("python-layout csv");
    assert_eq!(imported, 2, "TEXT + FILE imported, IMAGE skipped");

    let items = db.list_history(10000).expect("list");
    assert_eq!(items.len(), before + 2);
    let pinned_file = items
        .iter()
        .find(|i| i.content.contains("f.txt"))
        .expect("csv file row");
    assert!(pinned_file.pinned);
    assert_eq!(pinned_file.use_count, 2);

    let md = export_to_markdown(&db).expect("markdown");
    assert!(md.contains("# SmartClipboard Pro"));
    assert!(md.contains("csv probe one"));
}

#[test]
fn test_invalid_json_leaves_db_unchanged() {
    use smartclipboard_native_lib::import_export::import_from_json;

    let (_temp, db) = create_temp_db_copy();
    let before = db.list_history(10000).expect("list").len();
    assert!(import_from_json("{not valid json", &db).is_err());
    assert!(import_from_json("{\"history\": \"nope\"}", &db).is_err());
    assert_eq!(db.list_history(10000).expect("list").len(), before);
}
