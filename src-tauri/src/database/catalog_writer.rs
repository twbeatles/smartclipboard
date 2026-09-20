use rusqlite::params;
use rusqlite::OptionalExtension;

use super::connection::Database;
use crate::errors::{AppError, Result};

impl Database {
    // === Collections ===

    pub fn add_collection(&self, name: &str, icon: &str, color: &str) -> Result<i64> {
        let trimmed_name = name.trim();
        if trimmed_name.is_empty() {
            return Err(AppError::Internal("Collection name cannot be empty".into()));
        }

        self.with_conn(|conn| {
            conn.execute(
                "INSERT INTO collections (name, icon, color, created_at) \
                 VALUES (?, ?, ?, datetime('now', 'localtime'))",
                params![trimmed_name, icon, color],
            )?;
            Ok(conn.last_insert_rowid())
        })
    }

    pub fn update_collection(&self, id: i64, name: &str, icon: &str, color: &str) -> Result<()> {
        let trimmed_name = name.trim();
        if trimmed_name.is_empty() {
            return Err(AppError::Internal("Collection name cannot be empty".into()));
        }

        self.with_conn(|conn| {
            let count = conn.execute(
                "UPDATE collections SET name = ?, icon = ?, color = ? WHERE id = ?",
                params![trimmed_name, icon, color, id],
            )?;
            if count == 0 {
                return Err(AppError::NotFound(format!(
                    "Collection id not found: {}",
                    id
                )));
            }
            Ok(())
        })
    }

    pub fn delete_collection(&self, id: i64) -> Result<()> {
        self.with_conn(|conn| {
            conn.execute(
                "UPDATE history SET collection_id = NULL WHERE collection_id = ?",
                params![id],
            )?;
            conn.execute(
                "UPDATE deleted_history SET collection_id = NULL WHERE collection_id = ?",
                params![id],
            )?;
            conn.execute("DELETE FROM collections WHERE id = ?", params![id])?;
            Ok(())
        })
    }

    /// App-local snippet shortcuts must be unique across snippets.
    fn check_snippet_shortcut(
        conn: &rusqlite::Connection,
        self_id: Option<i64>,
        shortcut: Option<&str>,
    ) -> Result<()> {
        let norm = shortcut.unwrap_or("").trim();
        if norm.is_empty() {
            return Ok(());
        }
        let clash: Option<i64> = conn
            .query_row(
                "SELECT id FROM snippets WHERE shortcut = ? AND (? IS NULL OR id != ?)",
                params![norm, self_id, self_id],
                |row| row.get(0),
            )
            .optional()?;
        if clash.is_some() {
            return Err(AppError::Internal(format!(
                "Snippet shortcut already in use: {}",
                norm
            )));
        }
        Ok(())
    }

    /// Stores one settings key/value pair.
    pub fn set_setting(&self, key: &str, value: &str) -> Result<()> {
        self.with_conn(|conn| {
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                params![key, value],
            )?;
            Ok(())
        })
    }

    // === Snippets ===

    pub fn add_snippet(
        &self,
        name: &str,
        content: &str,
        shortcut: Option<&str>,
        category: &str,
    ) -> Result<i64> {
        let cat = if category.trim().is_empty() {
            "일반"
        } else {
            category.trim()
        };

        self.with_conn(|conn| {
            Self::check_snippet_shortcut(conn, None, shortcut)?;
            conn.execute(
                "INSERT INTO snippets (name, content, shortcut, category, created_at) \
                 VALUES (?, ?, ?, ?, datetime('now', 'localtime'))",
                params![name, content, shortcut, cat],
            )?;
            Ok(conn.last_insert_rowid())
        })
    }

    pub fn update_snippet(
        &self,
        id: i64,
        name: &str,
        content: &str,
        shortcut: Option<&str>,
        category: &str,
    ) -> Result<()> {
        let cat = if category.trim().is_empty() {
            "일반"
        } else {
            category.trim()
        };

        self.with_conn(|conn| {
            let count = conn.execute(
                "UPDATE snippets SET name = ?, content = ?, shortcut = ?, category = ? WHERE id = ?",
                params![name, content, shortcut, cat, id],
            )?;
            if count == 0 {
                return Err(AppError::NotFound(format!("Snippet id not found: {}", id)));
            }
            Ok(())
        })
    }

    pub fn delete_snippet(&self, id: i64) -> Result<()> {
        self.with_conn(|conn| {
            conn.execute("DELETE FROM snippets WHERE id = ?", params![id])?;
            Ok(())
        })
    }

    // === Trash ===

    pub fn empty_trash(&self) -> Result<()> {
        self.with_conn(|conn| {
            conn.execute("DELETE FROM deleted_history", [])?;
            Ok(())
        })
    }
}
