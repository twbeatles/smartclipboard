use base64::Engine;
use base64::engine::general_purpose::STANDARD as BASE64;
use rusqlite::params;
use serde::{Deserialize, Serialize};

use crate::database::{Collection, Database, Snippet};
use crate::errors::{AppError, Result};

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

/// Import data from JSON string into database
pub fn import_from_json(json_str: &str, db: &Database) -> Result<(usize, usize)> {
    let data: ExportData = serde_json::from_str(json_str)
        .map_err(|e| AppError::Internal(format!("Invalid JSON format: {}", e)))?;

    let mut imported_history = 0;
    let mut imported_snippets = 0;

    db.with_conn(|conn| {
        conn.execute("BEGIN TRANSACTION", [])?;

        // 1. Collections
        for col in &data.collections {
            conn.execute(
                "INSERT OR IGNORE INTO collections (id, name, icon, color, created_at) \
                 VALUES (?, ?, ?, ?, datetime('now'))",
                params![col.id, col.name, col.icon, col.color],
            )?;
        }

        // 2. Snippets
        for snip in &data.snippets {
            conn.execute(
                "INSERT OR IGNORE INTO snippets (name, content, shortcut, category, created_at) \
                 VALUES (?, ?, ?, ?, datetime('now'))",
                params![snip.name, snip.content, snip.shortcut, snip.category],
            )?;
            imported_snippets += 1;
        }

        // 3. History
        for item in &data.history {
            let img_bytes = item.image_data.as_ref().and_then(|b64| BASE64.decode(b64).ok());
            conn.execute(
                "INSERT INTO history (content, image_data, type, timestamp, tags, note, \
                 bookmark, collection_id, pinned, pin_order, use_count, url_title) \
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                params![
                    item.content,
                    img_bytes,
                    item.r#type,
                    item.timestamp,
                    item.tags,
                    item.note,
                    item.bookmark,
                    item.collection_id,
                    item.pinned,
                    item.pin_order,
                    item.use_count,
                    item.url_title
                ],
            )?;
            imported_history += 1;
        }

        conn.execute("COMMIT", [])?;
        Ok(())
    })?;

    Ok((imported_history, imported_snippets))
}

/// Export text history items to CSV string
pub fn export_to_csv(db: &Database) -> Result<String> {
    let items = db.list_history(10_000)?;
    let mut wtr = csv::Writer::from_writer(vec![]);

    // Header
    wtr.write_record(["id", "type", "timestamp", "content", "tags", "note", "bookmark"])
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
                if item.bookmark { "1".into() } else { "0".into() },
            ])
            .map_err(|e| AppError::Internal(e.to_string()))?;
        }
    }

    let bytes = wtr.into_inner().map_err(|e| AppError::Internal(e.to_string()))?;
    String::from_utf8(bytes).map_err(|e| AppError::Internal(e.to_string()))
}
