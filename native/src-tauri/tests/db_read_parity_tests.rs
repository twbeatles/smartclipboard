use std::path::PathBuf;

use smartclipboard_native_lib::database::{Database, SearchFilter};

fn get_test_db() -> Database {
    let db_path = PathBuf::from("../../tests/native_parity/fixtures/synthetic_test_v6.db");
    assert!(db_path.exists(), "Synthetic DB fixture missing: {:?}", db_path);
    Database::open_read_only(&db_path).expect("Failed to open synthetic DB in read-only mode")
}

#[test]
fn test_history_list_ordering_and_fields() {
    let db = get_test_db();
    let items = db.list_history(50).expect("list_history failed");
    assert!(!items.is_empty(), "Items should not be empty");

    // First items must be pinned items
    assert!(items[0].pinned, "First item must be pinned");
    assert_eq!(items[0].pin_order, 0);

    // Verify item types present
    let types: Vec<&str> = items.iter().map(|i| i.r#type.as_str()).collect();
    assert!(types.contains(&"TEXT"));
    assert!(types.contains(&"LINK"));
    assert!(types.contains(&"COLOR"));
    assert!(types.contains(&"CODE"));
    assert!(types.contains(&"IMAGE"));
    assert!(types.contains(&"FILE"));
}

#[test]
fn test_fts5_search_korean_and_english() {
    let db = get_test_db();

    // 1. Search Korean keyword
    let kr_filter = SearchFilter {
        query: "스마트클립보드".into(),
        ..Default::default()
    };
    let kr_results = db.search_items(&kr_filter).expect("search korean failed");
    assert!(!kr_results.is_empty(), "Should find Korean item");
    assert!(kr_results[0].content.contains("스마트클립보드"));

    // 2. Search English keyword
    let en_filter = SearchFilter {
        query: "Quick brown".into(),
        ..Default::default()
    };
    let en_results = db.search_items(&en_filter).expect("search english failed");
    assert!(!en_results.is_empty(), "Should find English item");
    assert!(en_results[0].content.contains("Quick brown"));

    // 3. Search Code term
    let code_filter = SearchFilter {
        query: "hashlib".into(),
        ..Default::default()
    };
    let code_results = db.search_items(&code_filter).expect("search code failed");
    assert!(!code_results.is_empty(), "Should find code item");
    assert_eq!(code_results[0].r#type, "CODE");
}

#[test]
fn test_type_and_bookmark_filters() {
    let db = get_test_db();

    // Color filter
    let color_filter = SearchFilter {
        query: "".into(),
        type_filter: Some("🎨 색상".into()),
        ..Default::default()
    };
    let color_results = db.search_items(&color_filter).expect("color filter failed");
    assert!(!color_results.is_empty());
    for item in color_results {
        assert_eq!(item.r#type, "COLOR");
    }

    // Bookmark filter
    let bm_filter = SearchFilter {
        query: "".into(),
        bookmarked: Some(true),
        ..Default::default()
    };
    let bm_results = db.search_items(&bm_filter).expect("bookmark filter failed");
    assert!(!bm_results.is_empty());
    for item in bm_results {
        assert!(item.bookmark);
    }
}

#[test]
fn test_catalog_and_settings() {
    let db = get_test_db();

    // Collections
    let collections = db.get_collections().expect("get_collections failed");
    assert_eq!(collections.len(), 3);
    assert_eq!(collections[0].name, "업무");
    assert_eq!(collections[1].name, "개인");
    assert_eq!(collections[2].name, "프로젝트");

    // Snippets
    let snippets = db.get_snippets().expect("get_snippets failed");
    assert_eq!(snippets.len(), 2);
    assert_eq!(snippets[0].name, "이메일 서명");

    // Settings
    let settings = db.get_settings().expect("get_settings failed");
    assert_eq!(settings.get("theme").map(|s| s.as_str()), Some("Ocean"));
    assert_eq!(settings.get("max_history").map(|s| s.as_str()), Some("200"));
    assert!(settings.contains_key("vault_salt"));
    assert!(settings.contains_key("vault_verification"));

    // Trash
    let trash = db.get_trash().expect("get_trash failed");
    assert_eq!(trash.len(), 1);
    assert!(trash[0].content.contains("삭제되어 휴지통에 보관된 임시 메모"));
}
