"""Home view showing live weight and quick actions."""
from __future__ import annotations

import logging
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
    FONT_BODY_BOLD,
    FONT_DIGITS,
    PALETTE,
    draw_neon_frame,
    draw_neon_separator,
    format_mmss,
    neon_border,
)
from ..widgets import NeoGhostButton
from ..dialogs import TimerDialog
from ..widgets_mascota import MascotaCanvas


LOGGER = logging.getLogger(__name__)

ENABLE_BUTTONS_NEON = False
ENABLE_CENTER_SEPARATOR = False

SAFE_BOTTOM = 32
MAX_COLS = 3
MAX_ROWS = 2
OUTER_MARGIN = 12
BUTTON_ASPECT = 1.35
BUTTON_BORDER_PAD = 12
BUTTON_MIN_W = 116
BUTTON_MIN_H = 86
BUTTON_MAX_W = 260
BUTTON_MAX_H = 186
WEIGHT_MIN_HEIGHT = 216
WEIGHT_PREF_RATIO = 0.38
WEIGHT_MAX_RATIO = 0.44
BUTTON_SIZE_SCALE = 0.66
GAP_FRACTION = 0.12
MIN_BUTTON_GAP = 12

# Physical offsets applied to the quick-actions block.
OFFSET_UP_CM = 1.0
OFFSET_RIGHT_CM = 0.5
MARGIN = 8


@dataclass(frozen=True)
class ButtonLayoutMetrics:
    button_w: int
    button_h: int
    rows: int
    cols: int
    col_gap: int
    row_gap: int
    frame_width: int
    frame_height: int
    outer_margin: int
    frame_padding: tuple[int, int, int, int]
    frame_top_pad: int
    frame_bottom_pad: int


@dataclass(frozen=True)
class HomeLayoutMetrics:
    content_pad_left: int
    content_pad_right: int
    top_margin: int
    weight_height: int
    weight_bottom_pad: int
    value_font_px: int
    unit_font_px: int
    separator_height: int
    separator_gap: int
    button_metrics: ButtonLayoutMetrics

ICONS = {
    "timer": "timer.png",
    "settings": "gear.png",
    "tare": "text:>T<",
    "swap": "text:g ↔ ml",
    "food": "apple.png",
    "recipe": "recipe.png",
}


def _scaled_font(font_def: tuple[str, ...] | tuple[str, int] | tuple[str, int, str], scale: float) -> tuple:
    """Return a font tuple scaled by ``scale`` while preserving style flags."""

    if not font_def:
        base = ("TkDefaultFont", 12)
    else:
        base = tuple(font_def)  # type: ignore[arg-type]

    family = base[0] if len(base) > 0 else "TkDefaultFont"
    size = base[1] if len(base) > 1 and isinstance(base[1], (int, float)) else 12
    scaled_size = max(8, int(round(float(size) * max(0.1, scale))))
    extras = tuple(base[2:]) if len(base) > 2 else ()
    return (family, scaled_size, *extras)


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
        self._mascota: MascotaCanvas | None = None
        self._mascota_fallback: tk.Label | None = None
        self._mascota_desired = False
        self._overlay_resize_job: str | None = None
        self._timer_dialog: TimerDialog | None = None
        self._timer_remaining = 0
        self._timer_tick_job: str | None = None
        self._timer_state: str = "idle"
        self._timer_flash_job: str | None = None
        self._timer_blink_job: str | None = None
        self._timer_blink_visible = True
        self._local_timer_text: str | None = None
        self._layout_metrics: HomeLayoutMetrics | None = None
        self._content_padding: tuple[int, int] = (OUTER_MARGIN, OUTER_MARGIN)
        self._separator_margin = OUTER_MARGIN
        self._buttons_outer: tk.Misc | None = None
        self._button_font = _scaled_font(FONT_BODY_BOLD, BUTTON_SIZE_SCALE)
        self._weight_border_job: str | None = None
        self._buttons_border_job: str | None = None
        self._weight_border_padding = BUTTON_BORDER_PAD
        self._weight_border_radius = 26
        self._weight_border_color = COLOR_PRIMARY
        self._buttons_border_padding = BUTTON_BORDER_PAD
        self._buttons_border_radius = 24
        self._buttons_border_color = COLOR_PRIMARY
        self._buttons_outer_padx: tuple[int, int] = (0, 0)
        self._buttons_outer_pady: tuple[int, int] = (0, 0)
        self._base_button_padx: tuple[int, int] = (0, 0)
        self._base_button_pady: tuple[int, int] = (0, 0)

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
        style.configure("Home.WeightGlowUnit.TLabel", background=COLOR_BG, foreground=COLOR_ACCENT, font=FONT_DIGITS)
        style.configure("Home.WeightUnit.TLabel", background=COLOR_BG, foreground=COLOR_PRIMARY, font=FONT_DIGITS)
        style.configure("Home.Status.TFrame", background=COLOR_BG)
        style.configure(
            "Home.StatusAccent.TLabel",
            background=COLOR_BG,
            foreground=COLOR_ACCENT,
            font=FONT_BODY_BOLD,
        )
        style.configure(
            "Home.Buttons.TFrame",
            background=COLOR_BG,
            padding=0,
            borderwidth=0,
            relief="flat",
        )
        style.configure(
            "Home.Timer.TLabel",
            background=COLOR_BG,
            foreground=PALETTE.get("neon_blue", COLOR_PRIMARY),
            font=FONT_BODY_BOLD,
        )
        style.configure(
            "Home.TimerFlash.TLabel",
            background=PALETTE.get("surface_hi", COLOR_BG),
            foreground=PALETTE.get("accent", COLOR_ACCENT),
            font=FONT_BODY_BOLD,
            padding=(SPACING["sm"], SPACING["xs"]),
        )

        self.configure(style="Home.Root.TFrame", padding=SPACING["lg"])

        self._weight_value_var = tk.StringVar(value="0")
        self._weight_unit_var = tk.StringVar(value="g")
        weight_container = ttk.Frame(self, style="Home.Weight.TFrame")
        weight_container.pack(fill="x")
        weight_container.pack_propagate(False)
        weight_container.pack_configure(padx=0)
        weight_container.bind("<Configure>", lambda _e: self._queue_weight_border_redraw(), add=True)

        glow_frame = ttk.Frame(weight_container, style="Home.Weight.TFrame")
        glow_frame.place(relx=0.5, rely=0.5, anchor="center")
        glow_value = ttk.Label(glow_frame, textvariable=self._weight_value_var, style="Home.WeightGlow.TLabel")
        glow_unit = ttk.Label(glow_frame, textvariable=self._weight_unit_var, style="Home.WeightGlowUnit.TLabel")
        glow_value.grid(row=0, column=0, sticky="s")
        glow_unit.grid(row=0, column=1, sticky="s", padx=(12, 0))
        glow_frame.grid_columnconfigure(0, weight=1)
        glow_frame.lower()

        value_frame = ttk.Frame(weight_container, style="Home.Weight.TFrame")
        value_frame.place(relx=0.5, rely=0.5, anchor="center")
        self._weight_label = ttk.Label(value_frame, textvariable=self._weight_value_var, style="Home.WeightPrimary.TLabel")
        self._unit_label = ttk.Label(value_frame, textvariable=self._weight_unit_var, style="Home.WeightUnit.TLabel")
        self._weight_label.grid(row=0, column=0, sticky="s")
        self._unit_label.grid(row=0, column=1, sticky="s", padx=(12, 0))
        value_frame.grid_columnconfigure(0, weight=1)
        self._weight_glow = glow_value
        self._weight_glow_unit = glow_unit
        self._weight_unit_label = self._unit_label
        self._weight_container = weight_container

        self._weight_label.name = "weight_display"  # type: ignore[attr-defined]
        if hasattr(self.controller, "register_widget"):
            self.controller.register_widget("weight_display", self._weight_label)

        self._weight_border = neon_border(
            weight_container,
            padding=self._weight_border_padding,
            radius=self._weight_border_radius,
            color=self._weight_border_color,
        )
        if self._weight_border is not None:
            try:
                self._weight_border.bind("<Configure>", lambda _e: self._queue_weight_border_redraw(), add=True)
            except Exception:
                pass

        status_frame = ttk.Frame(self, style="Home.Status.TFrame")
        self._status_frame = status_frame
        status_frame.pack(fill="x", pady=(SPACING["md"], SPACING["sm"]))
        status_frame.columnconfigure(0, weight=1)

        self._timer_var = tk.StringVar(value="")
        self._timer_label = ttk.Label(status_frame, textvariable=self._timer_var, style="Home.Timer.TLabel")
        self._timer_label.grid(row=0, column=0, sticky="e")
        try:
            self._timer_label.grid_remove()
        except Exception:
            pass

        self._timer_flash_label = ttk.Label(self, text="", style="Home.TimerFlash.TLabel")
        try:
            self._timer_flash_label.place_forget()
        except Exception:
            pass

        self._separator_container: ttk.Frame | None = None
        self._separator_canvas: tk.Canvas | None = None
        self._separator_job: str | None = None
        if ENABLE_CENTER_SEPARATOR:
            separator_container = ttk.Frame(self, style="Home.Status.TFrame")
            separator_container.pack(fill="x")
            self._separator_container = separator_container
            separator_canvas = tk.Canvas(
                separator_container,
                height=8,
                background=COLOR_BG,
                highlightthickness=0,
                bd=0,
            )
            separator_canvas.pack(fill="x", expand=True)
            self._separator_canvas = separator_canvas
            separator_container.bind("<Configure>", lambda _e: self._schedule_separator_redraw(), add=True)
            separator_canvas.bind("<Configure>", lambda _e: self._schedule_separator_redraw(), add=True)

        self.overlay_host: tk.Frame | None = None
        self.bind("<Configure>", lambda _e: self._queue_overlay_resize(), add=True)

        buttons_outer = ttk.Frame(self, style="Home.Buttons.TFrame", padding=0)
        buttons_outer.pack(fill="x", anchor="n")
        buttons_outer.pack_configure(padx=self._buttons_outer_padx)
        buttons_outer.grid_columnconfigure(0, weight=1, uniform="qa")
        buttons_outer.grid_rowconfigure(0, weight=1, uniform="qa")
        try:
            buttons_outer.pack_propagate(False)
        except Exception:
            pass
        self._buttons_outer = buttons_outer

        buttons_frame = ttk.Frame(buttons_outer, style="Home.Buttons.TFrame", padding=0)
        try:
            buttons_frame.configure(borderwidth=0, relief="flat")
            buttons_frame.configure(highlightthickness=0)
        except Exception:
            pass
        self._buttons_frame = buttons_frame
        self._buttons_border = None
        if ENABLE_BUTTONS_NEON:
            buttons_outer.bind("<Configure>", lambda _e: self._queue_buttons_border_redraw(), add=True)
            buttons_frame.bind("<Configure>", lambda _e: self._queue_buttons_border_redraw(), add=True)
            self._buttons_border = neon_border(
                buttons_frame,
                padding=self._buttons_border_padding,
                radius=self._buttons_border_radius,
                color=self._buttons_border_color,
            )
            if self._buttons_border is not None:
                try:
                    self._buttons_border.bind("<Configure>", lambda _e: self._queue_buttons_border_redraw(), add=True)
                except Exception:
                    pass

        self.buttons: Dict[str, tk.Misc] = {}
        self._tara_long_press_job: str | None = None
        self._tara_long_press_triggered = False
        self._button_icon_names: Dict[str, str | None] = {}
        self._button_order: list[str] = []
        self._layout_signature: tuple[int, ...] | None = None
        self._grid_columns = 0
        self._grid_rows = 0

        base_button_h = BUTTON_MIN_H
        base_button_w = int(round(base_button_h * BUTTON_ASPECT))
        base_icon_size = max(32, int(round(72 * BUTTON_SIZE_SCALE)))

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
            icon_image = (
                load_icon(spec["icon"], size=base_icon_size)
                if spec.get("icon")
                else None
            )
            show_text = spec.get("icon") is None or icon_image is None
            button = NeoGhostButton(
                buttons_frame,
                width=base_button_w,
                height=base_button_h,
                shape="pill",
                corner_radius=26,
                prefer_aspect=1.4,
                min_w=BUTTON_MIN_W,
                min_h=BUTTON_MIN_H,
                max_w=BUTTON_MAX_W,
                max_h=BUTTON_MAX_H,
                outline_color=PALETTE["neon_fuchsia"],
                outline_width=2,
                text=spec["text"],
                icon=icon_image,
                command=spec["command"],
                tooltip=spec["tooltip"],
                show_text=show_text,
                text_color=PALETTE["primary"] if show_text else None,
                font=self._button_font,
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
        self.after_idle(self._redraw_weight_border)
        if ENABLE_BUTTONS_NEON:
            self.after_idle(self._redraw_buttons_border)
        if ENABLE_CENTER_SEPARATOR:
            self.after_idle(self._redraw_separator)

    # ------------------------------------------------------------------
    def update_weight(self, grams: Optional[float], stable: bool) -> None:
        if grams is None:
            self._has_weight_value = False
            self._weight_value_var.set("--")
            self._weight_unit_var.set(self._units)
            return

        self._last_grams = float(grams)
        self._has_weight_value = True
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
        self._refresh_display()

    # ------------------------------------------------------------------
    def _handle_tare(self) -> None:
        self.on_tare()

    def _handle_toggle_units(self) -> None:
        self.on_toggle_units()

    def _handle_open_food(self) -> None:
        self.on_open_food()

    def _handle_open_recipes(self) -> None:
        self.on_open_recipes()

    def _handle_open_timer(self) -> None:
        dialog = self._ensure_timer_dialog()
        if dialog is None:
            self.on_open_timer()
            return
        try:
            initial = self._timer_remaining if self._timer_remaining > 0 else None
            dialog.present(initial_seconds=initial)
        except Exception:
            LOGGER.debug("No se pudo presentar TimerDialog", exc_info=True)

    def _ensure_timer_dialog(self) -> TimerDialog | None:
        dialog = self._timer_dialog
        if dialog is not None:
            try:
                if int(dialog.winfo_exists()):
                    return dialog
            except Exception:
                self._timer_dialog = None

        parent = getattr(self.controller, "root", None)
        if parent is None or not hasattr(parent, "winfo_exists"):
            parent = self.winfo_toplevel()
        else:
            try:
                if not int(parent.winfo_exists()):
                    parent = self.winfo_toplevel()
            except Exception:
                parent = self.winfo_toplevel()
        try:
            dialog = TimerDialog(
                parent,
                on_accept=self._start_timer_from_dialog,
                on_cancel=self._on_timer_dialog_closed,
            )
        except Exception:
            LOGGER.exception("No se pudo crear TimerDialog", exc_info=True)
            self._timer_dialog = None
            return None

        dialog.bind("<Destroy>", self._on_timer_dialog_destroyed, add=True)
        self._timer_dialog = dialog
        return dialog

    def _on_timer_dialog_closed(self) -> None:
        self._timer_dialog = None
        try:
            self.focus_set()
        except Exception:
            pass

    def _on_timer_dialog_destroyed(self, _event: tk.Event | None = None) -> None:
        self._timer_dialog = None

    def _handle_open_settings(self) -> None:
        self.on_open_settings()

    # Mascota overlay -------------------------------------------------
    def _ensure_overlay_host(self) -> tk.Frame | None:
        host = self.overlay_host
        if host is not None:
            try:
                if int(host.winfo_exists()):
                    return host
            except Exception:
                self.overlay_host = None
                host = None

        try:
            host = tk.Frame(self, bg=COLOR_BG, highlightthickness=0, bd=0)
        except Exception:
            self.overlay_host = None
            return None

        host.place_forget()
        try:
            host.configure(takefocus=0)
        except Exception:
            pass
        try:
            host.bind("<Configure>", lambda _e: self._queue_overlay_resize(), add=True)
        except Exception:
            pass
        self.overlay_host = host
        return host

    def show_mascota(self) -> None:
        if self._mascota_desired:
            return
        host = self._ensure_overlay_host()
        if host is None:
            return
        self._mascota_desired = True
        self._ensure_mascota_visible()

    def hide_mascota(self) -> None:
        if not self._mascota_desired and self._mascota is None and self._mascota_fallback is None:
            return
        self._mascota_desired = False
        self._teardown_mascota()

    def _ensure_mascota_visible(self) -> None:
        if not self._mascota_desired:
            return
        host = self._ensure_overlay_host()
        if host is None:
            return
        self._queue_overlay_resize()
        if not host.winfo_manager():
            self._apply_overlay_geometry()
        if self._mascota is None and self._mascota_fallback is None:
            try:
                canvas = MascotaCanvas(host, bg=host.cget("bg"))
                try:
                    canvas.configure(takefocus=0)
                except Exception:
                    pass
                canvas.pack(fill="both", expand=True)
                self._mascota = canvas
                self._mascota.start_animation()
            except Exception:
                self._mascota = None
                self._create_mascota_fallback()
        elif self._mascota is not None:
            self._mascota.start_animation()
        host.lift()
        try:
            self._buttons_frame.lift()
        except Exception:
            pass
        self._queue_overlay_resize()

    def _teardown_mascota(self) -> None:
        if self._mascota is not None:
            try:
                self._mascota.stop_animation()
            except Exception:
                pass
            try:
                self._mascota.destroy()
            except Exception:
                pass
            self._mascota = None
        if self._mascota_fallback is not None:
            try:
                self._mascota_fallback.destroy()
            except Exception:
                pass
            self._mascota_fallback = None
        host = self.overlay_host
        if host is not None:
            try:
                if int(host.winfo_exists()):
                    host.place_forget()
            except Exception:
                pass

    def _create_mascota_fallback(self) -> None:
        if self._mascota_fallback is not None:
            return
        host = self._ensure_overlay_host()
        if host is None:
            return
        label = tk.Label(
            host,
            text="BASCULÍN",
            bg=host.cget("bg"),
            fg=COLOR_ACCENT,
            font=("DejaVu Sans", 22, "bold"),
            anchor="center",
            justify="center",
        )
        try:
            label.configure(takefocus=0)
        except Exception:
            pass
        label.pack(fill="both", expand=True)
        self._mascota_fallback = label

    def _queue_overlay_resize(self) -> None:
        if self._overlay_resize_job is not None:
            try:
                self.after_cancel(self._overlay_resize_job)
            except Exception:
                pass
        host = self.overlay_host
        if host is None:
            return
        try:
            if not int(host.winfo_exists()):
                return
        except Exception:
            return
        self._overlay_resize_job = self.after(120, self._apply_overlay_geometry)

    def _apply_overlay_geometry(self) -> None:
        self._overlay_resize_job = None
        host = self.overlay_host
        if host is None:
            return
        try:
            if not int(host.winfo_exists()):
                return
        except Exception:
            return
        width = max(1, int(self.winfo_width() or 0))
        height = max(1, int(self.winfo_height() or 0))
        margin_x = max(12, int(width * 0.03))
        margin_y = max(12, int(height * 0.05))
        try:
            button_top = int(self._buttons_frame.winfo_y())
        except Exception:
            button_top = height - margin_y
        if button_top <= 0 or button_top > height:
            button_top = height - margin_y
        size = self._compute_overlay_size(width, button_top, margin_y)
        y = max(margin_y, button_top - size - margin_y)
        x = margin_x
        if not host.winfo_manager():
            host.place(x=x, y=max(0, y), width=size, height=size)
        else:
            host.place_configure(x=x, y=max(0, y), width=size, height=size)
        if self._mascota is not None:
            try:
                self._mascota.configure(width=size, height=size)
            except Exception:
                pass
        elif self._mascota_fallback is not None:
            try:
                self._mascota_fallback.configure(width=size, height=size)
            except Exception:
                pass

    def _compute_overlay_size(self, width: int, button_top: int, margin_y: int) -> int:
        available_height = max(180, button_top - margin_y * 2)
        scaled = int(width * 0.32)
        size = min(available_height, scaled)
        return max(180, min(260, size))

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
        self.after_idle(self._relayout)

    def _relayout(self) -> None:
        width = max(int(self.winfo_width()), 0)
        height = max(int(self.winfo_height()), 0)
        if width <= 0:
            width = 1024
        if height <= 0:
            height = 600

        button_count = max(1, len(self._button_order) or len(self.buttons) or 0)

        sample_button: Optional[NeoGhostButton] = None
        if self._button_order:
            for name in self._button_order:
                candidate = self.buttons.get(name)
                if isinstance(candidate, NeoGhostButton):
                    sample_button = candidate
                    break
        if sample_button is None and self.buttons:
            first = next(iter(self.buttons.values()))
            if isinstance(first, NeoGhostButton):
                sample_button = first

        metrics = self._compute_layout_metrics(width, height, button_count, sample_button)
        signature = (
            width,
            height,
            metrics.value_font_px,
            metrics.unit_font_px,
            metrics.weight_height,
            metrics.separator_height,
            metrics.separator_gap,
            metrics.button_metrics.button_w,
            metrics.button_metrics.button_h,
            metrics.button_metrics.rows,
            metrics.button_metrics.cols,
            metrics.button_metrics.col_gap,
            metrics.button_metrics.row_gap,
            metrics.button_metrics.frame_width,
            metrics.button_metrics.frame_height,
            metrics.button_metrics.outer_margin,
            metrics.top_margin,
            metrics.weight_bottom_pad,
            metrics.button_metrics.frame_top_pad,
            metrics.content_pad_left,
            metrics.content_pad_right,
        )
        if self._layout_signature == signature:
            self._apply_quick_action_offsets(metrics.button_metrics, width, height)
            return
        self._layout_signature = signature
        self._layout_metrics = metrics
        self._content_padding = (metrics.content_pad_left, metrics.content_pad_right)
        self._separator_margin = metrics.button_metrics.outer_margin

        self._apply_weight_metrics(
            metrics.value_font_px,
            metrics.unit_font_px,
            metrics.weight_height,
            metrics.top_margin,
            metrics.weight_bottom_pad,
        )
        if ENABLE_CENTER_SEPARATOR:
            self._apply_separator_metrics(metrics.separator_height, 0, metrics.separator_gap)
        self._apply_button_metrics(metrics.button_metrics, width, height)

        if LOGGER.isEnabledFor(logging.DEBUG):
            bm = metrics.button_metrics
            LOGGER.debug(
                "Home layout size=%dx%d buttons=%dx%d btn=%dx%d gaps=%d/%d pad=%d/%d",
                width,
                height,
                bm.cols,
                bm.rows,
                bm.button_w,
                bm.button_h,
                bm.col_gap,
                bm.row_gap,
                metrics.content_pad_left,
                metrics.content_pad_right,
            )

        self._queue_overlay_resize()
        self._apply_quick_action_offsets(metrics.button_metrics, width, height)

    def _compute_layout_metrics(
        self,
        width: int,
        height: int,
        button_count: int,
        sample_button: Optional[NeoGhostButton],
    ) -> HomeLayoutMetrics:
        prefer_aspect = BUTTON_ASPECT
        if sample_button is not None:
            try:
                prefer_aspect = float(getattr(sample_button, "prefer_aspect", BUTTON_ASPECT))
            except Exception:
                prefer_aspect = BUTTON_ASPECT
        if prefer_aspect <= 0:
            prefer_aspect = BUTTON_ASPECT
        prefer_aspect = max(1.3, min(1.4, prefer_aspect))

        safe_count = max(1, button_count)
        cols = MAX_COLS
        rows = MAX_ROWS if safe_count > MAX_COLS else 1
        rows = max(1, min(MAX_ROWS, rows))

        col_gap = MIN_BUTTON_GAP
        row_gap = MIN_BUTTON_GAP
        frame_margin_x = max(6, OUTER_MARGIN // 2)
        frame_margin_y = max(6, OUTER_MARGIN // 2)

        spacing_xl = SPACING.get("xl", 32)
        top_margin = max(spacing_xl, int(height * 0.05))

        available_after_margins = max(0, height - top_margin - SAFE_BOTTOM)
        weight_pref = int(round(height * WEIGHT_PREF_RATIO))
        weight_height = max(WEIGHT_MIN_HEIGHT, weight_pref)
        weight_height = min(weight_height, int(height * WEIGHT_MAX_RATIO))
        weight_height = min(weight_height, available_after_margins)
        if available_after_margins and weight_height <= 0:
            weight_height = min(available_after_margins, WEIGHT_MIN_HEIGHT)
        weight_height = max(0, weight_height)

        if ENABLE_CENTER_SEPARATOR:
            separator_height = max(6, min(12, int(height * 0.014)))
            separator_gap = max(14, row_gap + 6)
        else:
            separator_height = 0
            separator_gap = 0
        weight_bottom_pad = max(18, row_gap + 6)

        button_area_height = max(
            0,
            available_after_margins - weight_height - separator_gap - weight_bottom_pad,
        )

        usable_width = max(0, width - frame_margin_x * 2)
        usable_height = max(0, button_area_height - frame_margin_y * 2)

        button_width = BUTTON_MIN_W
        button_height = BUTTON_MIN_H
        btn_d = BUTTON_MIN_W

        for _ in range(2):
            total_row_gaps = max(0, (rows - 1) * row_gap)
            total_col_gaps = max(0, (cols - 1) * col_gap)

            per_col_cap = (usable_width - total_col_gaps) / cols if cols else usable_width
            cap_from_height = (usable_height - total_row_gaps) / rows if rows else usable_height
            cap_from_width = per_col_cap / prefer_aspect if prefer_aspect else per_col_cap

            btn_cap_h = max(0.0, min(cap_from_height, cap_from_width))
            if btn_cap_h <= 0:
                button_height = float(BUTTON_MIN_H)
            else:
                button_height = min(btn_cap_h, float(BUTTON_MAX_H))
                button_height = max(float(BUTTON_MIN_H), button_height)

            button_height = max(BUTTON_MIN_H, int(round(button_height)))

            button_width = int(round(button_height * prefer_aspect))
            if per_col_cap > 0:
                button_width = min(button_width, int(per_col_cap))
            button_width = max(BUTTON_MIN_W, min(button_width, BUTTON_MAX_W))

            btn_d = max(1, min(button_width, button_height))
            desired_gap = max(MIN_BUTTON_GAP, int(round(GAP_FRACTION * btn_d)))

            if desired_gap == col_gap == row_gap:
                break

            col_gap = desired_gap
            row_gap = desired_gap

        total_row_gaps = max(0, (rows - 1) * row_gap)
        total_col_gaps = max(0, (cols - 1) * col_gap)

        frame_width = cols * button_width + total_col_gaps + frame_margin_x * 2
        frame_height = rows * button_height + total_row_gaps + frame_margin_y * 2

        extra_vertical = max(0, button_area_height - frame_height)
        frame_top_pad = int(extra_vertical // 2)
        frame_bottom_pad = int(SAFE_BOTTOM + (extra_vertical - frame_top_pad))

        frame_padding = (
            frame_margin_x,
            frame_margin_y,
            frame_margin_x,
            frame_margin_y,
        )

        if weight_height:
            value_font = min(140, max(64, int(weight_height * 0.58)))
        else:
            value_font = 96
        unit_font = value_font

        button_metrics = ButtonLayoutMetrics(
            button_w=int(button_width),
            button_h=int(button_height),
            rows=rows,
            cols=cols,
            col_gap=col_gap,
            row_gap=row_gap,
            frame_width=int(frame_width),
            frame_height=int(frame_height),
            outer_margin=frame_margin_x,
            frame_padding=frame_padding,
            frame_top_pad=frame_top_pad,
            frame_bottom_pad=frame_bottom_pad,
        )

        return HomeLayoutMetrics(
            content_pad_left=frame_margin_x,
            content_pad_right=frame_margin_x,
            top_margin=top_margin,
            weight_height=int(weight_height),
            weight_bottom_pad=weight_bottom_pad,
            value_font_px=value_font,
            unit_font_px=unit_font,
            separator_height=separator_height,
            separator_gap=separator_gap,
            button_metrics=button_metrics,
        )

    def _apply_weight_metrics(
        self,
        weight_font_px: int,
        unit_font_px: int,
        container_height: int,
        margin_top: int,
        margin_bottom: int,
    ) -> None:
        family = self._resolve_digit_font()
        weight_font = (family, weight_font_px)
        unit_font = weight_font if unit_font_px == weight_font_px else (family, unit_font_px)
        for label in (self._weight_glow, self._weight_label):
            label.configure(font=weight_font)
        for label in (self._weight_glow_unit, self._weight_unit_label):
            label.configure(font=unit_font)

        unit_pad = max(4, min(8, weight_font_px // 8 if weight_font_px else 4))
        self._unit_label.grid_configure(padx=(unit_pad, 0))
        self._weight_glow_unit.grid_configure(padx=(unit_pad, 0))

        target_height = int(container_height)
        try:
            self._weight_container.configure(height=target_height)
        except Exception:
            pass
        self._weight_container.pack_configure(pady=(margin_top, margin_bottom))
        self._queue_weight_border_redraw()

    def _apply_separator_metrics(self, height_px: int, margin_top: int, margin_bottom: int) -> None:
        if not ENABLE_CENTER_SEPARATOR:
            return
        container = getattr(self, "_separator_container", None)
        canvas = getattr(self, "_separator_canvas", None)
        if container is None or canvas is None:
            return
        container.pack_configure(pady=(margin_top, margin_bottom))
        canvas.configure(height=height_px)
        self._schedule_separator_redraw()

    def _apply_button_metrics(self, metrics: ButtonLayoutMetrics, view_width: int, view_height: int) -> None:
        frame = getattr(self, "_buttons_frame", None)
        if frame is None or not self.buttons:
            return

        button_w = max(1, int(metrics.button_w))
        button_h = max(1, int(metrics.button_h))
        rows = max(1, int(metrics.rows))
        cols = max(1, int(metrics.cols))

        frame.configure(padding=metrics.frame_padding)
        outer = getattr(self, "_buttons_outer", None)
        if outer is not None:
            adjusted_bottom = max(0, int(metrics.frame_bottom_pad) - 20)
            top_pad = max(8, int(metrics.frame_top_pad) - 30)
            self._buttons_outer_padx = (0, 0)
            self._buttons_outer_pady = (top_pad, adjusted_bottom)
            outer.pack_configure(pady=self._buttons_outer_pady, padx=self._buttons_outer_padx)
            try:
                outer.configure(width=max(1, int(metrics.frame_width)))
            except Exception:
                pass
        frame.configure(width=max(1, int(metrics.frame_width)), height=max(1, int(metrics.frame_height)))
        try:
            frame.pack_propagate(False)
        except Exception:
            pass
        try:
            frame.grid_propagate(False)
        except Exception:
            pass

        for column in range(self._grid_columns):
            if column >= cols:
                frame.grid_columnconfigure(column, weight=0, minsize=0, uniform="qa")
        for row in range(self._grid_rows):
            if row >= rows:
                frame.grid_rowconfigure(row, weight=0, minsize=0, uniform="qa")

        for column in range(cols):
            frame.grid_columnconfigure(column, weight=1, minsize=button_w, uniform="qa")
        for row in range(rows):
            frame.grid_rowconfigure(row, weight=1, minsize=button_h, uniform="qa")

        base_padx = (24, 0)
        base_pady = (0, 0)
        self._base_button_padx = base_padx
        self._base_button_pady = base_pady

        self._grid_columns = cols
        self._grid_rows = rows

        h_left = max(0, metrics.col_gap // 2)
        h_right = max(0, metrics.col_gap - h_left)
        v_top = max(0, metrics.row_gap // 2)
        v_bottom = max(0, metrics.row_gap - v_top)

        for index, name in enumerate(self._button_order):
            button = self.buttons.get(name)
            if button is None:
                continue
            row = min(index // cols, max(rows - 1, 0))
            column = min(index % cols, max(cols - 1, 0))

            try:
                button.grid(
                    row=row,
                    column=column,
                    padx=(h_left, h_right),
                    pady=(v_top, v_bottom),
                    sticky="nsew",
                )
            except Exception:
                continue

            try:
                if hasattr(button, "set_size"):
                    button.set_size(button_w, button_h)  # type: ignore[attr-defined]
                else:
                    button.resize(width=button_w, height=button_h)
            except Exception:
                try:
                    button.configure(width=button_w, height=button_h)
                except Exception:
                    pass

        self._apply_quick_action_offsets(metrics, view_width, view_height)

    def _apply_quick_action_offsets(
        self,
        metrics: ButtonLayoutMetrics | None = None,
        view_width: int | None = None,
        view_height: int | None = None,
    ) -> None:
        """Shift and clamp the quick actions block based on button size."""

        frame = getattr(self, "_buttons_frame", None)
        outer = getattr(self, "_buttons_outer", None)
        if frame is None or outer is None:
            return

        if metrics is None:
            layout_metrics = getattr(self, "_layout_metrics", None)
            if layout_metrics is None:
                return
            metrics = layout_metrics.button_metrics

        button_w = max(1, int(metrics.button_w))
        button_h = max(1, int(metrics.button_h))
        cols = max(1, int(metrics.cols))
        rows = max(1, int(metrics.rows))
        col_gap = max(0, int(metrics.col_gap))
        row_gap = max(0, int(metrics.row_gap))

        btn_d = max(1, min(button_w, button_h))
        pad_under_weight = max(8, int(round(0.06 * btn_d)))

        buttons_w = max(
            int(metrics.frame_width),
            cols * button_w + max(0, (cols - 1) * col_gap),
        )
        buttons_h = max(
            int(metrics.frame_height),
            rows * button_h + max(0, (rows - 1) * row_gap),
        )

        try:
            frame.update_idletasks()
        except Exception:
            pass

        try:
            one_cm = max(1, int(round(self.winfo_fpixels("1c"))))
        except Exception:
            one_cm = 38

        px_up = int(round(OFFSET_UP_CM * one_cm))
        px_right = int(round(OFFSET_RIGHT_CM * one_cm))

        weight_container = getattr(self, "_weight_container", None)
        weight_y_root = 0
        weight_h = 0
        if weight_container is not None:
            try:
                weight_container.update_idletasks()
            except Exception:
                pass
            try:
                weight_rooty = int(weight_container.winfo_rooty())
                view_rooty = int(self.winfo_rooty())
                weight_y_root = weight_rooty - view_rooty
            except Exception:
                try:
                    weight_y_root = int(weight_container.winfo_y())
                except Exception:
                    weight_y_root = 0
            try:
                weight_h = int(weight_container.winfo_height())
            except Exception:
                weight_h = 0

        desired_y_root = weight_y_root + weight_h + pad_under_weight - px_up
        y = max(MARGIN, desired_y_root)

        try:
            place_manager = frame.winfo_manager()
        except Exception:
            place_manager = ""

        for forget in (getattr(frame, "pack_forget", None), getattr(frame, "grid_forget", None)):
            if forget is None:
                continue
            try:
                forget()
            except Exception:
                pass

        try:
            parent_widget = frame.nametowidget(frame.winfo_parent())
        except Exception:
            parent_widget = None


        if parent_widget is not None:
            for fn_name in ("pack_propagate", "grid_propagate"):
                fn = getattr(parent_widget, fn_name, None)
                if fn is None:
                    continue
                try:
                    fn(False)
                except Exception:
                    pass


        try:
            view_height_px = int(self.winfo_height())
        except Exception:
            view_height_px = 0
        if not view_height_px and view_height is not None:
            try:
                view_height_px = int(view_height)
            except Exception:
                view_height_px = 0
        if view_height_px:
            max_y = max(MARGIN, view_height_px - buttons_h - MARGIN)
            y = min(y, max_y)

        place_kwargs = dict(
            relx=0.5,
            rely=0.0,
            anchor="n",
            x=px_right,
            y=max(MARGIN, y),
            width=buttons_w,
            height=buttons_h,
        )

        try:
            if place_manager == "place":
                frame.place_configure(**place_kwargs)
            else:
                frame.place(in_=self, **place_kwargs)
        except Exception:
            pass

        try:
            placed_y = int(frame.place_info().get("y", y))
        except Exception:
            placed_y = y
        if view_height_px and placed_y + buttons_h > view_height_px - MARGIN:
            adjusted_y = max(MARGIN, view_height_px - buttons_h - MARGIN)
            try:
                frame.place_configure(y=adjusted_y)
            except Exception:
                pass
            placed_y = adjusted_y

        required_height = placed_y + buttons_h
        try:
            outer.configure(height=required_height)
            outer.pack_propagate(False)
        except Exception:
            pass

        try:
            self.after_idle(self._redraw_separator)
        except Exception:
            pass

            try:
                button.configure(font=self._button_font)
            except Exception:
                pass

            icon_name = self._button_icon_names.get(name)
            if icon_name:
                try:
                    icon_base = min(button_w, button_h)
                    desired_size = max(24, int(round(icon_base * BUTTON_SIZE_SCALE)))
                    icon_image = load_icon(
                        icon_name,
                        size=desired_size,
                        target_diameter=int(icon_base),
                    )
                    button.configure(icon=icon_image, show_text=False)
                except Exception:
                    pass
            else:
                button.configure(icon=None, show_text=True)

        if ENABLE_BUTTONS_NEON:
            self._queue_buttons_border_redraw()
        if ENABLE_CENTER_SEPARATOR:
            self._schedule_separator_redraw()

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

    def _queue_weight_border_redraw(self) -> None:
        if self._weight_border_job is not None:
            try:
                self.after_cancel(self._weight_border_job)
            except Exception:
                pass
        self._weight_border_job = self.after_idle(self._redraw_weight_border)

    def _redraw_weight_border(self) -> None:
        self._weight_border_job = None
        canvas = getattr(self, "_weight_border", None)
        container = getattr(self, "_weight_container", None)
        if canvas is None or container is None:
            return
        try:
            width = int(container.winfo_width())
            height = int(container.winfo_height())
        except Exception:
            return
        if width <= 0 or height <= 0:
            return
        try:
            draw_neon_frame(
                canvas,
                width=width,
                height=height,
                padding=self._weight_border_padding,
                radius=self._weight_border_radius,
                color=self._weight_border_color,
                tags_prefix="neon",
            )
        except Exception:
            pass

    def _queue_buttons_border_redraw(self) -> None:
        if not ENABLE_BUTTONS_NEON:
            return
        if self._buttons_border_job is not None:
            try:
                self.after_cancel(self._buttons_border_job)
            except Exception:
                pass
        self._buttons_border_job = self.after_idle(self._redraw_buttons_border)

    def _redraw_buttons_border(self) -> None:
        if not ENABLE_BUTTONS_NEON:
            return
        self._buttons_border_job = None
        canvas = getattr(self, "_buttons_border", None)
        frame = getattr(self, "_buttons_frame", None)
        if canvas is None or frame is None:
            return
        try:
            width = int(frame.winfo_width())
            height = int(frame.winfo_height())
        except Exception:
            return
        if width <= 0 or height <= 0:
            return
        try:
            draw_neon_frame(
                canvas,
                width=width,
                height=height,
                padding=self._buttons_border_padding,
                radius=self._buttons_border_radius,
                color=self._buttons_border_color,
                tags_prefix="neon",
            )
        except Exception:
            pass

    def _schedule_separator_redraw(self) -> None:
        if not ENABLE_CENTER_SEPARATOR:
            return
        if self._separator_job is not None:
            try:
                self.after_cancel(self._separator_job)
            except Exception:
                pass
        self._separator_job = self.after_idle(self._redraw_separator)

    def _redraw_separator(self) -> None:
        if not ENABLE_CENTER_SEPARATOR:
            return
        self._separator_job = None
        container = getattr(self, "_separator_container", None)
        canvas = getattr(self, "_separator_canvas", None)
        if container is None or canvas is None:
            return
        width = max(int(container.winfo_width()), 0)
        if width <= 0:
            return
        try:
            height_value = int(canvas.cget("height"))
        except Exception:
            height_value = 6
        height = max(4, height_value)
        margin = max(0, int(getattr(self, "_separator_margin", OUTER_MARGIN)))
        x0 = margin
        x1 = max(0, width - margin)
        if x1 <= x0:
            return
        centre_y = height / 2
        canvas.configure(width=width, height=height)
        draw_neon_separator(
            canvas,
            x0,
            centre_y,
            x1,
            centre_y,
            color=PALETTE.get("neon_blue", "#00E5FF"),
            enabled=ENABLE_CENTER_SEPARATOR,
        )

    # ------------------------------------------------------------------
    def _start_timer_from_dialog(self, seconds: int) -> None:
        try:
            seconds = int(seconds)
        except Exception:
            seconds = 0
        if seconds <= 0:
            self._clear_timer_countdown()
            return
        self._timer_state = "running"
        self._timer_remaining = seconds
        self._hide_timer_flash()
        self._update_timer_display()
        self._schedule_timer_tick()

    def _schedule_timer_tick(self) -> None:
        if self._timer_tick_job is not None:
            try:
                self.after_cancel(self._timer_tick_job)
            except Exception:
                pass
        if self._timer_state != "running" or self._timer_remaining <= 0:
            return
        self._timer_tick_job = self.after(1000, self._tick_timer)

    def _tick_timer(self) -> None:
        self._timer_tick_job = None
        if self._timer_state != "running":
            return
        if self._timer_remaining <= 0:
            self._handle_timer_finished()
            return
        self._timer_remaining = max(0, self._timer_remaining - 1)
        if self._timer_remaining <= 0:
            self._handle_timer_finished()
            return
        self._update_timer_display()
        self._schedule_timer_tick()

    def _update_timer_display(self) -> None:
        state = self._timer_state
        if state == "idle":
            self._set_toolbar_timer(None, state="idle")
        elif state == "finished":
            self._set_toolbar_timer(0, state="finished")
        elif state == "running":
            remaining = max(0, int(self._timer_remaining))
            blink = 0 < remaining <= 10
            self._set_toolbar_timer(remaining, state="running", blink=blink)
        else:
            self._set_toolbar_timer(self._timer_remaining, state=state)

    def _clear_timer_countdown(self) -> None:
        if self._timer_tick_job is not None:
            try:
                self.after_cancel(self._timer_tick_job)
            except Exception:
                pass
            self._timer_tick_job = None
        self._timer_state = "idle"
        self._timer_remaining = 0
        self._hide_timer_flash()
        self._cancel_local_timer_blink()
        self._update_timer_display()

    def _play_timer_finished(self) -> None:
        controller = getattr(self, "controller", None)
        audio_service = None
        if controller is not None:
            getter = getattr(controller, "get_audio", None)
            if callable(getter):
                try:
                    audio_service = getter()
                except Exception:
                    audio_service = None
            if audio_service is None:
                audio_service = getattr(controller, "audio_service", None)
            if audio_service is None:
                app = getattr(controller, "app", None)
                if app is not None:
                    get_audio = getattr(app, "get_audio", None)
                    if callable(get_audio):
                        try:
                            audio_service = get_audio()
                        except Exception:
                            audio_service = None
                    if audio_service is None:
                        audio_service = getattr(app, "audio_service", None)

        if audio_service is None:
            return

        played_tone = False

        timer_tone = getattr(audio_service, "timer_finished", None)
        if callable(timer_tone):
            try:
                played_tone = bool(timer_tone())
            except Exception:
                LOGGER.debug("No se pudo reproducir secuencia de temporizador", exc_info=True)

        if not played_tone:
            beep_alarm = getattr(audio_service, "beep_alarm", None)
            if callable(beep_alarm):
                try:
                    beep_alarm()
                    played_tone = True
                except Exception:
                    LOGGER.debug("No se pudo reproducir beep de alarma", exc_info=True)

        if not played_tone:
            beep_ok = getattr(audio_service, "beep_ok", None)
            if callable(beep_ok):
                try:
                    beep_ok()
                    played_tone = True
                    try:
                        beep_ok()
                    except Exception:
                        pass
                except Exception:
                    LOGGER.debug("No se pudo reproducir beep", exc_info=True)

        speak = getattr(audio_service, "speak", None)
        if callable(speak):
            try:
                speak("Temporizador finalizado")
            except Exception:
                LOGGER.debug("No se pudo reproducir TTS de temporizador", exc_info=True)

    def _handle_timer_finished(self) -> None:
        self._timer_state = "finished"
        self._timer_remaining = 0
        self._cancel_local_timer_blink()
        self._update_timer_display()
        self._play_timer_finished()
        self._show_timer_flash()

    def _set_toolbar_timer(self, seconds: int | None, *, state: str, blink: bool = False) -> None:
        text: str | None
        if seconds is None:
            text = None
        else:
            try:
                seconds = max(0, int(seconds))
            except Exception:
                seconds = 0
            text = f"⏱ {format_mmss(seconds)}"

        relayed = self._relay_toolbar_timer(
            text,
            state=state,
            flash=(state == "finished" and text is not None),
            blink=blink and text is not None and state == "running",
        )
        if relayed:
            self._update_local_timer_label(None, False)
        else:
            self._update_local_timer_label(text, blink and text is not None and state == "running")

    def _relay_toolbar_timer(
        self,
        text: str | None,
        *,
        state: str,
        flash: bool = False,
        blink: bool = False,
    ) -> bool:
        updater = getattr(self.controller, "update_toolbar_timer", None)
        if not callable(updater):
            return False
        try:
            updater(text=text, state=state, flash=flash, blink=blink)
            return True
        except Exception:
            LOGGER.debug("No se pudo actualizar el temporizador de la barra", exc_info=True)
            return False

    def _update_local_timer_label(self, text: str | None, blink: bool) -> None:
        label = self._timer_label
        if label is None:
            self._local_timer_text = None
            self._cancel_local_timer_blink()
            return

        self._local_timer_text = text
        if text:
            self._timer_var.set(text)
            try:
                label.grid()
            except Exception:
                pass
            self._configure_local_timer_blink(blink)
        else:
            self._timer_var.set("")
            self._configure_local_timer_blink(False)
            try:
                label.grid_remove()
            except Exception:
                pass

    def _configure_local_timer_blink(self, enabled: bool) -> None:
        if not enabled or not self._local_timer_text:
            self._cancel_local_timer_blink()
            if self._local_timer_text:
                self._timer_var.set(self._local_timer_text)
            return

        if self._timer_blink_job is None:
            self._timer_blink_visible = True
            self._apply_local_timer_blink_state()
            self._timer_blink_job = self.after(250, self._toggle_local_timer_blink)
        else:
            self._apply_local_timer_blink_state()

    def _apply_local_timer_blink_state(self) -> None:
        text = self._local_timer_text if self._timer_blink_visible else ""
        self._timer_var.set(text or "")

    def _toggle_local_timer_blink(self) -> None:
        self._timer_blink_job = None
        self._timer_blink_visible = not self._timer_blink_visible
        self._apply_local_timer_blink_state()
        try:
            self._timer_blink_job = self.after(250, self._toggle_local_timer_blink)
        except Exception:
            self._timer_blink_job = None

    def _cancel_local_timer_blink(self) -> None:
        if self._timer_blink_job is not None:
            try:
                self.after_cancel(self._timer_blink_job)
            except Exception:
                pass
            self._timer_blink_job = None
        self._timer_blink_visible = True

    def _show_timer_flash(self) -> None:
        label = getattr(self, "_timer_flash_label", None)
        if label is None:
            return
        self._hide_timer_flash()
        try:
            label.configure(text="Tiempo finalizado")
            label.place(relx=0.5, rely=0.06, anchor="n")
            label.lift()
        except Exception:
            LOGGER.debug("No se pudo mostrar aviso de fin de temporizador", exc_info=True)
            return
        self._timer_flash_job = self.after(2000, self._hide_timer_flash)

    def _hide_timer_flash(self) -> None:
        if self._timer_flash_job is not None:
            try:
                self.after_cancel(self._timer_flash_job)
            except Exception:
                pass
            self._timer_flash_job = None
        label = getattr(self, "_timer_flash_label", None)
        if label is not None:
            try:
                label.place_forget()
            except Exception:
                pass

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
