"""Compatibility facade for secure vault manager."""

from __future__ import annotations

from smartclipboard_app.features.vault import HAS_CRYPTO, SecureVaultManager

__all__ = ["SecureVaultManager", "HAS_CRYPTO"]
