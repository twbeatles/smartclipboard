use smartclipboard_native_lib::clipboard::{
    apply_copy_rules, classify_text, CopyRule, InternalWriteGuard,
};

#[test]
fn test_text_classifier_parity() {
    // 1. LINK
    assert_eq!(
        classify_text("https://github.com/twbeatles/smartclipboard"),
        "LINK"
    );
    assert_eq!(classify_text("http://example.com/test?a=1&b=2"), "LINK");

    // 2. COLOR
    assert_eq!(classify_text("#ffffff"), "COLOR");
    assert_eq!(classify_text("#6366f1"), "COLOR");
    assert_eq!(classify_text("#ABC"), "COLOR");
    assert_eq!(classify_text("rgb(255, 99, 71)"), "COLOR");
    assert_eq!(classify_text("RGB(0, 0, 0)"), "COLOR");
    assert_eq!(classify_text("hsl(120, 100%, 50%)"), "COLOR");

    // 3. CODE
    assert_eq!(classify_text("def solve():\n    return 42"), "CODE");
    assert_eq!(classify_text("const app = express();"), "CODE");
    assert_eq!(classify_text("function handleClick() => {}"), "CODE");
    assert_eq!(
        classify_text("public static void main(String[] args) {}"),
        "CODE"
    );
    assert_eq!(classify_text("import { useState } from 'react';"), "CODE");

    // 4. TEXT
    assert_eq!(
        classify_text("안녕하세요 스마트클립보드 프로입니다."),
        "TEXT"
    );
    assert_eq!(
        classify_text("The quick brown fox jumps over the lazy dog."),
        "TEXT"
    );
    assert_eq!(classify_text("전화번호: 010-1234-5678"), "TEXT");
}

#[test]
fn test_copy_rules_engine() {
    let rules = vec![
        CopyRule {
            id: 1,
            name: "Trim rule".into(),
            pattern: r"^\s+|\s+$".into(),
            action: "trim".into(),
            replacement: "".into(),
            enabled: true,
            priority: 1,
        },
        CopyRule {
            id: 2,
            name: "Uppercase rule".into(),
            pattern: r"^up_.*".into(),
            action: "uppercase".into(),
            replacement: "".into(),
            enabled: true,
            priority: 2,
        },
        CopyRule {
            id: 3,
            name: "Replace rule".into(),
            pattern: r"foo".into(),
            action: "custom_replace".into(),
            replacement: "bar".into(),
            enabled: true,
            priority: 3,
        },
        CopyRule {
            id: 4,
            name: "Disabled rule".into(),
            pattern: r".*".into(),
            action: "lowercase".into(),
            replacement: "".into(),
            enabled: false,
            priority: 4,
        },
    ];

    // Trim + Replace
    let input = "   hello foo world   ".to_string();
    let output = apply_copy_rules(input, &rules);
    assert_eq!(output, "hello bar world");

    // Uppercase
    let input2 = "   up_sample text   ".to_string();
    let output2 = apply_copy_rules(input2, &rules);
    assert_eq!(output2, "UP_SAMPLE TEXT");
}

#[test]
fn test_internal_write_guard() {
    let guard = InternalWriteGuard::new();
    let secret = "InternalClipboardContent!@#";

    guard.mark_internal(100, secret);

    // Matching sequence and content should be recognized as internal
    assert!(
        guard.is_internal(100, secret),
        "First call should match guard"
    );

    // Second call should not match (consumed)
    assert!(
        !guard.is_internal(100, secret),
        "Consumed guard should not match again"
    );

    // Different content should not match
    guard.mark_internal(200, "Secret A");
    assert!(
        !guard.is_internal(201, "Secret B"),
        "Unrelated content should not match"
    );
}

#[test]
fn test_png_dimensions_and_byte_guard() {
    use smartclipboard_native_lib::clipboard::image_reader::png_dimensions;

    // Minimal PNG: signature + IHDR (width 16, height 32) + empty IEND.
    let mut png = vec![0x89u8, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A];
    png.extend_from_slice(&[0, 0, 0, 13]);
    png.extend_from_slice(b"IHDR");
    png.extend_from_slice(&[0, 0, 0, 16, 0, 0, 0, 32, 8, 2, 0, 0, 0]);
    png.extend_from_slice(&[0, 0, 0, 0]);
    assert_eq!(png_dimensions(&png), Some((16, 32)));
    assert_eq!(png_dimensions(b"not a png"), None);
    assert_eq!(png_dimensions(&png[..10]), None);

    let guard = InternalWriteGuard::new();
    guard.mark_internal_bytes(42, &png);
    assert!(guard.is_internal_bytes(42, &png));
    assert!(!guard.is_internal_bytes(42, &png), "guard is single-shot");
    assert!(!guard.is_internal_bytes(43, b"something else"));
}
