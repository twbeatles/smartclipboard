use std::sync::atomic::AtomicBool;
use std::sync::Arc;
use crate::database::Database;

pub struct AppState {
    pub db: Arc<Database>,
    pub privacy_mode: AtomicBool,
    pub monitoring_paused: AtomicBool,
}

impl AppState {
    pub fn new(db: Database) -> Self {
        Self {
            db: Arc::new(db),
            privacy_mode: AtomicBool::new(false),
            monitoring_paused: AtomicBool::new(false),
        }
    }
}
