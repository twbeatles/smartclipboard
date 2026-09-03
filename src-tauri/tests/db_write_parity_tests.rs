use std::fs;
use std::path::PathBuf;
use tempfile::NamedTempFile;

use smartclipboard_native_lib::database::{Database, SearchFilter};

fn create_temp_db_copy() -> (NamedTempFile, Database) {
    let fixture_path = PathBuf::from("fixtures/synthetic_test_v6.db");
    assert!(fixture_path.exists());

    let temp = NamedTempFile::new().expect("create temp file");
    fs::copy(&fixture_path, temp.path()).expect("copy fixture db");

    let db = Database::open_read_write(temp.path()).expect("open read write");
    (temp, db)
}

#[test]
fn test_text_add_and_deduplication() {
    let (_temp, db) = create_temp_db_copy();

    let text = "동일한 텍스트 중복 추가 테스트 2026";
    let (id1, updated1) = db.add_item(text, None, "TEXT").expect("add 1");
    assert!(!updated1, "First insert should be new");

    let (id2, updated2) = db.add_item(text, None, "TEXT").expect("add 2");
    assert!(updated2, "Second insert should be update existing");
    assert_eq!(id1, id2, "Item id must be preserved on merge");
}

#[test]
fn test_file_add_and_signature_deduplication() {
    let (_temp, db) = create_temp_db_copy();

    let files = "C:\\Windows\\System32\\cmd.exe\nC:\\Windows\\System32\\calc.exe";
    let (id1, updated1) = db.add_item(files, None, "FILE").expect("add file 1");
    assert!(!updated1);

    // Same files with different whitespace/slashes
    let files_permuted = "c:/windows/system32/calc.exe\nc:/windows/system32/cmd.exe";
    let (id2, updated2) = db.add_item(files_permuted, None, "FILE").expect("add file 2");
    assert!(updated2, "Identical normalized files should merge by signature");
    assert_eq!(id1, id2);
}

#[test]
fn test_image_add_always_creates_new_row() {
    let (_temp, db) = create_temp_db_copy();

    let dummy_img = vec![1, 2, 3, 4, 5];
    let (id1, updated1) = db.add_item("이미지 A", Some(&dummy_img), "IMAGE").expect("img 1");
    assert!(!updated1);

    let (id2, updated2) = db.add_item("이미지 B", Some(&dummy_img), "IMAGE").expect("img 2");
    assert!(!updated2, "Image items must never overwrite existing rows");
    assert_ne!(id1, id2);
}

#[test]
fn test_replace_text_or_merge() {
    let (_temp, db) = create_temp_db_copy();

    // 1. Add "과일_사과"
    let (id_apple, _) = db.add_item("과일_사과", None, "TEXT").expect("add apple");
    db.toggle_bookmark(id_apple).expect("bookmark apple");
    db.set_note(id_apple, "맛있는 사과").expect("note apple");

    // 2. Add "과일_바나나"
    let (id_banana, _) = db.add_item("과일_바나나", None, "TEXT").expect("add banana");
    db.increment_use_count(id_banana).expect("use count banana");

    // 3. Rename "과일_바나나" into "과일_사과" -> Must merge into id_apple and delete id_banana!
    let merged_id = db.replace_text_item_or_merge(id_banana, "과일_사과", "TEXT").expect("merge");
    assert_eq!(merged_id, id_apple, "Target id must be the existing apple id");

    // Verify id_banana is deleted
    let detail_banana = db.get_history_detail(id_banana);
    assert!(detail_banana.is_err(), "Banana row must be deleted");

    // Verify merged metadata on id_apple
    let detail_apple = db.get_history_detail(id_apple).expect("apple detail");
    assert!(detail_apple.bookmark, "Bookmark preserved");
    assert_eq!(detail_apple.note, "맛있는 사과", "Note preserved");
    assert!(detail_apple.use_count >= 1, "Use count merged");
}

#[test]
fn test_fts_trigger_automatic_update_on_write() {
    let (_temp, db) = create_temp_db_copy();

    let unique_keyword = "유니크트리거검색키워드987654";
    let (item_id, _) = db.add_item(unique_keyword, None, "TEXT").expect("add item");

    // SQLite triggers (history_ai) should automatically index into history_fts!
    let filter = SearchFilter {
        query: unique_keyword.into(),
        ..Default::default()
    };
    let results = db.search_items(&filter).expect("search fts");
    assert!(!results.is_empty(), "FTS trigger must automatically index newly added item");
    assert_eq!(results[0].id, item_id);
    assert!(results[0].content.contains(unique_keyword));
}

#[test]
fn test_soft_delete_and_restore() {
    let (_temp, db) = create_temp_db_copy();

    let (item_id, _) = db.add_item("휴지통삭제복원테스트", None, "TEXT").expect("add");

    // Soft delete
    db.soft_delete(item_id).expect("soft delete");
    assert!(db.get_history_detail(item_id).is_err(), "Item should be removed from history");

    let trash = db.get_trash().expect("get trash");
    let trash_item = trash.iter().find(|t| t.content.contains("휴지통삭제복원테스트")).expect("found in trash");

    // Restore
    let restored_id = db.restore_item(trash_item.id).expect("restore item");
    let restored_detail = db.get_history_detail(restored_id).expect("restored item exists in history");
    assert!(restored_detail.content.contains("휴지통삭제복원테스트"));
}
