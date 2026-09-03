"""Vault golden test vectors generator for Python <-> Rust interoperability tests.

Generates deterministic cryptographic vectors using Python cryptography.fernet and PBKDF2HMAC.
These vectors will be used in Rust native tests to ensure exact compatibility:
- PBKDF2 key derivation (SHA-256, 480,000 iterations, 32-byte key)
- Fernet encryption and decryption compatibility
- Verification token ("VAULT_VERIFIED") check
- Error cases (wrong password, corrupted ciphertext)
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
VECTORS_JSON_PATH = FIXTURES_DIR / "vault_golden_vectors.json"


def derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def generate_vectors() -> dict[str, Any]:
    # Fixed deterministic salt (16 bytes)
    salt_bytes = bytes([i for i in range(16)])
    salt_b64 = base64.b64encode(salt_bytes).decode("ascii")

    master_password = "MasterPassword2026!@#"
    wrong_password = "WrongPassword999!@#"

    derived_key = derive_key(master_password, salt_bytes)
    derived_key_b64 = derived_key.decode("ascii")

    fernet = Fernet(derived_key)

    # Verification token
    verification_token = fernet.encrypt(b"VAULT_VERIFIED").decode("ascii")

    # Sample items to encrypt
    samples = [
        {"id": "ascii_password", "plaintext": "SuperSecretPassphrase123!"},
        {"id": "korean_secret", "plaintext": "스마트클립보드 암호화 보관함 비밀 데이터"},
        {"id": "api_key", "plaintext": "sk-proj-abcdef0123456789ABCDEF0123456789"},
        {"id": "multiline_secret", "plaintext": "Line 1: Private Key\nLine 2: Certificate Data\nLine 3: End"},
    ]

    encrypted_samples = []
    for sample in samples:
        ciphertext = fernet.encrypt(sample["plaintext"].encode("utf-8")).decode("ascii")
        encrypted_samples.append({
            "id": sample["id"],
            "plaintext": sample["plaintext"],
            "ciphertext": ciphertext,
        })

    corrupted_token = verification_token[:-4] + "XXXX"

    return {
        "kdf_params": {
            "algorithm": "PBKDF2-HMAC-SHA256",
            "iterations": 480000,
            "key_length": 32,
            "salt_b64": salt_b64,
        },
        "master_password": master_password,
        "derived_key_b64": derived_key_b64,
        "verification_plaintext": "VAULT_VERIFIED",
        "verification_token": verification_token,
        "samples": encrypted_samples,
        "negative_cases": {
            "wrong_password": wrong_password,
            "corrupted_token": corrupted_token,
        },
    }


def main():
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    vectors = generate_vectors()
    with open(VECTORS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(vectors, f, indent=2, ensure_ascii=False)
    print(f"[OK] Vault golden vectors written to: {VECTORS_JSON_PATH}")


if __name__ == "__main__":
    main()
