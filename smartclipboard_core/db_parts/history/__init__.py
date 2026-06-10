from __future__ import annotations

from .deletion import HistoryDeletionMixin
from .maintenance import HistoryMaintenanceMixin
from .metadata import HistoryMetadataMixin
from .queries import HistoryQueryMixin
from .write import HistoryWriteMixin


class HistoryOpsMixin(
    HistoryWriteMixin,
    HistoryQueryMixin,
    HistoryMetadataMixin,
    HistoryDeletionMixin,
    HistoryMaintenanceMixin,
):
    """Compatibility facade composed from focused history mixins."""


__all__ = [
    "HistoryDeletionMixin",
    "HistoryMaintenanceMixin",
    "HistoryMetadataMixin",
    "HistoryOpsMixin",
    "HistoryQueryMixin",
    "HistoryWriteMixin",
]
