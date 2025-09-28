#!/usr/bin/env python3
"""Pantalla de ajustes con el tema ttk holográfico."""
from __future__ import annotations

import logging
import os
import socket
import subprocess
import tkinter as tk
from tkinter import ttk

from bascula.config.pin import PinPersistenceError
from bascula.ui.fonts import font_tuple
from bascula.ui.icon_loader import load_icon
from bascula.ui.screens import BaseScreen
from bascula.ui.theme_holo import (
    COLOR_ACCENT,
    COLOR_BG,
    COLOR_PRIMARY,
    COLOR_SURFACE,
    COLOR_TEXT,
    FONT_BODY_BOLD,
    FONT_HEADER,
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
            "HoloSettings.Root.TFrame",
            background=COLOR_BG,
        )
        style.configure(
            "HoloSettings.Header.TFrame",
            background=COLOR_BG,
        )
        style.configure(
            "HoloSettings.HeaderPrimary.TLabel",
            background=COLOR_BG,
            foreground=COLOR_TEXT,
            font=FONT_HEADER,
        )
        style.configure(
            "HoloSettings.HeaderGlow.TLabel",
            background=COLOR_BG,
            foreground=COLOR_ACCENT,
            font=FONT_HEADER,
        )
        style.configure(
            "HoloHeader.TButton",
            background=COLOR_BG,
            foreground=COLOR_PRIMARY,
            font=FONT_BODY_BOLD,
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
            "HoloSettings.Card.TFrame",
            background=COLOR_SURFACE,
            borderwidth=0,
        )
        style.configure(
            "HoloSettings.Body.TFrame",
            background=COLOR_SURFACE,
        )
        style.configure(
            "HoloSettings.TNotebook",
            background=COLOR_SURFACE,
            borderwidth=0,
            padding=6,
            tabmargins=(18, 12, 18, 0),
        )
        style.configure(
            "HoloSettings.TNotebook.Tab",
            font=FONT_BODY_BOLD,
            background=COLOR_SURFACE,
            foreground=COLOR_PRIMARY,
            padding=(20, 12),
            bordercolor=COLOR_PRIMARY,
        )
        style.map(
            "HoloSettings.TNotebook.Tab",
            foreground=[("selected", COLOR_ACCENT)],
            background=[("selected", COLOR_BG)],
            bordercolor=[("selected", COLOR_ACCENT), ("!selected", COLOR_PRIMARY)],
        )
        style.configure(
            "HoloSettings.Tab.TFrame",
            background=COLOR_SURFACE,
            borderwidth=1,
            relief="solid",
            bordercolor=COLOR_PRIMARY,
        )
        style.configure(
            "HoloSettings.TabSelected.TFrame",
            background=COLOR_SURFACE,
            borderwidth=2,
            relief="solid",
            bordercolor=COLOR_ACCENT,
        )

        header = ttk.Frame(self, style="HoloSettings.Header.TFrame")
        header.pack(fill="x", padx=20, pady=(20, 14))

        self._back_btn = ttk.Button(
            header,
            text="←",
            style="HoloHeader.TButton",
            command=lambda: self.app.show_screen("home"),
            width=3,
        )
        self._back_btn.pack(side="left", padx=(0, 16))

        title_container = ttk.Frame(header, style="HoloSettings.Header.TFrame")
        title_container.pack(side="left")

        glow = ttk.Label(title_container, text="Ajustes", style="HoloSettings.HeaderGlow.TLabel")
        glow.place(x=0, y=2)
        title_label = ttk.Label(title_container, text="Ajustes", style="HoloSettings.HeaderPrimary.TLabel")
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
            text="Inicio",
            style="HoloHeader.TButton",
            command=lambda: self.app.show_screen("home"),
        )
        self._home_btn.pack(side="right")
        try:
            home_icon = load_icon("home.png", size=28)
        except Exception:
            home_icon = None
        if home_icon is not None:
            self._home_btn.configure(image=home_icon, compound="left")
            self._home_btn.image = home_icon  # type: ignore[attr-defined]

        card = ttk.Frame(self, style="HoloSettings.Card.TFrame")
        card.pack(fill="both", expand=True, padx=24, pady=(0, 24))
        neon_border(card, radius=20)

        body_frame = ttk.Frame(card, style="HoloSettings.Body.TFrame")
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
            (tabs_theme, "Tema"),
            (tabs_scale, "Báscula"),
            (tabs_network, "Red"),
            (tabs_diabetes, "Diabético"),
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
                is_selected = tab_id == current
                if isinstance(frame, ttk.Frame):
                    style_name = (
                        "HoloSettings.TabSelected.TFrame"
                        if is_selected
                        else "HoloSettings.Tab.TFrame"
                    )
                    try:
                        frame.configure(style=style_name)
                    except tk.TclError:
                        pass
                else:
                    highlight_color = COLOR_ACCENT if is_selected else COLOR_PRIMARY
                    highlight_thickness = 2 if is_selected else 1
                    try:
                        frame.configure(
                            highlightbackground=highlight_color,
                            highlightcolor=highlight_color,
                            highlightthickness=highlight_thickness,
                        )
                    except tk.TclError:
                        pass

    # ------------------------------------------------------------------
    def _create_ctk_tab(self, title: str) -> tk.Misc:
        frame = ttk.Frame(self.notebook, style="HoloSettings.Tab.TFrame")
        try:
            self.notebook.add(frame, text=title)
        except Exception:
            pass
        return frame

    def _add_placeholder_tab(self, title: str) -> None:
        frame = self._create_ctk_tab(title)
        placeholder_style = "HoloSettings.Placeholder.TLabel"
        style = ttk.Style(self)
        style.configure(
            placeholder_style,
            background=COLOR_SURFACE,
            foreground=COLOR_TEXT,
            font=font_tuple(14, "bold"),
        )
        message = ttk.Label(
            frame,
            text=f"{title}\nNo disponible",
            style=placeholder_style,
            justify="center",
            anchor="center",
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

    def get_miniweb_pin_text(self) -> str:
        try:
            pin = self.app.get_miniweb_pin()
        except AttributeError:
            pin = ""
        value = pin or "N/D"
        return f"PIN mini-web: {value}"

    def read_pin(self) -> str:
        try:
            pin = self.app.get_miniweb_pin()
            return pin or "N/D"
        except AttributeError:
            return "N/D"

    def regenerate_miniweb_pin(self) -> bool:
        try:
            new_pin = self.app.regenerate_miniweb_pin()
        except PinPersistenceError:
            try:
                self.toast.show("No se pudo guardar el PIN", 1800)
            except Exception:
                pass
            return False
        except AttributeError:
            return False
        try:
            self.toast.show(f"PIN regenerado: {new_pin}", 1400)
        except Exception:
            pass
        return True


__all__ = ["TabbedSettingsMenuScreen"]

