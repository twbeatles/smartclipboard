use rusqlite::{Connection, OpenFlags};
use std::path::{Path, PathBuf};
use std::sync::Mutex;

use crate::errors::{AppError, Result};

pub struct Database {
    conn: Mutex<Connection>,
    path: PathBuf,
}

impl Database {
    /// Open SQLite database in read-only mode for safe backward compatibility (Milestone C)
    pub fn open_read_only<P: AsRef<Path>>(path: P) -> Result<Self> {
        let p = path.as_ref().to_path_buf();
        if !p.exists() {
            return Err(AppError::NotFound(format!("Database file not found: {:?}", p)));
        }

        let flags = OpenFlags::SQLITE_OPEN_READ_ONLY
            | OpenFlags::SQLITE_OPEN_URI
            | OpenFlags::SQLITE_OPEN_NO_MUTEX;

        let conn = Connection::open_with_flags(&p, flags)?;
        let _ = conn.query_row("PRAGMA synchronous=NORMAL", [], |_| Ok(()));

        Ok(Self {
            conn: Mutex::new(conn),
            path: p,
        })
    }

    /// Open in read-write mode (with existing WAL configuration) and ensure schema exists
    pub fn open_read_write<P: AsRef<Path>>(path: P) -> Result<Self> {
        let p = path.as_ref().to_path_buf();
        let conn = Connection::open(&p)?;
        let _ = conn.query_row("PRAGMA journal_mode=WAL", [], |_| Ok(()));
        let _ = conn.query_row("PRAGMA synchronous=NORMAL", [], |_| Ok(()));

        let db = Self {
            conn: Mutex::new(conn),
            path: p,
        };
        db.init_schema()?;
        Ok(db)
    }

    pub fn init_schema(&self) -> Result<()> {
        self.with_conn(|conn| {
            conn.execute_batch(
                "CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT,
                    image_data BLOB,
                    type TEXT,
                    timestamp TEXT,
                    tags TEXT,
                    note TEXT,
                    bookmark INTEGER DEFAULT 0,
                    collection_id INTEGER,
                    pinned INTEGER DEFAULT 0,
                    pin_order INTEGER DEFAULT 0,
                    use_count INTEGER DEFAULT 0,
                    file_path TEXT DEFAULT '',
                    file_signature TEXT DEFAULT '',
                    url_title TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS collections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    icon TEXT,
                    color TEXT,
                    created_at TEXT
                );

                CREATE TABLE IF NOT EXISTS snippets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    shortcut TEXT,
                    category TEXT DEFAULT '일반',
                    created_at TEXT
                );

                CREATE TABLE IF NOT EXISTS copy_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    pattern TEXT NOT NULL,
                    action TEXT NOT NULL,
                    replacement TEXT,
                    enabled INTEGER DEFAULT 1,
                    priority INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS deleted_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_id INTEGER,
                    content TEXT,
                    image_data BLOB,
                    type TEXT,
                    original_timestamp TEXT,
                    tags TEXT,
                    note TEXT,
                    bookmark INTEGER DEFAULT 0,
                    collection_id INTEGER,
                    pinned INTEGER DEFAULT 0,
                    pin_order INTEGER DEFAULT 0,
                    use_count INTEGER DEFAULT 0,
                    url_title TEXT,
                    deleted_at TEXT,
                    expires_at TEXT
                );

                CREATE TABLE IF NOT EXISTS secure_vault (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    encrypted_content BLOB NOT NULL,
                    label TEXT,
                    created_at TEXT
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS history_fts USING fts5(
                    content, tags, note, url_title,
                    tokenize = 'unicode61'
                );

                CREATE TRIGGER IF NOT EXISTS history_ai AFTER INSERT ON history BEGIN
                    INSERT INTO history_fts(rowid, content, tags, note, url_title)
                    VALUES (new.id, new.content, new.tags, new.note, new.url_title);
                END;

                CREATE TRIGGER IF NOT EXISTS history_ad AFTER DELETE ON history BEGIN
                    INSERT INTO history_fts(history_fts, rowid, content, tags, note, url_title)
                    VALUES ('delete', old.id, old.content, old.tags, old.note, old.url_title);
                END;

                CREATE TRIGGER IF NOT EXISTS history_au AFTER UPDATE ON history BEGIN
                    INSERT INTO history_fts(history_fts, rowid, content, tags, note, url_title)
                    VALUES ('delete', old.id, old.content, old.tags, old.note, old.url_title);
                    INSERT INTO history_fts(rowid, content, tags, note, url_title)
                    VALUES (new.id, new.content, new.tags, new.note, new.url_title);
                END;"
            )?;
            Ok(())
        })
    }

    pub fn with_conn<F, R>(&self, f: F) -> Result<R>
    where
        F: FnOnce(&Connection) -> Result<R>,
    {
        let conn = self
            .conn
            .lock()
            .map_err(|e| AppError::Internal(format!("Mutex poisoned: {}", e)))?;
        f(&conn)
    }

    pub fn path(&self) -> &Path {
        &self.path
    }
}
