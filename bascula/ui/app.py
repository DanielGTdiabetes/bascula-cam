"""Compatibility wrapper exposing the Raspberry Pi optimised UI."""
from __future__ import annotations

from .rpi_optimized_ui import RpiOptimizedApp

BasculaAppTk = RpiOptimizedApp
BasculaApp = RpiOptimizedApp

__all__ = ["BasculaApp", "BasculaAppTk", "RpiOptimizedApp"]

