use rusqlite::types::ToSql;

use super::connection::Database;
use super::models::{HistoryItem, SearchFilter};
use crate::errors::Result;

impl Database {
    /// Tokenize search query identically to Python: tokens = re.findall(r"[\w]+", query)
    pub fn tokenize_query(query: &str) -> Vec<String> {
        let mut tokens = Vec::new();
        let mut current = String::new();

        for ch in query.chars() {
            if ch.is_alphanumeric() || ch == '_' {
                current.push(ch);
            } else if !current.is_empty() {
                tokens.push(current);
                current = String::new();
            }
        }
        if !current.is_empty() {
            tokens.push(current);
        }
        tokens
    }

    /// Build FTS MATCH expression: token* for len > 1, exact token for len == 1
    pub fn build_fts_match(query: &str) -> String {
        let tokens = Self::tokenize_query(query);
        if tokens.is_empty() {
            return String::new();
        }
        let parts: Vec<String> = tokens
            .into_iter()
            .map(|t| {
                if t.chars().count() > 1 {
                    format!("{}*", t)
                } else {
                    t
                }
            })
            .collect();
        parts.join(" ")
    }

    /// Execute search with FTS5 and identical bm25 ranking and filters
    pub fn search_items(&self, filter: &SearchFilter) -> Result<Vec<HistoryItem>> {
        let q = filter.query.trim();
        let match_expr = Self::build_fts_match(q);
        let limit = filter.limit.unwrap_or(100) as i64;

        self.with_conn(|conn| {
            if !match_expr.is_empty() {
                // Try FTS5 search
                let mut sql = String::from(
                    "SELECT h.id, h.content, h.type, h.timestamp, h.pinned, h.pin_order, h.use_count, \
                     h.bookmark, h.tags, h.note, h.url_title, h.collection_id, (h.image_data IS NOT NULL) AS has_image \
                     FROM history h \
                     JOIN history_fts ON history_fts.rowid = h.id \
                     WHERE history_fts MATCH ?"
                );

                let mut params: Vec<Box<dyn ToSql>> = vec![Box::new(match_expr)];

                if let Some(ref type_f) = filter.type_filter {
                    let actual_type = match type_f.as_str() {
                        "📝 텍스트" | "텍스트" => Some("TEXT"),
                        "🖼️ 이미지" | "이미지" => Some("IMAGE"),
                        "🔗 링크" | "링크" => Some("LINK"),
                        "💻 코드" | "코드" => Some("CODE"),
                        "🎨 색상" | "색상" => Some("COLOR"),
                        "📎 파일" | "파일" => Some("FILE"),
                        _ => None,
                    };

                    if type_f == "⭐ 북마크" {
                        sql.push_str(" AND h.bookmark = 1");
                    } else if type_f == "📌 고정" {
                        sql.push_str(" AND h.pinned = 1");
                    } else if let Some(t) = actual_type {
                        sql.push_str(" AND h.type = ?");
                        params.push(Box::new(t.to_string()));
                    }
                }

                if let Some(true) = filter.bookmarked {
                    sql.push_str(" AND h.bookmark = 1");
                }

                if let Some(cid) = filter.collection_id {
                    sql.push_str(" AND h.collection_id = ?");
                    params.push(Box::new(cid));
                }

                sql.push_str(" ORDER BY h.pinned DESC, h.pin_order ASC, bm25(history_fts) ASC, h.timestamp DESC, h.id DESC LIMIT ?");
                params.push(Box::new(limit));

                let param_refs: Vec<&dyn ToSql> = params.iter().map(|p| p.as_ref()).collect();

                let mut stmt = conn.prepare(&sql)?;
                let rows = stmt.query_map(&param_refs[..], |row| {
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

                let mut results = Vec::new();
                for r in rows {
                    results.push(r?);
                }
                if !results.is_empty() {
                    return Ok(results);
                }
            }

            // Fallback LIKE search
            let mut sql = String::from(
                "SELECT id, content, type, timestamp, pinned, pin_order, use_count, \
                 bookmark, tags, note, url_title, collection_id, (image_data IS NOT NULL) AS has_image \
                 FROM history WHERE 1=1"
            );
            let mut params: Vec<Box<dyn ToSql>> = Vec::new();

            if !q.is_empty() {
                let like_str = format!("%{}%", q);
                sql.push_str(" AND (content LIKE ? OR tags LIKE ? OR note LIKE ? OR url_title LIKE ?)");
                params.push(Box::new(like_str.clone()));
                params.push(Box::new(like_str.clone()));
                params.push(Box::new(like_str.clone()));
                params.push(Box::new(like_str));
            }

            if let Some(ref type_f) = filter.type_filter {
                let actual_type = match type_f.as_str() {
                    "📝 텍스트" | "텍스트" => Some("TEXT"),
                    "🖼️ 이미지" | "이미지" => Some("IMAGE"),
                    "🔗 링크" | "링크" => Some("LINK"),
                    "💻 코드" | "코드" => Some("CODE"),
                    "🎨 색상" | "색상" => Some("COLOR"),
                    "📎 파일" | "파일" => Some("FILE"),
                    _ => None,
                };
                if type_f == "⭐ 북마크" {
                    sql.push_str(" AND bookmark = 1");
                } else if type_f == "📌 고정" {
                    sql.push_str(" AND pinned = 1");
                } else if let Some(t) = actual_type {
                    sql.push_str(" AND type = ?");
                    params.push(Box::new(t.to_string()));
                }
            }

            if let Some(true) = filter.bookmarked {
                sql.push_str(" AND bookmark = 1");
            }

            if let Some(cid) = filter.collection_id {
                sql.push_str(" AND collection_id = ?");
                params.push(Box::new(cid));
            }

            sql.push_str(" ORDER BY pinned DESC, pin_order ASC, timestamp DESC, id DESC LIMIT ?");
            params.push(Box::new(limit));

            let param_refs: Vec<&dyn ToSql> = params.iter().map(|p| p.as_ref()).collect();
            let mut stmt = conn.prepare(&sql)?;
            let rows = stmt.query_map(&param_refs[..], |row| {
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

            let mut results = Vec::new();
            for r in rows {
                results.push(r?);
            }
            Ok(results)
        })
    }
}
