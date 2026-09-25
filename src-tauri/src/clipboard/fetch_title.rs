//! Remote page-title fetch for captured links (G-4).
//!
//! Mirrors `legacy/python/smartclipboard_core/automation/fetch_title.py`,
//! `network_guard.py` and the title-cache portion of `manager.py`:
//! first-URL extraction, SSRF preflight (scheme/host/DNS scoping) before
//! every request including redirects, manual redirect chain (max 5),
//! HTML-only capped streaming reads (1 MiB), 256-entry/24h title cache,
//! in-flight URL de-duplication and at most 4 concurrent fetch threads.

use regex::Regex;
use std::collections::{HashMap, VecDeque};
use std::io::Read;
use std::net::{SocketAddr, ToSocketAddrs};
use std::sync::{Arc, Condvar, Mutex};
use std::time::{Duration, Instant};

use crate::database::Database;

pub const TITLE_FETCH_MAX_BYTES: usize = 1024 * 1024;
pub const TITLE_FETCH_MAX_THREADS: usize = 4;
pub const TITLE_FETCH_MAX_REDIRECTS: u32 = 5;
pub const TITLE_CACHE_MAX_ENTRIES: usize = 256;
pub const TITLE_CACHE_TTL: Duration = Duration::from_secs(24 * 60 * 60);
pub const URL_TRAILING_PUNCTUATION: &[char] = &['.', ',', '!', '?', ':', ';'];
pub const BLOCKED_TITLE_HOSTS: &[&str] = &[
    "localhost",
    "metadata.google.internal",
    "metadata.google.internal.",
];
const FETCH_USER_AGENT: &str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36";
const CONNECT_TIMEOUT: Duration = Duration::from_secs(3);
const READ_TIMEOUT: Duration = Duration::from_secs(5);

static RE_FIRST_URL: std::sync::LazyLock<Regex> = std::sync::LazyLock::new(|| {
    Regex::new("https?://[^\\s<>'\"\\]\\)]+").expect("first-url regex must compile")
});

/// Normalize an extracted URL the way the Python implementation does.
pub fn normalize_extracted_url(url: &str) -> String {
    url.trim_end_matches(URL_TRAILING_PUNCTUATION).to_string()
}

/// Extract the first URL embedded in clipboard text, if any.
pub fn extract_first_url(text: &str) -> Option<String> {
    if text.is_empty() {
        return None;
    }
    RE_FIRST_URL
        .find(text)
        .map(|m| normalize_extracted_url(m.as_str()))
        .filter(|u| !u.is_empty())
}

/// Global-routability check mirroring Python ipaddress.is_global,
/// using only long-stable octets/segments accessors.
fn is_globally_routable(ip: std::net::IpAddr) -> bool {
    match ip {
        std::net::IpAddr::V4(v4) => {
            let o = v4.octets();
            if o == [0, 0, 0, 0] {
                return false;
            }
            if o[0] == 127 {
                return false;
            }
            if o[0] == 10 {
                return false;
            }
            if o[0] == 172 && (16..32).contains(&o[1]) {
                return false;
            }
            if o[0] == 192 && o[1] == 168 {
                return false;
            }
            if o[0] == 169 && o[1] == 254 {
                return false;
            }
            if o[0] >= 224 {
                return false;
            }
            if o == [255, 255, 255, 255] {
                return false;
            }
            if o[0] == 192 && o[1] == 0 && o[2] == 2 {
                return false;
            }
            if o[0] == 198 && o[1] == 51 && o[2] == 100 {
                return false;
            }
            if o[0] == 203 && o[1] == 0 && o[2] == 113 {
                return false;
            }
            if o[0] == 192 && o[1] == 0 && o[2] == 0 {
                return false;
            }
            if o[0] == 198 && (18..20).contains(&o[1]) {
                return false;
            }
            if o[0] == 192 && o[1] == 88 && o[2] == 99 {
                return false;
            }
            if o[0] == 100 && (64..128).contains(&o[1]) {
                return false;
            }
            true
        }
        std::net::IpAddr::V6(v6) => {
            let s = v6.segments();
            if s == [0, 0, 0, 0, 0, 0, 0, 0] {
                return false;
            }
            if s == [0, 0, 0, 0, 0, 0, 0, 1] {
                return false;
            }
            if s[0] & 0xffc0 == 0xfe80 {
                return false;
            }
            if s[0] & 0xfe00 == 0xfc00 {
                return false;
            }
            if s[0] & 0xff00 == 0xff00 {
                return false;
            }
            if s[0] == 0x2001 && s[1] == 0x0db8 {
                return false;
            }
            if s[0] == 0x0064 && s[1] == 0xff9b {
                return false;
            }
            true
        }
    }
}

/// SSRF preflight: only http/https, known non-metadata host, and every
/// resolved address must be globally routable. `Ok(())` means safe.
pub fn validate_title_fetch_url(url: &str) -> Result<(), String> {
    let parsed = url::Url::parse(url).map_err(|_| "invalid url".to_string())?;
    let scheme = parsed.scheme();
    if scheme != "http" && scheme != "https" {
        return Err("invalid scheme".to_string());
    }
    let hostname = parsed.host_str().unwrap_or("").trim().to_lowercase();
    if hostname.is_empty() {
        return Err("missing hostname".to_string());
    }
    // `Url` already strips a trailing dot; check both forms for parity.
    let bare = hostname.strip_suffix('.').unwrap_or(&hostname);
    if BLOCKED_TITLE_HOSTS.contains(&bare) || BLOCKED_TITLE_HOSTS.contains(&hostname.as_str()) {
        return Err(format!("blocked metadata hostname: {}", bare));
    }
    let port = parsed
        .port_or_known_default()
        .unwrap_or(if scheme == "https" { 443 } else { 80 });
    // Literal IPs resolve without DNS; names go through the system resolver.
    // Python documents DNS rebinding between check and use as residual risk;
    // the same caveat applies here.
    let addrs: Vec<SocketAddr> = (bare, port)
        .to_socket_addrs()
        .map_err(|e| format!("dns resolution failed: {}", e))?
        .collect();
    if addrs.is_empty() {
        return Err("dns resolution returned no addresses".to_string());
    }
    for addr in &addrs {
        if !is_globally_routable(addr.ip()) {
            return Err(format!("blocked non-global address: {}", addr.ip()));
        }
    }
    Ok(())
}

pub fn is_blocked_title_fetch_reason(reason: &str) -> bool {
    reason.starts_with("blocked")
}

/// Resolve a `Location` value against the current request URL (RFC 3986 join).
pub fn resolve_redirect(current_url: &str, location: &str) -> Result<String, String> {
    let location = location.trim();
    if location.is_empty() {
        return Err("redirect missing location".to_string());
    }
    let base = url::Url::parse(current_url).map_err(|_| "invalid url".to_string())?;
    let joined = base
        .join(location)
        .map_err(|_| "redirect missing location".to_string())?;
    Ok(normalize_extracted_url(joined.as_str()))
}

fn agent() -> ureq::Agent {
    ureq::AgentBuilder::new()
        .timeout_connect(CONNECT_TIMEOUT)
        .timeout_read(READ_TIMEOUT)
        .redirects(0)
        .build()
}

fn decode_body(bytes: &[u8], content_type: &str) -> String {
    let charset = content_type
        .split(';')
        .skip(1)
        .find_map(|part| {
            let part = part.trim();
            part.strip_prefix("charset=")
                .or_else(|| part.strip_prefix("Charset="))
                .map(|v| v.trim().trim_matches('"').to_lowercase())
        })
        .unwrap_or_default();
    if charset == "utf-8" || charset == "utf8" || charset == "ascii" || charset == "us-ascii" {
        return String::from_utf8_lossy(bytes).into_owned();
    }
    // No usable charset label: windows-1252 superset mapping (covers the
    // latin-1 fallback `requests` applies to header-less text pages).
    let mut out = String::with_capacity(bytes.len());
    for &b in bytes {
        out.push(match b {
            0x80 => '€',
            0x82 => '‚',
            0x83 => 'ƒ',
            0x84 => '„',
            0x85 => '…',
            0x86 => '†',
            0x87 => '‡',
            0x88 => 'ˆ',
            0x89 => '‰',
            0x8A => 'Š',
            0x8B => '‹',
            0x8C => 'Œ',
            0x8E => 'Ž',
            0x91 => '‘',
            0x92 => '’',
            0x93 => '“',
            0x94 => '”',
            0x95 => '•',
            0x96 => '–',
            0x97 => '—',
            0x98 => '˜',
            0x99 => '™',
            0x9A => 'š',
            0x9B => '›',
            0x9C => 'œ',
            0x9E => 'ž',
            0x9F => 'Ÿ',
            _ => b as char,
        });
    }
    out
}

fn decode_entity(entity: &str) -> Option<char> {
    match entity {
        "amp" => Some('&'),
        "lt" => Some('<'),
        "gt" => Some('>'),
        "quot" => Some('"'),
        "apos" => Some('\''),
        "nbsp" => Some('\u{a0}'),
        _ => {
            if let Some(num) = entity.strip_prefix('#') {
                let code =
                    if let Some(hex) = num.strip_prefix('x').or_else(|| num.strip_prefix('X')) {
                        u32::from_str_radix(hex, 16).ok()
                    } else {
                        num.parse::<u32>().ok()
                    }?;
                char::from_u32(code)
            } else {
                None
            }
        }
    }
}

fn decode_entities(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    let mut rest = text;
    while let Some(start) = rest.find('&') {
        out.push_str(&rest[..start]);
        let after = &rest[start + 1..];
        if let Some(end) = after.find(';').filter(|&e| e > 0 && e <= 32) {
            let entity = &after[..end];
            if let Some(ch) = decode_entity(entity) {
                out.push(ch);
                rest = &after[end + 1..];
                continue;
            }
        }
        out.push('&');
        rest = after;
    }
    out.push_str(rest);
    out
}

fn strip_tags(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    let mut in_tag = false;
    for ch in text.chars() {
        match ch {
            '<' => in_tag = true,
            '>' => in_tag = false,
            _ if !in_tag => out.push(ch),
            _ => {}
        }
    }
    out
}

/// Extract `<title>` text from an HTML document (case-insensitive).
/// Returns `None` for missing/empty titles.
pub fn extract_html_title(html: &str) -> Option<String> {
    let lower = html.to_lowercase();
    let start_tag = lower.find("<title")?;
    let after_open = lower[start_tag..].find('>')?;
    let content_start = start_tag + after_open + 1;
    let end_rel = lower[content_start..].find("</title")?;
    let raw = html[content_start..content_start + end_rel].trim();
    if raw.is_empty() {
        return None;
    }
    let title = decode_entities(&strip_tags(raw)).trim().to_string();
    if title.is_empty() {
        None
    } else {
        Some(title)
    }
}

#[derive(Debug, Clone)]
pub struct FetchOutcome {
    pub title: Option<String>,
    pub final_url: String,
    pub error: Option<String>,
}

fn outcome_err(_url: &str, final_url: &str, error: String) -> FetchOutcome {
    FetchOutcome {
        title: None,
        final_url: final_url.to_string(),
        error: Some(error),
    }
}

/// Perform the HTTP fetch. The caller is responsible for pre-validating
/// `start_url`; every redirect hop is re-validated here, mirroring the
/// Python redirect loop.
pub fn fetch_http_title(start_url: &str) -> FetchOutcome {
    fetch_http_title_validated(start_url, validate_title_fetch_url)
}

/// Same as fetch_http_title but with an injectable SSRF validator.
/// Production paths always pass validate_title_fetch_url; the parameter
/// exists so tests can exercise redirect and parsing logic against
/// loopback servers that the real validator (correctly) rejects.
pub fn fetch_http_title_validated(
    start_url: &str,
    validate: fn(&str) -> Result<(), String>,
) -> FetchOutcome {
    let agent = agent();
    let mut current_url = start_url.to_string();
    for _ in 0..=TITLE_FETCH_MAX_REDIRECTS {
        if let Err(reason) = validate(&current_url) {
            tracing::info!("Title fetch blocked for {}: {}", current_url, reason);
            return outcome_err(start_url, &current_url, reason);
        }
        let response = match agent
            .get(&current_url)
            .set("User-Agent", FETCH_USER_AGENT)
            .call()
        {
            Ok(resp) => resp,
            Err(ureq::Error::Status(code, resp)) => {
                // 3xx with redirects(0) arrives here on some ureq paths;
                // handle it as a redirect below, otherwise report the status.
                if (300..400).contains(&code) {
                    resp
                } else {
                    return outcome_err(start_url, &current_url, format!("http status {}", code));
                }
            }
            Err(e) => {
                return outcome_err(start_url, &current_url, e.to_string());
            }
        };

        let status = response.status();
        if (300..400).contains(&status) {
            let location = response.header("location").unwrap_or("").to_string();
            match resolve_redirect(&current_url, &location) {
                Ok(next) => {
                    current_url = next;
                    continue;
                }
                Err(reason) => return outcome_err(start_url, &current_url, reason),
            }
        }
        if !(200..300).contains(&status) {
            return outcome_err(start_url, &current_url, format!("http status {}", status));
        }

        let content_type = response.header("content-type").unwrap_or("").to_lowercase();
        if !content_type.is_empty() && !content_type.contains("html") {
            return outcome_err(
                start_url,
                &current_url,
                format!("unsupported content type: {}", content_type),
            );
        }
        let mut limited = response.into_reader().take(TITLE_FETCH_MAX_BYTES as u64);
        let mut buf = Vec::with_capacity(65536);
        if let Err(e) = limited.read_to_end(&mut buf) {
            return outcome_err(start_url, &current_url, e.to_string());
        }
        let html = decode_body(&buf, &content_type);
        return FetchOutcome {
            title: extract_html_title(&html),
            final_url: current_url,
            error: None,
        };
    }
    outcome_err(start_url, &current_url, "too many redirects".to_string())
}

/// Validate, then fetch. Error strings match the Python contract
/// (`blocked ...` prefix marks policy blocks for UI messaging).
pub fn fetch_title_for_url(url: &str) -> FetchOutcome {
    if let Err(reason) = validate_title_fetch_url(url) {
        return outcome_err(url, url, reason);
    }
    fetch_http_title(url)
}

/// Bounded LRU title cache with TTL, mirroring the Python OrderedDict cache
/// (256 entries / 24h TTL).
pub struct TitleCache {
    max_entries: usize,
    ttl: Duration,
    map: HashMap<String, (String, Instant)>,
    order: VecDeque<String>,
}

impl TitleCache {
    pub fn new(max_entries: usize, ttl: Duration) -> Self {
        Self {
            max_entries,
            ttl,
            map: HashMap::new(),
            order: VecDeque::new(),
        }
    }

    fn evict_expired_locked(&mut self, now: Instant) {
        let ttl = self.ttl;
        self.map.retain(|_, (_, at)| now.duration_since(*at) <= ttl);
        let map = &self.map;
        self.order.retain(|k| map.contains_key(k));
    }

    pub fn get(&mut self, url: &str) -> Option<String> {
        let now = Instant::now();
        self.evict_expired_locked(now);
        let entry = self.map.get(url)?;
        let (title, _) = entry.clone();
        self.order.retain(|k| k != url);
        self.order.push_back(url.to_string());
        Some(title)
    }

    pub fn set(&mut self, url: &str, title: &str) {
        let now = Instant::now();
        self.evict_expired_locked(now);
        self.map.insert(url.to_string(), (title.to_string(), now));
        self.order.retain(|k| k != url);
        self.order.push_back(url.to_string());
        while self.map.len() > self.max_entries.max(1) {
            if let Some(old) = self.order.pop_front() {
                self.map.remove(&old);
            } else {
                break;
            }
        }
    }

    #[cfg(test)]
    #[cfg(test)]
    #[allow(clippy::len_without_is_empty)]
    pub fn len(&self) -> usize {
        self.map.len()
    }
}

/// Result broadcast for one completed fetch (possibly shared by several rows).
#[derive(Debug, Clone)]
pub struct TitleEvent {
    pub item_ids: Vec<i64>,
    pub url: String,
    pub title: Option<String>,
    pub message: String,
}

struct FetcherInner {
    db: Arc<Database>,
    cache: Mutex<TitleCache>,
    inflight: Mutex<HashMap<String, Vec<i64>>>,
    running: Mutex<usize>,
    slot_free: Condvar,
}

/// Background title fetcher: cache-first, in-flight URL de-duplication,
/// at most 4 concurrent fetch threads. Holds the DB handle to write back
/// `url_title` with a stale-URL recheck, like the Python manager.
#[derive(Clone)]
pub struct TitleFetcher {
    inner: Arc<FetcherInner>,
}

impl TitleFetcher {
    pub fn new(db: Arc<Database>) -> Self {
        Self {
            inner: Arc::new(FetcherInner {
                db,
                cache: Mutex::new(TitleCache::new(TITLE_CACHE_MAX_ENTRIES, TITLE_CACHE_TTL)),
                inflight: Mutex::new(HashMap::new()),
                running: Mutex::new(0),
                slot_free: Condvar::new(),
            }),
        }
    }

    fn cached_title(&self, url: &str) -> Option<String> {
        self.inner.cache.lock().ok()?.get(url)
    }

    fn store_title(&self, url: &str, title: &str) {
        if let Ok(mut cache) = self.inner.cache.lock() {
            cache.set(url, title);
        }
    }

    fn acquire_slot(&self) {
        if let Ok(mut running) = self.inner.running.lock() {
            while *running >= TITLE_FETCH_MAX_THREADS {
                running = self
                    .inner
                    .slot_free
                    .wait(running)
                    .unwrap_or_else(|e| e.into_inner());
            }
            *running += 1;
        }
    }

    fn release_slot(&self) {
        if let Ok(mut running) = self.inner.running.lock() {
            *running = running.saturating_sub(1);
        }
        self.inner.slot_free.notify_one();
    }

    /// Queue a title fetch for a history row. `on_done` fires once per
    /// completed fetch (possibly covering several rows for one URL).
    pub fn fetch_async<F>(&self, url: &str, item_id: i64, on_done: F)
    where
        F: Fn(TitleEvent) + Send + Sync + 'static,
    {
        let url = url.to_string();
        if let Err(reason) = validate_title_fetch_url(&url) {
            tracing::info!("Title fetch precheck rejected {}: {}", url, reason);
            let message = if is_blocked_title_fetch_reason(&reason) {
                "보안상 로컬/사설 주소의 제목 가져오기는 건너뜁니다.".to_string()
            } else {
                "URL 제목을 가져오기 전에 주소 검증에 실패했습니다.".to_string()
            };
            on_done(TitleEvent {
                item_ids: vec![item_id],
                url,
                title: None,
                message,
            });
            return;
        }
        if let Some(title) = self.cached_title(&url) {
            let updated = self
                .inner
                .db
                .update_url_title_if_current(item_id, &url, &title)
                .unwrap_or(false);
            let message = if updated {
                String::new()
            } else {
                "URL 제목을 저장하지 못했습니다.".to_string()
            };
            on_done(TitleEvent {
                item_ids: vec![item_id],
                url: url.clone(),
                title: Some(title),
                message,
            });
            return;
        }
        {
            let mut inflight = match self.inner.inflight.lock() {
                Ok(g) => g,
                Err(_) => return,
            };
            if let Some(waiters) = inflight.get_mut(&url) {
                waiters.push(item_id);
                return;
            }
            inflight.insert(url.clone(), vec![item_id]);
        }
        let worker = self.clone();
        std::thread::spawn(move || {
            worker.acquire_slot();
            let outcome = fetch_http_title(&url);
            worker.release_slot();
            let waiters = worker
                .inner
                .inflight
                .lock()
                .ok()
                .and_then(|mut g| g.remove(&url))
                .unwrap_or_default();
            let mut updated_any = false;
            if let Some(title) = outcome.title.as_deref() {
                worker.store_title(&url, title);
                for id in &waiters {
                    if worker
                        .inner
                        .db
                        .update_url_title_if_current(*id, &url, title)
                        .unwrap_or(false)
                    {
                        updated_any = true;
                    }
                }
            }
            let message = match (&outcome.title, updated_any) {
                (Some(_), true) => String::new(),
                (Some(_), false) => "URL 제목을 저장하지 못했습니다.".to_string(),
                (None, _) => outcome
                    .error
                    .unwrap_or_else(|| "URL 제목을 가져오지 못했습니다.".to_string()),
            };
            on_done(TitleEvent {
                item_ids: waiters,
                url,
                title: outcome.title,
                message,
            });
        });
    }
}
