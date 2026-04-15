from __future__ import annotations

from .retention import TrashRetentionMixin, VaultRetentionMixin


class VaultTrashMixin(VaultRetentionMixin, TrashRetentionMixin):
    """Compatibility facade for vault/trash mixins."""


__all__ = ["VaultTrashMixin"]
