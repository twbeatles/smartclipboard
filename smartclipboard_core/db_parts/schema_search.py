from __future__ import annotations

from .search import SearchFtsMixin, SearchQueryMixin, SearchSchemaMixin


class SchemaSearchMixin(SearchSchemaMixin, SearchFtsMixin, SearchQueryMixin):
    """Compatibility facade for search/schema mixins."""


__all__ = ["SchemaSearchMixin"]
