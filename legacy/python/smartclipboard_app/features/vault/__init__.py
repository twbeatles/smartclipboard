"""Vault feature package."""

from .crypto import HAS_CRYPTO
from .service import SecureVaultManager

__all__ = ["SecureVaultManager", "HAS_CRYPTO"]
