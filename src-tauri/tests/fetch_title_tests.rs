//! G-4 regression tests: URL title fetch policy, parsing, cache and
//! stale-write-back guard. All hermetic except a loopback-local HTTP
//! server built on std TcpListener (no internet, no DNS).

use std::fs;
use std::io::{Read, Write};
use std::net::TcpListener;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use std::time::Duration;

use smartclipboard_native_lib::clipboard::fetch_title::{
    extract_first_url, extract_html_title, fetch_http_title_validated, fetch_title_for_url,
    is_blocked_title_fetch_reason, normalize_extracted_url, resolve_redirect,
    validate_title_fetch_url, TitleCache, TitleEvent, TitleFetcher, TITLE_FETCH_MAX_BYTES,
};

/// Permissive validator for loopback test servers only. Production paths
/// always use the real validator; this stands in for DNS/global-IP policy
/// so redirect and parsing logic can be exercised hermetically.
fn allow_loopback_for_tests(url: &str) -> Result<(), String> {
    let _ = url;
    Ok(())
}
use smartclipboard_native_lib::database::Database;
use tempfile::NamedTempFile;

fn create_temp_db_copy() -> (NamedTempFile, Database) {
    let fixture_path = PathBuf::from("fixtures/synthetic_test_v6.db");
    assert!(fixture_path.exists());
    let temp = NamedTempFile::new().expect("create temp file");
    fs::copy(&fixture_path, temp.path()).expect("copy fixture db");
    let db = Database::open_read_write(temp.path()).expect("open read write");
    (temp, db)
}

#[test]
fn test_extract_first_url_cases() {
    assert_eq!(extract_first_url(""), None);
    assert_eq!(
        extract_first_url("see https://example.com/page?a=1 here"),
        Some("https://example.com/page?a=1".to_string())
    );
    assert_eq!(
        extract_first_url("first http://a.example/x second https://b.example/y"),
        Some("http://a.example/x".to_string())
    );
    // Trailing sentence punctuation is stripped (Python parity).
    assert_eq!(
        extract_first_url("link: https://example.com/news, read it."),
        Some("https://example.com/news".to_string())
    );
    assert_eq!(
        extract_first_url("(https://example.com/in-parens)"),
        Some("https://example.com/in-parens".to_string())
    );
    assert_eq!(extract_first_url("no link here, ftp://example.com/x"), None);
}

#[test]
fn test_normalize_extracted_url() {
    assert_eq!(
        normalize_extracted_url("https://example.com/a..."),
        "https://example.com/a"
    );
    assert_eq!(
        normalize_extracted_url("https://example.com/a"),
        "https://example.com/a"
    );
}

#[test]
fn test_validate_blocks_non_global_targets() {
    assert_eq!(
        validate_title_fetch_url("ftp://example.com/x"),
        Err("invalid scheme".to_string())
    );
    // The url crate reads "http:///no-host" as host "no-host", which then
    // fails closed at DNS resolution. Either way it must never validate.
    assert!(validate_title_fetch_url("http:///no-host").is_err());
    assert!(validate_title_fetch_url("http://localhost/x").is_err());
    assert!(validate_title_fetch_url("http://LOCALHOST:8080/x").is_err());
    assert!(validate_title_fetch_url("http://127.0.0.1/").is_err());
    assert!(validate_title_fetch_url("http://10.1.2.3/").is_err());
    assert!(validate_title_fetch_url("http://192.168.0.1/").is_err());
    assert!(validate_title_fetch_url("http://172.16.5.4/").is_err());
    assert!(validate_title_fetch_url("http://169.254.169.254/").is_err());
    assert!(validate_title_fetch_url("http://[::1]/").is_err());
    assert!(validate_title_fetch_url("http://[fe80::1]/").is_err());
    assert!(validate_title_fetch_url("http://[fc00::1]/").is_err());
    assert!(validate_title_fetch_url("http://[ff02::1]/").is_err());
    assert!(validate_title_fetch_url("http://[2001:db8::1]/").is_err());
    assert!(validate_title_fetch_url("http://[64:ff9b::808:808]/").is_err());
    assert!(validate_title_fetch_url("http://metadata.google.internal/").is_err());
    assert!(validate_title_fetch_url("http://metadata.google.internal./").is_err());
    assert!(validate_title_fetch_url("http://224.0.0.1/").is_err());
}

#[test]
fn test_validate_accepts_global_literal_without_dns() {
    // Documentation TEST-NET-1 is reserved, not global.
    assert!(validate_title_fetch_url("http://192.0.2.1/").is_err());
    // example.com's public address needs no DNS when written literally.
    assert_eq!(validate_title_fetch_url("http://93.184.216.34/"), Ok(()));
    // A real global IPv6 address must stay allowed.
    assert_eq!(
        validate_title_fetch_url("http://[2001:4860:4860::8888]/"),
        Ok(())
    );
}

#[test]
fn test_blocked_reason_prefix() {
    assert!(is_blocked_title_fetch_reason(
        "blocked metadata hostname: x"
    ));
    assert!(!is_blocked_title_fetch_reason("dns resolution failed: x"));
    assert!(!is_blocked_title_fetch_reason("http status 404"));
}

#[test]
fn test_resolve_redirect_forms() {
    assert_eq!(
        resolve_redirect("http://a.example/x", "https://b.example/y"),
        Ok("https://b.example/y".to_string())
    );
    assert_eq!(
        resolve_redirect("http://a.example/x/y", "/z"),
        Ok("http://a.example/x/y".replace("/x/y", "/z"))
    );
    assert!(resolve_redirect("http://a.example/x", "").is_err());
    assert!(resolve_redirect("http://a.example/x", "   ").is_err());
}

#[test]
fn test_extract_html_title_cases() {
    assert_eq!(
        extract_html_title("<html><head><title>Hello World</title></head></html>"),
        Some("Hello World".to_string())
    );
    assert_eq!(
        extract_html_title("<TITLE class=\"t\">  Spaced  </TITLE>"),
        Some("Spaced".to_string())
    );
    assert_eq!(
        extract_html_title("<title>A &amp; B &#8212; C</title>"),
        Some("A & B — C".to_string())
    );
    assert_eq!(extract_html_title("<html><head></head></html>"), None);
    assert_eq!(extract_html_title("<title>   </title>"), None);
    assert_eq!(extract_html_title("not html at all"), None);
}

#[test]
fn test_title_cache_eviction_and_ttl() {
    let mut cache = TitleCache::new(2, Duration::from_secs(3600));
    cache.set("http://a.example/", "A");
    cache.set("http://b.example/", "B");
    assert_eq!(cache.get("http://a.example/"), Some("A".to_string()));
    // Touching A makes B the eviction victim.
    cache.set("http://c.example/", "C");
    assert_eq!(cache.get("http://b.example/"), None);
    assert_eq!(cache.get("http://a.example/"), Some("A".to_string()));

    let mut short = TitleCache::new(256, Duration::from_millis(40));
    short.set("http://a.example/", "A");
    std::thread::sleep(Duration::from_millis(80));
    assert_eq!(short.get("http://a.example/"), None);
}

#[test]
fn test_update_url_title_if_current_guards_stale_rows() {
    let (_temp, db) = create_temp_db_copy();
    let (item_id, _) = db
        .add_item("read https://example.com/fresh later", None, "TEXT")
        .expect("add item");

    assert!(db
        .update_url_title_if_current(item_id, "https://example.com/fresh", "Fresh Title")
        .expect("stale check write"));
    assert_eq!(
        db.get_history_detail(item_id).expect("detail").url_title,
        "Fresh Title"
    );

    // A fetch for a different URL must not overwrite the row.
    assert!(!db
        .update_url_title_if_current(item_id, "https://other.example/x", "Other")
        .expect("stale check reject"));
    assert_eq!(
        db.get_history_detail(item_id).expect("detail").url_title,
        "Fresh Title"
    );

    assert!(!db
        .update_url_title_if_current(999_999_999, "https://example.com/fresh", "X")
        .expect("missing row"));
    assert!(!db
        .update_url_title_if_current(item_id, "https://example.com/fresh", "")
        .expect("empty title"));
}

/// Minimal canned HTTP server on loopback for fetch tests.
struct CannedServer {
    base: String,
    _handle: std::thread::JoinHandle<()>,
}

fn request_path(raw: &[u8]) -> String {
    let request = String::from_utf8_lossy(raw);
    request
        .lines()
        .next()
        .unwrap_or("")
        .split_whitespace()
        .nth(1)
        .unwrap_or("/")
        .to_string()
}

fn start_canned_server() -> CannedServer {
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind loopback");
    let port = listener.local_addr().expect("port").port();
    let handle = std::thread::spawn(move || {
        for stream in listener.incoming().take(16) {
            let mut stream = match stream {
                Ok(s) => s,
                Err(_) => break,
            };
            // Keep-alive: serve requests until the client goes away, so the
            // HTTP client pool never races a server-side close (10054 flakes).
            loop {
                let mut req = Vec::new();
                let mut buf = [0u8; 1024];
                let path_opt = loop {
                    match stream.read(&mut buf) {
                        Ok(0) => break None,
                        Ok(n) => {
                            req.extend_from_slice(&buf[..n]);
                            if req.windows(4).any(|w| w == b"\r\n\r\n") {
                                break Some(request_path(&req));
                            }
                            if req.len() > 8192 {
                                break None;
                            }
                        }
                        Err(_) => break None,
                    }
                };
                let path = match path_opt {
                    Some(p) => p,
                    None => break,
                };
                let (status, extra_headers, body): (&str, &str, Vec<u8>) = match path.as_str() {
                    "/redirect" => ("302 Found", "Location: /page\r\n", Vec::new()),
                    "/page" => (
                        "200 OK",
                        "",
                        b"<html><head><title>Canned Page &amp; More</title></head><body>hi</body></html>"
                            .to_vec(),
                    ),
                    "/binary" => ("200 OK", "", b"%PDF-1.4 fake".to_vec()),
                    "/big" => {
                        let mut big =
                            b"<html><head><title>Big Page</title></head><body>".to_vec();
                        big.extend(std::iter::repeat_n(b'x', TITLE_FETCH_MAX_BYTES + 65536));
                        big.extend_from_slice(b"</body></html>");
                        ("200 OK", "", big)
                    }
                    _ => (
                        "200 OK",
                        "",
                        b"<html><head><title>Default</title></head></html>".to_vec(),
                    ),
                };
                let content_type = if path == "/binary" {
                    "application/pdf"
                } else {
                    "text/html; charset=utf-8"
                };
                let header = format!(
                    "HTTP/1.1 {}\r\nContent-Type: {}\r\nContent-Length: {}\r\n{}Connection: keep-alive\r\n\r\n",
                    status,
                    content_type,
                    body.len(),
                    extra_headers
                );
                if stream.write_all(header.as_bytes()).is_err() {
                    break;
                }
                if stream.write_all(&body).is_err() {
                    break;
                }
            }
        }
    });
    CannedServer {
        base: format!("http://127.0.0.1:{}", port),
        _handle: handle,
    }
}

#[test]
fn test_fetch_http_title_against_canned_server() {
    let server = start_canned_server();

    let page =
        fetch_http_title_validated(&format!("{}/page", server.base), allow_loopback_for_tests);
    assert_eq!(page.error, None);
    assert_eq!(page.title, Some("Canned Page & More".to_string()));

    let redir = fetch_http_title_validated(
        &format!("{}/redirect", server.base),
        allow_loopback_for_tests,
    );
    assert_eq!(redir.error, None);
    assert_eq!(redir.title, Some("Canned Page & More".to_string()));
    assert!(redir.final_url.ends_with("/page"));

    let binary =
        fetch_http_title_validated(&format!("{}/binary", server.base), allow_loopback_for_tests);
    assert_eq!(binary.title, None);
    assert!(binary
        .error
        .unwrap_or_default()
        .contains("unsupported content type"));

    // Oversized body streams without failure; title still parses.
    let big = fetch_http_title_validated(&format!("{}/big", server.base), allow_loopback_for_tests);
    assert_eq!(big.error, None);
    assert_eq!(big.title, Some("Big Page".to_string()));
}

#[test]
fn test_fetch_async_reports_blocked_loopback() {
    let (_temp, db) = create_temp_db_copy();
    let db = Arc::new(db);
    let (item_id, _) = db
        .add_item("see http://127.0.0.1/secret", None, "TEXT")
        .expect("add item");
    let fetcher = TitleFetcher::new(Arc::clone(&db));
    let events: Arc<Mutex<Vec<TitleEvent>>> = Arc::new(Mutex::new(Vec::new()));
    let sink = Arc::clone(&events);
    fetcher.fetch_async("http://127.0.0.1/secret", item_id, move |event| {
        sink.lock().expect("lock").push(event);
    });
    // Blocked precheck reports synchronously.
    let events = events.lock().expect("lock");
    assert_eq!(events.len(), 1);
    assert_eq!(events[0].title, None);
    assert!(events[0].message.contains("건너뜁니다"));
    // Blocked fetch never touches the row.
    assert_eq!(
        db.get_history_detail(item_id).expect("detail").url_title,
        ""
    );
}

#[test]
fn test_fetch_title_for_url_rejects_without_network() {
    let outcome = fetch_title_for_url("http://127.0.0.1:9/nope");
    assert_eq!(outcome.title, None);
    assert!(outcome.error.unwrap_or_default().starts_with("blocked"));
}
