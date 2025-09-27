#!/usr/bin/env python3
"""Pantalla de ajustes con tema holográfico usando CustomTkinter."""
from __future__ import annotations

import logging
import os
import socket
import subprocess
import tkinter as tk
from pathlib import Path

from bascula.ui.screens import BaseScreen
from bascula.ui.theme_ctk import (
    COLORS as HOLO_COLORS,
    CTK_AVAILABLE,
    create_button as holo_button,
    create_canvas_grid,
    create_frame as holo_frame,
    create_glow_title,
    create_label as holo_label,
    create_tabview,
    font_tuple,
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

        if CTK_AVAILABLE:
            create_canvas_grid(self)

        header = holo_frame(self, fg_color=HOLO_COLORS["bg"])
        header.pack(fill="x", padx=16, pady=(16, 12))

        self._back_btn = holo_button(
            header,
            text="←",
            command=lambda: self.app.show_screen("home"),
            width=70 if CTK_AVAILABLE else 3,
        )
        self._back_btn.pack(side="left", padx=(0, 12))

        title = create_glow_title(header, "Ajustes", font_size=26)
        title.pack(side="left")

        self._audio_btn = holo_button(
            header,
            text=_safe_audio_icon(self.app.get_cfg()),
            command=self._toggle_audio_quick,
            width=100 if CTK_AVAILABLE else 6,
        )
        self._audio_btn.pack(side="right", padx=(12, 0))

        self._home_btn = holo_button(
            header,
            text="🏠 Inicio",
            command=lambda: self.app.show_screen("home"),
            width=130 if CTK_AVAILABLE else 8,
        )
        self._home_btn.pack(side="right")

        card = holo_frame(self, fg_color=HOLO_COLORS["surface"], corner_radius=16)
        card.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        body_frame = holo_frame(card, fg_color=HOLO_COLORS["surface_alt"], corner_radius=14)
        body_frame.pack(fill="both", expand=True, padx=18, pady=18)

        self.notebook = create_tabview(body_frame)
        self.notebook.pack(fill="both", expand=True)

        if hasattr(self.notebook, "bind"):
            try:
                self.notebook.bind("<<TabChanged>>", self._on_tab_changed, add=True)
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
        if CTK_AVAILABLE and hasattr(self.notebook, "_segmented_button"):
            return
        if hasattr(self.notebook, "tabs"):
            current = self.notebook.select()
            for tab_id in self.notebook.tabs():
                frame = self.nametowidget(tab_id)
                if tab_id == current:
                    frame.configure(bg=HOLO_COLORS["surface"], highlightbackground=HOLO_COLORS["accent"], highlightcolor=HOLO_COLORS["accent"], highlightthickness=2)
                else:
                    frame.configure(bg=HOLO_COLORS["surface"], highlightbackground=HOLO_COLORS["primary"], highlightcolor=HOLO_COLORS["primary"], highlightthickness=1)

    # ------------------------------------------------------------------
    def _create_ctk_tab(self, title: str) -> tk.Misc:
        if CTK_AVAILABLE and hasattr(self.notebook, "tab"):
            try:
                self.notebook.add(title)
            except Exception:
                pass
            tab = self.notebook.tab(title)
            inner = holo_frame(tab, fg_color=HOLO_COLORS["surface_alt"], corner_radius=12)
            inner.pack(fill="both", expand=True, padx=18, pady=18)
            return inner
        frame = tk.Frame(self.notebook, bg=HOLO_COLORS["surface"])
        try:
            self.notebook.add(frame, text=title)
        except Exception:
            pass
        return frame

    def _add_placeholder_tab(self, title: str) -> None:
        frame = self._create_ctk_tab(title)
        message = holo_label(
            frame,
            text=f"{title}\nNo disponible",
            font=font_tuple(14, "bold"),
            text_color=HOLO_COLORS["text"],
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

