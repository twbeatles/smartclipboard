use regex::Regex;
use std::sync::LazyLock;

static RE_URL: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^https?://").unwrap());
static RE_HEX_COLOR: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^#(?:[0-9a-fA-F]{3}){1,2}$").unwrap());
static RE_RGB_COLOR: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?i)^rgb\s*\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)$").unwrap());
static RE_HSL_COLOR: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)^hsl\s*\(\s*\d+\s*,\s*\d+%?\s*,\s*\d+%?\s*\)$").unwrap()
});

const CODE_INDICATORS: &[&str] = &[
    "def ", "class ", "function ", "const ", "let ", "var ", "{", "}", "=>", "import ",
    "from ", "#include", "public ", "private ",
];

/// Identical to Python's analyze_text_impl
pub fn classify_text(text: &str) -> &'static str {
    if RE_URL.is_match(text) {
        return "LINK";
    }
    if RE_HEX_COLOR.is_match(text) {
        return "COLOR";
    }
    if RE_RGB_COLOR.is_match(text) {
        return "COLOR";
    }
    if RE_HSL_COLOR.is_match(text) {
        return "COLOR";
    }
    for &indicator in CODE_INDICATORS {
        if text.contains(indicator) {
            return "CODE";
        }
    }
    "TEXT"
}
