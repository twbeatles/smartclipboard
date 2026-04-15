"""Shared controller base for feature-oriented window composition."""

from __future__ import annotations

from .state import WindowServices, WindowState, WindowWidgets, bind_window_facets


class FeatureController:
    """Base controller that keeps lightweight synchronized access to the host window."""

    def __init__(self, window):
        self.window = window
        self.state: WindowState
        self.services: WindowServices
        self.widgets: WindowWidgets
        self.sync()

    def sync(self) -> tuple[WindowState, WindowServices, WindowWidgets]:
        self.state, self.services, self.widgets = bind_window_facets(self.window)
        return self.state, self.services, self.widgets
