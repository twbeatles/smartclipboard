from __future__ import annotations

import base64
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from scripts.verify_update_release_key import verify_release_keypair


class UpdateReleaseKeyTests(unittest.TestCase):
    def test_matching_keypair_passes_verification(self) -> None:
        private_key = Ed25519PrivateKey.generate()
        private_key_b64 = base64.b64encode(
            private_key.private_bytes(
                serialization.Encoding.Raw,
                serialization.PrivateFormat.Raw,
                serialization.NoEncryption(),
            )
        ).decode("ascii")
        public_key_b64 = base64.b64encode(
            private_key.public_key().public_bytes(
                serialization.Encoding.Raw,
                serialization.PublicFormat.Raw,
            )
        ).decode("ascii")

        # Must not raise
        verify_release_keypair(private_key_b64, public_key_b64)

    def test_mismatched_keypair_raises_value_error(self) -> None:
        private_key1 = Ed25519PrivateKey.generate()
        private_key2 = Ed25519PrivateKey.generate()

        priv1_b64 = base64.b64encode(
            private_key1.private_bytes(
                serialization.Encoding.Raw,
                serialization.PrivateFormat.Raw,
                serialization.NoEncryption(),
            )
        ).decode("ascii")
        pub2_b64 = base64.b64encode(
            private_key2.public_key().public_bytes(
                serialization.Encoding.Raw,
                serialization.PublicFormat.Raw,
            )
        ).decode("ascii")

        with self.assertRaises(ValueError):
            verify_release_keypair(priv1_b64, pub2_b64)


if __name__ == "__main__":
    unittest.main()
