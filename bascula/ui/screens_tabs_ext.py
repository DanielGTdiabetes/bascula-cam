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
from bascula.ui.widgets import (
    Card,
    Toast,
    COL_BG,
    COL_CARD,
    COL_TEXT,
    COL_ACCENT,
    COL_PRIMARY,
    BORDER_PRIMARY_THIN,
    BORDER_ACCENT,
    FONT_FAMILY_TITLE,
    FONT_FAMILY_BODY,
    apply_holo_tabs_style,
    use_holo_notebook,
    style_holo_checkbuttons,
    apply_holo_theme_to_tree,
)
from bascula.ui.backgrounds import apply_holo_grid_background


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

        apply_holo_grid_background(self)
        apply_holo_tabs_style(self)
        style_holo_checkbuttons(self)

        # Header
        header = tk.Frame(self, bg=COL_BG)
        header.pack(fill="x", padx=12, pady=(12, 8))

        self._back_btn = tk.Button(
            header,
            text="←",
            command=lambda: self.app.show_screen('home'),
            bg=COL_BG,
            fg=COL_PRIMARY,
            activebackground=COL_BG,
            activeforeground=COL_ACCENT,
            relief="flat",
            cursor="hand2",
            font=FONT_FAMILY_TITLE,
        )
        self._back_btn.configure(**BORDER_PRIMARY_THIN)
        self._back_btn.pack(side="left", padx=(0, 10))

        title_lbl = tk.Label(
            header,
            text="Ajustes",
            bg=COL_BG,
            fg=COL_TEXT,
            font=FONT_FAMILY_TITLE,
            padx=8,
            pady=2,
        )
        title_lbl.configure(**BORDER_PRIMARY_THIN)
        title_lbl.pack(side="left")

        self._audio_btn = tk.Button(
            header,
            text=_safe_audio_icon(self.app.get_cfg()),
            command=self._toggle_audio_quick,
            bg=COL_BG,
            fg=COL_PRIMARY,
            bd=0,
            relief="flat",
            cursor="hand2",
            font=FONT_FAMILY_BODY,
            highlightthickness=1,
            highlightbackground=COL_PRIMARY,
            width=3,
        )
        self._audio_btn.configure(**BORDER_PRIMARY_THIN)
        self._audio_btn.pack(side="right")
        self._audio_btn.bind("<Enter>", lambda _e: self._audio_btn.configure(fg=COL_ACCENT), add=True)
        self._audio_btn.bind("<Leave>", lambda _e: self._audio_btn.configure(fg=COL_PRIMARY), add=True)

        self._home_btn = tk.Button(
            header,
            text="🏠 Inicio",
            command=lambda: self.app.show_screen('home'),
            bg=COL_BG,
            fg=COL_PRIMARY,
            bd=0,
            relief="flat",
            cursor="hand2",
            font=FONT_FAMILY_BODY,
            highlightthickness=1,
            highlightbackground=COL_PRIMARY,
        )
        self._home_btn.configure(**BORDER_PRIMARY_THIN)
        self._home_btn.pack(side="right", padx=(0, 8))
        self._home_btn.bind("<Enter>", lambda _e: self._home_btn.configure(fg=COL_ACCENT), add=True)
        self._home_btn.bind("<Leave>", lambda _e: self._home_btn.configure(fg=COL_PRIMARY), add=True)

        # Contenedor principal
        card = Card(self, padding=0)
        card.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        card.configure(bg=COL_CARD)
        inner_panel = card.add_glass_layer()

        body_frame = tk.Frame(inner_panel, bg=COL_CARD)
        body_frame.pack(fill="both", expand=True, padx=18, pady=18)

        # Estilo básico para pestañas
        self.notebook = ttk.Notebook(body_frame, style="Holo.TNotebook")
        self.notebook.pack(fill="both", expand=True)
        use_holo_notebook(self.notebook)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed, add=True)

        # Toast de feedback
        self.toast = Toast(self)

        # Construcción de pestañas delegada a submódulos
        try:
            from bascula.ui.settings_tabs import (
                tabs_general,
                tabs_theme,
                tabs_scale,
                tabs_network,
                tabs_diabetes,
                tabs_storage,
                tabs_about,
                tabs_ota,
            )
        except Exception:
            tabs_general = (
                tabs_theme
            ) = (
                tabs_scale
            ) = (
                tabs_network
            ) = (
                tabs_diabetes
            ) = (
                tabs_storage
            ) = (
                tabs_about
            ) = tabs_ota = None

        builders = [
            (tabs_general, "General"),
            (tabs_theme, "Tema"),
            (tabs_scale, "Báscula"),
            (tabs_network, "Conectividad"),
            (tabs_diabetes, "Diabético"),
            (tabs_storage, "Datos"),
            (tabs_about, "Acerca de"),
            (tabs_ota, "OTA"),
        ]

        for module, title in builders:
            try:
                if module is not None and hasattr(module, "add_tab"):
                    module.add_tab(self, self.notebook)
                else:
                    self._add_placeholder_tab(title)
            except Exception:
                self.logger.exception("Fallo creando pestaña %s", title)
                self._add_placeholder_tab(title)

        self._update_tab_borders()
        apply_holo_theme_to_tree(body_frame)

    def _update_tab_borders(self, *_event):
        current = self.notebook.select()
        for tab_id in self.notebook.tabs():
            frame = self.nametowidget(tab_id)
            if tab_id == current:
                frame.configure(bg=COL_CARD, **BORDER_ACCENT)
            else:
                frame.configure(bg=COL_CARD, **BORDER_PRIMARY_THIN)

    def _on_tab_changed(self, _event):
        self._update_tab_borders()

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

    def _add_placeholder_tab(self, title: str) -> None:
        frame = tk.Frame(self.notebook, bg=COL_CARD)
        msg = tk.Label(
            frame,
            text=f"{title}\nNo disponible",
            bg=COL_CARD,
            fg=COL_TEXT,
            font=FONT_FAMILY_BODY,
            padx=20,
            pady=20,
            justify="center",
        )
        msg.pack(expand=True)
        self.notebook.add(frame, text=title)
