"""Shim de compatibilidad para temas.

Esta ruta reexporta la API desde bascula.config.themes para consolidar
una única implementación de temas en la aplicación.
"""
from __future__ import annotations

# Reexportar nombres principales usados por la UI/documentación
from bascula.config.themes import (  # noqa: F401
    THEMES,
    get_theme_manager,
    apply_theme,
    update_color_constants,
)

