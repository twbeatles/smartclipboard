use std::fs;
use std::path::PathBuf;
use tempfile::NamedTempFile;

use smartclipboard_native_lib::database::Database;

fn create_temp_db_copy() -> (NamedTempFile, Database) {
    let fixture_path = PathBuf::from("fixtures/synthetic_test_v6.db");
    assert!(fixture_path.exists());

    let temp = NamedTempFile::new().expect("create temp file");
    fs::copy(&fixture_path, temp.path()).expect("copy fixture db");

    let db = Database::open_read_write(temp.path()).expect("open read write");
    (temp, db)
}

#[test]
fn test_restore_clears_missing_collection() {
    let (_temp, db) = create_temp_db_copy();
    let col_id = db
        .add_collection("Doomed", "📁", "#6366f1")
        .expect("add col");
    let (item_id, _) = db
        .add_item("restore probe", None, "TEXT")
        .expect("add item");
    db.with_conn(|conn| {
        conn.execute(
            "UPDATE history SET collection_id = ? WHERE id = ?",
            rusqlite::params![col_id, item_id],
        )?;
        Ok(())
    })
    .expect("assign collection");

    db.soft_delete(item_id).expect("soft delete");
    let trash: Vec<i64> = db
        .with_conn(|conn| {
            let mut stmt = conn.prepare("SELECT id FROM deleted_history WHERE original_id = ?")?;
            let rows = stmt.query_map(rusqlite::params![item_id], |r| r.get(0))?;
            let mut ids = Vec::new();
            for r in rows {
                ids.push(r?);
            }
            Ok(ids)
        })
        .expect("trash ids");
    assert_eq!(trash.len(), 1);

    db.delete_collection(col_id).expect("delete collection");
    let new_id = db.restore_item(trash[0]).expect("restore");
    let detail = db.get_history_detail(new_id).expect("detail");
    assert_eq!(
        detail.collection_id, None,
        "dangling collection must become NULL"
    );
}

#[test]
fn test_file_trash_roundtrip_preserves_signature() {
    let (_temp, db) = create_temp_db_copy();
    let files = "C:\\roundtrip\\one.txt\nC:\\roundtrip\\two.txt";
    let (item_id, _) = db.add_item(files, None, "FILE").expect("add file");
    let before_sig = db
        .get_history_detail(item_id)
        .expect("detail")
        .file_signature;
    assert!(!before_sig.is_empty());

    db.soft_delete(item_id).expect("soft delete");
    let trash_id: i64 = db
        .with_conn(|conn| {
            Ok(conn.query_row(
                "SELECT id FROM deleted_history WHERE original_id = ?",
                rusqlite::params![item_id],
                |r| r.get(0),
            )?)
        })
        .expect("trash id");
    let restored = db.restore_item(trash_id).expect("restore");
    let after = db.get_history_detail(restored).expect("detail");
    assert_eq!(after.file_signature, before_sig);

    let (_, updated) = db.add_item(files, None, "FILE").expect("re-add");
    assert!(updated, "restored FILE must match signature dedupe");
}

#[test]
fn test_purge_expired_trash() {
    let (_temp, db) = create_temp_db_copy();
    // The shared fixture ships an already-expired trash row; clear it so the
    // test observes only rows it creates itself.
    db.with_conn(|conn| {
        conn.execute("DELETE FROM deleted_history", [])?;
        Ok(())
    })
    .expect("clear trash");
    let (item_id, _) = db.add_item("purge probe", None, "TEXT").expect("add");
    db.soft_delete(item_id).expect("soft delete");
    db.with_conn(|conn| {
        conn.execute(
            "UPDATE deleted_history SET expires_at = '2000-01-01 00:00:00' WHERE original_id = ?",
            rusqlite::params![item_id],
        )?;
        Ok(())
    })
    .expect("expire row");

    let (fresh_id, _) = db.add_item("fresh probe", None, "TEXT").expect("add fresh");
    db.soft_delete(fresh_id).expect("soft delete fresh");

    let purged = db.purge_expired_trash().expect("purge");
    assert_eq!(purged, 1);
    assert_eq!(db.get_trash().expect("trash").len(), 1);
}

#[test]
fn test_enforce_history_limit_keeps_pinned() {
    let (_temp, db) = create_temp_db_copy();
    db.set_setting("max_history", "3").expect("set limit");
    db.with_conn(|conn| {
        conn.execute("DELETE FROM history", [])?;
        Ok(())
    })
    .expect("clear");

    let (pinned_id, _) = db
        .add_item("pinned survivor", None, "TEXT")
        .expect("add pinned");
    assert!(db.toggle_pin(pinned_id).expect("pin"));
    for i in 0..5 {
        db.add_item(&format!("ephemeral {}", i), None, "TEXT")
            .expect("add");
    }

    let deleted = db.enforce_history_limit().expect("enforce");
    assert!(deleted >= 2);
    let items = db.list_history(100).expect("list");
    assert!(
        items.iter().any(|i| i.id == pinned_id),
        "pinned row must survive"
    );
    assert_eq!(items.iter().filter(|i| !i.pinned).count(), 3);
}

#[test]
fn test_latest_paste_candidate_ignores_pin_order() {
    let (_temp, db) = create_temp_db_copy();
    db.with_conn(|conn| {
        conn.execute("DELETE FROM history", [])?;
        Ok(())
    })
    .expect("clear");

    let (old_id, _) = db.add_item("older pinned", None, "TEXT").expect("add old");
    assert!(db.toggle_pin(old_id).expect("pin"));
    db.add_item("newer plain", None, "TEXT").expect("add new");

    let candidate = db
        .latest_paste_candidate()
        .expect("candidate")
        .expect("some");
    assert_eq!(candidate.content, "newer plain");
}

#[test]
fn test_migrate_adds_missing_columns() {
    let temp = NamedTempFile::new().expect("temp file");
    {
        let db = Database::open_read_write(temp.path()).expect("open");
        db.with_conn(|conn| {
            conn.execute("DROP TABLE IF EXISTS history", [])?;
            conn.execute(
                "CREATE TABLE history (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT)",
                [],
            )?;
            Ok(())
        })
        .expect("shrink history");
    }

    let db = Database::open_read_write(temp.path()).expect("reopen");
    let cols: Vec<String> = db
        .with_conn(|conn| {
            let mut stmt = conn.prepare("PRAGMA table_info(history)")?;
            let rows = stmt.query_map([], |r| r.get::<_, String>(1))?;
            let mut out = Vec::new();
            for r in rows {
                out.push(r?);
            }
            Ok(out)
        })
        .expect("columns");
    for required in [
        "url_title",
        "file_signature",
        "file_path",
        "tags",
        "collection_id",
    ] {
        assert!(
            cols.contains(&required.to_string()),
            "missing migrated column {}",
            required
        );
    }
    db.add_item("post-migration write", None, "TEXT")
        .expect("write after migrate");
}

#[test]
fn test_snippet_shortcut_collision() {
    let (_temp, db) = create_temp_db_copy();
    db.with_conn(|conn| {
        conn.execute("DELETE FROM snippets", [])?;
        Ok(())
    })
    .expect("clear");

    db.add_snippet("a", "content a", Some("Ctrl+1"), "일반")
        .expect("add a");
    assert!(db
        .add_snippet("b", "content b", Some("Ctrl+1"), "일반")
        .is_err());
    let b_id = db
        .add_snippet("b", "content b", Some("Ctrl+2"), "일반")
        .expect("add b");
    assert!(db
        .update_snippet(b_id, "b", "content b", Some("Ctrl+1"), "일반")
        .is_err());
    db.update_snippet(b_id, "b", "content b", Some("Ctrl+2"), "일반")
        .expect("same shortcut ok");
    db.update_snippet(b_id, "b", "content b", None, "일반")
        .expect("clear shortcut ok");
}

#[test]
fn test_fts_failure_falls_back_to_like() {
    let (_temp, db) = create_temp_db_copy();
    db.add_item("fallback-probe-xyz-unique", None, "TEXT")
        .expect("add probe");
    db.with_conn(|conn| {
        conn.execute("DROP TABLE history_fts", [])?;
        Ok(())
    })
    .expect("break fts");

    let filter = smartclipboard_native_lib::database::SearchFilter {
        query: "fallback-probe-xyz-unique".to_string(),
        ..Default::default()
    };
    let results = db.search_items(&filter).expect("search must not fail");
    assert!(results
        .iter()
        .any(|i| i.content.contains("fallback-probe-xyz-unique")));
}
