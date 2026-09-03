use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum ItemType {
    TEXT,
    IMAGE,
    LINK,
    CODE,
    COLOR,
    FILE,
}

impl std::str::FromStr for ItemType {
    type Err = std::convert::Infallible;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        Ok(match s {
            "IMAGE" => ItemType::IMAGE,
            "LINK" => ItemType::LINK,
            "CODE" => ItemType::CODE,
            "COLOR" => ItemType::COLOR,
            "FILE" => ItemType::FILE,
            _ => ItemType::TEXT,
        })
    }
}

impl ItemType {

    pub fn as_str(&self) -> &'static str {
        match self {
            ItemType::TEXT => "TEXT",
            ItemType::IMAGE => "IMAGE",
            ItemType::LINK => "LINK",
            ItemType::CODE => "CODE",
            ItemType::COLOR => "COLOR",
            ItemType::FILE => "FILE",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HistoryItem {
    pub id: i64,
    pub content: String,
    pub r#type: String,
    pub timestamp: String,
    pub pinned: bool,
    pub pin_order: i64,
    pub use_count: i64,
    pub bookmark: bool,
    pub tags: String,
    pub note: String,
    pub url_title: String,
    pub collection_id: Option<i64>,
    pub has_image: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HistoryDetail {
    pub id: i64,
    pub content: String,
    pub r#type: String,
    pub timestamp: String,
    pub pinned: bool,
    pub pin_order: i64,
    pub use_count: i64,
    pub bookmark: bool,
    pub tags: String,
    pub note: String,
    pub url_title: String,
    pub collection_id: Option<i64>,
    pub image_data_base64: Option<String>,
    pub file_path: String,
    pub file_signature: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Collection {
    pub id: i64,
    pub name: String,
    pub icon: String,
    pub color: String,
    pub created_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Snippet {
    pub id: i64,
    pub name: String,
    pub content: String,
    pub shortcut: Option<String>,
    pub category: String,
    pub created_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrashItem {
    pub id: i64,
    pub original_id: Option<i64>,
    pub content: String,
    pub r#type: String,
    pub deleted_at: Option<String>,
    pub original_timestamp: Option<String>,
    pub tags: String,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct SearchFilter {
    pub query: String,
    pub type_filter: Option<String>,
    pub tag_filter: Option<String>,
    pub bookmarked: Option<bool>,
    pub collection_id: Option<i64>,
    pub limit: Option<usize>,
}
