from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from scripts.build_update_manifest import build_manifest
from smartclipboard_core.update_manifest import verify_release_manifest
import base64
from cryptography.hazmat.primitives import serialization


class BuildUpdateManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        self.private_key = Ed25519PrivateKey.generate()
        self.public_key_b64 = base64.b64encode(
            self.private_key.public_key().public_bytes(
                serialization.Encoding.Raw,
                serialization.PublicFormat.Raw,
            )
        ).decode("ascii")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_build_and_verify_manifest(self) -> None:
        artifact = self.tmp_path / "SmartClipboard-v10.7.exe"
        artifact.write_bytes(b"dummy exe content for v10.7")

        document = build_manifest(
            version="10.7",
            artifact=artifact,
            artifact_url="https://github.com/twbeatles/smartclipboard/releases/download/v10.7/SmartClipboard-v10.7.exe",
            private_key=self.private_key,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )

        self.assertIn("payload", document)
        self.assertIn("signature", document)

        # Verify with update_manifest
        manifest = verify_release_manifest(
            document,
            public_key=self.public_key_b64,
            current_version="10.6",
        )
        self.assertEqual(manifest.version, "10.7")
        self.assertEqual(manifest.artifact_size, len(b"dummy exe content for v10.7"))


if __name__ == "__main__":
    unittest.main()
