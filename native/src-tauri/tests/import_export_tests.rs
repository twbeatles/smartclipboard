use std::fs;
use std::path::PathBuf;
use tempfile::NamedTempFile;

use smartclipboard_native_lib::database::Database;
use smartclipboard_native_lib::import_export::{export_to_csv, export_to_json, import_from_json};
use smartclipboard_native_lib::paths::resolve_app_data_dir;

fn get_source_db() -> Database {
    let fixture_path = PathBuf::from("../../tests/native_parity/fixtures/synthetic_test_v6.db");
    assert!(fixture_path.exists());
    Database::open_read_only(&fixture_path).expect("open read only")
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
    let fixture_path = PathBuf::from("../../tests/native_parity/fixtures/synthetic_test_v6.db");
    let target_temp = NamedTempFile::new().expect("create temp");
    fs::copy(&fixture_path, target_temp.path()).expect("copy schema");

    let target_db = Database::open_read_write(target_temp.path()).expect("open target");
    // Clear existing history to test pure import
    target_db.with_conn(|c| {
        c.execute("DELETE FROM history", [])?;
        c.execute("DELETE FROM snippets", [])?;
        c.execute("DELETE FROM collections", [])?;
        Ok(())
    }).expect("clear target");

    // 3. Import JSON
    let (imported_hist, imported_snip) = import_from_json(&json_str, &target_db).expect("import from json");
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
