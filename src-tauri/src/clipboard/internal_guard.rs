use std::sync::Mutex;
use std::time::{Duration, Instant};

#[derive(Debug, Clone)]
struct GuardEntry {
    sequence: u32,
    content_hash: u64,
    expires_at: Instant,
}

pub struct InternalWriteGuard {
    state: Mutex<Option<GuardEntry>>,
}

impl Default for InternalWriteGuard {
    fn default() -> Self {
        Self::new()
    }
}

impl InternalWriteGuard {
    pub fn new() -> Self {
        Self {
            state: Mutex::new(None),
        }
    }

    fn hash_content(content: &str) -> u64 {
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};
        let mut hasher = DefaultHasher::new();
        content.hash(&mut hasher);
        hasher.finish()
    }

    /// Mark that the application itself has written text to the clipboard
    pub fn mark_internal(&self, sequence: u32, content: &str) {
        if let Ok(mut lock) = self.state.lock() {
            *lock = Some(GuardEntry {
                sequence,
                content_hash: Self::hash_content(content),
                expires_at: Instant::now() + Duration::from_secs(3),
            });
        }
    }

    /// Returns true if this clipboard update event was caused by the app itself
    pub fn is_internal(&self, sequence: u32, content: &str) -> bool {
        if let Ok(mut lock) = self.state.lock() {
            if let Some(entry) = lock.as_ref() {
                if Instant::now() <= entry.expires_at {
                    if entry.sequence != 0 && entry.sequence == sequence {
                        *lock = None;
                        return true;
                    }
                    if entry.content_hash == Self::hash_content(content) {
                        *lock = None;
                        return true;
                    }
                } else {
                    *lock = None;
                }
            }
        }
        false
    }
}
