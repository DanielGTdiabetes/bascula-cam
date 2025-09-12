#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pantalla de ajustes saneada y modular.

Se divide la construcción de cada pestaña en submódulos bajo
bascula.ui.settings_tabs para reducir el tamaño y los errores.
"""
from __future__ import annotations

import os
import socket
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from bascula.ui.screens import BaseScreen
from bascula.ui.widgets import Card, Toast, COL_BG, COL_CARD, COL_TEXT


def _safe_audio_icon(cfg: dict) -> str:
    no_emoji = bool(cfg.get('no_emoji', False)) or bool(os.environ.get('BASCULA_NO_EMOJI'))
    enabled = bool(cfg.get('sound_enabled', True))
    if no_emoji:
        return 'ON' if enabled else 'OFF'
    return '🔊' if enabled else '🔇'


class TabbedSettingsMenuScreen(BaseScreen):
    """Pantalla de ajustes con navegación por pestañas (versión limpia)."""

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app, **kwargs)

        # Header
        header = tk.Frame(self, bg=COL_BG)
        header.pack(fill="x", padx=10, pady=(10, 6))
        tk.Label(header, text="Ajustes", bg=COL_BG, fg=COL_TEXT,
                 font=("DejaVu Sans", 18, "bold")).pack(side="left")
        self._audio_btn = tk.Button(
            header,
            text=_safe_audio_icon(self.app.get_cfg()),
            command=self._toggle_audio_quick,
            bg=COL_BG,
            fg=COL_TEXT,
            bd=0,
            relief="flat",
            cursor="hand2",
            font=("DejaVu Sans", 12, "bold"),
            highlightthickness=0,
            width=3,
        )
        self._audio_btn.pack(side="right")
        tk.Button(
            header,
            text="Volver",
            command=lambda: self.app.show_screen('home'),
            bg=COL_BG,
            fg=COL_TEXT,
            bd=0,
            relief="flat",
            cursor="hand2",
            font=("DejaVu Sans", 12, "bold"),
            highlightthickness=0,
        ).pack(side="right", padx=(0, 4))

        # Contenedor principal
        card = Card(self)
        card.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # Estilo básico para pestañas
        try:
            style = ttk.Style(self)
            style.theme_use('clam')
            style.configure('Settings.TNotebook', background=COL_CARD, borderwidth=0)
            style.configure('Settings.TNotebook.Tab', background=COL_CARD, foreground=COL_TEXT,
                            padding=[18, 8], font=("DejaVu Sans", 12))
            # Vincular colores seleccionados al tema actual
            style.map('Settings.TNotebook.Tab',
                      background=[('selected', COL_ACCENT)],
                      foreground=[('selected', COL_BG)])
            nb_style = 'Settings.TNotebook'
        except Exception:
            nb_style = None

        self.notebook = ttk.Notebook(card, style=(nb_style or 'TNotebook'))
        self.notebook.pack(fill="both", expand=True)

        # Toast de feedback
        self.toast = Toast(self)

        # Construcción de pestañas delegada a submódulos
        try:
            from bascula.ui.settings_tabs import (
                tabs_general, tabs_theme, tabs_scale, tabs_network, tabs_diabetes, tabs_storage, tabs_about, tabs_ota
            )
        except Exception:
            tabs_general = tabs_theme = tabs_scale = tabs_network = tabs_diabetes = tabs_storage = tabs_about = tabs_ota = None

        builders = [
            (tabs_general, "General"),
            (tabs_theme, "Tema"),
            (tabs_scale, "Báscula"),
            (tabs_network, "Red"),
            (tabs_diabetes, "Diabetes"),
            (tabs_storage, "Datos"),
            (tabs_about, "Acerca de"),
            (tabs_ota, "OTA"),
        ]

        for module, title in builders:
            try:
                if module is not None and hasattr(module, 'add_tab'):
                    module.add_tab(self, self.notebook)
                else:
                    self._add_placeholder_tab(title)
            except Exception:
                self._add_placeholder_tab(title)

    def _add_placeholder_tab(self, title: str):
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text=title)
        tk.Label(tab, text=f"{title} no disponible", bg=COL_CARD, fg=COL_TEXT).pack(pady=20)

    # Acciones rápidas
    def _toggle_audio_quick(self):
        try:
            cfg = self.app.get_cfg()
            new_val = not bool(cfg.get('sound_enabled', True))
            cfg['sound_enabled'] = new_val
            self.app.save_cfg()
            au = getattr(self.app, 'get_audio', lambda: None)()
            if au:
                try:
                    au.set_enabled(new_val)
                except Exception:
                    pass
            try:
                self._audio_btn.config(text=_safe_audio_icon(cfg))
            except Exception:
                pass
            self.toast.show("Sonido: " + ("ON" if new_val else "OFF"), 900)
        except Exception:
            pass

    # Utilidades usadas por pestañas
    def get_current_ip(self) -> str | None:
        ip = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.2)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        except Exception:
            pass
        finally:
            try:
                s.close()
            except Exception:
                pass
        if not ip:
            try:
                out = subprocess.check_output(["/bin/sh", "-lc", "hostname -I | awk '{print $1}'"], text=True, timeout=1).strip()
                ip = out or None
            except Exception:
                ip = None
        return ip

    def read_pin(self) -> str:
        try:
            p = Path.home() / '.config' / 'bascula' / 'pin.txt'
            if p.exists():
                return p.read_text(encoding='utf-8', errors='ignore').strip()
        except Exception:
            pass
        return "N/D"
