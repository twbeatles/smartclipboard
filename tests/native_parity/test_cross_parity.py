"""Cross-parity verification test runner in Python.

Verifies:
1. Synthetic DB fixture exists, passes PRAGMA integrity_check, has FTS5 table and all item types.
2. Vault golden vectors JSON matches Python cryptography output.
"""

from __future__ import annotations

import base64
import json
import sqlite3
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
DB_PATH = FIXTURES_DIR / "synthetic_test_v6.db"
VECTORS_PATH = FIXTURES_DIR / "vault_golden_vectors.json"


def test_synthetic_db_integrity():
    assert DB_PATH.exists(), f"Missing synthetic test DB: {DB_PATH}"
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    cur.execute("PRAGMA integrity_check")
    assert cur.fetchone()[0] == "ok"

    # Verify tables
    cur.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual')")
    table_names = {row[0] for row in cur.fetchall()}
    assert "history" in table_names
    assert "history_fts" in table_names
    assert "collections" in table_names
    assert "snippets" in table_names
    assert "settings" in table_names
    assert "deleted_history" in table_names

    # Check row count
    cur.execute("SELECT COUNT(*) FROM history")
    count = cur.fetchone()[0]
    assert count >= 6

    # Verify FTS index entries match history count
    cur.execute("SELECT COUNT(*) FROM history_fts")
    fts_count = cur.fetchone()[0]
    assert fts_count == count

    conn.close()


def test_vault_golden_vectors_python_decrypt():
    assert VECTORS_PATH.exists(), f"Missing golden vectors file: {VECTORS_PATH}"
    with open(VECTORS_PATH, "r", encoding="utf-8") as f:
        vectors = json.load(f)

    master_password = vectors["master_password"]
    salt = base64.b64decode(vectors["kdf_params"]["salt_b64"])
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=vectors["kdf_params"]["iterations"],
    )
    derived_key = base64.urlsafe_b64encode(kdf.derive(master_password.encode("utf-8"))).decode("ascii")
    assert derived_key == vectors["derived_key_b64"]

    fernet = Fernet(derived_key.encode("ascii"))

    # Test verification token
    decrypted_token = fernet.decrypt(vectors["verification_token"].encode("ascii")).decode("utf-8")
    assert decrypted_token == vectors["verification_plaintext"]

    # Test samples
    for sample in vectors["samples"]:
        decrypted = fernet.decrypt(sample["ciphertext"].encode("ascii")).decode("utf-8")
        assert decrypted == sample["plaintext"]
