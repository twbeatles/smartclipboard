use crate::clipboard::fetch_title::TitleFetcher;
use crate::clipboard::internal_guard::InternalWriteGuard;
use crate::database::Database;
use crate::vault::VaultManager;
use std::sync::atomic::AtomicBool;
use std::sync::Arc;

#[derive(Clone)]
pub struct AppState {
    pub db: Arc<Database>,
    pub privacy_mode: Arc<AtomicBool>,
    pub monitoring_paused: Arc<AtomicBool>,
    /// Single guard shared by the capture pipeline and every internal
    /// clipboard write (paste-last, palette, vault reveal).
    pub write_guard: Arc<InternalWriteGuard>,
    pub vault: Arc<VaultManager>,
    /// Background page-title fetcher for captured links (G-4).
    pub title_fetcher: Arc<TitleFetcher>,
}

impl AppState {
    pub fn new(db: Database) -> Self {
        let db = Arc::new(db);
        let title_fetcher = Arc::new(TitleFetcher::new(Arc::clone(&db)));
        Self {
            db,
            privacy_mode: Arc::new(AtomicBool::new(false)),
            monitoring_paused: Arc::new(AtomicBool::new(false)),
            write_guard: Arc::new(InternalWriteGuard::new()),
            vault: Arc::new(VaultManager::new()),
            title_fetcher,
        }
    }
}
