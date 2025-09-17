"""Screen definitions used by :mod:`bascula.ui.app`.

Historically this module exposed a rich set of widgets – home dashboard,
interactive scale, multi-tabbed settings – but the pared down version bundled
with the previous release only left skeletal placeholders.  The installation
worked yet practically every navigation entry resulted in an empty panel,
which is precisely the behaviour reported by the user.

The classes below reinstate the expressive UI while keeping the code compact
and well documented.  They rely exclusively on the widgets reintroduced in
``bascula.ui.widgets`` so they remain testable without any special Tk extensions.
"""

from __future__ import annotations

import tkinter as tk

from bascula.ui.widgets import (
    Card,
    Toast,
    BigButton,
    GhostButton,
    WeightLabel,
    COL_BG,
    COL_CARD,
    COL_TEXT,
    COL_MUTED,
)
from bascula.ui.widgets_mascota import MascotaCanvas


class BaseScreen(tk.Frame):
    """Common base with a title heading and themed background."""

    name = "base"
    title = "Pantalla"

    def __init__(self, parent: tk.Misc, app, **kwargs) -> None:
        super().__init__(parent, bg=COL_BG, **kwargs)
        self.app = app

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.heading = tk.Label(
            self,
            text=self.title,
            font=("DejaVu Sans", 26, "bold"),
            bg=COL_BG,
            fg=COL_TEXT,
            anchor="w",
        )
        self.heading.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 8))

        self.content = tk.Frame(self, bg=COL_BG)
        self.content.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))

    def on_show(self) -> None:  # pragma: no cover - hooks for runtime behaviour
        """Hook executed when the screen becomes visible."""

    def on_hide(self) -> None:  # pragma: no cover
        """Hook executed when the screen is hidden."""


class HomeScreen(BaseScreen):
    name = "home"
    title = "Inicio"

    def __init__(self, parent: tk.Misc, app, **kwargs) -> None:
        super().__init__(parent, app, **kwargs)

        hero = Card(self.content)
        hero.pack(fill="both", expand=True)

        header = tk.Frame(hero, bg=COL_CARD)
        header.pack(fill="x", pady=(0, 12))

        text_box = tk.Frame(header, bg=COL_CARD)
        text_box.pack(side="left", fill="both", expand=True)

        title = tk.Label(
            text_box,
            text="Báscula lista",
            font=("DejaVu Sans", 22, "bold"),
            bg=COL_CARD,
            fg=COL_TEXT,
            anchor="w",
            justify=tk.LEFT,
        )
        title.pack(anchor="w", pady=(0, 6))

        subtitle = tk.Label(
            text_box,
            text="Coloca un alimento sobre la bandeja o accede a Ajustes para personalizar tu experiencia.",
            wraplength=520,
            justify=tk.LEFT,
            bg=COL_CARD,
            fg=COL_MUTED,
        )
        subtitle.pack(anchor="w", pady=(0, 12))

        self.mascota = MascotaCanvas(header, width=200, height=200, bg=COL_CARD)
        self.mascota.pack(side="right", padx=(16, 0))

        weight_box = Card(hero)
        weight_box.configure(padding=20)
        weight_box.pack(fill="x", expand=False)

        WeightLabel(weight_box, textvariable=app.weight_text).pack(fill="x")
        tk.Label(
            weight_box,
            textvariable=app.stability_text,
            bg=COL_CARD,
            fg=COL_MUTED,
            font=("DejaVu Sans", 14),
        ).pack(anchor="w", pady=(6, 0))

        actions = tk.Frame(hero, bg=COL_CARD)
        actions.pack(fill="x", pady=(18, 4))

        BigButton(actions, text="Pesar ahora", command=lambda: app.show_screen("scale")).pack(side="left", padx=6)
        GhostButton(actions, text="Ver historial", command=app.show_history, micro=True).pack(side="left", padx=6)

        self.history_card = Card(hero)
        self.history_card.pack(fill="both", expand=True, pady=(16, 0))
        self.history_list = tk.Listbox(
            self.history_card,
            bg=COL_CARD,
            fg=COL_TEXT,
            activestyle="none",
            highlightthickness=0,
            borderwidth=0,
            font=("DejaVu Sans", 13),
        )
        self.history_list.pack(fill="both", expand=True)

    def on_show(self) -> None:  # pragma: no cover - UI update
        self._refresh_history()
        if hasattr(self.mascota, "start"):
            try:
                self.mascota.start()
            except Exception:
                pass

    def on_hide(self) -> None:  # pragma: no cover - UI update
        if hasattr(self.mascota, "stop"):
            try:
                self.mascota.stop()
            except Exception:
                pass

    def _refresh_history(self) -> None:
        self.history_list.delete(0, tk.END)
        for entry in self.app.weight_history:
            ts = entry["ts"].strftime("%H:%M")
            self.history_list.insert(tk.END, f"{ts} · {entry['value']}")


class ScaleScreen(BaseScreen):
    name = "scale"
    title = "Báscula"

    def __init__(self, parent: tk.Misc, app, **kwargs) -> None:
        super().__init__(parent, app, **kwargs)

        card = Card(self.content)
        card.pack(fill="both", expand=True)

        self.weight_lbl = WeightLabel(card, textvariable=app.weight_text, bg=COL_CARD)
        self.weight_lbl.pack(fill="x", padx=6, pady=(6, 12))

        self.status_lbl = tk.Label(card, textvariable=app.stability_text, bg=COL_CARD, fg=COL_MUTED)
        self.status_lbl.pack(anchor="w")

        buttons = tk.Frame(card, bg=COL_CARD)
        buttons.pack(fill="x", pady=18)

        BigButton(buttons, text="Tara", command=app.perform_tare).pack(side="left", expand=True, fill="x", padx=4)
        BigButton(buttons, text="Cero", command=app.perform_zero).pack(side="left", expand=True, fill="x", padx=4)
        GhostButton(buttons, text="Capturar", command=app.capture_weight).pack(side="left", expand=True, fill="x", padx=4)
        GhostButton(buttons, text="📷 Escanear", command=app.open_scanner).pack(side="left", expand=True, fill="x", padx=4)

        info = tk.Label(
            card,
            text="Los valores mostrados se actualizan en tiempo real desde el ESP32.",
            bg=COL_CARD,
            fg=COL_MUTED,
        )
        info.pack(anchor="w", pady=(12, 0))

        self.toast = Toast(card)

    def on_show(self) -> None:  # pragma: no cover - interactive behaviour
        self.app.set_focus_mode(True)

    def on_hide(self) -> None:  # pragma: no cover - interactive behaviour
        self.app.set_focus_mode(False)


class SettingsScreen(BaseScreen):
    name = "settingsmenu"
    title = "Ajustes"

    def __init__(self, parent: tk.Misc, app, **kwargs) -> None:
        super().__init__(parent, app, **kwargs)
        # Import lazily to avoid circular dependency during module import.
        from bascula.ui.screens_tabs_ext import TabbedSettingsMenuScreen

        notebook_screen = TabbedSettingsMenuScreen(self.content, app)
        notebook_screen.pack(fill="both", expand=True)
        self._proxied = notebook_screen

    def on_show(self) -> None:  # pragma: no cover - delegated to proxy
        if hasattr(self._proxied, "on_show"):
            self._proxied.on_show()


# Convenience alias kept for compatibility with older imports.
SettingsMenuScreen = SettingsScreen

