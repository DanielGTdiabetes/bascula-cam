"""Home view showing live weight and quick actions."""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk
from typing import Callable, Dict, Optional

from ..icon_loader import load_icon
from ..theme_neo import SPACING
from ..theme_holo import (
    COLOR_ACCENT,
    COLOR_BG,
    COLOR_PRIMARY,
    COLOR_SURFACE,
    COLOR_TEXT,
    FONT_DIGITS,
    FONT_BODY_BOLD,
    PALETTE,
    neon_border,
    draw_neon_separator,
)
from ..widgets import NeoGhostButton


LOGGER = logging.getLogger(__name__)

ICONS = {
    "timer": "timer.png",
    "settings": "settings.png",
    "tare": "tare.png",
    "swap": "swap.png",
    "food": "food.png",
    "recipe": "recipe.png",
}


@dataclass(frozen=True)
class _QuickActionMetrics:
    """Layout metrics for quick action buttons derived from viewport size."""

    diameter: int
    padding: int
    columns: int
    rows: int


def _calculate_quick_action_metrics(
    count: int, container_w: int, container_h: int, *, toolbar_h: int = 0
) -> _QuickActionMetrics:
    """Compute button sizing ensuring two rows fit within the available area."""

    if count <= 0:
        return _QuickActionMetrics(diameter=NeoGhostButton.MIN_DIAMETER, padding=9, columns=1, rows=1)

    container_w = max(int(container_w), 0)
    container_h = max(int(container_h), 0)
    avail_w = max(0.0, float(container_w - 2 * 16))
    avail_h = max(0.0, float(container_h - toolbar_h - 2 * 16))

    columns = min(3, max(1, count))
    rows = max(1, math.ceil(count / columns))
    rows = min(rows, 2)
    columns = max(1, min(3, math.ceil(count / rows)))

    cell_w = avail_w / columns if columns else 0.0
    cell_h = avail_h / rows if rows else 0.0
    base_diameter = min(cell_w, cell_h) if cell_w and cell_h else 0.0
    diameter = int(base_diameter - 24)
    diameter = max(NeoGhostButton.MIN_DIAMETER, min(NeoGhostButton.MAX_DIAMETER, diameter))

    padding = 9
    return _QuickActionMetrics(diameter=diameter, padding=padding, columns=columns, rows=rows)


class HomeView(ttk.Frame):
    """Main landing view displaying current weight and shortcuts."""

    def __init__(self, parent: tk.Misc, controller: object, **kwargs: object) -> None:
        kwargs.pop("bg", None)
        super().__init__(parent, **kwargs)

        self.controller = controller
        self._units = "g"
        self._last_grams = 0.0
        self._decimals = 0
        self._has_weight_value = True
        self._resize_job: str | None = None
        self._digit_font_family: str | None = None

        self.on_tare: Callable[[], None] = lambda: None
        self.on_zero: Callable[[], None] = lambda: None
        self.on_toggle_units: Callable[[], None] = lambda: None
        self.on_open_food: Callable[[], None] = lambda: None
        self.on_open_recipes: Callable[[], None] = lambda: None
        self.on_open_timer: Callable[[], None] = lambda: None
        self.on_open_settings: Callable[[], None] = lambda: None
        self.on_set_decimals: Callable[[int], None] = lambda _: None

        style = ttk.Style(self)
        style.configure("Home.Root.TFrame", background=COLOR_BG)
        style.configure("Home.Weight.TFrame", background=COLOR_BG)
        style.configure("Home.WeightGlow.TLabel", background=COLOR_BG, foreground=COLOR_ACCENT, font=FONT_DIGITS)
        style.configure("Home.WeightPrimary.TLabel", background=COLOR_BG, foreground=COLOR_PRIMARY, font=FONT_DIGITS)
        style.configure("Home.WeightGlowUnit.TLabel", background=COLOR_BG, foreground=COLOR_ACCENT, font=FONT_BODY_BOLD)
        style.configure("Home.WeightUnit.TLabel", background=COLOR_BG, foreground=COLOR_TEXT, font=FONT_BODY_BOLD)
        style.configure("Home.Status.TFrame", background=COLOR_BG)
        style.configure(
            "Home.StatusAccent.TLabel",
            background=COLOR_BG,
            foreground=COLOR_ACCENT,
            font=FONT_BODY_BOLD,
        )
        style.configure(
            "Home.Toggle.TCheckbutton",
            background=COLOR_BG,
            foreground=COLOR_TEXT,
            font=FONT_BODY_BOLD,
            indicatordiameter=16,
            padding=(8, 4),
        )
        style.map(
            "Home.Toggle.TCheckbutton",
            foreground=[("selected", COLOR_ACCENT)],
            background=[("active", COLOR_SURFACE)],
        )
        style.configure("Home.Buttons.TFrame", background=COLOR_BG)

        self.configure(style="Home.Root.TFrame", padding=SPACING["lg"])

        self._weight_value_var = tk.StringVar(value="0")
        self._weight_unit_var = tk.StringVar(value="g")
        weight_container = ttk.Frame(self, style="Home.Weight.TFrame")
        weight_container.configure(height=220)
        weight_container.pack(fill="x", pady=(0, SPACING["lg"]))
        weight_container.pack_propagate(False)

        glow_frame = ttk.Frame(weight_container, style="Home.Weight.TFrame")
        glow_frame.place(relx=0.5, rely=0.52, anchor="center")
        glow_value = ttk.Label(glow_frame, textvariable=self._weight_value_var, style="Home.WeightGlow.TLabel")
        glow_unit = ttk.Label(glow_frame, textvariable=self._weight_unit_var, style="Home.WeightGlowUnit.TLabel")
        glow_value.grid(row=0, column=0, sticky="s")
        glow_unit.grid(row=0, column=1, sticky="sw", padx=(12, 0))
        glow_frame.grid_columnconfigure(0, weight=1)
        glow_frame.lower()

        value_frame = ttk.Frame(weight_container, style="Home.Weight.TFrame")
        value_frame.place(relx=0.5, rely=0.5, anchor="center")
        self._weight_label = ttk.Label(value_frame, textvariable=self._weight_value_var, style="Home.WeightPrimary.TLabel")
        self._unit_label = ttk.Label(value_frame, textvariable=self._weight_unit_var, style="Home.WeightUnit.TLabel")
        self._weight_label.grid(row=0, column=0, sticky="s")
        self._unit_label.grid(row=0, column=1, sticky="sw", padx=(12, 0))
        value_frame.grid_columnconfigure(0, weight=1)
        self._weight_glow = glow_value
        self._weight_glow_unit = glow_unit
        self._weight_unit_label = self._unit_label
        self._weight_container = weight_container

        self._weight_label.name = "weight_display"  # type: ignore[attr-defined]
        if hasattr(self.controller, "register_widget"):
            self.controller.register_widget("weight_display", self._weight_label)

        self._weight_border = neon_border(weight_container)

        status_frame = ttk.Frame(self, style="Home.Status.TFrame")
        status_frame.pack(anchor="center", pady=(0, SPACING["md"]))

        self._stable_var = tk.StringVar(value="Inestable")
        self._stable_label = ttk.Label(status_frame, textvariable=self._stable_var, style="Home.StatusAccent.TLabel")
        self._stable_label.pack(side="left", padx=(0, SPACING["md"]))

        self._decimals_var = tk.IntVar(value=0)
        decimals_switch = ttk.Checkbutton(
            status_frame,
            text="1 decimal",
            variable=self._decimals_var,
            command=self._handle_decimals_toggle,
            style="Home.Toggle.TCheckbutton",
        )
        decimals_switch.pack(side="left")

        separator_container = ttk.Frame(self, style="Home.Status.TFrame")
        separator_container.pack(fill="x", pady=(0, SPACING["md"]))
        self._separator_container = separator_container
        separator_canvas = tk.Canvas(
            separator_container,
            height=16,
            background=COLOR_BG,
            highlightthickness=0,
            bd=0,
        )
        separator_canvas.pack(fill="x", expand=True)
        self._separator_canvas = separator_canvas

        buttons_frame = ttk.Frame(self, style="Home.Buttons.TFrame")
        buttons_frame.pack(fill="both", expand=True, padx=SPACING["sm"], pady=(0, SPACING["sm"]))
        self._buttons_frame = buttons_frame
        self._buttons_border = neon_border(buttons_frame, padding=6, radius=20)

        self.buttons: Dict[str, tk.Misc] = {}
        self._tara_long_press_job: str | None = None
        self._tara_long_press_triggered = False
        self._button_icon_names: Dict[str, str | None] = {}
        self._button_order: list[str] = []
        self._quick_action_metrics: _QuickActionMetrics | None = None

        button_specs = (
            {
                "name": "btn_tare",
                "icon": ICONS["tare"],
                "text": "Tara",
                "tooltip": "Tara",
                "command": self._handle_tare,
            },
            {
                "name": "btn_swap",
                "icon": ICONS["swap"],
                "text": "g/ml",
                "tooltip": "Cambiar unidades g↔ml",
                "command": self._handle_toggle_units,
            },
            {
                "name": "btn_food",
                "icon": ICONS["food"],
                "text": "Alimentos",
                "tooltip": "Alimentos",
                "command": self._handle_open_food,
            },
            {
                "name": "btn_recipe",
                "icon": ICONS["recipe"],
                "text": "Recetas",
                "tooltip": "Recetas",
                "command": self._handle_open_recipes,
            },
            {
                "name": "btn_timer",
                "icon": ICONS["timer"],
                "text": "Temporizador",
                "tooltip": "Temporizador",
                "command": self._handle_open_timer,
            },
            {
                "name": "btn_settings",
                "icon": ICONS["settings"],
                "text": "Ajustes",
                "tooltip": "Ajustes",
                "command": self._handle_open_settings,
            },
        )
        for spec in button_specs:
            icon_image = load_icon(spec["icon"], size=72) if spec.get("icon") else None
            show_text = spec.get("icon") is None or icon_image is None
            button = NeoGhostButton(
                buttons_frame,
                width=120,
                height=120,
                radius=60,
                outline_color=PALETTE["neon_fuchsia"],
                outline_width=2,
                text=spec["text"],
                icon=icon_image,
                command=spec["command"],
                tooltip=spec["tooltip"],
                show_text=show_text,
                text_color=PALETTE["primary"] if show_text else None,
            )
            button.grid(row=0, column=0, sticky="nsew")
            button.name = spec["name"]  # type: ignore[attr-defined]
            if hasattr(self.controller, "register_widget"):
                self.controller.register_widget(spec["name"], button)
            self.buttons[spec["name"]] = button
            self._button_icon_names[spec["name"]] = spec.get("icon")
            self._button_order.append(spec["name"])

        self._configure_tare_long_press()
        self.bind("<Configure>", self._on_configure, add=True)
        self.after(120, self._apply_layout_metrics)

    # ------------------------------------------------------------------
    def update_weight(self, grams: Optional[float], stable: bool) -> None:
        if grams is None:
            self._stable_var.set("Sin señal")
            self._stable_label.configure(foreground=COLOR_ACCENT)
            self._has_weight_value = False
            self._weight_value_var.set("--")
            self._weight_unit_var.set(self._units)
            return

        self._last_grams = float(grams)
        self._has_weight_value = True
        self._stable_var.set("Estable" if stable else "Inestable")
        self._stable_label.configure(foreground=COLOR_PRIMARY if stable else COLOR_ACCENT)
        self._refresh_display()

    def toggle_units(self) -> str:
        self._units = "ml" if self._units == "g" else "g"
        self._refresh_display()
        return self._units

    def set_units(self, unit: str) -> None:
        unit_lower = (unit or "g").strip().lower()
        self._units = "ml" if unit_lower == "ml" else "g"
        self._refresh_display()

    # ------------------------------------------------------------------
    def _grams_to_ml(self, grams: float) -> float:
        try:
            if hasattr(self.controller, "get_ml_factor"):
                density = float(self.controller.get_ml_factor())  # type: ignore[call-arg]
            elif hasattr(self.controller, "scale_service"):
                density = float(getattr(self.controller.scale_service, "get_ml_factor")())  # type: ignore[attr-defined]
            elif hasattr(self.controller, "scale"):
                density = float(getattr(self.controller.scale, "density", 1.0))  # type: ignore[attr-defined]
            else:
                density = 1.0
            if density <= 0:
                density = 1.0
        except Exception:
            density = 1.0
        return grams / density

    def _refresh_display(self) -> None:
        if not self._has_weight_value:
            self._weight_value_var.set("--")
            self._weight_unit_var.set(self._units)
            return

        decimals = 1 if self._decimals else 0
        grams = self._last_grams
        if self._units == "g":
            self._weight_value_var.set(f"{grams:.{decimals}f}")
        else:
            self._weight_value_var.set(f"{self._grams_to_ml(grams):.{decimals}f}")
        self._weight_unit_var.set(self._units)

    def set_decimals(self, decimals: int) -> None:
        self._decimals = 1 if int(decimals) > 0 else 0
        self._decimals_var.set(self._decimals)
        self._refresh_display()

    # ------------------------------------------------------------------
    def _handle_tare(self) -> None:
        self.on_tare()

    def _handle_toggle_units(self) -> None:
        self.on_toggle_units()

    def _handle_decimals_toggle(self) -> None:
        value = 1 if self._decimals_var.get() else 0
        self.on_set_decimals(value)

    def _handle_open_food(self) -> None:
        self.on_open_food()

    def _handle_open_recipes(self) -> None:
        self.on_open_recipes()

    def _handle_open_timer(self) -> None:
        self.on_open_timer()

    def _handle_open_settings(self) -> None:
        self.on_open_settings()

    # ------------------------------------------------------------------
    def _on_configure(self, _event: tk.Event | None = None) -> None:
        if self._resize_job is not None:
            try:
                self.after_cancel(self._resize_job)
            except Exception:
                pass
        self._resize_job = self.after(80, self._apply_layout_metrics)

    def _apply_layout_metrics(self) -> None:
        self._resize_job = None
        self.after_idle(self._update_weight_fonts)
        self.after_idle(self._redraw_separator)
        self.after_idle(self._update_button_layout)

    def _update_weight_fonts(self) -> None:
        height = max(self.winfo_height(), 1)
        if height <= 1:
            height = 600
        size = max(96, min(int(height * 0.22), 160))
        unit_size = max(48, int(size * 0.65))
        family = self._resolve_digit_font()

        weight_font = (family, size)
        unit_font = (family, unit_size)
        for label in (self._weight_glow, self._weight_label):
            label.configure(font=weight_font)
        for label in (self._weight_glow_unit, self._weight_unit_label):
            label.configure(font=unit_font)

        unit_pad = max(8, size // 6)
        self._unit_label.grid_configure(padx=(unit_pad, 0))
        self._weight_glow_unit.grid_configure(padx=(unit_pad, 0))

    def _update_button_layout(self) -> None:
        if not self.buttons:
            return

        frame = getattr(self, "_buttons_frame", None)
        if frame is None:
            return

        width = int(frame.winfo_width())
        height = int(frame.winfo_height())
        if width <= 0 or height <= 0:
            width = max(width, int(self.winfo_width()))
            height = max(height, int(self.winfo_height()))
        try:
            toplevel = self.winfo_toplevel()
        except Exception:
            toplevel = None
        if (width <= 0 or height <= 0) and toplevel is not None:
            try:
                width = max(width, int(toplevel.winfo_width()))
                height = max(height, int(toplevel.winfo_height()))
            except Exception:
                pass
        if width <= 0 or height <= 0:
            width = max(width, int(self.winfo_screenwidth()))
            height = max(height, int(self.winfo_screenheight()))
        if width <= 0 or height <= 0:
            return

        toolbar_h = 0
        toolbar = getattr(self.controller, "toolbar", None)
        if toolbar is not None:
            try:
                toolbar.update_idletasks()
            except Exception:
                pass
            try:
                toolbar_h = int(toolbar.winfo_height())
            except Exception:
                toolbar_h = 0

        container_w = max(width, int(self.winfo_width()))
        container_h = max(height, int(self.winfo_height()))
        if toplevel is not None:
            try:
                toplevel.update_idletasks()
            except Exception:
                pass
            try:
                container_w = max(container_w, int(toplevel.winfo_width()))
                container_h = max(container_h, int(toplevel.winfo_height()))
            except Exception:
                pass

        if container_w <= 0 or container_h <= 0:
            container_w = max(container_w, width)
            container_h = max(container_h, height)

        metrics = _calculate_quick_action_metrics(
            len(self._button_order), container_w, container_h, toolbar_h=toolbar_h
        )
        previous = self._quick_action_metrics
        if previous is not None:
            diameter_change = abs(metrics.diameter - previous.diameter)
            relative_change = diameter_change / max(previous.diameter, 1)
            if (
                relative_change < 0.05
                and metrics.columns == previous.columns
                and metrics.rows == previous.rows
                and metrics.padding == previous.padding
            ):
                return

        self._quick_action_metrics = metrics
        self._apply_quick_action_metrics(metrics, viewport_height=height)

    def _apply_quick_action_metrics(
        self, metrics: _QuickActionMetrics, *, viewport_height: int
    ) -> None:
        frame = getattr(self, "_buttons_frame", None)
        if frame is None:
            return

        outline_width = max(2, int(metrics.diameter * 0.04))
        icon_limit = max(24, metrics.diameter - 2 * (outline_width + max(6, outline_width // 2)))

        max_columns = 3
        for column in range(max_columns):
            weight = 1 if column < metrics.columns else 0
            minsize = metrics.diameter + metrics.padding * 2 if column < metrics.columns else 0
            try:
                frame.grid_columnconfigure(column, weight=weight, minsize=minsize, uniform="quick_actions")
            except Exception:
                pass

        max_rows = 3
        for row_index in range(max_rows):
            weight = 1 if row_index < metrics.rows else 0
            minsize = metrics.diameter + metrics.padding * 2 if row_index < metrics.rows else 0
            try:
                frame.grid_rowconfigure(row_index, weight=weight, minsize=minsize, uniform="quick_actions_rows")
            except Exception:
                pass

        for index, name in enumerate(self._button_order):
            button = self.buttons.get(name)
            if button is None:
                continue
            try:
                button.grid_forget()
            except Exception:
                pass
            row = index // metrics.columns
            column = index % metrics.columns
            try:
                button.grid(row=row, column=column, padx=metrics.padding, pady=metrics.padding, sticky="nsew")
            except Exception:
                continue
            try:
                button.resize(metrics.diameter)
            except Exception:
                button.configure(width=metrics.diameter, height=metrics.diameter)
            icon_name = self._button_icon_names.get(name)
            if icon_name:
                try:
                    icon_image = load_icon(icon_name, size=min(128, int(icon_limit)))
                    button.configure(icon=icon_image, show_text=False)
                except Exception:
                    pass
            else:
                button.configure(icon=None, show_text=True)

        min_height = max(metrics.diameter * 2, int(viewport_height * 0.32))
        max_height = max(min_height, int(viewport_height * 0.48))
        target_height = max(min_height, min(max_height, int(viewport_height * 0.4)))
        try:
            self._weight_container.configure(height=target_height)
        except Exception:
            pass

    def _resolve_digit_font(self) -> str:
        if self._digit_font_family:
            return self._digit_font_family
        try:
            available = tkfont.families(self)
        except Exception:
            available = []
        normalized = {name.lower(): name for name in available}
        for candidate in ("Share Tech Mono", "ShareTechMono", "DejaVu Sans Mono", "Monospace", "TkFixedFont"):
            if candidate.lower() in normalized:
                self._digit_font_family = normalized[candidate.lower()]
                break
        else:
            self._digit_font_family = "TkFixedFont"
        return self._digit_font_family

    def _redraw_separator(self) -> None:
        width = max(int(self._separator_container.winfo_width()), 0)
        if width <= 0:
            return
        height = max(10, int(self._separator_canvas.cget("height") or 12))
        usable_width = max(12, width - 12)
        x0 = max(0, (width - usable_width) // 2)
        x1 = x0 + usable_width
        centre_y = height // 2
        if x1 <= x0:
            return
        self._separator_canvas.configure(width=width, height=height)
        draw_neon_separator(
            self._separator_canvas,
            x0,
            centre_y,
            x1,
            centre_y,
            color="#00E5FF",
        )

    # ------------------------------------------------------------------
    def _configure_tare_long_press(self) -> None:
        button = self.buttons.get("btn_tare")
        if button is None:
            return
        button.configure(command=self._on_tare_command)
        button.bind("<ButtonPress-1>", self._on_tare_press, add="+")
        button.bind("<ButtonRelease-1>", self._on_tare_release, add="+")
        button.bind("<Leave>", self._on_tare_leave, add="+")

    def _on_tare_press(self, _event: tk.Event | None = None) -> None:
        self._tara_long_press_triggered = False
        self._cancel_tare_timer()
        self._tara_long_press_job = self.after(600, self._trigger_tare_long_press)

    def _on_tare_release(self, _event: tk.Event | None = None) -> str | None:
        self._cancel_tare_timer()
        return None

    def _on_tare_leave(self, _event: tk.Event | None = None) -> None:
        if not self._tara_long_press_triggered:
            self._cancel_tare_timer()

    def _on_tare_command(self) -> None:
        if self._tara_long_press_triggered:
            self._tara_long_press_triggered = False
            return
        self._handle_tare()

    def _cancel_tare_timer(self) -> None:
        if self._tara_long_press_job is not None:
            try:
                self.after_cancel(self._tara_long_press_job)
            except Exception:
                pass
            self._tara_long_press_job = None

    def _trigger_tare_long_press(self) -> None:
        self._tara_long_press_job = None
        self._tara_long_press_triggered = True
        if not messagebox.askyesno("Zero", "¿Poner peso a cero?"):
            return
        try:
            self.on_zero()
        except Exception as exc:  # pragma: no cover - defensive UI logging
            LOGGER.error("Zero failed: %s", exc, exc_info=True)


__all__ = ["HomeView"]
