use rusqlite::params;
use std::collections::HashSet;

use super::connection::Database;
use super::file_paths::{
    file_content_from_paths, file_paths_from_content, file_signature_from_paths,
};
use crate::errors::{AppError, Result};

fn current_timestamp() -> String {
    use std::time::SystemTime;
    let now = SystemTime::now();
    let datetime: chrono::DateTime<chrono::Local> = now.into();
    datetime.format("%Y-%m-%d %H:%M:%S").to_string()
}

fn merge_tag_strings(tags_a: &str, tags_b: &str) -> String {
    let mut set = HashSet::new();
    let mut order = Vec::new();

    for t in tags_a.split(',').chain(tags_b.split(',')) {
        let trimmed = t.trim();
        if !trimmed.is_empty() && !set.contains(trimmed) {
            set.insert(trimmed.to_string());
            order.push(trimmed.to_string());
        }
    }
    order.join(", ")
}

impl Database {
    /// Add history item. If a non-image/non-file text duplicate exists, it updates timestamp and type.
    /// If an identical file exists, it matches by file_signature and updates.
    /// Images always insert a new row.
    pub fn add_item(
        &self,
        content: &str,
        image_data: Option<&[u8]>,
        type_tag: &str,
    ) -> Result<(i64, bool)> {
        self.with_conn(|conn| {
            let timestamp = current_timestamp();

            if type_tag == "FILE" {
                let paths = file_paths_from_content(content);
                let normalized_content = file_content_from_paths(&paths);
                if normalized_content.is_empty() {
                    return Err(AppError::Internal("Empty file content".into()));
                }

                let file_path = paths.first().cloned().unwrap_or_default();
                let file_signature = file_signature_from_paths(&paths);

                let mut check_stmt = conn.prepare(
                    "SELECT id FROM history WHERE type = 'FILE' AND file_signature = ? \
                     ORDER BY timestamp DESC, id DESC LIMIT 1"
                )?;
                let mut rows = check_stmt.query(params![file_signature])?;

                if let Some(row) = rows.next()? {
                    let existing_id: i64 = row.get(0)?;
                    conn.execute(
                        "UPDATE history SET content = ?, image_data = NULL, type = ?, timestamp = ?, \
                         file_path = ?, file_signature = ? WHERE id = ?",
                        params![normalized_content, type_tag, timestamp, file_path, file_signature, existing_id],
                    )?;
                    return Ok((existing_id, true));
                } else {
                    conn.execute(
                        "INSERT INTO history (content, image_data, type, timestamp, file_path, file_signature) \
                         VALUES (?, NULL, ?, ?, ?, ?)",
                        params![normalized_content, type_tag, timestamp, file_path, file_signature],
                    )?;
                    return Ok((conn.last_insert_rowid(), false));
                }
            }

            if type_tag != "IMAGE" {
                let mut check_stmt = conn.prepare(
                    "SELECT id FROM history WHERE content = ? AND type NOT IN ('IMAGE', 'FILE') \
                     ORDER BY timestamp DESC, id DESC LIMIT 1"
                )?;
                let mut rows = check_stmt.query(params![content])?;

                if let Some(row) = rows.next()? {
                    let existing_id: i64 = row.get(0)?;
                    conn.execute(
                        "UPDATE history SET content = ?, image_data = NULL, type = ?, timestamp = ?, \
                         file_path = '', file_signature = '' WHERE id = ?",
                        params![content, type_tag, timestamp, existing_id],
                    )?;
                    return Ok((existing_id, true));
                } else {
                    conn.execute(
                        "INSERT INTO history (content, image_data, type, timestamp, file_path, file_signature) \
                         VALUES (?, NULL, ?, ?, '', '')",
                        params![content, type_tag, timestamp],
                    )?;
                    return Ok((conn.last_insert_rowid(), false));
                }
            }

            // IMAGE
            conn.execute(
                "INSERT INTO history (content, image_data, type, timestamp, file_path, file_signature) \
                 VALUES (?, ?, ?, ?, '', '')",
                params![content, image_data, type_tag, timestamp],
            )?;
            Ok((conn.last_insert_rowid(), false))
        })
    }

    /// Replace text history item, merging metadata into an existing duplicate when needed.
    #[allow(clippy::type_complexity)]
    pub fn replace_text_item_or_merge(
        &self,
        item_id: i64,
        content: &str,
        type_tag: &str,
    ) -> Result<i64> {
        if content.is_empty() {
            return Err(AppError::Internal("Content cannot be empty".into()));
        }

        self.with_conn(|conn| {
            // 1. Get current item's metadata
            let mut curr_stmt = conn.prepare(
                "SELECT tags, note, bookmark, collection_id, pinned, pin_order, use_count, timestamp, url_title \
                 FROM history WHERE id = ?"
            )?;
            let mut curr_rows = curr_stmt.query(params![item_id])?;
            let (
                curr_tags,
                curr_note,
                curr_bm,
                curr_col,
                curr_pinned,
                curr_pin_order,
                curr_use_count,
                _curr_ts,
                curr_url_title,
            ): (
                Option<String>,
                Option<String>,
                i64,
                Option<i64>,
                i64,
                i64,
                i64,
                Option<String>,
                Option<String>,
            ) = if let Some(r) = curr_rows.next()? {
                (
                    r.get(0)?,
                    r.get(1)?,
                    r.get(2)?,
                    r.get(3)?,
                    r.get(4)?,
                    r.get(5)?,
                    r.get(6)?,
                    r.get(7)?,
                    r.get(8)?,
                )
            } else {
                return Err(AppError::NotFound(format!("Item not found: {}", item_id)));
            };

            // 2. Check if another row has the exact same content
            let mut dup_stmt = conn.prepare(
                "SELECT id, tags, note, bookmark, collection_id, pinned, pin_order, use_count, url_title \
                 FROM history \
                 WHERE id != ? AND content = ? AND type NOT IN ('IMAGE', 'FILE') \
                 ORDER BY timestamp DESC, id DESC LIMIT 1"
            )?;
            let mut dup_rows = dup_stmt.query(params![item_id, content])?;

            if let Some(target_row) = dup_rows.next()? {
                let target_id: i64 = target_row.get(0)?;
                let target_tags: Option<String> = target_row.get(1)?;
                let target_note: Option<String> = target_row.get(2)?;
                let target_bm: i64 = target_row.get(3)?;
                let target_col: Option<i64> = target_row.get(4)?;
                let target_pinned: i64 = target_row.get(5)?;
                let target_pin_order: i64 = target_row.get(6)?;
                let target_use_count: i64 = target_row.get(7)?;
                let target_url_title: Option<String> = target_row.get(8)?;

                // Merge metadata
                let merged_tags = merge_tag_strings(
                    curr_tags.as_deref().unwrap_or(""),
                    target_tags.as_deref().unwrap_or(""),
                );
                let merged_note = if target_note.as_deref().unwrap_or("").trim().is_empty() {
                    curr_note.unwrap_or_default()
                } else {
                    target_note.unwrap_or_default()
                };
                let merged_bm = if curr_bm == 1 || target_bm == 1 { 1 } else { 0 };
                let merged_pinned = if target_pinned == 1 || curr_pinned == 1 { 1 } else { 0 };
                let merged_pin_order = if target_pinned == 1 {
                    target_pin_order
                } else if curr_pinned == 1 {
                    curr_pin_order
                } else {
                    0
                };
                let merged_col = target_col.or(curr_col);
                let merged_use_count = target_use_count + curr_use_count;
                let merged_url_title = if target_url_title.as_deref().unwrap_or("").trim().is_empty() {
                    curr_url_title.unwrap_or_default()
                } else {
                    target_url_title.unwrap_or_default()
                };

                conn.execute(
                    "UPDATE history SET tags = ?, note = ?, bookmark = ?, collection_id = ?, \
                     pinned = ?, pin_order = ?, use_count = ?, url_title = ? WHERE id = ?",
                    params![
                        merged_tags,
                        merged_note,
                        merged_bm,
                        merged_col,
                        merged_pinned,
                        merged_pin_order,
                        merged_use_count,
                        merged_url_title,
                        target_id
                    ],
                )?;

                conn.execute("DELETE FROM history WHERE id = ?", params![item_id])?;
                Ok(target_id)
            } else {
                conn.execute(
                    "UPDATE history SET content = ?, image_data = NULL, type = ?, file_path = '', \
                     file_signature = '', url_title = '' WHERE id = ?",
                    params![content, type_tag, item_id],
                )?;
                Ok(item_id)
            }
        })
    }

    pub fn toggle_pin(&self, item_id: i64) -> Result<bool> {
        self.with_conn(|conn| {
            let curr: Option<i64> = conn
                .query_row("SELECT pinned FROM history WHERE id = ?", params![item_id], |r| r.get(0))
                .ok();

            if let Some(status) = curr {
                let new_status = if status == 1 { 0 } else { 1 };
                if new_status == 1 {
                    let next_order: i64 = conn.query_row(
                        "SELECT COALESCE(MAX(pin_order), -1) + 1 FROM history WHERE pinned = 1",
                        [],
                        |r| r.get(0),
                    )?;
                    conn.execute(
                        "UPDATE history SET pinned = 1, pin_order = ? WHERE id = ?",
                        params![next_order, item_id],
                    )?;
                } else {
                    conn.execute(
                        "UPDATE history SET pinned = 0, pin_order = 0 WHERE id = ?",
                        params![item_id],
                    )?;
                }
                Ok(new_status == 1)
            } else {
                Err(AppError::NotFound(format!("Item not found: {}", item_id)))
            }
        })
    }

    pub fn toggle_bookmark(&self, item_id: i64) -> Result<bool> {
        self.with_conn(|conn| {
            let curr: i64 = conn.query_row(
                "SELECT bookmark FROM history WHERE id = ?",
                params![item_id],
                |r| r.get(0),
            )?;
            let new_bm = if curr == 1 { 0 } else { 1 };
            conn.execute(
                "UPDATE history SET bookmark = ? WHERE id = ?",
                params![new_bm, item_id],
            )?;
            Ok(new_bm == 1)
        })
    }

    pub fn increment_use_count(&self, item_id: i64) -> Result<()> {
        self.with_conn(|conn| {
            conn.execute(
                "UPDATE history SET use_count = use_count + 1 WHERE id = ?",
                params![item_id],
            )?;
            Ok(())
        })
    }

    pub fn set_note(&self, item_id: i64, note: &str) -> Result<()> {
        self.with_conn(|conn| {
            conn.execute(
                "UPDATE history SET note = ? WHERE id = ?",
                params![note, item_id],
            )?;
            Ok(())
        })
    }

    /// Soft delete an item by moving to deleted_history (7-day retention)
    pub fn soft_delete(&self, item_id: i64) -> Result<()> {
        self.with_conn(|conn| {
            let mut stmt = conn.prepare(
                "SELECT id, content, image_data, type, timestamp, tags, note, bookmark, \
                 collection_id, pinned, pin_order, use_count, url_title \
                 FROM history WHERE id = ?"
            )?;
            let mut rows = stmt.query(params![item_id])?;

            if let Some(row) = rows.next()? {
                let content: Option<String> = row.get(1)?;
                let image_data: Option<Vec<u8>> = row.get(2)?;
                let type_tag: String = row.get(3)?;
                let timestamp: Option<String> = row.get(4)?;
                let tags: Option<String> = row.get(5)?;
                let note: Option<String> = row.get(6)?;
                let bookmark: i64 = row.get(7)?;
                let collection_id: Option<i64> = row.get(8)?;
                let pinned: i64 = row.get(9)?;
                let pin_order: i64 = row.get(10)?;
                let use_count: i64 = row.get(11)?;
                let url_title: Option<String> = row.get(12)?;
                let deleted_at = current_timestamp();

                // 7 days expiration
                let expires_at = {
                    let now = chrono::Local::now();
                    let exp = now + chrono::Duration::days(7);
                    exp.format("%Y-%m-%d %H:%M:%S").to_string()
                };

                conn.execute(
                    "INSERT INTO deleted_history (original_id, content, image_data, type, \
                     original_timestamp, tags, note, bookmark, collection_id, pinned, pin_order, \
                     use_count, url_title, deleted_at, expires_at) \
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    params![
                        item_id,
                        content,
                        image_data,
                        type_tag,
                        timestamp,
                        tags,
                        note,
                        bookmark,
                        collection_id,
                        pinned,
                        pin_order,
                        use_count,
                        url_title,
                        deleted_at,
                        expires_at
                    ],
                )?;

                conn.execute("DELETE FROM history WHERE id = ?", params![item_id])?;
                Ok(())
            } else {
                Err(AppError::NotFound(format!("Item not found: {}", item_id)))
            }
        })
    }

    /// Restore item from deleted_history back to history
    pub fn restore_item(&self, deleted_id: i64) -> Result<i64> {
        self.with_conn(|conn| {
            let mut stmt = conn.prepare(
                "SELECT original_id, content, image_data, type, original_timestamp, tags, note, \
                 bookmark, collection_id, pinned, pin_order, use_count, url_title \
                 FROM deleted_history WHERE id = ?"
            )?;
            let mut rows = stmt.query(params![deleted_id])?;

            if let Some(row) = rows.next()? {
                let content: Option<String> = row.get(1)?;
                let image_data: Option<Vec<u8>> = row.get(2)?;
                let type_tag: String = row.get(3)?;
                let timestamp: Option<String> = row.get(4)?;
                let tags: Option<String> = row.get(5)?;
                let note: Option<String> = row.get(6)?;
                let bookmark: i64 = row.get(7)?;
                let collection_id: Option<i64> = row.get(8)?;
                let pinned: i64 = row.get(9)?;
                let pin_order: i64 = row.get(10)?;
                let use_count: i64 = row.get(11)?;
                let url_title: Option<String> = row.get(12)?;

                conn.execute(
                    "INSERT INTO history (content, image_data, type, timestamp, tags, note, bookmark, \
                     collection_id, pinned, pin_order, use_count, url_title) \
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    params![
                        content,
                        image_data,
                        type_tag,
                        timestamp,
                        tags,
                        note,
                        bookmark,
                        collection_id,
                        pinned,
                        pin_order,
                        use_count,
                        url_title
                    ],
                )?;

                let new_id = conn.last_insert_rowid();
                conn.execute("DELETE FROM deleted_history WHERE id = ?", params![deleted_id])?;
                Ok(new_id)
            } else {
                Err(AppError::NotFound(format!("Trash item not found: {}", deleted_id)))
            }
        })
    }

    pub fn permanent_delete(&self, deleted_id: i64) -> Result<()> {
        self.with_conn(|conn| {
            conn.execute("DELETE FROM deleted_history WHERE id = ?", params![deleted_id])?;
            Ok(())
        })
    }
}
