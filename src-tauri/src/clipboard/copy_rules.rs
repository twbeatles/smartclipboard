use regex::Regex;

#[derive(Debug, Clone)]
pub struct CopyRule {
    pub id: i64,
    pub name: String,
    pub pattern: String,
    pub action: String,
    pub replacement: String,
    pub enabled: bool,
    pub priority: i64,
}

/// Applies active copy rules sequentially, matching Python's apply_copy_rules_impl
pub fn apply_copy_rules(mut text: String, rules: &[CopyRule]) -> String {
    for rule in rules {
        if !rule.enabled || rule.pattern.is_empty() {
            continue;
        }

        if let Ok(re) = Regex::new(&rule.pattern) {
            if re.is_match(&text) {
                match rule.action.as_str() {
                    "trim" => {
                        text = text.trim().to_string();
                    }
                    "lowercase" => {
                        text = text.to_lowercase();
                    }
                    "uppercase" => {
                        text = text.to_uppercase();
                    }
                    "remove_newlines" => {
                        text = text.replace('\n', " ").replace('\r', "");
                    }
                    "custom_replace" => {
                        text = re.replace_all(&text, rule.replacement.as_str()).to_string();
                    }
                    _ => {}
                }
            }
        }
    }
    text
}
