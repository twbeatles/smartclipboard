use std::sync::atomic::AtomicBool;
use std::sync::Arc;
use crate::database::Database;

#[derive(Clone)]
pub struct AppState {
    pub db: Arc<Database>,
    pub privacy_mode: Arc<AtomicBool>,
    pub monitoring_paused: Arc<AtomicBool>,
}

impl AppState {
    pub fn new(db: Database) -> Self {
        Self {
            db: Arc::new(db),
            privacy_mode: Arc::new(AtomicBool::new(false)),
            monitoring_paused: Arc::new(AtomicBool::new(false)),
        }
    }
}
