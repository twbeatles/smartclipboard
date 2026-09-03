use base64::Engine;
use base64::engine::general_purpose::STANDARD as BASE64;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::errors::{AppError, Result};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PaletteAction {
    pub id: &'static str,
    pub title: &'static str,
    pub description: &'static str,
    pub category: &'static str,
}

pub const BUILTIN_ACTIONS: &[PaletteAction] = &[
    PaletteAction {
        id: "uppercase",
        title: "대문자로 변환",
        description: "모든 알파벳을 대문자로 변환합니다",
        category: "텍스트",
    },
    PaletteAction {
        id: "lowercase",
        title: "소문자로 변환",
        description: "모든 알파벳을 소문자로 변환합니다",
        category: "텍스트",
    },
    PaletteAction {
        id: "trim",
        title: "앞뒤 공백 정리",
        description: "문자열 앞뒤의 불필요한 공백과 줄바꿈을 제거합니다",
        category: "텍스트",
    },
    PaletteAction {
        id: "base64_encode",
        title: "Base64 인코딩",
        description: "텍스트를 Base64 형식으로 인코딩합니다",
        category: "개발자",
    },
    PaletteAction {
        id: "base64_decode",
        title: "Base64 디코딩",
        description: "Base64 문자열을 원본 텍스트로 디코딩합니다",
        category: "개발자",
    },
    PaletteAction {
        id: "sha256_hash",
        title: "SHA-256 해시 계산",
        description: "텍스트의 SHA-256 체크섬을 계산합니다",
        category: "개발자",
    },
    PaletteAction {
        id: "json_format",
        title: "JSON 예쁘게 포맷팅",
        description: "JSON 문자열을 2칸 들여쓰기로 포맷팅합니다",
        category: "개발자",
    },
    PaletteAction {
        id: "text_statistics",
        title: "글자 수 및 통계",
        description: "글자 수, 단어 수, 줄 수를 계산합니다",
        category: "분석",
    },
];

pub fn execute_action(action_id: &str, text: &str) -> Result<String> {
    match action_id {
        "uppercase" => Ok(text.to_uppercase()),
        "lowercase" => Ok(text.to_lowercase()),
        "trim" => Ok(text.trim().to_string()),
        "base64_encode" => Ok(BASE64.encode(text.as_bytes())),
        "base64_decode" => {
            let decoded = BASE64
                .decode(text.trim())
                .map_err(|e| AppError::Internal(format!("Base64 decoding failed: {}", e)))?;
            String::from_utf8(decoded)
                .map_err(|e| AppError::Internal(format!("Decoded bytes are not valid UTF-8: {}", e)))
        }
        "sha256_hash" => {
            let mut hasher = Sha256::new();
            hasher.update(text.as_bytes());
            Ok(format!("{:x}", hasher.finalize()))
        }
        "json_format" => {
            let val: serde_json::Value = serde_json::from_str(text)
                .map_err(|e| AppError::Internal(format!("Invalid JSON: {}", e)))?;
            serde_json::to_string_pretty(&val)
                .map_err(|e| AppError::Internal(format!("Formatting JSON failed: {}", e)))
        }
        "text_statistics" => {
            let chars = text.chars().count();
            let words = text.split_whitespace().count();
            let lines = text.lines().count();
            Ok(format!(
                "글자 수: {}자 (공백 제외 {}자)\n단어 수: {}개\n줄 수: {}줄",
                chars,
                text.chars().filter(|c| !c.is_whitespace()).count(),
                words,
                lines
            ))
        }
        _ => Err(AppError::NotFound(format!("Unknown action id: {}", action_id))),
    }
}
