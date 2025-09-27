#!/usr/bin/env python3
"""Pantalla de ajustes con el tema ttk holográfico."""
from __future__ import annotations

import logging
import os
import socket
import subprocess
import tkinter as tk
from tkinter import ttk
from pathlib import Path

from bascula.ui.fonts import font_tuple
from bascula.ui.screens import BaseScreen
from bascula.ui.theme_holo import (
    COLOR_ACCENT,
    COLOR_BG,
    COLOR_PRIMARY,
    COLOR_TEXT,
    FONT_UI,
    FONT_UI_BOLD,
    neon_border,
    paint_grid_background,
)
from bascula.ui.widgets import Toast


log = logging.getLogger(__name__)


def _safe_audio_icon(cfg: dict) -> str:
    no_emoji = bool(cfg.get("no_emoji", False)) or bool(os.environ.get("BASCULA_NO_EMOJI"))
    enabled = bool(cfg.get("sound_enabled", True))
    if no_emoji:
        return "ON" if enabled else "OFF"
    return "🔊" if enabled else "🔇"


class TabbedSettingsMenuScreen(BaseScreen):
    """Pantalla de ajustes con pestañas holográficas."""

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app, **kwargs)

        self.configure(bg=COLOR_BG)
        paint_grid_background(self)

        style = ttk.Style(self)
        style.configure(
            "HoloHeader.TButton",
            background=COLOR_BG,
            foreground=COLOR_PRIMARY,
            font=FONT_UI_BOLD,
            borderwidth=1,
            padding=(14, 8),
            focusthickness=1,
            focuscolor=COLOR_ACCENT,
            bordercolor=COLOR_PRIMARY,
            relief="flat",
        )
        style.map(
            "HoloHeader.TButton",
            foreground=[("active", COLOR_ACCENT), ("pressed", COLOR_BG)],
            background=[("pressed", COLOR_ACCENT)],
            bordercolor=[("active", COLOR_ACCENT), ("pressed", COLOR_ACCENT)],
        )

        style.configure(
            "HoloSettings.TNotebook",
            background="#101015",
            borderwidth=0,
            padding=6,
            tabmargins=(18, 12, 18, 0),
        )
        style.configure(
            "HoloSettings.TNotebook.Tab",
            font=FONT_UI_BOLD,
            background="#101015",
            foreground=COLOR_PRIMARY,
            padding=(20, 12),
            bordercolor=COLOR_PRIMARY,
        )
        style.map(
            "HoloSettings.TNotebook.Tab",
            foreground=[("selected", COLOR_ACCENT)],
            background=[("selected", "#141424")],
            bordercolor=[("selected", COLOR_ACCENT), ("!selected", COLOR_PRIMARY)],
        )

        base_family = FONT_UI[0] if isinstance(FONT_UI, (tuple, list)) else FONT_UI
        title_font = (base_family, 24, "bold")

        header = tk.Frame(self, bg=COLOR_BG)
        header.pack(fill="x", padx=20, pady=(20, 14))

        self._back_btn = ttk.Button(
            header,
            text="←",
            style="HoloHeader.TButton",
            command=lambda: self.app.show_screen("home"),
            width=3,
        )
        self._back_btn.pack(side="left", padx=(0, 16))

        title_container = tk.Frame(header, bg=COLOR_BG)
        title_container.pack(side="left")

        glow = tk.Label(
            title_container,
            text="Ajustes",
            font=title_font,
            fg=COLOR_ACCENT,
            bg=COLOR_BG,
        )
        glow.place(x=0, y=2)
        title_label = tk.Label(
            title_container,
            text="Ajustes",
            font=title_font,
            fg=COLOR_TEXT,
            bg=COLOR_BG,
        )
        title_label.pack()

        self._audio_btn = ttk.Button(
            header,
            text=_safe_audio_icon(self.app.get_cfg()),
            style="HoloHeader.TButton",
            command=self._toggle_audio_quick,
            width=6,
        )
        self._audio_btn.pack(side="right", padx=(16, 0))

        self._home_btn = ttk.Button(
            header,
            text="🏠 Inicio",
            style="HoloHeader.TButton",
            command=lambda: self.app.show_screen("home"),
        )
        self._home_btn.pack(side="right")

        card = tk.Frame(self, bg="#101015", highlightthickness=0, bd=0)
        card.pack(fill="both", expand=True, padx=24, pady=(0, 24))
        neon_border(card, radius=20)

        body_frame = tk.Frame(card, bg="#141424", highlightthickness=0, bd=0)
        body_frame.pack(fill="both", expand=True, padx=20, pady=20)

        self.notebook = ttk.Notebook(body_frame, style="HoloSettings.TNotebook")
        self.notebook.pack(fill="both", expand=True)

        try:
            self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed, add=True)
        except Exception:
            pass

        self.toast = Toast(self)

        try:
            from bascula.ui.settings_tabs import (
                tabs_general,
                tabs_theme,
                tabs_scale,
                tabs_network,
                tabs_diabetes,
                tabs_storage,
                tabs_ota,
                tabs_about,
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
            ) = tabs_ota = tabs_about = None

        builders = [
            (tabs_general, "General"),
            (tabs_network, "Conectividad"),
            (tabs_diabetes, "Diabético"),
            (tabs_scale, "Báscula"),
            (tabs_theme, "Tema"),
            (tabs_storage, "Datos"),
            (tabs_ota, "OTA"),
            (tabs_about, "Acerca de"),
        ]

        for module, title_name in builders:
            try:
                if module is not None and hasattr(module, "add_tab"):
                    module.add_tab(self, self.notebook)
                else:
                    self._add_placeholder_tab(title_name)
            except Exception:
                log.exception("Fallo creando pestaña %s", title_name)
                self._add_placeholder_tab(title_name)

        self._update_tab_borders()

    # ------------------------------------------------------------------
    def _on_tab_changed(self, _event) -> None:
        self._update_tab_borders()

    # ------------------------------------------------------------------
    def _update_tab_borders(self, *_event):
        if hasattr(self.notebook, "tabs"):
            current = self.notebook.select()
            for tab_id in self.notebook.tabs():
                frame = self.nametowidget(tab_id)
                if tab_id == current:
                    frame.configure(
                        bg="#141424",
                        highlightbackground=COLOR_ACCENT,
                        highlightcolor=COLOR_ACCENT,
                        highlightthickness=2,
                    )
                else:
                    frame.configure(
                        bg="#141424",
                        highlightbackground=COLOR_PRIMARY,
                        highlightcolor=COLOR_PRIMARY,
                        highlightthickness=1,
                    )

    # ------------------------------------------------------------------
    def _create_ctk_tab(self, title: str) -> tk.Misc:
        frame = tk.Frame(self.notebook, bg="#141424", highlightthickness=1, highlightbackground=COLOR_PRIMARY)
        try:
            self.notebook.add(frame, text=title)
        except Exception:
            pass
        return frame

    def _add_placeholder_tab(self, title: str) -> None:
        frame = self._create_ctk_tab(title)
        message = tk.Label(
            frame,
            text=f"{title}\nNo disponible",
            font=font_tuple(14, "bold"),
            fg=COLOR_TEXT,
            bg="#141424",
        )
        message.pack(expand=True)

    # ------------------------------------------------------------------
    def _toggle_audio_quick(self) -> None:
        try:
            cfg = self.app.get_cfg()
            new_val = not bool(cfg.get("sound_enabled", True))
            cfg["sound_enabled"] = new_val
            self.app.save_cfg()
            audio = getattr(self.app, "get_audio", lambda: None)()
            if audio:
                try:
                    audio.set_enabled(new_val)
                except Exception:
                    pass
            self._audio_btn.configure(text=_safe_audio_icon(cfg))
            self.toast.show("Sonido: " + ("ON" if new_val else "OFF"), 900)
        except Exception:
            log.debug("No se pudo alternar el audio", exc_info=True)

    # ------------------------------------------------------------------
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
                out = subprocess.check_output(
                    ["/bin/sh", "-lc", "hostname -I | awk '{print $1}'"],
                    text=True,
                    timeout=1,
                ).strip()
                ip = out or None
            except Exception:
                ip = None
        return ip

    def read_pin(self) -> str:
        try:
            path = Path.home() / ".config" / "bascula" / "pin.txt"
            if path.exists():
                return path.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            pass
        return "N/D"


__all__ = ["TabbedSettingsMenuScreen"]

