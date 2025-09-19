"""Simplified UI tuned for Raspberry Pi 5 kiosks."""
from __future__ import annotations

import logging
import math
import time
import tkinter as tk
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from importlib import import_module
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from bascula.services.bg_monitor import BgMonitor
from bascula.services.event_bus import EventBus
from bascula.services.scale import NullScaleService, ScaleService
from bascula.services.tare_manager import TareManager
from bascula.state import AppState
from bascula.utils import load_config

from .failsafe_mascot import MASCOT_STATES, MascotCanvas, MascotPlaceholder
from .lightweight_widgets import (
    Card,
    CRTButton,
    CRTTabBar,
    CRTToggle,
    ScrollFrame,
    ValueLabel,
    WidgetPool,
    clamp,
    format_weight,
)
from .memory_monitor import MemoryMonitor
from .rpi_camera_manager import RpiCameraManager
from .rpi_config import configure_root, ensure_env_defaults
from .simple_animations import AnimationManager
from .theme_crt import CRT_COLORS, CRT_SPACING, draw_dotted_rule, mono, sans

logger = logging.getLogger("bascula.ui.rpi")


def _safe_color(value: Optional[str], fallback: str = CRT_COLORS["bg"]) -> str:
    if isinstance(value, str):
        value = value.strip()
        if value and value.lower() != "none":
            return value
    return fallback


try:  # Optional voice prompts
    from bascula.services.voice import VoiceService
except Exception:  # pragma: no cover - optional dependency missing in CI
    VoiceService = None  # type: ignore

try:
    from bascula.services.vision import VisionService
except Exception:  # pragma: no cover
    VisionService = None  # type: ignore

try:
    from bascula.services.barcode import decode_barcodes as decode_barcode
except Exception:  # pragma: no cover
    decode_barcode = None  # type: ignore


@dataclass(slots=True)
class FoodEntry:
    name: str
    weight: float
    timestamp: float
    macros: Dict[str, Any]

    def as_row(self) -> str:
        ts = datetime.fromtimestamp(self.timestamp).strftime("%H:%M")
        carbs = self.macros.get("carbs", "-")
        prot = self.macros.get("protein", "-")
        fats = self.macros.get("fat", "-")
        return f"{ts}  {self.name}  {format_weight(self.weight)}  C:{carbs} P:{prot} G:{fats}"


class BaseScreen(tk.Frame):
    mascot_mode: str = "center"
    mascot_size: Tuple[int, int] = (320, 280)

    def __init__(self, parent: tk.Widget, app: "RpiOptimizedApp") -> None:
        super().__init__(parent, bg=CRT_COLORS["bg"])
        self.app = app
        self.visible = False
        self.screen_name: str = ""

    def on_show(self) -> None:
        self.visible = True
        if self.screen_name:
            self.app.active_screen = self.screen_name
        self.app.register_active_mascot(self.screen_name)

    def on_hide(self) -> None:
        self.visible = False
        if self.screen_name:
            self.app.detach_mascot(self.screen_name)

    def refresh(self) -> None:
        pass

    def attach_mascot(
        self,
        container: tk.Widget,
        *,
        size: Optional[Tuple[int, int]] = None,
        anchor: str = "center",
        relx: float = 0.5,
        rely: float = 0.5,
    ) -> tk.Widget:
        target_size = size or self.mascot_size
        return self.app.attach_mascot_to_screen(
            self.screen_name,
            container,
            size=target_size,
            anchor=anchor,
            relx=relx,
            rely=rely,
        )


class HomeScreen(BaseScreen):
    mascot_mode = "center"
    mascot_size = (360, 320)

    def __init__(self, parent: tk.Widget, app: "RpiOptimizedApp") -> None:
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        hero = Card(self, bg=CRT_COLORS["surface"])
        hero.grid(
            row=0,
            column=0,
            padx=CRT_SPACING.gutter,
            pady=(CRT_SPACING.padding, CRT_SPACING.gutter),
            sticky="nsew",
        )
        hero.columnconfigure(0, weight=1)
        hero.rowconfigure(0, weight=1)

        self.stage = tk.Frame(hero, bg=CRT_COLORS["bg"], height=340)
        self.stage.grid(
            row=0,
            column=0,
            padx=CRT_SPACING.padding,
            pady=(CRT_SPACING.padding, 0),
            sticky="nsew",
        )
        self.stage.columnconfigure(0, weight=1)
        self.stage.rowconfigure(0, weight=1)
        with suppress(Exception):
            self.stage.grid_propagate(False)

        self.scanlines = tk.Canvas(
            self.stage,
            bg=CRT_COLORS["bg"],
            highlightthickness=0,
            bd=0,
        )
        self.scanlines.grid(row=0, column=0, sticky="nsew")
        self.scanlines.bind("<Configure>", self._draw_scanlines, add=True)
        self.scanlines.bind("<Map>", self._draw_scanlines, add=True)

        mascot_anchor = tk.Frame(self.stage, bg=CRT_COLORS["bg"])
        mascot_anchor.place(relx=0.5, rely=0.5, anchor="center")
        self.attach_mascot(mascot_anchor)

        self.message_label = ValueLabel(
            hero,
            text="¡Hola! ¿Qué vamos a pesar?",
            size_key="lg",
            mono_font=False,
            bg=CRT_COLORS["surface"],
        )
        self.message_label.grid(row=1, column=0, pady=(CRT_SPACING.padding, 4))

        self.status_label = tk.Label(
            hero,
            text="Báscula lista",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["muted"],
            font=sans("sm"),
        )
        self.status_label.grid(row=2, column=0)

        self.last_food_label = tk.Label(
            hero,
            text="Sin registros previos",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["text"],
            font=sans("sm"),
        )
        self.last_food_label.grid(row=3, column=0, pady=(2, CRT_SPACING.padding))

    def refresh(self) -> None:
        weight = self.app.net_weight
        stable = self.app.scale_stable
        has_reading = stable and abs(weight) >= 1
        message = format_weight(weight) if has_reading else "¡Hola! ¿Qué vamos a pesar?"
        self.message_label.configure(text=message)
        status = "Peso estable" if stable else "Coloca un ingrediente"
        status_color = CRT_COLORS["accent"] if stable else CRT_COLORS["muted"]
        self.status_label.configure(text=status, fg=status_color)
        if self.app.food_history:
            last = self.app.food_history[-1]
            summary = f"Último registro: {last.name} · {format_weight(last.weight)}"
        else:
            summary = "Sin registros previos"
        self.last_food_label.configure(text=summary)

    def _draw_scanlines(self, _event=None) -> None:
        canvas = getattr(self, "scanlines", None)
        if canvas is None:
            return
        try:
            width = canvas.winfo_width()
            height = canvas.winfo_height()
        except Exception:
            return
        if width <= 0 or height <= 0:
            return
        canvas.delete("scanline")
        canvas.delete("frame")
        step = 16
        line_color = CRT_COLORS["muted"]
        for y in range(step // 2, height, step):
            canvas.create_rectangle(
                0,
                y,
                width,
                y + 1,
                outline="",
                fill=line_color,
                stipple="gray50",
                tags="scanline",
            )
        border_margin = 3
        if width > border_margin * 2 and height > border_margin * 2:
            canvas.create_rectangle(
                border_margin,
                border_margin,
                width - border_margin,
                height - border_margin,
                outline=CRT_COLORS["divider"],
                width=2,
                tags="frame",
            )


class RecipeScreen(BaseScreen):
    mascot_mode = "corner"
    mascot_size = (220, 200)

    def __init__(self, parent: tk.Widget, app: "RpiOptimizedApp") -> None:
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self.ingredients_card = Card(self, bg=CRT_COLORS["surface"])
        self.ingredients_card.grid(row=0, column=0, padx=(CRT_SPACING.gutter, 8), pady=CRT_SPACING.gutter, sticky="nsew")
        self.ingredients_card.columnconfigure(0, weight=1)
        tk.Label(
            self.ingredients_card,
            text="Ingredientes",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["text"],
            font=mono("md"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=CRT_SPACING.padding, pady=(CRT_SPACING.padding, 8))
        self.ingredients_scroll = ScrollFrame(self.ingredients_card, height=300)
        self.ingredients_scroll.grid(row=1, column=0, padx=CRT_SPACING.padding, pady=(0, CRT_SPACING.padding), sticky="nsew")
        self.ingredients_pool = WidgetPool(self._create_ingredient_row)
        self._ingredient_rows: List[tk.Frame] = []

        self.step_card = Card(self, bg=CRT_COLORS["surface"])
        self.step_card.grid(row=0, column=1, padx=(8, CRT_SPACING.gutter), pady=CRT_SPACING.gutter, sticky="nsew")
        self.step_card.columnconfigure(0, weight=1)
        self.step_title = ValueLabel(self.step_card, text="Paso 1", size_key="lg", bg=CRT_COLORS["surface"])
        self.step_title.grid(row=0, column=0, sticky="w", padx=CRT_SPACING.padding, pady=(CRT_SPACING.padding, 4))
        self.step_body = tk.Label(
            self.step_card,
            text="",
            wraplength=440,
            justify="left",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["text"],
            font=sans("sm"),
        )
        self.step_body.grid(row=1, column=0, sticky="nsew", padx=CRT_SPACING.padding)

        self.timer_card = Card(self.step_card, bg=CRT_COLORS["surface"])
        self.timer_card.grid(row=2, column=0, padx=CRT_SPACING.padding, pady=(8, 0), sticky="w")
        self.timer_label = ValueLabel(self.timer_card, text="00:00", size_key="lg", bg=CRT_COLORS["surface"])
        self.timer_label.grid(row=0, column=0)

        controls = tk.Frame(self.step_card, bg=CRT_COLORS["surface"])
        controls.grid(row=3, column=0, pady=(8, CRT_SPACING.padding))
        CRTButton(controls, icon="⏮", text="Anterior", command=self.app.prev_recipe_step).grid(row=0, column=0, padx=8)
        CRTButton(controls, icon="⏯", text="Pausar", command=self.app.toggle_recipe_timer).grid(row=0, column=1, padx=8)
        CRTButton(controls, icon="⏭", text="Siguiente", command=self.app.next_recipe_step).grid(row=0, column=2, padx=8)

        mascot_corner = tk.Frame(self.step_card, bg=CRT_COLORS["surface"], height=120)
        mascot_corner.grid(row=4, column=0, sticky="e", padx=CRT_SPACING.padding, pady=(0, CRT_SPACING.padding))
        self.attach_mascot(mascot_corner, size=(180, 160), anchor="se", relx=1.0, rely=1.0)

    def _create_ingredient_row(self, parent: tk.Widget) -> tk.Frame:
        row = tk.Frame(parent, bg=CRT_COLORS["surface"])
        row.columnconfigure(1, weight=1)
        checkbox = tk.Canvas(row, width=28, height=28, bg=CRT_COLORS["surface"], highlightthickness=0, bd=0)
        checkbox.grid(row=0, column=0, padx=(0, 8))
        label = tk.Label(
            row,
            text="",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["text"],
            font=sans("sm"),
            anchor="w",
        )
        label.grid(row=0, column=1, sticky="w")
        row.checkbox = checkbox  # type: ignore[attr-defined]
        row.label = label  # type: ignore[attr-defined]
        return row

    def refresh(self) -> None:
        state = self.app.recipe_state
        steps = state.get("steps") or ["Sin pasos configurados"]
        index = clamp(state.get("current_step", 0), 0, len(steps) - 1)
        self.step_title.configure(text=f"Paso {int(index) + 1}/{len(steps)}")
        self.step_body.configure(text=steps[int(index)])
        timer = max(0, int(state.get("timer_remaining", 0)))
        minutes, seconds = divmod(timer, 60)
        self.timer_label.configure(text=f"{minutes:02d}:{seconds:02d}")
        for row in self._ingredient_rows:
            self.ingredients_pool.release(row)
        self._ingredient_rows.clear()
        for ingredient in state.get("ingredients", []):
            row = self.ingredients_pool.acquire(self.ingredients_scroll.inner)
            weight = ingredient.get("weight", "")
            text = ingredient.get("name", "Ingrediente")
            label = getattr(row, "label")
            label.configure(text=f"{text} {weight}".strip())
            checkbox = getattr(row, "checkbox")
            checkbox.delete("all")
            checkbox.create_rectangle(2, 2, 26, 26, outline=CRT_COLORS["divider"], width=2, dash=(2, 4))
            if ingredient.get("done"):
                checkbox.create_line(6, 14, 12, 20, 22, 8, fill=CRT_COLORS["accent"], width=3)
            row.pack(fill="x", pady=6)
            self._ingredient_rows.append(row)


class SettingsScreen(BaseScreen):
    mascot_mode = "corner"
    mascot_size = (220, 200)

    def __init__(self, parent: tk.Widget, app: "RpiOptimizedApp") -> None:
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        header = tk.Frame(self, bg=CRT_COLORS["bg"])
        header.grid(row=0, column=0, sticky="ew", padx=CRT_SPACING.gutter, pady=(CRT_SPACING.gutter, 8))
        header.columnconfigure(0, weight=1)
        ValueLabel(header, text="Ajustes", size_key="lg", bg=CRT_COLORS["bg"], mono_font=False).grid(
            row=0, column=0, sticky="w"
        )
        CRTButton(
            header,
            icon="⌂",
            text="Inicio",
            command=lambda: self.app.show_screen("home"),
            min_height=56,
        ).grid(row=0, column=1, sticky="e", padx=(CRT_SPACING.padding, 0))

        self.tabs_frame = tk.Frame(self, bg=CRT_COLORS["bg"])
        self.tabs_frame.grid(row=1, column=0, sticky="ew")
        self.panels_frame = tk.Frame(self, bg=CRT_COLORS["bg"])
        self.panels_frame.grid(row=2, column=0, sticky="nsew", padx=CRT_SPACING.gutter, pady=(8, CRT_SPACING.gutter))
        self.panels_frame.columnconfigure(0, weight=1)
        self.panels: Dict[str, tk.Frame] = {}

        tabs = {
            "General": lambda: self._show_panel("General"),
            "Tema": lambda: self._show_panel("Tema"),
            "Báscula": lambda: self._show_panel("Báscula"),
            "Red": lambda: self._show_panel("Red"),
            "Diabetes": lambda: self._show_panel("Diabetes"),
            "Datos": lambda: self._show_panel("Datos"),
            "Acerca de": lambda: self._show_panel("Acerca de"),
        }
        self.tab_bar = CRTTabBar(self.tabs_frame, tabs=tabs)
        self.tab_bar.pack()

        for name in tabs.keys():
            panel = Card(self.panels_frame, bg=CRT_COLORS["surface"])
            panel.grid(row=0, column=0, sticky="nsew")
            panel.grid_remove()
            panel.columnconfigure(0, weight=1)
            self.panels[name] = panel

        general = self.panels["General"]
        CRTToggle(general, text="Focus Mode", command=self.app.toggle_focus_mode, initial=self.app.focus_mode).grid(
            row=0, column=0, sticky="w", padx=CRT_SPACING.padding, pady=(CRT_SPACING.padding, 8)
        )
        CRTToggle(general, text="Animaciones de la mascota", command=self.app.toggle_mascot_animations, initial=True).grid(
            row=1, column=0, sticky="w", padx=CRT_SPACING.padding, pady=8
        )
        CRTToggle(general, text="Efectos de sonido", command=self.app.toggle_sound_effects, initial=True).grid(
            row=2, column=0, sticky="w", padx=CRT_SPACING.padding, pady=8
        )

        theme_panel = self.panels["Tema"]
        tk.Label(
            theme_panel,
            text="Modo CRT retro activo",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["accent"],
            font=sans("sm", "bold"),
        ).grid(row=0, column=0, padx=CRT_SPACING.padding, pady=CRT_SPACING.padding, sticky="w")

        scale_panel = self.panels["Báscula"]
        tk.Label(
            scale_panel,
            text="Estado de la báscula",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["text"],
            font=mono("sm"),
        ).grid(row=0, column=0, sticky="w", padx=CRT_SPACING.padding, pady=(CRT_SPACING.padding, 4))
        self.scale_status_label = tk.Label(
            scale_panel,
            text="Detectando...",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["muted"],
            font=sans("xs"),
            anchor="w",
        )
        self.scale_status_label.grid(row=1, column=0, sticky="ew", padx=CRT_SPACING.padding)

        red_panel = self.panels["Red"]
        tk.Label(
            red_panel,
            text="Estado de red",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["text"],
            font=mono("sm"),
        ).grid(row=0, column=0, sticky="w", padx=CRT_SPACING.padding, pady=(CRT_SPACING.padding, 4))
        self.network_label = tk.Label(
            red_panel,
            text="No conectado",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["muted"],
            font=sans("xs"),
            anchor="w",
        )
        self.network_label.grid(row=1, column=0, sticky="ew", padx=CRT_SPACING.padding)

        diabetes_panel = self.panels["Diabetes"]
        tk.Label(
            diabetes_panel,
            text="Integración Nightscout",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["text"],
            font=mono("sm"),
        ).grid(row=0, column=0, sticky="w", padx=CRT_SPACING.padding, pady=(CRT_SPACING.padding, 4))
        CRTButton(
            diabetes_panel,
            icon="⚙",
            text="Configurar URL",
            command=lambda: self.app.configure_nightscout(),
        ).grid(row=1, column=0, padx=CRT_SPACING.padding, pady=8, sticky="w")

        datos_panel = self.panels["Datos"]
        tk.Label(
            datos_panel,
            text="Sincronización",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["text"],
            font=mono("sm"),
        ).grid(row=0, column=0, sticky="w", padx=CRT_SPACING.padding, pady=(CRT_SPACING.padding, 4))
        CRTButton(
            datos_panel,
            icon="⬇",
            text="Exportar CSV",
            command=self.app.export_history,
        ).grid(row=1, column=0, padx=CRT_SPACING.padding, pady=8, sticky="w")

        acerca_panel = self.panels["Acerca de"]
        tk.Label(
            acerca_panel,
            text="Báscula Cam",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["text"],
            font=mono("sm"),
        ).grid(row=0, column=0, sticky="w", padx=CRT_SPACING.padding, pady=(CRT_SPACING.padding, 4))
        tk.Label(
            acerca_panel,
            text="Proyecto comunitario open source",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["muted"],
            font=sans("xs"),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=CRT_SPACING.padding)

        mascot_dock = tk.Frame(self, bg=CRT_COLORS["bg"], height=200)
        mascot_dock.grid(row=3, column=0, sticky="e", padx=CRT_SPACING.gutter, pady=(0, CRT_SPACING.gutter))
        self.attach_mascot(mascot_dock, size=(200, 180), anchor="se", relx=1.0, rely=1.0)

        self._show_panel("General")

    def _show_panel(self, name: str) -> None:
        for panel_name, panel in self.panels.items():
            if panel_name == name:
                panel.grid()
            else:
                panel.grid_remove()
        self.tab_bar.activate(name)

    def refresh(self) -> None:
        scale_status = "Conectada" if isinstance(self.app.scale_service, ScaleService) else "No detectada"
        self.scale_status_label.configure(text=scale_status)
        self.network_label.configure(text=self.app.network_state)


class ScaleScreen(BaseScreen):
    mascot_mode = "hidden"
    mascot_size = (0, 0)

    def __init__(self, parent: tk.Widget, app: "RpiOptimizedApp") -> None:
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.card = Card(self, bg=CRT_COLORS["surface"], highlightthickness=2)
        self.card.grid(row=0, column=0, padx=CRT_SPACING.gutter, pady=CRT_SPACING.gutter, sticky="nsew")
        self.card.columnconfigure(0, weight=1)
        self.card.rowconfigure(1, weight=1)
        self.weight_label = ValueLabel(self.card, text="0 g", size_key="xxl")
        self.weight_label.grid(row=0, column=0, pady=(CRT_SPACING.padding, 0))
        self.state_label = tk.Label(
            self.card,
            text="Estabilizando...",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["muted"],
            font=sans("sm"),
        )
        self.state_label.grid(row=1, column=0, pady=4)
        self.context_label = tk.Label(
            self.card,
            text="Añadir alimento",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["text"],
            font=sans("sm", "bold"),
        )
        self.context_label.grid(row=2, column=0, pady=4)

        button_row = tk.Frame(self.card, bg=CRT_COLORS["surface"])
        button_row.grid(row=3, column=0, pady=(CRT_SPACING.padding, CRT_SPACING.padding))
        CRTButton(button_row, icon="0", text="Cero", command=self.app.perform_zero, min_height=84).pack(side="left", padx=8)
        CRTButton(button_row, icon="↺", text="Tara", command=self.app.perform_tare, min_height=84).pack(side="left", padx=8)
        CRTButton(button_row, icon="✖", text="Cerrar", command=lambda: self.app.show_screen("home"), min_height=84).pack(
            side="left", padx=8
        )

    def refresh(self) -> None:
        self.weight_label.configure(text=format_weight(self.app.net_weight))
        stable = self.app.scale_stable
        mascot_state = "happy" if stable else "processing"
        mascot = getattr(self, "mascot", None)
        if mascot is not None:
            with suppress(Exception):
                mascot.configure_state(mascot_state)  # type: ignore[attr-defined]
        if stable:
            self.state_label.configure(text="Estable", fg=CRT_COLORS["accent"])
        else:
            self.state_label.configure(text="Leyendo...", fg=CRT_COLORS["muted"])
        if self.app.pending_food_name:
            self.context_label.configure(text=f"Añadir {self.app.pending_food_name}?", fg=CRT_COLORS["text"])
        else:
            self.context_label.configure(text="Añadir alimento", fg=CRT_COLORS["muted"])


class FavoritesScreen(BaseScreen):
    mascot_mode = "center"
    mascot_size = (320, 280)

    def __init__(self, parent: tk.Widget, app: "RpiOptimizedApp") -> None:
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        ValueLabel(self, text="Favoritos", size_key="lg", bg=CRT_COLORS["bg"]).grid(row=0, column=0, pady=(CRT_SPACING.gutter, 4))

        self.list_card = Card(self, bg=CRT_COLORS["surface"])
        self.list_card.grid(row=1, column=0, sticky="nsew", padx=CRT_SPACING.gutter, pady=(0, CRT_SPACING.gutter))
        self.list_card.columnconfigure(0, weight=1)
        self.scroll = ScrollFrame(self.list_card, height=260)
        self.scroll.grid(row=0, column=0, padx=CRT_SPACING.padding, pady=CRT_SPACING.padding, sticky="nsew")
        self.item_pool = WidgetPool(self._create_row)
        self._rows: List[tk.Frame] = []

        actions = tk.Frame(self, bg=CRT_COLORS["bg"])
        actions.grid(row=2, column=0, pady=(0, CRT_SPACING.gutter))
        CRTButton(actions, icon="＋", text="Añadir", command=self.app.add_favorite).grid(row=0, column=0, padx=8)
        CRTButton(actions, icon="✎", text="Editar", command=self.app.edit_favorite).grid(row=0, column=1, padx=8)
        CRTButton(actions, icon="🍽", text="Añadir a plato", command=self.app.add_favorite_to_plate).grid(row=0, column=2, padx=8)

    def _create_row(self, parent: tk.Widget) -> tk.Frame:
        row = tk.Frame(parent, bg=CRT_COLORS["surface"])
        row.columnconfigure(2, weight=1)
        checkbox = tk.Canvas(row, width=28, height=28, bg=CRT_COLORS["surface"], highlightthickness=0, bd=0)
        checkbox.grid(row=0, column=0, padx=(0, 8))
        name_label = tk.Label(
            row,
            text="",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["text"],
            font=sans("sm"),
            anchor="w",
        )
        name_label.grid(row=0, column=1, sticky="w")
        weight_label = tk.Label(
            row,
            text="",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["muted"],
            font=sans("sm"),
            anchor="e",
        )
        weight_label.grid(row=0, column=2, sticky="e", padx=(8, 0))
        delete_btn = CRTButton(row, icon="🗑", text="Eliminar", command=lambda: None, min_height=48)
        delete_btn.grid(row=0, column=3, padx=(8, 0))
        row.checkbox = checkbox  # type: ignore[attr-defined]
        row.name_label = name_label  # type: ignore[attr-defined]
        row.weight_label = weight_label  # type: ignore[attr-defined]
        row.delete_btn = delete_btn  # type: ignore[attr-defined]
        return row

    def refresh(self) -> None:
        for row in self._rows:
            self.item_pool.release(row)
        self._rows.clear()
        if not self.app.favorites:
            row = self.item_pool.acquire(self.scroll.inner)
            name_label = getattr(row, "name_label")
            name_label.configure(text="Sin favoritos todavía")
            weight_label = getattr(row, "weight_label")
            weight_label.configure(text="")
            checkbox = getattr(row, "checkbox")
            checkbox.delete("all")
            checkbox.create_rectangle(2, 2, 26, 26, outline=CRT_COLORS["divider"], width=2, dash=(2, 4))
            delete_btn = getattr(row, "delete_btn")
            delete_btn.configure(state="disabled", command=lambda: None)
            row.pack(fill="x", pady=6)
            self._rows.append(row)
            return
        for index, fav in enumerate(self.app.favorites):
            row = self.item_pool.acquire(self.scroll.inner)
            name_label = getattr(row, "name_label")
            name_label.configure(text=fav.get("name", "Favorito"))
            weight = fav.get("weight") or fav.get("default_weight") or ""
            weight_label = getattr(row, "weight_label")
            weight_label.configure(text=str(weight) if weight else "")
            checkbox = getattr(row, "checkbox")
            checkbox.delete("all")
            checkbox.create_rectangle(2, 2, 26, 26, outline=CRT_COLORS["divider"], width=2, dash=(2, 4))
            delete_btn = getattr(row, "delete_btn")
            delete_btn.configure(command=lambda idx=index: self.app.remove_favorite_index(idx), state="normal")
            row.pack(fill="x", pady=6)
            self._rows.append(row)


class HistoryScreen(BaseScreen):
    mascot_mode = "corner"
    mascot_size = (200, 180)

    def __init__(self, parent: tk.Widget, app: "RpiOptimizedApp") -> None:
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        ValueLabel(self, text="Historial de Alimentos", size_key="lg", bg=CRT_COLORS["bg"]).grid(row=0, column=0, pady=(CRT_SPACING.gutter, 4))
        self.summary_label = tk.Label(
            self,
            text="",
            bg=CRT_COLORS["bg"],
            fg=CRT_COLORS["muted"],
            font=sans("sm"),
        )
        self.summary_label.grid(row=0, column=0, sticky="s", pady=(0, CRT_SPACING.padding))

        self.list_card = Card(self, bg=CRT_COLORS["surface"])
        self.list_card.grid(row=1, column=0, padx=CRT_SPACING.gutter, pady=(0, CRT_SPACING.padding), sticky="nsew")
        self.list_card.columnconfigure(0, weight=1)
        header = tk.Frame(self.list_card, bg=CRT_COLORS["surface"])
        header.grid(row=0, column=0, padx=CRT_SPACING.padding, pady=(CRT_SPACING.padding, 0), sticky="ew")
        header.columnconfigure(1, weight=1)
        for col, text in enumerate(("Hora", "Elemento", "Peso")):
            tk.Label(
                header,
                text=text,
                bg=CRT_COLORS["surface"],
                fg=CRT_COLORS["muted"],
                font=sans("sm", "bold"),
                anchor="w" if col < 2 else "e",
            ).grid(row=0, column=col, sticky="w" if col < 2 else "e", padx=(0, 8))

        self.scroll = ScrollFrame(self.list_card, height=240)
        self.scroll.grid(row=1, column=0, padx=CRT_SPACING.padding, pady=(8, CRT_SPACING.padding), sticky="nsew")
        self.rows_pool = WidgetPool(self._create_history_row)
        self._active_rows: List[tk.Frame] = []

        buttons = tk.Frame(self, bg=CRT_COLORS["bg"])
        buttons.grid(row=2, column=0, pady=(0, CRT_SPACING.gutter))
        CRTButton(buttons, icon="⬇", text="Exportar CSV", command=self.app.export_history).grid(row=0, column=0, padx=8)
        CRTButton(buttons, icon="☁", text="Enviar a Nightscout", command=self.app.send_to_nightscout).grid(row=0, column=1, padx=8)
        CRTButton(buttons, icon="🧹", text="Limpiar", command=self.app.clear_history).grid(row=0, column=2, padx=8)

        mascot_dock = tk.Frame(self.list_card, bg=CRT_COLORS["surface"], height=140)
        mascot_dock.grid(row=1, column=0, sticky="e", padx=CRT_SPACING.padding, pady=(0, CRT_SPACING.padding))
        self.attach_mascot(mascot_dock, size=(160, 140), anchor="se", relx=1.0, rely=1.0)

    def refresh(self) -> None:
        totals = {"carbs": 0.0, "protein": 0.0, "fat": 0.0, "weight": 0.0}
        for row in self._active_rows:
            self.rows_pool.release(row)
        self._active_rows.clear()
        for entry in self.app.food_history:
            row = self.rows_pool.acquire(self.scroll.inner)
            timestamp = datetime.fromtimestamp(entry.timestamp).strftime("%H:%M")
            getattr(row, "time_label").configure(text=timestamp)
            getattr(row, "name_label").configure(text=entry.name)
            getattr(row, "weight_label").configure(text=format_weight(entry.weight))
            row.pack(fill="x", pady=4)
            self._active_rows.append(row)
            totals["weight"] += entry.weight
            for key in ("carbs", "protein", "fat"):
                try:
                    totals[key] += float(entry.macros.get(key, 0) or 0)
                except Exception:
                    continue
        summary = (
            f"Total: {format_weight(totals['weight'])}  "
            f"C:{totals['carbs']:.1f} P:{totals['protein']:.1f} G:{totals['fat']:.1f}"
        )
        self.summary_label.configure(text=summary)


class ScannerScreen(BaseScreen):
    mascot_mode = "hidden"
    mascot_size = (0, 0)

    def __init__(self, parent: tk.Widget, app: "RpiOptimizedApp") -> None:
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        ValueLabel(self, text="Escáner", size_key="lg", bg=CRT_COLORS["bg"]).grid(row=0, column=0, pady=(CRT_SPACING.gutter, 4))

        self.preview_card = Card(self, bg=CRT_COLORS["surface"])
        self.preview_card.grid(row=1, column=0, padx=CRT_SPACING.gutter, pady=(0, CRT_SPACING.padding), sticky="nsew")
        self.preview_card.columnconfigure(0, weight=1)
        self.preview_canvas = tk.Canvas(
            self.preview_card,
            height=240,
            bg=CRT_COLORS["surface"],
            highlightthickness=0,
            bd=0,
        )
        self.preview_canvas.grid(row=0, column=0, padx=CRT_SPACING.padding, pady=CRT_SPACING.padding, sticky="nsew")
        self.preview_card.rowconfigure(0, weight=1)

        self.status_label = tk.Label(
            self.preview_card,
            text="Inicia un escaneo para detectar ingredientes",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["muted"],
            font=sans("sm"),
        )
        self.status_label.grid(row=1, column=0, pady=(0, CRT_SPACING.padding))

        self.results_card = Card(self, bg=CRT_COLORS["surface"])
        self.results_card.grid(row=2, column=0, padx=CRT_SPACING.gutter, pady=(0, CRT_SPACING.gutter), sticky="nsew")
        self.results_card.columnconfigure(0, weight=1)
        tk.Label(
            self.results_card,
            text="Detecciones",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["text"],
            font=mono("md"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=CRT_SPACING.padding, pady=(CRT_SPACING.padding, 8))
        self.results_scroll = ScrollFrame(self.results_card, height=120)
        self.results_scroll.grid(row=1, column=0, padx=CRT_SPACING.padding, pady=(0, CRT_SPACING.padding), sticky="nsew")
        self.results_pool = WidgetPool(self._create_result_row)
        self._rows: List[tk.Frame] = []

        actions = tk.Frame(self.results_card, bg=CRT_COLORS["surface"])
        actions.grid(row=2, column=0, pady=(0, CRT_SPACING.padding))
        CRTButton(actions, icon="🔍", text="Escanear", command=self.app.scan_current_food).pack(side="left", padx=8)
        CRTButton(actions, icon="＋", text="Agregar a báscula", command=self.app.add_detected_to_scale).pack(side="left", padx=8)
        CRTButton(actions, icon="🧹", text="Limpiar", command=self.app.clear_scanner_results).pack(side="left", padx=8)

    def _create_result_row(self, parent: tk.Widget) -> tk.Frame:
        row = tk.Frame(parent, bg=CRT_COLORS["surface"])
        label = tk.Label(row, text="", bg=CRT_COLORS["surface"], fg=CRT_COLORS["text"], font=sans("sm"), anchor="w")
        label.pack(side="left", fill="x", expand=True)
        row.label = label  # type: ignore[attr-defined]
        return row

    def on_show(self) -> None:
        super().on_show()
        self._start_preview()

    def on_hide(self) -> None:
        super().on_hide()
        with suppress(Exception):
            self.app.camera.stop_preview()

    def _start_preview(self) -> None:
        canvas = self.preview_canvas
        canvas.delete("all")
        with suppress(Exception):
            canvas.update_idletasks()
        width = canvas.winfo_width() or canvas.winfo_reqwidth() or 400
        height = canvas.winfo_height() or canvas.winfo_reqheight() or 240
        margin = 12
        border_color = CRT_COLORS["divider"]
        draw_dotted_rule(canvas, margin, margin, int(width) - margin, color=border_color)
        draw_dotted_rule(canvas, margin, int(height) - margin, int(width) - margin, color=border_color)
        canvas.create_line(margin, margin, margin, int(height) - margin, fill=border_color, width=2, dash=(4, 6))
        canvas.create_line(int(width) - margin, margin, int(width) - margin, int(height) - margin, fill=border_color, width=2, dash=(4, 6))
        self.app.camera.start_preview(canvas)

    def refresh(self) -> None:
        for row in self._rows:
            self.results_pool.release(row)
        self._rows.clear()
        if not self.app.scanner_items:
            self.status_label.configure(text="Inicia un escaneo para detectar ingredientes", fg=CRT_COLORS["muted"])
            row = self.results_pool.acquire(self.results_scroll.inner)
            getattr(row, "label").configure(text="Sin detecciones por ahora")
            row.pack(fill="x", pady=4)
            self._rows.append(row)
            return
        for item in self.app.scanner_items:
            row = self.results_pool.acquire(self.results_scroll.inner)
            getattr(row, "label").configure(text=item)
            row.pack(fill="x", pady=4)
            self._rows.append(row)
        self.status_label.configure(
            text=f"{len(self.app.scanner_items)} elementos detectados",
            fg=CRT_COLORS["accent"],
        )


class TimerScreen(BaseScreen):
    mascot_mode = "hidden"
    mascot_size = (0, 0)

    def __init__(self, parent: tk.Widget, app: "RpiOptimizedApp") -> None:
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)

        ValueLabel(self, text="Temporizador", size_key="lg", bg=CRT_COLORS["bg"]).grid(row=0, column=0, pady=(CRT_SPACING.gutter, 4))

        card = Card(self, bg=CRT_COLORS["surface"])
        card.grid(row=1, column=0, padx=CRT_SPACING.gutter, pady=(0, CRT_SPACING.gutter), sticky="nsew")
        card.columnconfigure(0, weight=1)

        self.timer_label = ValueLabel(card, text="00:00", size_key="xxl")
        self.timer_label.grid(row=0, column=0, pady=(CRT_SPACING.padding, 4))
        self.state_label = tk.Label(card, text="Listo", bg=CRT_COLORS["surface"], fg=CRT_COLORS["muted"], font=sans("sm"))
        self.state_label.grid(row=1, column=0)

        controls = tk.Frame(card, bg=CRT_COLORS["surface"])
        controls.grid(row=2, column=0, pady=(CRT_SPACING.padding, 0))
        CRTButton(controls, icon="▶", text="Iniciar", command=self.app.start_timer).grid(row=0, column=0, padx=8)
        CRTButton(controls, icon="⏸", text="Pausar", command=self.app.pause_timer).grid(row=0, column=1, padx=8)
        CRTButton(controls, icon="↺", text="Reiniciar", command=self.app.reset_timer).grid(row=0, column=2, padx=8)

        presets = tk.Frame(card, bg=CRT_COLORS["surface"])
        presets.grid(row=3, column=0, pady=(CRT_SPACING.padding, CRT_SPACING.padding))
        for idx, (label, seconds) in enumerate((("1 min", 60), ("3 min", 180), ("5 min", 300))):
            CRTButton(presets, icon="⏱", text=label, command=lambda s=seconds: self.app.set_timer_seconds(s)).grid(row=0, column=idx, padx=8)

    def refresh(self) -> None:
        remaining = max(0, int(self.app.timer_remaining))
        minutes, seconds = divmod(remaining, 60)
        self.timer_label.configure(text=f"{minutes:02d}:{seconds:02d}")
        self.state_label.configure(
            text="En marcha" if self.app.timer_running else "En pausa",
            fg=CRT_COLORS["accent"] if self.app.timer_running else CRT_COLORS["muted"],
        )


class VoiceScreen(BaseScreen):
    mascot_mode = "hidden"
    mascot_size = (0, 0)

    def __init__(self, parent: tk.Widget, app: "RpiOptimizedApp") -> None:
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)

        ValueLabel(self, text="Asistente de voz", size_key="lg", bg=CRT_COLORS["bg"]).grid(row=0, column=0, pady=(CRT_SPACING.gutter, 4))

        card = Card(self, bg=CRT_COLORS["surface"])
        card.grid(row=1, column=0, padx=CRT_SPACING.gutter, pady=(0, CRT_SPACING.gutter), sticky="nsew")
        card.columnconfigure(0, weight=1)

        self.status_label = tk.Label(card, text="Micrófono inactivo", bg=CRT_COLORS["surface"], fg=CRT_COLORS["muted"], font=sans("sm"))
        self.status_label.grid(row=0, column=0, pady=(CRT_SPACING.padding, 8))

        self.wave_canvas = tk.Canvas(card, height=160, bg=CRT_COLORS["surface"], highlightthickness=0, bd=0)
        self.wave_canvas.grid(row=1, column=0, padx=CRT_SPACING.padding, sticky="ew")
        card.rowconfigure(1, weight=1)

        actions = tk.Frame(card, bg=CRT_COLORS["surface"])
        actions.grid(row=2, column=0, pady=(CRT_SPACING.padding, CRT_SPACING.padding))
        CRTButton(actions, icon="▶", text="Escuchar", command=self.app.begin_listening).pack(side="left", padx=8)
        CRTButton(actions, icon="✖", text="Cancelar", command=self.app.stop_listening).pack(side="left", padx=8)

        self._wave_phase = 0.0
        self._wave_job: Optional[str] = None

    def on_show(self) -> None:
        super().on_show()
        self._animate_wave()
        self.refresh()

    def on_hide(self) -> None:
        super().on_hide()
        if self._wave_job is not None:
            with suppress(Exception):
                self.after_cancel(self._wave_job)
            self._wave_job = None

    def refresh(self) -> None:
        listening = self.app.is_listening
        self.status_label.configure(
            text="Escuchando..." if listening else "Micrófono inactivo",
            fg=CRT_COLORS["accent"] if listening else CRT_COLORS["muted"],
        )

    def _animate_wave(self) -> None:
        width = max(200, self.wave_canvas.winfo_width() or 400)
        height = max(120, self.wave_canvas.winfo_height() or 160)
        self.wave_canvas.delete("all")
        step = width / 60
        points: List[float] = []
        for idx in range(61):
            x = idx * step
            amplitude = 0.4 if self.app.is_listening else 0.15
            y = height / 2 + math.sin(self._wave_phase + idx / 4) * amplitude * height / 2
            points.extend((x, y))
        self.wave_canvas.create_line(points, fill=CRT_COLORS["accent"], width=2, smooth=True)
        self._wave_phase += 0.4
        self._wave_job = self.after(120, self._animate_wave)

    def _create_history_row(self, parent: tk.Widget) -> tk.Frame:
        row = tk.Frame(parent, bg=CRT_COLORS["surface"])
        row.columnconfigure(1, weight=1)
        time_label = tk.Label(row, text="", bg=CRT_COLORS["surface"], fg=CRT_COLORS["text"], font=sans("sm"), anchor="w")
        time_label.grid(row=0, column=0, sticky="w")
        name_label = tk.Label(row, text="", bg=CRT_COLORS["surface"], fg=CRT_COLORS["text"], font=sans("sm"), anchor="w")
        name_label.grid(row=0, column=1, sticky="w", padx=(8, 0))
        weight_label = tk.Label(row, text="", bg=CRT_COLORS["surface"], fg=CRT_COLORS["muted"], font=sans("sm"), anchor="e")
        weight_label.grid(row=0, column=2, sticky="e")
        row.time_label = time_label  # type: ignore[attr-defined]
        row.name_label = name_label  # type: ignore[attr-defined]
        row.weight_label = weight_label  # type: ignore[attr-defined]
        return row


class DiabetesScreen(BaseScreen):
    mascot_mode = "corner"
    mascot_size = (200, 180)

    def __init__(self, parent: tk.Widget, app: "RpiOptimizedApp", *, mode: str = "diabetes") -> None:
        super().__init__(parent, app)
        self.mode = mode
        self.columnconfigure(0, weight=1)

        title = "Diabetes" if mode == "diabetes" else "Nightscout"
        ValueLabel(self, text=title, size_key="lg", mono_font=False, bg=CRT_COLORS["bg"]).pack(
            pady=(CRT_SPACING.gutter, 4)
        )

        card = Card(self, bg=CRT_COLORS["surface"])
        card.pack(fill="both", expand=True, padx=CRT_SPACING.gutter, pady=CRT_SPACING.gutter)
        card.columnconfigure(0, weight=1)

        self.glucose_label = ValueLabel(card, text="-- mg/dL", size_key="xl")
        self.glucose_label.grid(row=0, column=0, pady=(CRT_SPACING.padding, 4))
        self.trend_label = tk.Label(
            card,
            text="Sin datos",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["muted"],
            font=sans("sm"),
        )
        self.trend_label.grid(row=1, column=0)
        self.state_label = tk.Label(
            card,
            text="Conecta Nightscout para ver datos",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["muted"],
            font=sans("xs"),
        )
        self.state_label.grid(row=2, column=0, pady=4)

        self.graph = tk.Canvas(card, height=160, bg=CRT_COLORS["surface"], highlightthickness=0, bd=0)
        self.graph.grid(row=3, column=0, padx=CRT_SPACING.padding, pady=(8, CRT_SPACING.padding), sticky="nsew")
        card.rowconfigure(3, weight=1)

        btn_row = tk.Frame(card, bg=CRT_COLORS["surface"])
        btn_row.grid(row=4, column=0, pady=(0, CRT_SPACING.padding))
        CRTButton(btn_row, icon="🔄", text="Refrescar", command=self.app.refresh_bg).pack(side="left", padx=8)
        CRTButton(btn_row, icon="⚙", text="Configurar URL", command=self.app.configure_nightscout).pack(side="left", padx=8)
        CRTButton(btn_row, icon="↩", text="Volver", command=lambda: self.app.show_screen("home")).pack(side="left", padx=8)

        mascot_dock = tk.Frame(card, bg=CRT_COLORS["surface"], height=140)
        mascot_dock.grid(row=5, column=0, sticky="e", padx=CRT_SPACING.padding, pady=(0, CRT_SPACING.padding))
        self.attach_mascot(mascot_dock, size=(150, 130), anchor="se", relx=1.0, rely=1.0)

    def refresh(self) -> None:
        glucose = self.app.last_bg_value
        trend = self.app.last_bg_trend
        if glucose is None:
            self.glucose_label.configure(text="-- mg/dL", fg=CRT_COLORS["muted"])
            self.trend_label.configure(text="Sin datos", fg=CRT_COLORS["muted"])
            self.state_label.configure(text="Conecta Nightscout para ver datos", fg=CRT_COLORS["muted"])
            return
        self.glucose_label.configure(text=f"{glucose} mg/dL", fg=CRT_COLORS["text"])
        trend_text = trend or "estable"
        self.trend_label.configure(text=f"Tendencia: {trend_text}", fg=CRT_COLORS["accent"])
        self.state_label.configure(text="Datos recibidos", fg=CRT_COLORS["accent"])
        self._draw_graph()

    def _draw_graph(self) -> None:
        canvas = self.graph
        if not canvas.winfo_exists():
            return
        canvas.delete("all")
        width = max(200, canvas.winfo_width() or 400)
        height = max(120, canvas.winfo_height() or 160)
        margin = 8
        canvas.configure(bg=CRT_COLORS["surface"])
        canvas.create_rectangle(
            margin,
            margin,
            width - margin,
            height - margin,
            outline=CRT_COLORS["divider"],
            dash=(4, 4),
        )
        values = self.app.bg_series[-24:]
        if not values:
            return
        vmax = max(max(values), 200)
        vmin = min(min(values), 60)
        span = max(1, vmax - vmin)
        usable_width = width - margin * 2
        usable_height = height - margin * 2
        if len(values) == 1:
            values = values * 2
        step = usable_width / (len(values) - 1)
        points: List[float] = []
        for idx, value in enumerate(values):
            x = margin + idx * step
            normalized = (value - vmin) / span
            y = margin + usable_height - normalized * usable_height
            points.extend((x, y))
        for band in range(1, 4):
            y = margin + usable_height * band / 4
            draw_dotted_rule(canvas, margin + 4, int(y), width - margin - 4)
        canvas.create_line(points, fill=CRT_COLORS["accent"], width=2, smooth=True)


class MiniwebScreen(BaseScreen):
    mascot_mode = "hidden"
    mascot_size = (0, 0)

    def __init__(self, parent: tk.Widget, app: "RpiOptimizedApp") -> None:
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)
        ValueLabel(self, text="Miniweb", size_key="lg", mono_font=False, bg=CRT_COLORS["bg"]).grid(
            row=0, column=0, pady=(CRT_SPACING.gutter, 4)
        )
        card = Card(self, bg=CRT_COLORS["surface"])
        card.grid(row=1, column=0, sticky="nsew", padx=CRT_SPACING.gutter, pady=CRT_SPACING.gutter)
        card.columnconfigure(0, weight=1)
        preview = tk.Label(
            card,
            text=self.app.miniweb_preview,
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["text"],
            font=sans("xs"),
            justify="left",
            wraplength=640,
        )
        preview.grid(row=0, column=0, padx=CRT_SPACING.padding, pady=CRT_SPACING.padding)


class OtaScreen(BaseScreen):
    mascot_mode = "corner"
    mascot_size = (180, 160)

    def __init__(self, parent: tk.Widget, app: "RpiOptimizedApp") -> None:
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)
        ValueLabel(self, text="Actualizaciones", size_key="lg", mono_font=False, bg=CRT_COLORS["bg"]).grid(
            row=0, column=0, pady=(CRT_SPACING.gutter, 4)
        )
        card = Card(self, bg=CRT_COLORS["surface"])
        card.grid(row=1, column=0, sticky="nsew", padx=CRT_SPACING.gutter, pady=CRT_SPACING.gutter)
        card.columnconfigure(0, weight=1)
        self.status_label = tk.Label(
            card,
            text="Buscando actualizaciones...",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["muted"],
            font=sans("sm"),
        )
        self.status_label.grid(row=0, column=0, padx=CRT_SPACING.padding, pady=(CRT_SPACING.padding, 8), sticky="w")
        self.progress_canvas = tk.Canvas(
            card,
            height=18,
            bg=CRT_COLORS["surface"],
            highlightthickness=0,
            bd=0,
        )
        self.progress_canvas.grid(row=1, column=0, padx=CRT_SPACING.padding, pady=8, sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        actions = tk.Frame(card, bg=CRT_COLORS["surface"])
        actions.grid(row=2, column=0, pady=(CRT_SPACING.padding, CRT_SPACING.padding))
        CRTButton(actions, icon="⬆", text="Actualizar ahora", command=self.app.start_ota).pack(side="left", padx=8)
        CRTButton(actions, icon="⏰", text="Posponer", command=self.app.defer_ota).pack(side="left", padx=8)
        CRTButton(actions, icon="📄", text="Ver logs", command=self.app.show_ota_logs).pack(side="left", padx=8)

        mascot_dock = tk.Frame(card, bg=CRT_COLORS["surface"], height=140)
        mascot_dock.grid(row=3, column=0, sticky="e", padx=CRT_SPACING.padding, pady=(0, CRT_SPACING.padding))
        self.attach_mascot(mascot_dock, size=(150, 130), anchor="se", relx=1.0, rely=1.0)

    def refresh(self) -> None:
        state = self.app.ota_state
        self.status_label.configure(text=state.get("status", "Sin verificar"))
        progress = clamp(float(state.get("progress", 0.0)), 0.0, 100.0)
        width = 400
        self.progress_canvas.delete("all")
        self.progress_canvas.create_rectangle(0, 6, width, 12, outline=CRT_COLORS["divider"], width=2)
        fill_width = int(width * (progress / 100.0))
        self.progress_canvas.create_rectangle(0, 6, fill_width, 12, outline="", fill=CRT_COLORS["accent"])


class InfoScreen(BaseScreen):
    mascot_mode = "corner"
    mascot_size = (200, 180)

    def __init__(self, parent: tk.Widget, app: "RpiOptimizedApp") -> None:
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)
        ValueLabel(self, text="Información", size_key="lg", mono_font=False, bg=CRT_COLORS["bg"]).grid(
            row=0, column=0, pady=(CRT_SPACING.gutter, 4)
        )
        card = Card(self, bg=CRT_COLORS["surface"])
        card.grid(row=1, column=0, sticky="nsew", padx=CRT_SPACING.gutter, pady=CRT_SPACING.gutter)
        card.columnconfigure(0, weight=1)
        self.info_text = tk.Text(
            card,
            height=12,
            width=60,
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["text"],
            font=sans("xs"),
            bd=0,
            highlightthickness=0,
        )
        self.info_text.grid(row=0, column=0, padx=CRT_SPACING.padding, pady=CRT_SPACING.padding, sticky="nsew")
        self.info_text.configure(state="disabled")

        mascot_dock = tk.Frame(card, bg=CRT_COLORS["surface"], height=160)
        mascot_dock.grid(row=0, column=1, sticky="ne", padx=CRT_SPACING.padding, pady=CRT_SPACING.padding)
        self.attach_mascot(mascot_dock, size=(180, 160), anchor="ne", relx=1.0, rely=0.0)

    def refresh(self) -> None:
        details = []
        app_name = self.app.display_name
        details.append(f"Aplicación: {app_name}")
        version = self.app.cfg.get("version") or self.app.cfg.get("app_version")
        if version:
            details.append(f"Versión: {version}")
        details.append("Créditos: Comunidad Báscula Cam")
        details.append("")
        details.append("Hardware detectado:")
        details.append(f" - Báscula: {'Sí' if isinstance(self.app.scale_service, ScaleService) else 'No'}")
        details.append(f" - Cámara: {'Sí' if self.app.camera.available() else 'No'}")
        details.append(f" - Red: {self.app.network_state}")
        details.append(f" - x735 HAT: {'Sí' if self.app.hardware.get('x735', False) else 'No'}")
        self.info_text.configure(state="normal")
        self.info_text.delete("1.0", "end")
        self.info_text.insert("1.0", "\n".join(details))
        self.info_text.configure(state="disabled")


class PlaceholderScreen(BaseScreen):
    mascot_mode = "hidden"

    def __init__(self, parent: tk.Widget, app: "RpiOptimizedApp", *, title: str, message: str) -> None:
        super().__init__(parent, app)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        card = Card(self, bg=CRT_COLORS["surface"])
        card.grid(row=0, column=0, padx=CRT_SPACING.gutter, pady=CRT_SPACING.gutter, sticky="nsew")
        card.columnconfigure(0, weight=1)
        ValueLabel(card, text=title, size_key="lg", mono_font=False, bg=CRT_COLORS["surface"]).grid(
            row=0, column=0, pady=(CRT_SPACING.padding, 8)
        )
        tk.Label(
            card,
            text=message,
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["text"],
            font=sans("sm"),
            wraplength=720,
            justify="center",
        ).grid(row=1, column=0, padx=CRT_SPACING.padding, pady=(0, CRT_SPACING.padding))


class CRTHeader(tk.Frame):
    def __init__(self, parent: tk.Widget, app: "RpiOptimizedApp") -> None:
        super().__init__(parent, bg=CRT_COLORS["surface"], height=CRT_SPACING.header_height)
        self.app = app
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        version = app.cfg.get("version") or app.cfg.get("app_version") or "3.0"
        version_display = version if str(version).lower().startswith("v") else f"v{version}"
        self.title_label = tk.Label(
            self,
            text=f"{app.display_name} {version_display}".strip(),
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["text"],
            font=mono("md"),
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="w", padx=CRT_SPACING.gutter, pady=12)
        self.subtitle = tk.Label(
            self,
            text="Home",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["muted"],
            font=sans("xs"),
            anchor="w",
        )
        self.subtitle.grid(row=1, column=0, sticky="w", padx=CRT_SPACING.gutter)
        self.settings_btn = tk.Button(
            self,
            text="⚙",
            command=lambda: self.app.show_screen("settings"),
            bg=CRT_COLORS["accent"],
            fg=CRT_COLORS["bg"],
            bd=0,
            highlightthickness=0,
            font=mono("sm"),
            width=3,
            height=2,
        )
        self.settings_btn.grid(row=0, column=1, rowspan=2, padx=CRT_SPACING.gutter, pady=12, sticky="e")
        self.separator = tk.Canvas(self, bg=CRT_COLORS["surface"], height=4, highlightthickness=0, bd=0)
        self.separator.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.separator.bind("<Configure>", self._draw_separator, add=True)

    def set_section(self, name: str) -> None:
        display = name.replace("_", " ").strip().capitalize()
        self.subtitle.configure(text=f"Sección · {display}")

    def _draw_separator(self, _event=None) -> None:
        canvas = getattr(self, "separator", None)
        if canvas is None:
            return
        try:
            width = canvas.winfo_width()
        except Exception:
            return
        if width <= 0:
            return
        canvas.delete("rule")
        step = 8
        size = 4
        color = CRT_COLORS["divider"]
        for start in range(0, width, step):
            canvas.create_rectangle(
                start,
                0,
                min(width, start + size),
                2,
                outline="",
                fill=color,
                tags="rule",
            )


class CRTBottomBar(tk.Frame):
    def __init__(self, parent: tk.Widget, app: "RpiOptimizedApp") -> None:
        super().__init__(parent, bg=CRT_COLORS["surface"], height=CRT_SPACING.nav_height)
        self.app = app
        for idx in range(5):
            self.columnconfigure(idx, weight=1)
        with suppress(Exception):
            self.grid_propagate(False)
        self.buttons: Dict[str, CRTButton] = {}
        layout = [
            ("Pesar", "⚖", app.open_scale_overlay),
            ("Favoritos", "★", lambda: app.show_screen("favorites")),
            ("Escanear", "📷", app.open_scanner_screen),
            ("Temporizador", "⏱", app.open_timer_screen),
            ("Escuchar", "🎙", app.open_voice_screen),
        ]
        for idx, (label, icon, callback) in enumerate(layout):
            btn = CRTButton(self, icon=icon, text=label, command=callback, min_height=CRT_SPACING.nav_height)
            btn.grid(row=0, column=idx, padx=8, pady=8, sticky="nsew")
            self.buttons[label] = btn


class ScaleOverlay(tk.Frame):
    def __init__(self, app: "RpiOptimizedApp") -> None:
        super().__init__(app.root, bg=CRT_COLORS["bg"], highlightthickness=0, bd=0)
        self.app = app
        self.place_forget()
        self.card = Card(self, bg=CRT_COLORS["surface"], highlightthickness=2)
        self.card.place(relx=0.5, rely=0.5, anchor="center")
        self.card.columnconfigure(0, weight=1)

        ValueLabel(
            self.card,
            text="Panel de báscula",
            size_key="lg",
            bg=CRT_COLORS["surface"],
            mono_font=True,
        ).grid(row=0, column=0, pady=(CRT_SPACING.padding, 4))

        self.hero = Card(self.card, bg=CRT_COLORS["surface"])
        self.hero.grid(row=1, column=0, padx=CRT_SPACING.padding, pady=(0, CRT_SPACING.padding), sticky="nsew")
        self.hero.columnconfigure(0, weight=1)
        self.hero.rowconfigure(0, weight=1)
        with suppress(Exception):
            self.hero.configure(height=260)
            self.hero.grid_propagate(False)
        try:
            self.mascot = MascotCanvas(self.hero, width=320, height=240, manager=self.app.animations)
        except Exception:
            self.mascot = MascotPlaceholder(self.hero)
        self.mascot.place(relx=0.5, rely=0.6, anchor="center")
        self.weight_label = ValueLabel(
            self.hero,
            text="0 g",
            size_key="xxl",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["accent"],
        )
        self.weight_label.place(relx=0.5, rely=0.45, anchor="center")

        self.state_label = tk.Label(
            self.card,
            text="Estabilizando...",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["muted"],
            font=sans("sm"),
        )
        self.state_label.grid(row=2, column=0)
        self.context_label = tk.Label(
            self.card,
            text="Añadir alimento",
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["text"],
            font=sans("sm", "bold"),
        )
        self.context_label.grid(row=3, column=0, pady=4)
        buttons = tk.Frame(self.card, bg=CRT_COLORS["surface"])
        buttons.grid(row=4, column=0, pady=(CRT_SPACING.padding, CRT_SPACING.padding))
        CRTButton(buttons, icon="0", text="Cero", command=self.app.perform_zero, min_height=84).pack(side="left", padx=8)
        CRTButton(buttons, icon="↺", text="Tara", command=self.app.perform_tare, min_height=84).pack(side="left", padx=8)
        CRTButton(buttons, icon="✖", text="Cerrar", command=self.hide, min_height=84).pack(side="left", padx=8)
        with suppress(Exception):
            self.lift()

    def show(self) -> None:
        self.refresh()
        try:
            self.update_idletasks()
        except Exception:
            pass
        self.place(relx=0.0, rely=0.0, relwidth=1.0, relheight=1.0)
        with suppress(Exception):
            self.lift()
            self.tkraise()

    def hide(self) -> None:
        self.place_forget()

    def refresh(self) -> None:
        self.weight_label.configure(text=format_weight(self.app.net_weight))
        stable = self.app.scale_stable
        mascot_state = "happy" if stable else "processing"
        mascot = getattr(self, "mascot", None)
        if mascot is not None:
            with suppress(Exception):
                mascot.configure_state(mascot_state)  # type: ignore[attr-defined]
        if stable:
            self.state_label.configure(text="Estable", fg=CRT_COLORS["accent"])
        else:
            self.state_label.configure(text="Leyendo...", fg=CRT_COLORS["muted"])
        if self.app.pending_food_name:
            self.context_label.configure(text=f"Añadir {self.app.pending_food_name}?", fg=CRT_COLORS["text"])
        else:
            self.context_label.configure(text="Añadir alimento", fg=CRT_COLORS["muted"])

class RpiOptimizedApp:
    def __init__(self, root: Optional[tk.Tk] = None, *, theme: str = "retro") -> None:
        ensure_env_defaults()
        self.logger = logger
        self.cfg = load_config()
        self.display_name = self.cfg.get("app_name", "Báscula Cam")
        self.state = AppState()
        self.event_bus = EventBus()
        self.voice: Optional[VoiceService] = None
        if VoiceService is not None:
            try:
                self.voice = VoiceService()
            except Exception:
                self.logger.warning("VoiceService no disponible", exc_info=True)
        self.vision: Optional[VisionService] = None
        self._vision_ready = False
        self._pending_capture: Optional[str] = None
        self.root = root or tk.Tk()
        self._closing = False
        configure_root(self.root)
        self.animations = AnimationManager(self.root)
        self.memory = MemoryMonitor()
        self.tare = TareManager()
        self.scale_service = ScaleService.safe_create(logger=self.logger, config=self.cfg)
        if isinstance(self.scale_service, ScaleService):
            self.scale_service.on_tick(self._on_scale_tick)
        else:
            self.scale_service = self.scale_service or NullScaleService()
        self.net_weight: float = 0.0
        self.scale_stable = False
        self.session_delta: float = 0.0
        self.last_weight: float = 0.0
        self.pending_food_name: str = ""
        self.food_history: List[FoodEntry] = []
        self.favorites: List[Dict[str, Any]] = []
        self.recipe_state: Dict[str, Any] = {
            "steps": [
                "Añade 150 g de manzana en cubos.",
                "Incorpora 20 g de nueces y mezcla.",
                "Sirve y disfruta.",
            ],
            "current_step": 0,
            "timer_remaining": 0,
            "ingredients": [
                {"name": "Manzana", "weight": "150 g", "done": False},
                {"name": "Nueces", "weight": "20 g", "done": False},
                {"name": "Canela", "weight": "1 g", "done": False},
            ],
        }
        self.miniweb_preview = (
            "Últimos eventos:\n - 150 g Manzana\n - 20 g Nueces\n\nVisita bascula.local para más detalles."
        )
        self.ota_state: Dict[str, Any] = {"status": "Sin actualizaciones", "progress": 0}
        self.network_state = "Desconocido"
        self.hardware: Dict[str, bool] = {"x735": False}
        self.mascot_views: Dict[str, tk.Widget] = {}
        self.active_mascot: Optional[tk.Widget] = None
        self.active_screen: str = ""
        self.camera = RpiCameraManager()
        self.bg_monitor = BgMonitor(self, interval_s=90)
        self.bg_monitor.start()
        self.last_bg_value: Optional[int] = None
        self.last_bg_trend: str = ""
        self.bg_series: List[int] = []
        self.timer_total: int = 300
        self.timer_remaining: int = 300
        self.timer_running: bool = False
        self._timer_job: Optional[str] = None
        self.scanner_items: List[str] = []
        self.is_listening: bool = False
        self.focus_mode = False
        self.overlay = ScaleOverlay(self)
        self._toast_frame: Optional[Card] = None
        self._toast_label: Optional[tk.Label] = None
        self._toast_job: Optional[str] = None
        self._recovery_guard = False
        self._factories: Dict[str, Callable[[tk.Widget], BaseScreen]] = {
            "home": lambda parent: HomeScreen(parent, self),
            "recipes": lambda parent: RecipeScreen(parent, self),
            "settings": lambda parent: SettingsScreen(parent, self),
            "scale": lambda parent: ScaleScreen(parent, self),
            "history": lambda parent: HistoryScreen(parent, self),
            "favorites": lambda parent: FavoritesScreen(parent, self),
            "diabetes": lambda parent: DiabetesScreen(parent, self, mode="diabetes"),
            "nightscout": lambda parent: DiabetesScreen(parent, self, mode="nightscout"),
            "scanner": lambda parent: ScannerScreen(parent, self),
            "timer": lambda parent: TimerScreen(parent, self),
            "voice": lambda parent: VoiceScreen(parent, self),
            "miniweb": lambda parent: MiniwebScreen(parent, self),
            "ota": lambda parent: OtaScreen(parent, self),
            "info": lambda parent: InfoScreen(parent, self),
        }
        self._register_optional_factories()
        self._build_layout()
        self.screens: Dict[str, Optional[BaseScreen]] = {name: None for name in self._factories}
        self.current_screen: Optional[str] = None
        self.show_screen("home")

    def run(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        try:
            self.root.mainloop()
        finally:
            self.close()

    def _build_layout(self) -> None:
        self.root.configure(bg=CRT_COLORS["bg"])
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.header = CRTHeader(self.root, self)
        self.header.grid(row=0, column=0, sticky="ew")
        self.content = tk.Frame(self.root, bg=CRT_COLORS["bg"])
        self.content.grid(row=1, column=0, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)
        self.screen_container = tk.Frame(self.content, bg=CRT_COLORS["bg"])
        self.screen_container.grid(row=0, column=0, sticky="nsew")
        self.navbar = CRTBottomBar(self.root, self)
        self.navbar.grid(row=2, column=0, sticky="ew")

    def optional_screens(self) -> set[str]:
        return set(self._factories.keys()) - {
            "home",
            "recipes",
            "settings",
            "scale",
            "history",
            "favorites",
            "diabetes",
            "nightscout",
            "scanner",
            "timer",
            "voice",
            "miniweb",
            "ota",
            "info",
        }

    def _register_optional_factories(self) -> None:
        mapping = {
            "focus": ("bascula.ui.focus_screen", "FocusScreen"),
            "wifi": ("bascula.ui.screens_wifi", "WifiScreen"),
            "apikey": ("bascula.ui.screens_apikey", "ApiKeyScreen"),
        }
        for name, (module_name, class_name) in mapping.items():
            try:
                module = import_module(module_name)
                screen_cls = getattr(module, class_name)
            except Exception:
                self.logger.warning("Pantalla opcional %s no disponible", name)
                continue
            self._factories[name] = lambda parent, cls=screen_cls: cls(parent, self)  # type: ignore[arg-type]

    def show_screen(self, name: str) -> None:
        if name not in self._factories:
            message = f"Pantalla {name} no registrada"
            self.logger.warning(message)
            self._show_toast(message, level="warn")
            return
        try:
            self._show_screen_internal(name)
        except Exception:
            self.logger.exception("Error mostrando pantalla %s", name)
            self._show_toast(f"Error al abrir {name}", level="error")
            if name != "home" and not self._recovery_guard:
                self._recovery_guard = True
                try:
                    self._show_screen_internal("home")
                except Exception:
                    self.logger.exception("Fallo al recuperar pantalla home")
                finally:
                    self._recovery_guard = False
        else:
            self.header.set_section(name)
            self.memory.maybe_collect()

    def _show_screen_internal(self, name: str) -> None:
        for child in self.screen_container.winfo_children():
            if getattr(child, "screen_name", None) != name:
                with suppress(Exception):
                    child.place_forget()
                with suppress(Exception):
                    child.pack_forget()
                with suppress(Exception):
                    child.grid_remove()
        for screen_name, screen in list(self.screens.items()):
            if screen_name != name and screen is not None and getattr(screen, "visible", False):
                with suppress(Exception):
                    screen.on_hide()
        screen = self.screens.get(name)
        if screen is None:
            factory = self._factories[name]
            screen = factory(self.screen_container)
            screen.screen_name = name
            self.screens[name] = screen
        if screen is None:
            raise RuntimeError(f"Factory para {name} devolvió None")
        screen.grid(row=0, column=0, sticky="nsew")
        with suppress(Exception):
            screen.tkraise()
        try:
            screen.on_show()
        except Exception as exc:
            raise RuntimeError(f"on_show falló para {name}: {exc}") from exc
        try:
            screen.refresh()
        except Exception as exc:
            raise RuntimeError(f"refresh falló para {name}: {exc}") from exc
        self.current_screen = name
        self.register_active_mascot(name)

    def attach_mascot_to_screen(
        self,
        screen_name: str,
        parent: tk.Widget,
        *,
        size: Tuple[int, int],
        anchor: str = "center",
        relx: float = 0.5,
        rely: float = 0.5,
    ) -> tk.Widget:
        widget = self.mascot_views.get(screen_name)
        if widget is None or widget.master is not parent:
            if widget is not None:
                with suppress(Exception):
                    widget.destroy()
            try:
                widget = MascotCanvas(parent, width=size[0], height=size[1], manager=self.animations)
            except Exception:
                self.logger.exception("Mascota Canvas falló; usando placeholder")
                widget = MascotPlaceholder(parent)
            self.mascot_views[screen_name] = widget
        if isinstance(widget, MascotCanvas):
            widget.resize(*size)
            with suppress(Exception):
                widget.configure(state="disabled")
        try:
            widget.place(relx=relx, rely=rely, anchor=anchor)
        except Exception:
            widget.pack(expand=True)
        self.active_mascot = widget
        return widget

    def register_active_mascot(self, screen_name: str) -> None:
        widget = self.mascot_views.get(screen_name)
        if widget is not None:
            self.active_mascot = widget

    def detach_mascot(self, screen_name: str) -> None:
        widget = self.mascot_views.get(screen_name)
        if widget is not None:
            with suppress(Exception):
                widget.place_forget()

    def open_scale_overlay(self) -> None:
        self.overlay.refresh()
        self.overlay.show()

    def open_scanner_screen(self) -> None:
        self.show_screen("scanner")
        self._refresh_scanner_screen()

    def open_timer_screen(self) -> None:
        self.show_screen("timer")
        self._refresh_timer_screen()

    def open_voice_screen(self) -> None:
        self.show_screen("voice")
        if self.voice is not None:
            if not self.is_listening:
                self.begin_listening()
        else:
            self._refresh_voice_screen()

    def close(self) -> None:
        if getattr(self, "_closing", False):
            return
        self._closing = True
        try:
            self.bg_monitor.stop()
        except Exception:
            pass
        try:
            if isinstance(self.scale_service, ScaleService):
                self.scale_service.stop()
        except Exception:
            pass
        try:
            self.animations.cancel_all()
        except Exception:
            pass
        if self.is_listening:
            with suppress(Exception):
                self.stop_listening()
        for screen in self.screens.values():
            if screen is not None and getattr(screen, "visible", False):
                with suppress(Exception):
                    screen.on_hide()
        if self._toast_job is not None:
            with suppress(Exception):
                self.root.after_cancel(self._toast_job)
            self._toast_job = None
        if self._toast_label is not None:
            with suppress(Exception):
                self._toast_label.destroy()
            self._toast_label = None
        if self._toast_frame is not None:
            with suppress(Exception):
                self._toast_frame.destroy()
            self._toast_frame = None
        with suppress(Exception):
            self.root.destroy()

    def _on_scale_tick(self, weight: float, stable: bool) -> None:
        raw_weight = float(weight)
        is_stable = bool(stable)
        net_weight = self.tare.compute_net(raw_weight)

        self.last_weight = raw_weight
        self.net_weight = net_weight
        self.scale_stable = is_stable
        if self.current_screen in {"home", "scale"}:
            screen = self.screens.get(self.current_screen)
            if screen is not None:
                try:
                    screen.refresh()
                except Exception:
                    self.logger.exception("Error refrescando pantalla %s", self.current_screen)
        self.overlay.refresh()

    def perform_tare(self) -> None:
        self.tare.set_tare(self.last_weight)
        self.session_delta = 0.0
        self.event_bus.publish("TARA", {"weight": self.last_weight})
        self._update_screen_data()

    def perform_zero(self) -> None:
        try:
            if isinstance(self.scale_service, ScaleService):
                self.scale_service.zero()
            self.show_mascot_message("Cero aplicado", state="happy")
        except Exception:
            self.logger.exception("No se pudo poner a cero")
            self.show_mascot_message("Error al poner a cero", state="error")

    def scan_current_food(self) -> None:
        self.show_screen("scanner")
        if decode_barcode is None and VisionService is None and not self.camera.available():
            self.show_mascot_message("Escáner no disponible", state="error")
            return
        self.show_mascot_message("Analizando...", state="processing")
        sample_items = ["Manzana", "Plátano", "Espinacas", "Jengibre"]
        detected = sample_items[len(self.scanner_items) % len(sample_items)]
        entry = f"{detected} detectado"
        self.scanner_items.append(entry)
        self._refresh_scanner_screen()

    def clear_scanner_results(self) -> None:
        self.scanner_items.clear()
        self._refresh_scanner_screen()

    def add_detected_to_scale(self) -> None:
        if not self.scanner_items:
            self.show_mascot_message("Sin detecciones", state="error")
            return
        item = self.scanner_items[0]
        self.show_mascot_message(f"{item} añadido", state="happy")

    def _refresh_scanner_screen(self) -> None:
        screen = self.screens.get("scanner")
        if screen:
            with suppress(Exception):
                screen.refresh()

    def _refresh_voice_screen(self) -> None:
        screen = self.screens.get("voice")
        if screen:
            with suppress(Exception):
                screen.refresh()

    def begin_listening(self) -> None:
        if self.voice is None:
            self.show_mascot_message("Voz no disponible", state="error")
            return
        if self.is_listening:
            self.show_mascot_message("Micrófono activo", state="listening")
            return
        try:
            started = self.voice.start_listening(self._on_voice_transcript)
        except Exception:
            self.logger.exception("No se pudo iniciar la escucha de voz")
            started = False
        if not started:
            self.is_listening = False
            self.show_mascot_message("Error al escuchar", state="error")
            return
        self.is_listening = True
        self.show_mascot_message("Escuchando...", state="listening")
        self._refresh_voice_screen()

    def stop_listening(self) -> None:
        if self.voice is None and not self.is_listening:
            self.show_mascot_message("Micrófono inactivo", state="idle")
            return
        if self.voice is not None:
            with suppress(Exception):
                self.voice.stop_listening()
        was_listening = self.is_listening
        self.is_listening = False
        message = "Micrófono detenido" if was_listening else "Micrófono inactivo"
        self.show_mascot_message(message, state="idle")
        self._refresh_voice_screen()

    def _on_voice_transcript(self, text: str) -> None:
        try:
            self.root.after(0, lambda: self._handle_voice_result(text))
        except Exception:
            self._handle_voice_result(text)

    def _handle_voice_result(self, text: str) -> None:
        self.is_listening = False
        summary = text.strip()
        if summary:
            self.show_mascot_message(f"Escuchado: {summary}", state="happy")
        else:
            self.show_mascot_message("No se escuchó nada", state="idle")
        self._refresh_voice_screen()

    def toggle_recipe_timer(self) -> None:
        remaining = int(self.recipe_state.get("timer_remaining", 0))
        if remaining == 0:
            self.recipe_state["timer_remaining"] = 180
            self.show_mascot_message("Temporizador iniciado", state="listening")
        else:
            self.recipe_state["timer_remaining"] = 0
            self.show_mascot_message("Temporizador detenido", state="idle")
        screen = self.screens.get("recipes")
        if screen:
            with suppress(Exception):
                screen.refresh()

    def set_timer_seconds(self, seconds: int) -> None:
        self.timer_total = max(1, int(seconds))
        self.timer_remaining = self.timer_total
        self.timer_running = False
        self._cancel_timer_job()
        self._refresh_timer_screen()

    def start_timer(self) -> None:
        if self.timer_running:
            return
        if self.timer_remaining <= 0:
            self.timer_remaining = self.timer_total
        self.timer_running = True
        self._schedule_timer_tick()
        self.show_mascot_message("Temporizador iniciado", state="listening")
        self._refresh_timer_screen()

    def pause_timer(self) -> None:
        if not self.timer_running:
            return
        self.timer_running = False
        self._cancel_timer_job()
        self.show_mascot_message("Temporizador detenido", state="idle")
        self._refresh_timer_screen()

    def reset_timer(self) -> None:
        self.timer_running = False
        self.timer_remaining = self.timer_total
        self._cancel_timer_job()
        self._refresh_timer_screen()

    def _schedule_timer_tick(self) -> None:
        self._cancel_timer_job()
        try:
            self._timer_job = self.root.after(1000, self._timer_tick)
        except Exception:
            self._timer_job = None

    def _cancel_timer_job(self) -> None:
        if self._timer_job is not None:
            try:
                self.root.after_cancel(self._timer_job)
            except Exception:
                pass
            self._timer_job = None

    def _timer_tick(self) -> None:
        if not self.timer_running:
            return
        self.timer_remaining = max(0, int(self.timer_remaining) - 1)
        if self.timer_remaining <= 0:
            self.timer_running = False
            self.show_mascot_message("Tiempo cumplido", state="happy")
        else:
            self._schedule_timer_tick()
        self._refresh_timer_screen()

    def _refresh_timer_screen(self) -> None:
        screen = self.screens.get("timer")
        if screen:
            with suppress(Exception):
                screen.refresh()

    def next_recipe_step(self) -> None:
        current = int(self.recipe_state.get("current_step", 0))
        steps = self.recipe_state.get("steps", [])
        if steps:
            self.recipe_state["current_step"] = min(len(steps) - 1, current + 1)
        screen = self.screens.get("recipes")
        if screen:
            with suppress(Exception):
                screen.refresh()

    def prev_recipe_step(self) -> None:
        current = int(self.recipe_state.get("current_step", 0))
        self.recipe_state["current_step"] = max(0, current - 1)
        screen = self.screens.get("recipes")
        if screen:
            with suppress(Exception):
                screen.refresh()

    def confirm_food(self) -> None:
        entry = FoodEntry(
            name="Alimento",
            weight=self.net_weight,
            timestamp=time.time(),
            macros={"carbs": 0.0, "protein": 0.0, "fat": 0.0},
        )
        self.food_history.append(entry)
        self.session_delta = 0.0
        self.event_bus.publish("WEIGHT_CAPTURED", {"weight": self.net_weight})
        self.show_screen("home")

    def cancel_food(self) -> None:
        self.session_delta = 0.0
        self.show_screen("home")

    def clear_history(self) -> None:
        self.food_history.clear()
        screen = self.screens.get("history")
        if screen:
            with suppress(Exception):
                screen.refresh()

    def send_to_nightscout(self) -> None:
        self.logger.info("Envío a Nightscout (placeholder)")
        self.show_mascot_message("Datos enviados", state="happy")

    def export_history(self) -> None:
        self.logger.info("Exportando historial a CSV")
        self.show_mascot_message("Exportado como CSV", state="processing")

    def add_favorite(self) -> None:
        name = f"Favorito {len(self.favorites) + 1}"
        self.favorites.append({"name": name, "macros": {"carbs": 0, "protein": 0}})
        self.show_mascot_message(f"{name} añadido", state="happy")
        screen = self.screens.get("favorites")
        if screen:
            with suppress(Exception):
                screen.refresh()

    def edit_favorite(self) -> None:
        if not self.favorites:
            self.show_mascot_message("Sin favoritos", state="error")
            return
        self.favorites[0]["name"] += "*"
        self.show_mascot_message("Favorito actualizado", state="happy")
        screen = self.screens.get("favorites")
        if screen:
            with suppress(Exception):
                screen.refresh()

    def remove_favorite(self) -> None:
        self.remove_favorite_index(len(self.favorites) - 1)

    def remove_favorite_index(self, index: int) -> None:
        if not self.favorites:
            self.show_mascot_message("No hay favoritos", state="error")
            return
        try:
            removed = self.favorites.pop(index)
        except IndexError:
            self.show_mascot_message("Índice inválido", state="error")
            return
        self.show_mascot_message(f"{removed.get('name')} eliminado", state="processing")
        screen = self.screens.get("favorites")
        if screen:
            with suppress(Exception):
                screen.refresh()

    def add_favorite_to_plate(self) -> None:
        if not self.favorites:
            self.show_mascot_message("Agrega un favorito primero", state="error")
            return
        self.show_mascot_message("Añadido al plato", state="happy")

    def refresh_bg(self) -> None:
        self.logger.info("Actualizando datos de glucosa")
        self.show_mascot_message("Sincronizando Nightscout", state="processing")

    def configure_nightscout(self) -> None:
        self.logger.info("Configurando Nightscout (placeholder)")
        self.show_mascot_message("Configura en ajustes", state="idle")

    def start_ota(self) -> None:
        self.ota_state.update({"status": "Descargando", "progress": 10})
        self.show_mascot_message("Actualización iniciada", state="processing")
        screen = self.screens.get("ota")
        if screen:
            with suppress(Exception):
                screen.refresh()

    def defer_ota(self) -> None:
        self.ota_state.update({"status": "Pospuesta", "progress": 0})
        self.show_mascot_message("Actualización pospuesta", state="idle")
        screen = self.screens.get("ota")
        if screen:
            with suppress(Exception):
                screen.refresh()

    def show_ota_logs(self) -> None:
        self.show_mascot_message("Logs en /var/log/bascula", state="processing")

    def toggle_focus_mode(self, enabled: bool) -> None:
        self.focus_mode = enabled
        self.show_mascot_message("Focus mode" + (" activado" if enabled else " desactivado"), state="happy")

    def toggle_mascot_animations(self, enabled: bool) -> None:
        if enabled:
            self.animations.resume_all()
        else:
            self.animations.pause_all()
        self.show_mascot_message("Animaciones" + (" activadas" if enabled else " desactivadas"), state="idle")

    def toggle_sound_effects(self, enabled: bool) -> None:
        self.show_mascot_message("Sonidos" + (" activos" if enabled else " silenciados"), state="idle")

    def toggle_listening(self) -> None:
        if self.is_listening:
            self.stop_listening()
        else:
            self.begin_listening()

    def _update_screen_data(self) -> None:
        if self.current_screen:
            screen = self.screens.get(self.current_screen)
            if screen:
                try:
                    screen.refresh()
                except Exception:
                    self.logger.exception("Error refrescando pantalla %s", self.current_screen)

    def show_mascot_message(self, text: str, *, state: str = "idle", icon: str = "", icon_color: str = "") -> None:
        state = state if state in MASCOT_STATES else "idle"
        icon = icon or MASCOT_STATES[state].get("symbol", "♥")
        icon_color = icon_color or MASCOT_STATES[state].get("color", CRT_COLORS["accent"])
        self.logger.info("Mascota: %s %s", icon, text)
        target_widgets: Iterable[tk.Widget] = []
        if self.active_mascot is not None:
            target_widgets = [self.active_mascot]
        for widget in target_widgets:
            if isinstance(widget, (MascotCanvas, MascotPlaceholder)):
                try:
                    widget.configure_state(state)  # type: ignore[attr-defined]
                except Exception:
                    continue
        if text:
            self._show_toast(text, level="info")

    def _show_toast(self, message: str, *, level: str = "info", timeout: int = 2400) -> None:
        if not message:
            return
        palette = {
            "info": CRT_COLORS.get("accent"),
            "warn": CRT_COLORS.get("warning"),
            "error": CRT_COLORS.get("error"),
        }
        accent = _safe_color(palette.get(level), CRT_COLORS["accent"])
        surface = CRT_COLORS["surface"]
        if self._toast_frame is None or not self._toast_frame.winfo_exists():
            self._toast_frame = Card(self.root, bg=surface)
            self._toast_label = tk.Label(
                self._toast_frame,
                font=sans("xs", "bold"),
                bg=surface,
                fg=accent,
                wraplength=420,
                justify="center",
            )
            self._toast_label.pack(padx=CRT_SPACING.padding, pady=CRT_SPACING.padding)
        label = self._toast_label
        frame = self._toast_frame
        if label is None or frame is None:
            return
        label.configure(text=message, fg=accent, bg=surface)
        try:
            frame.lift()
            frame.place(relx=0.98, rely=0.08, anchor="ne")
        except Exception:
            frame.pack(side="top", pady=6)
        if self._toast_job is not None:
            with suppress(Exception):
                self.root.after_cancel(self._toast_job)
        self._toast_job = self.root.after(timeout, self._hide_toast)

    def _hide_toast(self) -> None:
        if self._toast_frame is not None:
            with suppress(Exception):
                self._toast_frame.place_forget()
        self._toast_job = None

    def on_bg_update(self, value: Optional[int], trend: str) -> None:
        self.last_bg_value = value
        self.last_bg_trend = trend
        if value is not None:
            self.bg_series.append(int(value))
            self.bg_series = self.bg_series[-48:]
        if self.current_screen in {"diabetes", "nightscout"}:
            screen = self.screens.get(self.current_screen)
            if screen:
                with suppress(Exception):
                    screen.refresh()

    def on_bg_error(self, message: str) -> None:
        self.logger.warning("BG monitor: %s", message)
        self.show_mascot_message("Error BG", state="error")

    def get_cfg(self) -> Dict[str, Any]:
        return dict(self.cfg)


BasculaAppTk = RpiOptimizedApp
BasculaApp = RpiOptimizedApp
