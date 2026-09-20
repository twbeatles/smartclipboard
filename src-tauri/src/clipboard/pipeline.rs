use std::sync::atomic::Ordering;
use std::sync::Arc;
use std::time::Duration;
use tauri::{AppHandle, Emitter};

use super::classifier::classify_text;
use super::copy_rules::{apply_copy_rules, CopyRule};
use super::internal_guard::InternalWriteGuard;
use super::win32::{get_sequence_number, read_clipboard_text};
use crate::app_state::AppState;

const MAX_TEXT_BYTES: usize = 1024 * 1024; // 1 MiB

pub struct ClipboardPipeline {
    app_state: Arc<AppState>,
    write_guard: Arc<InternalWriteGuard>,
}

impl ClipboardPipeline {
    pub fn new(app_state: Arc<AppState>, write_guard: Arc<InternalWriteGuard>) -> Self {
        Self {
            app_state,
            write_guard,
        }
    }

    /// Process clipboard event after 100ms debounce
    pub fn process_event(&self, app_handle: Option<&AppHandle>) {
        // 1. Debounce delay (100ms, identical to Python)
        std::thread::sleep(Duration::from_millis(100));

        // 2. Check privacy and pause flags
        if self.app_state.privacy_mode.load(Ordering::SeqCst) {
            tracing::debug!("Clipboard capture skipped: Privacy mode is active");
            return;
        }
        if self.app_state.monitoring_paused.load(Ordering::SeqCst) {
            tracing::debug!("Clipboard capture skipped: Monitoring is paused");
            return;
        }

        // 3. Priority 1: Check FILE (CF_HDROP)
        if let Some(files) = super::file_reader::read_clipboard_files() {
            let content = crate::database::file_paths::file_content_from_paths(&files);
            if !content.is_empty() {
                let seq = get_sequence_number();
                if self.write_guard.is_internal(seq, &content) {
                    return;
                }
                if let Ok((id, updated)) = self.app_state.db.add_item(&content, None, "FILE") {
                    tracing::info!(
                        "Captured FILE clipboard item: id={}, count={}",
                        id,
                        files.len()
                    );
                    self.enforce_limit();
                    self.emit_history_changed(app_handle, id, "FILE", updated);
                    return;
                }
            }
        }

        // 4. Priority 2: Check IMAGE (CF_DIB)
        if let Some(png_bytes) = super::image_reader::read_clipboard_image() {
            let seq = get_sequence_number();
            if self.write_guard.is_internal_bytes(seq, &png_bytes) {
                tracing::debug!("Clipboard event skipped: Internal image write guard match");
                return;
            }
            let (img_w, img_h) = super::image_reader::png_dimensions(&png_bytes).unwrap_or((0, 0));
            let label = format!("이미지 [{}x{}]", img_w, img_h);
            if let Ok((id, updated)) = self
                .app_state
                .db
                .add_item(&label, Some(&png_bytes), "IMAGE")
            {
                tracing::info!(
                    "Captured IMAGE clipboard item: id={}, bytes={}",
                    id,
                    png_bytes.len()
                );
                self.enforce_limit();
                self.emit_history_changed(app_handle, id, "IMAGE", updated);
                return;
            }
        }

        // 5. Priority 3: Check TEXT (CF_UNICODETEXT)
        let raw_text = match read_clipboard_text() {
            Some(t) if !t.is_empty() => t,
            _ => return,
        };

        if raw_text.len() > MAX_TEXT_BYTES {
            tracing::warn!("Clipboard text exceeds 1 MiB limit, skipped");
            return;
        }

        // 4. Internal copy guard
        let seq = get_sequence_number();
        if self.write_guard.is_internal(seq, &raw_text) {
            tracing::debug!("Clipboard event skipped: Internal write guard match");
            return;
        }

        // 5. Load and apply copy rules
        let rules = self.load_copy_rules();
        let processed_text = apply_copy_rules(raw_text, &rules);
        if processed_text.trim().is_empty() {
            return;
        }

        // 6. Classification
        let type_tag = classify_text(&processed_text);

        // 7. Save to DB
        match self.app_state.db.add_item(&processed_text, None, type_tag) {
            Ok((item_id, updated_existing)) => {
                tracing::info!(
                    "Captured clipboard item: id={}, type={}, updated={}",
                    item_id,
                    type_tag,
                    updated_existing
                );

                self.enforce_limit();
                self.emit_history_changed(app_handle, item_id, type_tag, updated_existing);
                self.maybe_fetch_title(app_handle, item_id, type_tag, &processed_text);
            }
            Err(e) => {
                tracing::error!("Failed to save captured clipboard item: {:?}", e);
            }
        }
    }

    fn emit_history_changed(
        &self,
        app_handle: Option<&AppHandle>,
        id: i64,
        type_tag: &str,
        updated: bool,
    ) {
        if let Some(app) = app_handle {
            #[derive(serde::Serialize, Clone)]
            struct HistoryChangedEvent {
                id: i64,
                r#type: String,
                updated: bool,
            }
            let _ = app.emit(
                "history_changed",
                HistoryChangedEvent {
                    id,
                    r#type: type_tag.to_string(),
                    updated,
                },
            );
        }
    }

    fn enforce_limit(&self) {
        if let Err(e) = self.app_state.db.enforce_history_limit() {
            tracing::warn!("Failed to enforce history limit: {:?}", e);
        }
    }

    fn title_fetch_enabled(&self) -> bool {
        self.app_state
            .db
            .get_setting("title_fetch_enabled")
            .ok()
            .flatten()
            .map(|v| v.trim() != "0")
            .unwrap_or(true)
    }

    /// Queue a background page-title fetch for captured text containing a
    /// URL (automatic `fetch_title`, mirroring the Python action manager).
    /// The fetch never blocks capture; results arrive via `title_fetch_result`.
    fn maybe_fetch_title(
        &self,
        app_handle: Option<&AppHandle>,
        item_id: i64,
        type_tag: &str,
        text: &str,
    ) {
        if type_tag != "TEXT" && type_tag != "LINK" {
            return;
        }
        if !self.title_fetch_enabled() {
            return;
        }
        let url = match super::fetch_title::extract_first_url(text) {
            Some(u) => u,
            None => return,
        };
        let fetcher = Arc::clone(&self.app_state.title_fetcher);
        let app = app_handle.cloned();
        fetcher.fetch_async(&url, item_id, move |event| {
            if let Some(app) = app.as_ref() {
                #[derive(serde::Serialize, Clone)]
                struct TitleFetchEvent {
                    item_ids: Vec<i64>,
                    url: String,
                    title: Option<String>,
                    message: String,
                }
                let _ = app.emit(
                    "title_fetch_result",
                    TitleFetchEvent {
                        item_ids: event.item_ids,
                        url: event.url,
                        title: event.title,
                        message: event.message,
                    },
                );
            }
        });
    }

    fn load_copy_rules(&self) -> Vec<CopyRule> {
        self.app_state
            .db
            .with_conn(|conn| {
                let mut stmt = conn.prepare(
                    "SELECT id, name, pattern, action, replacement, enabled, priority \
                     FROM copy_rules WHERE enabled = 1 ORDER BY priority ASC",
                )?;
                let rows = stmt.query_map([], |row| {
                    Ok(CopyRule {
                        id: row.get(0)?,
                        name: row.get(1)?,
                        pattern: row.get(2)?,
                        action: row.get(3)?,
                        replacement: row.get::<_, Option<String>>(4)?.unwrap_or_default(),
                        enabled: row.get::<_, i64>(5)? == 1,
                        priority: row.get(6)?,
                    })
                })?;
                let mut rules = Vec::new();
                for r in rows {
                    rules.push(r?);
                }
                Ok(rules)
            })
            .unwrap_or_default()
    }
}
