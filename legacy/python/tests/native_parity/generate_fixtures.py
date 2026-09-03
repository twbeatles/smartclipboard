"""Synthetic SQLite DB fixture generator for Python-Rust parity tests.

Strict safety rule: This script NEVER uses or modifies any actual user DB.
It constructs an isolated synthetic DB fixture populated with all supported item types,
metadata, collections, snippets, copy rules, actions, trash, and settings.
"""

from __future__ import annotations

import base64
import os
import sqlite3
import sys
from pathlib import Path

# Ensure root repository is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from smartclipboard_core.database import ClipboardDB
from smartclipboard_core.file_paths import file_content_from_paths, file_signature_from_paths

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SYNTHETIC_DB_PATH = FIXTURES_DIR / "synthetic_test_v6.db"

# Minimal 1x1 transparent PNG bytes
TINY_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def build_synthetic_db(target_path: Path = SYNTHETIC_DB_PATH) -> Path:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        target_path.unlink()

    # Remove stale wal/shm if present
    wal_file = target_path.with_name(f"{target_path.name}-wal")
    shm_file = target_path.with_name(f"{target_path.name}-shm")
    if wal_file.exists():
        wal_file.unlink()
    if shm_file.exists():
        shm_file.unlink()

    db = ClipboardDB(db_file=str(target_path), app_dir=str(target_path.parent))

    # 1. Add Collections
    col1 = db.add_collection("업무", icon="💼", color="#3b82f6")
    col2 = db.add_collection("개인", icon="🏠", color="#10b981")
    col3 = db.add_collection("프로젝트", icon="🚀", color="#8b5cf6")

    # 2. Add History Items
    # 2.1 TEXT
    id_text1 = db.add_item("스마트클립보드 네이티브 전환 프로젝트", None, "TEXT")
    db.set_item_metadata(
        id_text1,
        tags="업무, Rust, Tauri",
        note="2026 마이그레이션 핵심 프로젝트",
        bookmark=1,
        pinned=1,
        pin_order=0,
        collection_id=col1,
    )

    id_text2 = db.add_item("Quick brown fox jumps over the lazy dog 12345", None, "TEXT")
    db.set_item_metadata(id_text2, tags="English, Sample", bookmark=0, pinned=1, pin_order=1)

    id_text3 = db.add_item("한국어 검색 테스트: 전문 검색 인덱스가 정상 작동하는지 확인합니다.", None, "TEXT")
    db.set_item_metadata(id_text3, tags="검색, 테스트", bookmark=1, collection_id=col3)

    # 2.2 LINK
    id_link = db.add_item("https://github.com/twbeatles/smartclipboard", None, "LINK")
    db.set_item_metadata(
        id_link,
        tags="GitHub, OpenSource",
        url_title="GitHub - twbeatles/smartclipboard",
        bookmark=1,
        collection_id=col1,
    )

    # 2.3 COLOR
    id_color1 = db.add_item("#6366f1", None, "COLOR")
    db.set_item_metadata(id_color1, tags="Theme, Indigo", note="기본 포인트 컬러")

    id_color2 = db.add_item("rgb(255, 99, 71)", None, "COLOR")
    db.set_item_metadata(id_color2, tags="Tomato, Accent")

    # 2.4 CODE
    code_content = "def calculate_hash(content: str) -> str:\n    return hashlib.sha256(content.encode()).hexdigest()"
    id_code = db.add_item(code_content, None, "CODE")
    db.set_item_metadata(id_code, tags="Python, Crypto", note="해시 유틸리티 함수", collection_id=col3)

    # 2.5 IMAGE
    id_img = db.add_item("이미지 [1x1]", TINY_PNG_BYTES, "IMAGE")
    db.set_item_metadata(id_img, tags="아이콘, 더미", bookmark=0)

    # 2.6 FILE
    file_list = [r"C:\Windows\notepad.exe", r"C:\Windows\explorer.exe"]
    normalized_file_content = file_content_from_paths(file_list)
    id_file = db.add_item(normalized_file_content, None, "FILE")
    db.set_item_metadata(id_file, tags="System, Executables", note="윈도우 기본 실행 파일")

    # 3. Add Snippets
    db.add_snippet("이메일 서명", "감사합니다.\nSmartClipboard 팀 드림", "Alt+Shift+1", "업무")
    db.add_snippet("템플릿 응답", "문의주신 사항을 신속히 확인하여 답변드리겠습니다.", "Alt+Shift+2", "고객지원")

    # 4. Add Copy Rules
    with db.lock:
        cur = db.conn.cursor()
        cur.execute(
            "INSERT INTO copy_rules (name, pattern, action, replacement, enabled, priority) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("공백 제거", r"^\s+|\s+$", "trim", "", 1, 10),
        )
        cur.execute(
            "INSERT INTO copy_rules (name, pattern, action, replacement, enabled, priority) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("대문자 변환", r"^conv_.*", "uppercase", "", 1, 20),
        )

        # 5. Add Clipboard Actions
        cur.execute(
            "INSERT INTO clipboard_actions (name, pattern, action_type, action_params, enabled, priority) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("웹 제목 가져오기", r"^https?://", "fetch_title", '{"timeout": 5}', 1, 10),
        )

        # 6. Add Settings
        cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("theme", "Ocean"))
        cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("max_history", "200"))
        cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("hotkey_main", "Alt+V"))
        cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("hotkey_mini", "Ctrl+Shift+V"))

        # Fixed dummy vault settings (16-byte zero salt for deterministic fixture testing)
        fixed_salt = b"\x01" * 16
        cur.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("vault_salt", base64.b64encode(fixed_salt).decode("ascii")),
        )
        cur.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("vault_verification", "gAAAAABlDummyVerificationTokenHereForParityTest=="),
        )

        # 7. Add Secure Vault Item
        cur.execute(
            "INSERT INTO secure_vault (encrypted_content, label, created_at) VALUES (?, ?, datetime('now'))",
            (b"gAAAAABlDummyEncryptedSecretTokenBytesForTesting==", "테스트 비밀번호"),
        )

        # 8. Soft Delete an item into Trash (deleted_history)
        del_item_id = db.add_item("삭제되어 휴지통에 보관된 임시 메모", None, "TEXT")
        db.set_item_metadata(del_item_id, tags="임시, 삭제대상", note="휴지통 복원 테스트용")
        db.soft_delete(del_item_id)

        db.conn.commit()

    # 9. Force FTS index build and optimize
    db.ensure_search_index()

    # 10. Check integrity and checkpoint WAL
    with db.lock:
        cur = db.conn.cursor()
        cur.execute("PRAGMA integrity_check")
        check_res = cur.fetchone()
        assert check_res and check_res[0] == "ok", f"Integrity check failed: {check_res}"
        cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    db.conn.close()
    return target_path


if __name__ == "__main__":
    db_path = build_synthetic_db()
    print(f"[OK] Synthetic DB fixture generated successfully at: {db_path} (size={db_path.stat().st_size} bytes)")
