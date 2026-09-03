use base64::Engine;
use base64::engine::general_purpose::STANDARD as BASE64;
use rusqlite::params;

use super::connection::Database;
use super::models::{HistoryDetail, HistoryItem};
use crate::errors::{AppError, Result};

impl Database {
    /// List history items without heavy image blobs (ordered identical to Python implementation)
    pub fn list_history(&self, limit: usize) -> Result<Vec<HistoryItem>> {
        self.with_conn(|conn| {
            let mut stmt = conn.prepare(
                "SELECT id, content, type, timestamp, pinned, pin_order, use_count, bookmark, \
                 tags, note, url_title, collection_id, (image_data IS NOT NULL) AS has_image \
                 FROM history \
                 ORDER BY pinned DESC, pin_order ASC, timestamp DESC, id DESC \
                 LIMIT ?"
            )?;

            let rows = stmt.query_map(params![limit as i64], |row| {
                Ok(HistoryItem {
                    id: row.get(0)?,
                    content: row.get::<_, Option<String>>(1)?.unwrap_or_default(),
                    r#type: row.get::<_, Option<String>>(2)?.unwrap_or_else(|| "TEXT".into()),
                    timestamp: row.get::<_, Option<String>>(3)?.unwrap_or_default(),
                    pinned: row.get::<_, i64>(4)? == 1,
                    pin_order: row.get(5)?,
                    use_count: row.get(6)?,
                    bookmark: row.get::<_, i64>(7)? == 1,
                    tags: row.get::<_, Option<String>>(8)?.unwrap_or_default(),
                    note: row.get::<_, Option<String>>(9)?.unwrap_or_default(),
                    url_title: row.get::<_, Option<String>>(10)?.unwrap_or_default(),
                    collection_id: row.get(11)?,
                    has_image: row.get::<_, i64>(12)? == 1,
                })
            })?;

            let mut items = Vec::new();
            for r in rows {
                items.push(r?);
            }
            Ok(items)
        })
    }

    /// Retrieve full item detail including image blob (converted to base64) or file paths
    pub fn get_history_detail(&self, item_id: i64) -> Result<HistoryDetail> {
        self.with_conn(|conn| {
            let mut stmt = conn.prepare(
                "SELECT id, content, type, timestamp, pinned, pin_order, use_count, bookmark, \
                 tags, note, url_title, collection_id, image_data, file_path, file_signature \
                 FROM history WHERE id = ?"
            )?;

            let mut rows = stmt.query(params![item_id])?;
            if let Some(row) = rows.next()? {
                let image_bytes: Option<Vec<u8>> = row.get(12)?;
                let image_data_base64 = image_bytes.map(|b| BASE64.encode(&b));

                Ok(HistoryDetail {
                    id: row.get(0)?,
                    content: row.get::<_, Option<String>>(1)?.unwrap_or_default(),
                    r#type: row.get::<_, Option<String>>(2)?.unwrap_or_else(|| "TEXT".into()),
                    timestamp: row.get::<_, Option<String>>(3)?.unwrap_or_default(),
                    pinned: row.get::<_, i64>(4)? == 1,
                    pin_order: row.get(5)?,
                    use_count: row.get(6)?,
                    bookmark: row.get::<_, i64>(7)? == 1,
                    tags: row.get::<_, Option<String>>(8)?.unwrap_or_default(),
                    note: row.get::<_, Option<String>>(9)?.unwrap_or_default(),
                    url_title: row.get::<_, Option<String>>(10)?.unwrap_or_default(),
                    collection_id: row.get(11)?,
                    image_data_base64,
                    file_path: row.get::<_, Option<String>>(13)?.unwrap_or_default(),
                    file_signature: row.get::<_, Option<String>>(14)?.unwrap_or_default(),
                })
            } else {
                Err(AppError::NotFound(format!("Item not found with id: {}", item_id)))
            }
        })
    }
}
