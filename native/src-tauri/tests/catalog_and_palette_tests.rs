use std::fs;
use std::path::PathBuf;
use tempfile::NamedTempFile;

use smartclipboard_native_lib::action_palette::{execute_action, BUILTIN_ACTIONS};
use smartclipboard_native_lib::database::Database;

fn create_temp_db_copy() -> (NamedTempFile, Database) {
    let fixture_path = PathBuf::from("../../tests/native_parity/fixtures/synthetic_test_v6.db");
    assert!(fixture_path.exists());

    let temp = NamedTempFile::new().expect("create temp file");
    fs::copy(&fixture_path, temp.path()).expect("copy fixture db");

    let db = Database::open_read_write(temp.path()).expect("open read write");
    (temp, db)
}

#[test]
fn test_collection_crud_and_cascade_null() {
    let (_temp, db) = create_temp_db_copy();

    // 1. Add Collection
    let col_id = db.add_collection("테스트 프로젝트", "🧪", "#ec4899").expect("add collection");
    let (item_id, _) = db.add_item("컬렉션 연동 아이템", None, "TEXT").expect("add item");

    // Assign collection_id
    db.with_conn(|conn| {
        conn.execute("UPDATE history SET collection_id = ? WHERE id = ?", rusqlite::params![col_id, item_id])?;
        Ok(())
    }).expect("assign collection");

    let detail = db.get_history_detail(item_id).expect("detail");
    assert_eq!(detail.collection_id, Some(col_id));

    // 2. Update Collection
    db.update_collection(col_id, "수정된 프로젝트", "🔬", "#3b82f6").expect("update collection");
    let cols = db.get_collections().expect("get collections");
    let updated_col = cols.iter().find(|c| c.id == col_id).expect("find col");
    assert_eq!(updated_col.name, "수정된 프로젝트");

    // 3. Delete Collection -> History item should cascade collection_id to NULL
    db.delete_collection(col_id).expect("delete collection");
    let detail_after = db.get_history_detail(item_id).expect("detail after");
    assert_eq!(detail_after.collection_id, None, "collection_id must be set to NULL on collection delete");
}

#[test]
fn test_snippet_crud() {
    let (_temp, db) = create_temp_db_copy();

    let snip_id = db.add_snippet("환영 메시지", "환영합니다!", Some("Alt+H"), "인사").expect("add snippet");
    let snippets = db.get_snippets().expect("get snippets");
    assert!(snippets.iter().any(|s| s.id == snip_id && s.name == "환영 메시지"));

    db.update_snippet(snip_id, "환영 메시지 v2", "스마트클립보드에 오신 것을 환영합니다!", None, "인사").expect("update");
    let snippets_updated = db.get_snippets().expect("get snippets");
    let snip = snippets_updated.iter().find(|s| s.id == snip_id).expect("found");
    assert_eq!(snip.content, "스마트클립보드에 오신 것을 환영합니다!");

    db.delete_snippet(snip_id).expect("delete snippet");
    let snippets_final = db.get_snippets().expect("get snippets");
    assert!(!snippets_final.iter().any(|s| s.id == snip_id));
}

#[test]
fn test_action_palette_execution() {
    assert!(!BUILTIN_ACTIONS.is_empty());

    // 1. Uppercase & Lowercase & Trim
    assert_eq!(execute_action("uppercase", "hello world").unwrap(), "HELLO WORLD");
    assert_eq!(execute_action("lowercase", "HELLO WORLD").unwrap(), "hello world");
    assert_eq!(execute_action("trim", "  \n text \t ").unwrap(), "text");

    // 2. Base64 Roundtrip
    let plain = "SmartClipboard Rust Native 2026";
    let encoded = execute_action("base64_encode", plain).unwrap();
    let decoded = execute_action("base64_decode", &encoded).unwrap();
    assert_eq!(decoded, plain);

    // 3. SHA-256
    let hash = execute_action("sha256_hash", "hello").unwrap();
    assert_eq!(hash, "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824");

    // 4. JSON Format
    let raw_json = r#"{"name":"smartclipboard","version":10}"#;
    let formatted = execute_action("json_format", raw_json).unwrap();
    assert!(formatted.contains('\n'));

    // 5. Statistics
    let stats = execute_action("text_statistics", "Hello world\nSecond line").unwrap();
    assert!(stats.contains("글자 수: 23자"));
    assert!(stats.contains("단어 수: 4개"));
    assert!(stats.contains("줄 수: 2줄"));
}
