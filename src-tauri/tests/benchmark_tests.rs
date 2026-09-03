use std::path::PathBuf;
use std::time::Instant;

use smartclipboard_native_lib::database::{Database, SearchFilter};

#[test]
fn test_native_benchmark_comparison() {
    let db_path = PathBuf::from("fixtures/synthetic_test_v6.db");
    assert!(db_path.exists());

    // 1. DB Open Latency
    let t0 = Instant::now();
    let db = Database::open_read_only(&db_path).expect("open failed");
    let db_open_dur = t0.elapsed();

    // 2. History List Latency (10 iterations)
    let mut list_durs = Vec::new();
    for _ in 0..10 {
        let t = Instant::now();
        let _ = db.list_history(100).expect("list failed");
        list_durs.push(t.elapsed().as_secs_f64() * 1000.0);
    }
    list_durs.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let list_median = list_durs[list_durs.len() / 2];

    // 3. FTS Search English (10 iterations)
    let en_filter = SearchFilter {
        query: "Quick brown".into(),
        limit: Some(50),
        ..Default::default()
    };
    let mut fts_en_durs = Vec::new();
    for _ in 0..10 {
        let t = Instant::now();
        let _ = db.search_items(&en_filter).expect("search failed");
        fts_en_durs.push(t.elapsed().as_secs_f64() * 1000.0);
    }
    fts_en_durs.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let fts_en_median = fts_en_durs[fts_en_durs.len() / 2];

    // 4. FTS Search Korean (10 iterations)
    let kr_filter = SearchFilter {
        query: "스마트클립보드".into(),
        limit: Some(50),
        ..Default::default()
    };
    let mut fts_kr_durs = Vec::new();
    for _ in 0..10 {
        let t = Instant::now();
        let _ = db.search_items(&kr_filter).expect("search failed");
        fts_kr_durs.push(t.elapsed().as_secs_f64() * 1000.0);
    }
    fts_kr_durs.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let fts_kr_median = fts_kr_durs[fts_kr_durs.len() / 2];

    println!("\n=== Rust Native Performance Benchmark ===");
    println!("  db_open_ms: {:.3}", db_open_dur.as_secs_f64() * 1000.0);
    println!("  history_list_ms_median: {:.3}", list_median);
    println!("  fts_en_ms_median: {:.3}", fts_en_median);
    println!("  fts_kr_ms_median: {:.3}", fts_kr_median);
}
