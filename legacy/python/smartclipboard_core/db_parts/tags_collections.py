from __future__ import annotations

from .catalog import CollectionCatalogMixin, TagCatalogMixin


class TagsCollectionsMixin(TagCatalogMixin, CollectionCatalogMixin):
    """Compatibility facade for tags/collections mixins."""


__all__ = ["TagsCollectionsMixin"]
