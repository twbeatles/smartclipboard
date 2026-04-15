"""Shared state bundles for window feature controllers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class WindowState:
    current_theme: str = "dark"
    always_on_top: bool = False
    is_data_dirty: bool = True
    is_monitoring_paused: bool = False
    is_internal_copy: bool = False
    is_privacy_mode: bool = False
    current_tag_filter: str | None = None
    current_collection_filter: object = "__all__"
    sort_column: int = 3
    sort_order: object = None


@dataclass
class WindowServices:
    db: Any = None
    clipboard: Any = None
    vault_manager: Any = None
    action_manager: Any = None
    export_manager: Any = None
    settings: Any = None


@dataclass
class WindowWidgets:
    table: Any = None
    search_input: Any = None
    filter_combo: Any = None
    collection_filter_combo: Any = None
    detail_text: Any = None
    detail_stack: Any = None
    detail_image_lbl: Any = None
    tray_icon: Any = None
    tray_menu: Any = None
    status_bar: Any = None


def bind_window_facets(window) -> tuple[WindowState, WindowServices, WindowWidgets]:
    state = WindowState(
        current_theme=getattr(window, "current_theme", "dark"),
        always_on_top=bool(getattr(window, "always_on_top", False)),
        is_data_dirty=bool(getattr(window, "is_data_dirty", True)),
        is_monitoring_paused=bool(getattr(window, "is_monitoring_paused", False)),
        is_internal_copy=bool(getattr(window, "is_internal_copy", False)),
        is_privacy_mode=bool(getattr(window, "is_privacy_mode", False)),
        current_tag_filter=getattr(window, "current_tag_filter", None),
        current_collection_filter=getattr(window, "current_collection_filter", "__all__"),
        sort_column=int(getattr(window, "sort_column", 3) or 3),
        sort_order=getattr(window, "sort_order", None),
    )
    services = WindowServices(
        db=getattr(window, "db", None),
        clipboard=getattr(window, "clipboard", None),
        vault_manager=getattr(window, "vault_manager", None),
        action_manager=getattr(window, "action_manager", None),
        export_manager=getattr(window, "export_manager", None),
        settings=getattr(window, "settings", None),
    )
    status_bar_getter = getattr(window, "statusBar", None)
    widgets = WindowWidgets(
        table=getattr(window, "table", None),
        search_input=getattr(window, "search_input", None),
        filter_combo=getattr(window, "filter_combo", None),
        collection_filter_combo=getattr(window, "collection_filter_combo", None),
        detail_text=getattr(window, "detail_text", None),
        detail_stack=getattr(window, "detail_stack", None),
        detail_image_lbl=getattr(window, "detail_image_lbl", None),
        tray_icon=getattr(window, "tray_icon", None),
        tray_menu=getattr(window, "tray_menu", None),
        status_bar=status_bar_getter() if callable(status_bar_getter) else None,
    )
    window._feature_state = state
    window._feature_services = services
    window._feature_widgets = widgets
    return state, services, widgets
