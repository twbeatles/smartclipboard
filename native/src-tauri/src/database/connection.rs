use std::path::{Path, PathBuf};
use std::sync::Mutex;
use rusqlite::{Connection, OpenFlags};
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

    /// Open in read-write mode (with existing WAL configuration)
    pub fn open_read_write<P: AsRef<Path>>(path: P) -> Result<Self> {
        let p = path.as_ref().to_path_buf();
        let conn = Connection::open(&p)?;
        let _ = conn.query_row("PRAGMA journal_mode=WAL", [], |_| Ok(()));
        let _ = conn.query_row("PRAGMA synchronous=NORMAL", [], |_| Ok(()));

        Ok(Self {
            conn: Mutex::new(conn),
            path: p,
        })
    }

    pub fn with_conn<F, R>(&self, f: F) -> Result<R>
    where
        F: FnOnce(&Connection) -> Result<R>,
    {
        let conn = self.conn.lock().map_err(|e| AppError::Internal(format!("Mutex poisoned: {}", e)))?;
        f(&conn)
    }

    pub fn path(&self) -> &Path {
        &self.path
    }
}
