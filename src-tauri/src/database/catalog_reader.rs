use std::collections::HashMap;
use rusqlite::params;

use super::connection::Database;
use super::models::{Collection, Snippet, TrashItem};
use crate::errors::Result;

impl Database {
    pub fn get_collections(&self) -> Result<Vec<Collection>> {
        self.with_conn(|conn| {
            let mut stmt = conn.prepare("SELECT id, name, icon, color, created_at FROM collections ORDER BY id ASC")?;
            let rows = stmt.query_map([], |row| {
                Ok(Collection {
                    id: row.get(0)?,
                    name: row.get(1)?,
                    icon: row.get::<_, Option<String>>(2)?.unwrap_or_else(|| "📁".into()),
                    color: row.get::<_, Option<String>>(3)?.unwrap_or_else(|| "#6366f1".into()),
                    created_at: row.get(4)?,
                })
            })?;

            let mut list = Vec::new();
            for r in rows {
                list.push(r?);
            }
            Ok(list)
        })
    }

    pub fn get_snippets(&self) -> Result<Vec<Snippet>> {
        self.with_conn(|conn| {
            let mut stmt = conn.prepare("SELECT id, name, content, shortcut, category, created_at FROM snippets ORDER BY id ASC")?;
            let rows = stmt.query_map([], |row| {
                Ok(Snippet {
                    id: row.get(0)?,
                    name: row.get(1)?,
                    content: row.get(2)?,
                    shortcut: row.get(3)?,
                    category: row.get::<_, Option<String>>(4)?.unwrap_or_else(|| "일반".into()),
                    created_at: row.get(5)?,
                })
            })?;

            let mut list = Vec::new();
            for r in rows {
                list.push(r?);
            }
            Ok(list)
        })
    }

    pub fn get_settings(&self) -> Result<HashMap<String, String>> {
        self.with_conn(|conn| {
            let mut stmt = conn.prepare("SELECT key, value FROM settings")?;
            let rows = stmt.query_map([], |row| {
                Ok((row.get::<_, String>(0)?, row.get::<_, Option<String>>(1)?.unwrap_or_default()))
            })?;

            let mut map = HashMap::new();
            for r in rows {
                let (k, v) = r?;
                map.insert(k, v);
            }
            Ok(map)
        })
    }

    pub fn get_setting(&self, key: &str) -> Result<Option<String>> {
        self.with_conn(|conn| {
            let mut stmt = conn.prepare("SELECT value FROM settings WHERE key = ?")?;
            let mut rows = stmt.query(params![key])?;
            if let Some(row) = rows.next()? {
                Ok(row.get(0)?)
            } else {
                Ok(None)
            }
        })
    }

    pub fn get_trash(&self) -> Result<Vec<TrashItem>> {
        self.with_conn(|conn| {
            let mut stmt = conn.prepare(
                "SELECT id, original_id, content, type, deleted_at, original_timestamp, tags \
                 FROM deleted_history ORDER BY deleted_at DESC, id DESC"
            )?;

            let rows = stmt.query_map([], |row| {
                Ok(TrashItem {
                    id: row.get(0)?,
                    original_id: row.get(1)?,
                    content: row.get::<_, Option<String>>(2)?.unwrap_or_default(),
                    r#type: row.get::<_, Option<String>>(3)?.unwrap_or_else(|| "TEXT".into()),
                    deleted_at: row.get(4)?,
                    original_timestamp: row.get(5)?,
                    tags: row.get::<_, Option<String>>(6)?.unwrap_or_default(),
                })
            })?;

            let mut list = Vec::new();
            for r in rows {
                list.push(r?);
            }
            Ok(list)
        })
    }

    pub fn vault_has_password(&self) -> Result<bool> {
        let settings = self.get_settings()?;
        Ok(settings.contains_key("vault_salt") && settings.contains_key("vault_verification"))
    }
}
