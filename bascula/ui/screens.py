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

from typing import Optional

import tkinter as tk
from tkinter import ttk

from bascula.services.scale import ScaleService
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
    COL_ACCENT,
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

        actions = tk.Frame(hero, bg=COL_CARD)
        actions.pack(fill="x", pady=(18, 4))

        BigButton(actions, text="Pesar ahora", command=lambda: app.show_screen("scale")).pack(side="left", padx=6)
        GhostButton(actions, text="Ver historial", command=app.show_history, micro=True).pack(side="left", padx=6)
        GhostButton(actions, text="Recetas", command=app.open_recipes, micro=True).pack(side="left", padx=6)
        GhostButton(actions, text="⏱ Timer", command=app.open_timer_overlay, micro=True).pack(side="left", padx=6)

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

        self.scale = getattr(app, "reader", None)
        if self.scale is None:
            try:
                self.scale = ScaleService.safe_create(
                    port=str(app.cfg.get("port", "/dev/serial0")),
                    baud=int(app.cfg.get("baud", 115200)),
                    logger=getattr(app, "logger", None),
                )
                if getattr(self.scale, "start", None):
                    try:
                        self.scale.start()
                        if hasattr(app, "_scale_started"):
                            app._scale_started = True
                    except Exception:
                        if getattr(app, "logger", None):
                            app.logger.warning("No se pudo iniciar la báscula", exc_info=True)
                app.reader = self.scale
            except Exception:
                if getattr(app, "logger", None):
                    app.logger.warning("Fallo inicializando báscula en pantalla Pesar", exc_info=True)
                self.scale = ScaleService.safe_create(logger=getattr(app, "logger", None))
                app.reader = self.scale
        elif not getattr(app, "_scale_started", False) and getattr(self.scale, "start", None):
            try:
                self.scale.start()
                app._scale_started = True
            except Exception:
                if getattr(app, "logger", None):
                    app.logger.warning("No se pudo iniciar la báscula existente", exc_info=True)

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

        extras = tk.Frame(card, bg=COL_CARD)
        extras.pack(fill="x", pady=(0, 12))
        GhostButton(extras, text="⭐ Favoritos", command=app.open_favorites, micro=True).pack(side="left", expand=True, fill="x", padx=4)
        GhostButton(extras, text="⏱ Timer", command=app.open_timer_overlay, micro=True).pack(side="left", expand=True, fill="x", padx=4)
        GhostButton(extras, text="🍳 Recetas", command=app.open_recipes, micro=True).pack(side="left", expand=True, fill="x", padx=4)

        info = tk.Label(
            card,
            text="Los valores mostrados se actualizan en tiempo real desde el ESP32.",
            bg=COL_CARD,
            fg=COL_MUTED,
        )
        info.pack(anchor="w", pady=(12, 0))

        self._build_meal_panel(card)

        self.toast = Toast(card)
        try:
            self.app.event_bus.subscribe("meal_updated", self._on_meal_updated)
        except Exception:
            pass

    def on_show(self) -> None:  # pragma: no cover - interactive behaviour
        self.app.set_focus_mode(True)
        self._render_meal({"items": self.app.meal_items, "totals": self.app.get_meal_totals()})

    def on_hide(self) -> None:  # pragma: no cover - interactive behaviour
        self.app.set_focus_mode(False)

    # ------------------------------------------------------------------ Meal UI helpers
    def _build_meal_panel(self, parent: tk.Misc) -> None:
        panel = Card(parent)
        panel.pack(fill="both", expand=True, pady=(16, 0))

        header = tk.Frame(panel, bg=COL_CARD)
        header.pack(fill="x")
        tk.Label(
            header,
            text="Plato actual",
            bg=COL_CARD,
            fg=COL_ACCENT,
            font=("DejaVu Sans", 16, "bold"),
        ).pack(side="left", padx=6)
        GhostButton(header, text="Nueva comida", command=self._start_new_meal, micro=True).pack(side="right", padx=4)

        tree_container = tk.Frame(panel, bg=COL_CARD)
        tree_container.pack(fill="both", expand=True, padx=6, pady=(6, 0))

        style = ttk.Style(self)
        try:
            style.configure(
                "Meal.Treeview",
                background=COL_CARD,
                fieldbackground=COL_CARD,
                foreground=COL_TEXT,
                rowheight=32,
                font=("DejaVu Sans", 13),
            )
            style.configure(
                "Meal.Treeview.Heading",
                background=COL_ACCENT,
                foreground=COL_BG,
                font=("DejaVu Sans", 13, "bold"),
            )
        except Exception:
            pass

        columns = ("alimento", "gramos", "hc", "kcal", "ig", "fuente")
        self.meal_tree = ttk.Treeview(
            tree_container,
            columns=columns,
            show="headings",
            style="Meal.Treeview",
        )
        for col, label in zip(columns, ["Alimento", "g", "HC", "kcal", "IG", "Fuente"]):
            anchor = "e" if col in {"gramos", "hc", "kcal", "ig"} else "w"
            self.meal_tree.heading(col, text=label)
            self.meal_tree.column(col, anchor=anchor, stretch=True, width=80)

        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.meal_tree.yview)
        self.meal_tree.configure(yscrollcommand=scrollbar.set)
        self.meal_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        totals = tk.Frame(panel, bg=COL_CARD)
        totals.pack(fill="x", pady=(8, 0))
        self.total_grams_var = tk.StringVar(value="0 g")
        self.total_carbs_var = tk.StringVar(value="HC 0 g")
        self.total_kcal_var = tk.StringVar(value="0 kcal")
        self.total_ig_var = tk.StringVar(value="IG n/d")

        for var in (self.total_grams_var, self.total_carbs_var, self.total_kcal_var, self.total_ig_var):
            tk.Label(totals, textvariable=var, bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 13, "bold")).pack(
                side="left", padx=6
            )

        actions = tk.Frame(panel, bg=COL_CARD)
        actions.pack(fill="x", pady=(12, 0))
        BigButton(actions, text="Guardar comida", command=self._save_meal, micro=True).pack(
            side="left", expand=True, fill="x", padx=4
        )
        GhostButton(actions, text="Quitar último", command=self._remove_last, micro=True).pack(
            side="left", expand=True, fill="x", padx=4
        )

    def _on_meal_updated(self, payload: Optional[dict]) -> None:
        if payload is None:
            return
        self._render_meal(payload)

    def _render_meal(self, payload: dict) -> None:
        try:
            self.meal_tree.delete(*self.meal_tree.get_children())
        except Exception:
            return
        items = payload.get("items") if isinstance(payload, dict) else []
        if not isinstance(items, list):
            items = []
        for item in items:
            name = item.get("name", "?")
            grams = item.get("grams", 0)
            carbs = item.get("carbs", 0)
            kcal = item.get("kcal", 0)
            ig = item.get("ig", "n/d")
            src = item.get("source", "")
            self.meal_tree.insert("", tk.END, values=(name, grams, carbs, kcal, ig, src))
        totals = payload.get("totals", {}) if isinstance(payload, dict) else {}
        self._update_totals(totals)

    def _update_totals(self, totals: dict) -> None:
        grams = float(totals.get("grams") or 0.0)
        carbs = float(totals.get("carbs") or 0.0)
        kcal = float(totals.get("kcal") or 0.0)
        ig = totals.get("gi")
        self.total_grams_var.set(f"{grams:.1f} g")
        self.total_carbs_var.set(f"HC {carbs:.1f} g")
        self.total_kcal_var.set(f"{kcal:.0f} kcal")
        self.total_ig_var.set(f"IG {ig}" if ig is not None else "IG n/d")

    def _start_new_meal(self) -> None:
        try:
            self.app.reset_meal()
        except Exception:
            pass

    def _save_meal(self) -> None:
        try:
            payload = self.app.save_current_meal()
            if payload:
                self.app.reset_meal()
        except Exception:
            self.toast.show("No se pudo guardar", 1500)

    def _remove_last(self) -> None:
        try:
            self.app.remove_last_meal_item()
        except Exception:
            pass


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

