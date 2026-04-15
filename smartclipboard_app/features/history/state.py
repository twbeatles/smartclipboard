"""History feature state models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HistoryViewState:
    last_display_count: int = 0
    last_search_query: str = ""
