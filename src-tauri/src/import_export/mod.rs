use base64::engine::general_purpose::STANDARD as BASE64;
use base64::Engine;

use serde::{Deserialize, Serialize};

use std::collections::HashMap;

use crate::database::file_paths::{
    file_content_from_paths, file_signature_from_paths, normalize_local_file_paths,
};
use crate::database::{Collection, Database, Snippet};
use crate::errors::{AppError, Result};
use rusqlite::OptionalExtension;

#[derive(Debug, Serialize, Deserialize)]
pub struct ExportData {
    pub version: u32,
    pub app_version: String,
    pub export_date: String,
    pub item_count: usize,
    pub history: Vec<ExportHistoryItem>,
    pub collections: Vec<Collection>,
    pub snippets: Vec<Snippet>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ExportHistoryItem {
    pub id: i64,
    pub content: String,
    pub image_data: Option<String>, // Base64
    pub r#type: String,
    pub timestamp: String,
    pub tags: String,
    pub note: String,
    pub bookmark: i64,
    pub collection_id: Option<i64>,
    pub pinned: i64,
    pub pin_order: i64,
    pub use_count: i64,
    pub url_title: String,
}

/// Export full database to JSON string matching Python's json_codec format
pub fn export_to_json(db: &Database) -> Result<String> {
    let collections = db.get_collections()?;
    let snippets = db.get_snippets()?;

    let history_items = db.list_history(10_000)?;
    let mut export_history = Vec::with_capacity(history_items.len());

    for item in history_items {
        let detail = db.get_history_detail(item.id)?;
        export_history.push(ExportHistoryItem {
            id: detail.id,
            content: detail.content,
            image_data: detail.image_data_base64,
            r#type: detail.r#type,
            timestamp: detail.timestamp,
            tags: detail.tags,
            note: detail.note,
            bookmark: if detail.bookmark { 1 } else { 0 },
            collection_id: detail.collection_id,
            pinned: if detail.pinned { 1 } else { 0 },
            pin_order: detail.pin_order,
            use_count: detail.use_count,
            url_title: detail.url_title,
        });
    }

    let data = ExportData {
        version: 1,
        app_version: "10.7.0".into(),
        export_date: chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string(),
        item_count: export_history.len(),
        history: export_history,
        collections,
        snippets,
    };

    serde_json::to_string_pretty(&data).map_err(|e| AppError::Internal(e.to_string()))
}

/// Import data from JSON string into database.
///
/// Accepts both the native payload (`history` array) and the Python migration
/// payload (`items` array with `collections` legacy metadata). Collections are
/// remapped by name, FILE signatures are rebuilt, a pre-import backup is
/// attempted, and the whole import runs as one transaction that rolls back on
/// any hard failure. Invalid rows are skipped with a warning instead of
/// aborting the import.
pub fn import_from_json(json_str: &str, db: &Database) -> Result<(usize, usize)> {
    let root: serde_json::Value = serde_json::from_str(json_str)
        .map_err(|e| AppError::Internal(format!("Invalid JSON format: {}", e)))?;
    let obj = root
        .as_object()
        .ok_or_else(|| AppError::Internal("JSON import payload must be an object".into()))?;

    let items = obj
        .get("items")
        .or_else(|| obj.get("history"))
        .and_then(serde_json::Value::as_array)
        .ok_or_else(|| {
            AppError::Internal("JSON import payload must contain an items list".into())
        })?;
    let collections = obj.get("collections").and_then(serde_json::Value::as_array);
    let collections_present = collections
        .map(|entries| !entries.is_empty())
        .unwrap_or(false);
    let snippets = obj.get("snippets").and_then(serde_json::Value::as_array);

    backup_before_import(db);

    let mut imported_history = 0usize;
    let mut imported_snippets = 0usize;
    let mut skipped = 0usize;

    db.with_conn(|conn| {
        conn.execute("BEGIN IMMEDIATE", [])?;
        let outcome: Result<()> = (|| {
            let (native_map, legacy_map) = match collections {
                Some(entries) => import_collection_entries(conn, entries)?,
                None => (HashMap::new(), HashMap::new()),
            };

            if let Some(entries) = snippets {
                for entry in entries {
                    if import_snippet_entry(conn, entry)? {
                        imported_snippets += 1;
                    }
                }
            }

            for item in items {
                match prepare_json_item(item, &native_map, &legacy_map, collections_present) {
                    Some(prepared) => {
                        upsert_import_item(conn, &prepared)?;
                        imported_history += 1;
                    }
                    None => skipped += 1,
                }
            }
            Ok(())
        })();
        match outcome {
            Ok(()) => {
                conn.execute("COMMIT", [])?;
                Ok(())
            }
            Err(e) => {
                let _ = conn.execute("ROLLBACK", []);
                Err(e)
            }
        }
    })?;

    if skipped > 0 {
        tracing::warn!("JSON import skipped {} invalid rows", skipped);
    }
    Ok((imported_history, imported_snippets))
}

const VALID_ITEM_TYPES: &[&str] = &["TEXT", "LINK", "IMAGE", "CODE", "COLOR", "FILE"];
const MAX_IMAGE_IMPORT_BYTES: usize = 5 * 1024 * 1024;

fn current_timestamp_str() -> String {
    chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string()
}

fn normalize_import_timestamp(raw: Option<&str>) -> String {
    let t = raw.unwrap_or("").trim();
    if t.is_empty() {
        current_timestamp_str()
    } else {
        t.to_string()
    }
}

/// Best-effort copy of the database file before a destructive import.
/// A failed backup never blocks the import; the transaction still guards it.
fn backup_before_import(db: &Database) {
    let src = db.path();
    if !src.is_file() {
        return;
    }
    let stamp = chrono::Local::now().format("%Y%m%d-%H%M%S").to_string();
    let dst = src.with_extension(format!("pre-import-{}.bak", stamp));
    match std::fs::copy(src, &dst) {
        Ok(_) => tracing::info!("Pre-import backup written to {:?}", dst),
        Err(e) => tracing::warn!("Pre-import backup failed (continuing): {}", e),
    }
}

/// Mirrors Python's CSV/JSON bool normalization (1/true/yes/on/예/y).
fn import_bool(value: Option<&serde_json::Value>) -> Option<i64> {
    match value? {
        serde_json::Value::Bool(b) => Some(i64::from(*b)),
        serde_json::Value::Number(n) => n.as_i64().filter(|x| *x == 0 || *x == 1),
        serde_json::Value::String(s) => match s.trim().to_lowercase().as_str() {
            "1" | "true" | "yes" | "on" | "예" | "y" => Some(1),
            "0" | "false" | "no" | "off" | "아니오" | "n" => Some(0),
            _ => None,
        },
        _ => None,
    }
}

fn import_nonnegative(value: Option<&serde_json::Value>) -> Option<i64> {
    match value? {
        serde_json::Value::Bool(_) => None,
        serde_json::Value::Number(n) => n.as_i64().map(|x| x.max(0)),
        serde_json::Value::String(s) => s.trim().parse::<i64>().ok().map(|x| x.max(0)),
        _ => None,
    }
}

/// Mirrors Python's normalize_collection_lookup_key: ints and numeric strings.
fn collection_key(value: Option<&serde_json::Value>) -> Option<i64> {
    match value? {
        serde_json::Value::Bool(_) | serde_json::Value::Null => None,
        serde_json::Value::Number(n) => n.as_i64(),
        serde_json::Value::String(s) => s.trim().parse::<i64>().ok(),
        _ => None,
    }
}

/// Imports collection entries, reusing same-named collections.
/// Returns (native id map, legacy id map) for item remapping.
fn import_collection_entries(
    conn: &rusqlite::Connection,
    entries: &[serde_json::Value],
) -> Result<(HashMap<i64, i64>, HashMap<i64, i64>)> {
    let mut native_map = HashMap::new();
    let mut legacy_map = HashMap::new();
    for entry in entries {
        let name = entry
            .get("name")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("")
            .trim();
        if name.is_empty() {
            tracing::warn!("Skipping collection with empty name");
            continue;
        }
        let icon = entry
            .get("icon")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("📁");
        let color = entry
            .get("color")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("#6366f1");

        let existing: Option<i64> = conn
            .query_row(
                "SELECT id FROM collections WHERE name = ?",
                rusqlite::params![name],
                |row| row.get(0),
            )
            .optional()?;
        let real_id = match existing {
            Some(id) => id,
            None => {
                conn.execute(
                    "INSERT INTO collections (name, icon, color, created_at) \
                     VALUES (?, ?, ?, datetime('now', 'localtime'))",
                    rusqlite::params![name, icon, color],
                )?;
                conn.last_insert_rowid()
            }
        };
        if let Some(native_id) = entry.get("id").and_then(serde_json::Value::as_i64) {
            native_map.insert(native_id, real_id);
        }
        if let Some(legacy_id) = collection_key(entry.get("legacy_id")) {
            legacy_map.insert(legacy_id, real_id);
        }
    }
    Ok((native_map, legacy_map))
}

/// Imports one snippet entry. Returns true when a row was added.
/// Existing (name, content) pairs are reused instead of duplicated.
fn import_snippet_entry(conn: &rusqlite::Connection, entry: &serde_json::Value) -> Result<bool> {
    let name = entry
        .get("name")
        .and_then(serde_json::Value::as_str)
        .unwrap_or("")
        .trim();
    let content = entry
        .get("content")
        .and_then(serde_json::Value::as_str)
        .unwrap_or("");
    if name.is_empty() || content.is_empty() {
        tracing::warn!("Skipping snippet with empty name or content");
        return Ok(false);
    }
    let shortcut = entry.get("shortcut").and_then(serde_json::Value::as_str);
    let category = entry
        .get("category")
        .and_then(serde_json::Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .unwrap_or("일반");

    let existing: Option<i64> = conn
        .query_row(
            "SELECT id FROM snippets WHERE name = ? AND content = ?",
            rusqlite::params![name, content],
            |row| row.get(0),
        )
        .optional()?;
    if existing.is_some() {
        return Ok(false);
    }
    conn.execute(
        "INSERT INTO snippets (name, content, shortcut, category, created_at) \
         VALUES (?, ?, ?, ?, datetime('now', 'localtime'))",
        rusqlite::params![name, content, shortcut, category],
    )?;
    Ok(true)
}

struct PreparedItem {
    content: String,
    image_data: Option<Vec<u8>>,
    type_tag: String,
    timestamp: String,
    tags: String,
    note: String,
    bookmark: i64,
    collection_id: Option<i64>,
    pinned: i64,
    pin_order: i64,
    use_count: i64,
    url_title: String,
    file_path: String,
    file_signature: String,
}

/// Validates and normalizes one JSON item. Returns None for rows that must
/// be skipped (bad image, no usable FILE paths, empty content).
fn prepare_json_item(
    item: &serde_json::Value,
    native_map: &HashMap<i64, i64>,
    legacy_map: &HashMap<i64, i64>,
    collections_present: bool,
) -> Option<PreparedItem> {
    let raw_type = item
        .get("type")
        .and_then(serde_json::Value::as_str)
        .unwrap_or("TEXT");
    let type_tag = if VALID_ITEM_TYPES.contains(&raw_type) {
        raw_type.to_string()
    } else {
        "TEXT".to_string()
    };

    let image_data = if type_tag == "IMAGE" {
        let b64 = item
            .get("image_data_b64")
            .or_else(|| item.get("image_data"))
            .and_then(serde_json::Value::as_str)?;
        let bytes = BASE64.decode(b64).ok()?;
        if bytes.is_empty() || bytes.len() > MAX_IMAGE_IMPORT_BYTES {
            return None;
        }
        Some(bytes)
    } else {
        None
    };

    let mut file_paths_norm: Vec<String> = Vec::new();
    let mut content = item
        .get("content")
        .and_then(serde_json::Value::as_str)
        .unwrap_or("")
        .to_string();
    if type_tag == "FILE" {
        let mut candidates: Vec<String> = Vec::new();
        if let Some(arr) = item.get("file_paths").and_then(serde_json::Value::as_array) {
            for e in arr {
                if let Some(s) = e.as_str() {
                    candidates.push(s.to_string());
                }
            }
        }
        if candidates.is_empty() {
            candidates = content.lines().map(str::to_string).collect();
        }
        file_paths_norm = normalize_local_file_paths(&candidates);
        if file_paths_norm.is_empty() {
            return None;
        }
        content = file_content_from_paths(&file_paths_norm);
    }
    if content.is_empty() && image_data.is_none() {
        return None;
    }
    if type_tag == "IMAGE" && content.is_empty() {
        content = "[이미지 캡처]".to_string();
    }

    let collection_id = match item.get("collection_id") {
        None => None,
        Some(v) => {
            if !collections_present {
                None
            } else {
                collection_key(Some(v))
                    .and_then(|k| legacy_map.get(&k).or_else(|| native_map.get(&k)).copied())
            }
        }
    };

    Some(PreparedItem {
        content,
        timestamp: normalize_import_timestamp(
            item.get("timestamp").and_then(serde_json::Value::as_str),
        ),
        tags: item
            .get("tags")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("")
            .to_string(),
        note: item
            .get("note")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("")
            .to_string(),
        bookmark: import_bool(item.get("bookmark")).unwrap_or(0),
        collection_id,
        pinned: import_bool(item.get("pinned")).unwrap_or(0),
        pin_order: import_nonnegative(item.get("pin_order")).unwrap_or(0),
        use_count: import_nonnegative(item.get("use_count")).unwrap_or(0),
        url_title: item
            .get("url_title")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("")
            .to_string(),
        file_path: file_paths_norm.first().cloned().unwrap_or_default(),
        file_signature: if type_tag == "FILE" {
            file_signature_from_paths(&file_paths_norm)
        } else {
            String::new()
        },
        type_tag,
        image_data,
    })
}

/// Inserts a prepared item, merging into an existing duplicate the same way
/// the live capture path does (content/signature match refreshes the row).
fn upsert_import_item(conn: &rusqlite::Connection, item: &PreparedItem) -> Result<()> {
    let existing: Option<i64> = if item.type_tag == "FILE" {
        conn.query_row(
            "SELECT id FROM history WHERE type = 'FILE' AND file_signature = ? \
             ORDER BY timestamp DESC, id DESC LIMIT 1",
            rusqlite::params![item.file_signature],
            |row| row.get(0),
        )
        .optional()?
    } else if item.type_tag == "IMAGE" {
        None
    } else {
        conn.query_row(
            "SELECT id FROM history WHERE content = ? AND type NOT IN ('IMAGE', 'FILE') \
             ORDER BY timestamp DESC, id DESC LIMIT 1",
            rusqlite::params![item.content],
            |row| row.get(0),
        )
        .optional()?
    };

    match existing {
        Some(id) => {
            conn.execute(
                "UPDATE history SET content = ?, image_data = NULL, type = ?, timestamp = ?, \
                 file_path = ?, file_signature = ?, tags = ?, note = ?, bookmark = ?, \
                 collection_id = ?, pinned = ?, pin_order = ?, use_count = ?, url_title = ? \
                 WHERE id = ?",
                rusqlite::params![
                    item.content,
                    item.type_tag,
                    item.timestamp,
                    item.file_path,
                    item.file_signature,
                    item.tags,
                    item.note,
                    item.bookmark,
                    item.collection_id,
                    item.pinned,
                    item.pin_order,
                    item.use_count,
                    item.url_title,
                    id
                ],
            )?;
        }
        None => {
            conn.execute(
                "INSERT INTO history (content, image_data, type, timestamp, tags, note, bookmark, \
                 collection_id, pinned, pin_order, use_count, url_title, file_path, file_signature) \
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rusqlite::params![
                    item.content,
                    item.image_data,
                    item.type_tag,
                    item.timestamp,
                    item.tags,
                    item.note,
                    item.bookmark,
                    item.collection_id,
                    item.pinned,
                    item.pin_order,
                    item.use_count,
                    item.url_title,
                    item.file_path,
                    item.file_signature
                ],
            )?;
        }
    }
    Ok(())
}

/// Import history rows from a CSV string.
///
/// Accepts the Python layout (header row skipped, positional columns
/// 내용,유형,시간,고정,사용횟수) and the native layout (named header with
/// content/type/... columns). IMAGE rows are skipped: binaries never
/// round-trip through CSV.
pub fn import_from_csv(csv_str: &str, db: &Database) -> Result<(usize, usize)> {
    let mut reader = csv::ReaderBuilder::new()
        .flexible(true)
        .trim(csv::Trim::Fields)
        .has_headers(true)
        .from_reader(csv_str.as_bytes());
    let header = reader
        .headers()
        .map_err(|e| AppError::Internal(format!("Invalid CSV header: {}", e)))?
        .clone();
    let lower: Vec<String> = header.iter().map(|h| h.trim().to_lowercase()).collect();
    let native = lower.iter().any(|h| h == "content");
    let col = |names: &[&str]| lower.iter().position(|h| names.contains(&h.as_str()));
    let (c_content, c_type, c_time, c_pinned, c_use) = if native {
        (
            col(&["content", "내용"]),
            col(&["type", "유형"]),
            col(&["timestamp", "시간", "time"]),
            col(&["pinned", "고정"]),
            col(&["use_count", "사용횟수"]),
        )
    } else {
        (Some(0), Some(1), Some(2), Some(3), Some(4))
    };

    backup_before_import(db);

    let mut imported = 0usize;
    let mut skipped = 0usize;

    db.with_conn(|conn| {
        conn.execute("BEGIN IMMEDIATE", [])?;
        let outcome: Result<()> = (|| {
            for record in reader.records() {
                let rec =
                    record.map_err(|e| AppError::Internal(format!("Invalid CSV row: {}", e)))?;
                let get = |idx: Option<usize>| idx.and_then(|i| rec.get(i)).unwrap_or("").trim();

                let raw_type = get(c_type);
                let type_tag = if raw_type.is_empty() {
                    "TEXT".to_string()
                } else if VALID_ITEM_TYPES.contains(&raw_type) {
                    raw_type.to_string()
                } else {
                    "TEXT".to_string()
                };
                if type_tag == "IMAGE" {
                    skipped += 1;
                    continue;
                }

                let raw_content = get(c_content);
                let (content, file_path, file_signature) = if type_tag == "FILE" {
                    let paths = normalize_local_file_paths(
                        &raw_content.lines().map(str::to_string).collect::<Vec<_>>(),
                    );
                    if paths.is_empty() {
                        skipped += 1;
                        continue;
                    }
                    let sig = file_signature_from_paths(&paths);
                    let first = paths.first().cloned().unwrap_or_default();
                    (file_content_from_paths(&paths), first, sig)
                } else {
                    (raw_content.to_string(), String::new(), String::new())
                };
                if content.is_empty() {
                    skipped += 1;
                    continue;
                }

                let pinned = matches!(
                    get(c_pinned).to_lowercase().as_str(),
                    "1" | "true" | "yes" | "on" | "예" | "y"
                );
                let use_count: i64 = get(c_use).parse::<i64>().unwrap_or(0).max(0);
                let pin_order = if pinned {
                    conn.query_row(
                        "SELECT COALESCE(MAX(pin_order), -1) + 1 FROM history WHERE pinned = 1",
                        [],
                        |row| row.get(0),
                    )?
                } else {
                    0
                };

                upsert_import_item(
                    conn,
                    &PreparedItem {
                        content,
                        image_data: None,
                        type_tag,
                        timestamp: normalize_import_timestamp(Some(get(c_time))),
                        tags: String::new(),
                        note: String::new(),
                        bookmark: 0,
                        collection_id: None,
                        pinned: i64::from(pinned),
                        pin_order,
                        use_count,
                        url_title: String::new(),
                        file_path,
                        file_signature,
                    },
                )?;
                imported += 1;
            }
            Ok(())
        })();
        match outcome {
            Ok(()) => {
                conn.execute("COMMIT", [])?;
                Ok(())
            }
            Err(e) => {
                let _ = conn.execute("ROLLBACK", []);
                Err(e)
            }
        }
    })?;

    if skipped > 0 {
        tracing::warn!("CSV import skipped {} rows", skipped);
    }
    Ok((imported, 0))
}

/// Export history to a Markdown document (Python markdown_codec layout).
pub fn export_to_markdown(db: &Database) -> Result<String> {
    use crate::database::file_paths::file_paths_from_content;

    let items = db.list_history(10_000)?;
    let mut out = String::new();
    out.push_str("# SmartClipboard Pro 히스토리\n\n");
    out.push_str(&format!(
        "내보낸 날짜: {}\n\n",
        chrono::Local::now().format("%Y-%m-%d %H:%M:%S")
    ));
    out.push_str("---\n\n");

    for item in items {
        let pin_mark = if item.pinned { "[PIN] " } else { "" };
        let icon = match item.r#type.as_str() {
            "LINK" => "[L]",
            "IMAGE" => "[I]",
            "CODE" => "[C]",
            "COLOR" => "[K]",
            "FILE" => "[F]",
            _ => "[T]",
        };
        out.push_str(&format!("### {}{} {}\n\n", pin_mark, icon, item.timestamp));
        match item.r#type.as_str() {
            "IMAGE" => {
                let label = if item.content.is_empty() {
                    "[이미지 항목]".to_string()
                } else {
                    item.content.clone()
                };
                out.push_str(&format!(
                    "{}\n\n> 이미지 바이너리 데이터는 Markdown 내보내기에서 제외됩니다.\n\n",
                    label
                ));
            }
            "FILE" => {
                let paths = file_paths_from_content(&item.content);
                let lines = if paths.is_empty() {
                    vec![if item.content.is_empty() {
                        "[파일 항목]".to_string()
                    } else {
                        item.content.clone()
                    }]
                } else {
                    paths
                };
                out.push_str("```text\n");
                out.push_str(&lines.join("\n"));
                out.push_str("\n```\n\n");
            }
            "CODE" => {
                out.push_str(&format!("```\n{}\n```\n\n", item.content));
            }
            "LINK" => {
                out.push_str(&format!("[{0}]({0})\n\n", item.content));
            }
            _ => {
                out.push_str(&format!("{}\n\n", item.content));
            }
        }
        out.push_str("---\n\n");
    }
    Ok(out)
}

/// Export text history items to CSV string
pub fn export_to_csv(db: &Database) -> Result<String> {
    let items = db.list_history(10_000)?;
    let mut wtr = csv::Writer::from_writer(vec![]);

    // Header
    wtr.write_record([
        "id",
        "type",
        "timestamp",
        "content",
        "tags",
        "note",
        "bookmark",
    ])
    .map_err(|e| AppError::Internal(e.to_string()))?;

    for item in items {
        if item.r#type != "IMAGE" {
            wtr.write_record([
                item.id.to_string(),
                item.r#type,
                item.timestamp,
                item.content,
                item.tags,
                item.note,
                if item.bookmark {
                    "1".into()
                } else {
                    "0".into()
                },
            ])
            .map_err(|e| AppError::Internal(e.to_string()))?;
        }
    }

    let bytes = wtr
        .into_inner()
        .map_err(|e| AppError::Internal(e.to_string()))?;
    String::from_utf8(bytes).map_err(|e| AppError::Internal(e.to_string()))
}
