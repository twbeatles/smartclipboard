"""Shared feature state for window-oriented controllers."""

from .controller import FeatureController
from .state import WindowServices, WindowState, WindowWidgets, bind_window_facets

__all__ = ["FeatureController", "WindowServices", "WindowState", "WindowWidgets", "bind_window_facets"]
