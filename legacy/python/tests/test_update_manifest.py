from __future__ import annotations

import base64
import unittest
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from smartclipboard_core.update_manifest import (
    NoUpdateAvailableError,
    canonical_manifest_payload,
    is_newer_version,
    verify_release_manifest,
)


class UpdateManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.private_key = Ed25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()
        self.public_key_b64 = base64.b64encode(
            self.public_key.public_bytes(
                serialization.Encoding.Raw,
                serialization.PublicFormat.Raw,
            )
        ).decode("ascii")

    def _sign_document(self, payload: dict[str, object]) -> dict[str, object]:
        signature = self.private_key.sign(canonical_manifest_payload(payload))
        return {
            "payload": payload,
            "signature": base64.b64encode(signature).decode("ascii"),
        }

    def test_version_comparison_rules(self) -> None:
        self.assertTrue(is_newer_version("10.7", "10.6"))
        self.assertTrue(is_newer_version("10.6.1", "10.6"))
        self.assertTrue(is_newer_version("11.0", "10.9.9"))
        self.assertFalse(is_newer_version("10.6", "10.6"))
        self.assertFalse(is_newer_version("10.5", "10.6"))
        self.assertFalse(is_newer_version("10.6.0", "10.6"))

    def test_valid_manifest_verifies_successfully(self) -> None:
        payload = {
            "version": "10.7",
            "artifact_url": "https://github.com/twbeatles/smartclipboard/releases/download/v10.7/SmartClipboard-v10.7.exe",
            "sha256": "a" * 64,
            "size": 1024 * 1024,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30))
            .replace(microsecond=0)
            .isoformat(),
        }
        document = self._sign_document(payload)
        manifest = verify_release_manifest(
            document,
            public_key=self.public_key_b64,
            current_version="10.6",
        )
        self.assertEqual(manifest.version, "10.7")
        self.assertEqual(manifest.artifact_sha256, "a" * 64)
        self.assertEqual(manifest.artifact_size, 1024 * 1024)

    def test_tampered_payload_fails_verification(self) -> None:
        payload = {
            "version": "10.7",
            "artifact_url": "https://github.com/twbeatles/smartclipboard/releases/download/v10.7/SmartClipboard-v10.7.exe",
            "sha256": "a" * 64,
            "size": 1024 * 1024,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30))
            .replace(microsecond=0)
            .isoformat(),
        }
        document = self._sign_document(payload)
        # Tamper payload
        payload["version"] = "10.8"
        document["payload"] = payload
        with self.assertRaises(ValueError):
            verify_release_manifest(
                document,
                public_key=self.public_key_b64,
                current_version="10.6",
            )

    def test_expired_manifest_fails_verification(self) -> None:
        payload = {
            "version": "10.7",
            "artifact_url": "https://github.com/twbeatles/smartclipboard/releases/download/v10.7/SmartClipboard-v10.7.exe",
            "sha256": "a" * 64,
            "size": 1024 * 1024,
            "expires_at": (datetime.now(timezone.utc) - timedelta(days=1))
            .replace(microsecond=0)
            .isoformat(),
        }
        document = self._sign_document(payload)
        with self.assertRaises(ValueError):
            verify_release_manifest(
                document,
                public_key=self.public_key_b64,
                current_version="10.6",
            )

    def test_older_version_raises_no_update_available(self) -> None:
        payload = {
            "version": "10.5",
            "artifact_url": "https://github.com/twbeatles/smartclipboard/releases/download/v10.5/SmartClipboard-v10.5.exe",
            "sha256": "a" * 64,
            "size": 1024 * 1024,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30))
            .replace(microsecond=0)
            .isoformat(),
        }
        document = self._sign_document(payload)
        with self.assertRaises(NoUpdateAvailableError):
            verify_release_manifest(
                document,
                public_key=self.public_key_b64,
                current_version="10.6",
            )

    def test_non_https_url_is_rejected(self) -> None:
        payload = {
            "version": "10.7",
            "artifact_url": "http://example.com/SmartClipboard.exe",
            "sha256": "a" * 64,
            "size": 1024 * 1024,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30))
            .replace(microsecond=0)
            .isoformat(),
        }
        document = self._sign_document(payload)
        with self.assertRaises(ValueError):
            verify_release_manifest(
                document,
                public_key=self.public_key_b64,
                current_version="10.6",
            )


if __name__ == "__main__":
    unittest.main()
