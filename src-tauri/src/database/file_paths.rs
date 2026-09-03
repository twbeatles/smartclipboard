use sha2::{Digest, Sha256};
use std::path::Path;

/// Normalize a local file path (handles Windows slashes, trimming, standardizing)
pub fn normalize_local_file_path(raw: &str) -> String {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return String::new();
    }

    // Strip "file://" or "file:///" if present
    let s = if let Some(stripped) = trimmed.strip_prefix("file:///") {
        stripped
    } else if let Some(stripped) = trimmed.strip_prefix("file://") {
        stripped
    } else {
        trimmed
    };

    let p = Path::new(s);
    let mut normalized = p.to_string_lossy().replace('/', "\\");

    // Remove trailing slash/backslash if not root
    if normalized.len() > 3 && (normalized.ends_with('\\') || normalized.ends_with('/')) {
        normalized.pop();
    }
    normalized
}

pub fn normalize_local_file_paths(paths: &[String]) -> Vec<String> {
    let mut normalized_paths = Vec::new();
    let mut seen = std::collections::HashSet::new();

    for p in paths {
        let norm = normalize_local_file_path(p);
        if norm.is_empty() {
            continue;
        }
        let lower = norm.to_lowercase();
        if seen.contains(&lower) {
            continue;
        }
        seen.insert(lower);
        normalized_paths.push(norm);
    }
    normalized_paths
}

pub fn file_paths_from_content(content: &str) -> Vec<String> {
    let lines: Vec<String> = content.lines().map(|s| s.to_string()).collect();
    normalize_local_file_paths(&lines)
}

pub fn file_content_from_paths(paths: &[String]) -> String {
    normalize_local_file_paths(paths).join("\n")
}

/// Computes deterministic SHA-256 signature matching Python's file_signature_from_paths
pub fn file_signature_from_paths(paths: &[String]) -> String {
    let normalized = normalize_local_file_paths(paths);
    if normalized.is_empty() {
        return String::new();
    }

    let mut lowercase_paths: Vec<String> = normalized.into_iter().map(|p| p.to_lowercase()).collect();
    lowercase_paths.sort();

    let source = lowercase_paths.join("\n");
    let mut hasher = Sha256::new();
    hasher.update(source.as_bytes());
    format!("{:x}", hasher.finalize())
}
