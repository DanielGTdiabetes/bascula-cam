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
    FONT_BODY_BOLD,
    FONT_DIGITS,
    PALETTE,
    neon_border,
    draw_neon_separator,
)
from ..widgets import NeoGhostButton
from ..widgets_mascota import MascotaCanvas


LOGGER = logging.getLogger(__name__)

SAFE_TOP = 88
SAFE_BOTTOM = 24
SIDE_PAD = 24
MAX_COLS = 4
MAX_ROWS = 2
MIN_GAP = 16
MAX_GAP = 20
BUTTON_ASPECT = 1.25
BUTTON_BORDER_PAD = 10


@dataclass(frozen=True)
class ButtonLayoutMetrics:
    button_w: int
    button_h: int
    rows: int
    cols: int
    col_gap: int
    row_gap: int
    frame_height: int
    frame_padding: tuple[int, int, int, int]
    frame_top_pad: int
    frame_bottom_pad: int
    frame_bbox: tuple[int, int, int, int]

ICONS = {
    "timer": "timer.png",
    "settings": "gear.png",
    "tare": "text:>T<",
    "swap": "text:g ↔ ml",
    "food": "apple.png",
    "recipe": "recipe.png",
}


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
        style.configure("Home.Buttons.TFrame", background=COLOR_BG)

        self.configure(style="Home.Root.TFrame", padding=SPACING["lg"])

        self._weight_value_var = tk.StringVar(value="0")
        self._weight_unit_var = tk.StringVar(value="g")
        weight_container = ttk.Frame(self, style="Home.Weight.TFrame")
        weight_container.pack(fill="x")
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

        self._weight_border = neon_border(weight_container, padding=BUTTON_BORDER_PAD, radius=26)

        status_frame = ttk.Frame(self, style="Home.Status.TFrame")
        self._status_frame = status_frame

        self._stable_var = tk.StringVar(value="Inestable")
        self._stable_label = ttk.Label(status_frame, textvariable=self._stable_var, style="Home.StatusAccent.TLabel")

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
        separator_container.bind("<Configure>", lambda _e: self._redraw_separator(), add=True)
        separator_canvas.bind("<Configure>", lambda _e: self._redraw_separator(), add=True)

        self.overlay_host = tk.Frame(self, bg=COLOR_BG, highlightthickness=0, bd=0)
        self.overlay_host.place_forget()
        try:
            self.overlay_host.configure(takefocus=0)
        except Exception:
            pass
        self.overlay_host.bind("<Configure>", lambda _e: self._queue_overlay_resize(), add=True)
        self.bind("<Configure>", lambda _e: self._queue_overlay_resize(), add=True)

        buttons_frame = ttk.Frame(self, style="Home.Buttons.TFrame")
        buttons_frame.pack(fill="x")
        buttons_frame.pack_propagate(False)
        self._buttons_frame = buttons_frame
        self._buttons_border = neon_border(buttons_frame, padding=BUTTON_BORDER_PAD, radius=24)

        self.buttons: Dict[str, tk.Misc] = {}
        self._tara_long_press_job: str | None = None
        self._tara_long_press_triggered = False
        self._button_icon_names: Dict[str, str | None] = {}
        self._button_order: list[str] = []
        self._layout_signature: tuple[int, ...] | None = None
        self._grid_columns = 0
        self._grid_rows = 0

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
                width=180,
                height=128,
                shape="pill",
                corner_radius=24,
                prefer_aspect=1.4,
                min_w=128,
                min_h=96,
                max_w=220,
                max_h=150,
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
            if self._stable_label is not None:
                self._stable_label.configure(foreground=COLOR_ACCENT)
            self._has_weight_value = False
            self._weight_value_var.set("--")
            self._weight_unit_var.set(self._units)
            return

        self._last_grams = float(grams)
        self._has_weight_value = True
        self._stable_var.set("Estable" if stable else "Inestable")
        if self._stable_label is not None:
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
        controller = getattr(self, "controller", None)
        if controller is not None and hasattr(controller, "open_timer_dialog"):
            try:
                controller.open_timer_dialog()
                return
            except Exception:
                pass
        self.on_open_timer()

    def _handle_open_settings(self) -> None:
        self.on_open_settings()

    # Mascota overlay -------------------------------------------------
    def show_mascota(self) -> None:
        if self._mascota_desired:
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
        if not int(self.overlay_host.winfo_exists()):
            return
        self._queue_overlay_resize()
        if not self.overlay_host.winfo_manager():
            self._apply_overlay_geometry()
        if self._mascota is None and self._mascota_fallback is None:
            try:
                canvas = MascotaCanvas(self.overlay_host, bg=self.overlay_host.cget("bg"))
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
        self.overlay_host.lift()
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
        if int(self.overlay_host.winfo_exists()):
            try:
                self.overlay_host.place_forget()
            except Exception:
                pass

    def _create_mascota_fallback(self) -> None:
        if self._mascota_fallback is not None:
            return
        label = tk.Label(
            self.overlay_host,
            text="BASCULÍN",
            bg=self.overlay_host.cget("bg"),
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
        self._overlay_resize_job = self.after(120, self._apply_overlay_geometry)

    def _apply_overlay_geometry(self) -> None:
        self._overlay_resize_job = None
        if not int(self.overlay_host.winfo_exists()):
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
        if not self.overlay_host.winfo_manager():
            self.overlay_host.place(x=x, y=max(0, y), width=size, height=size)
        else:
            self.overlay_host.place_configure(x=x, y=max(0, y), width=size, height=size)
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
                if candidate is not None:
                    sample_button = candidate
                    break
        if sample_button is None and self.buttons:
            first = next(iter(self.buttons.values()))
            if isinstance(first, NeoGhostButton):
                sample_button = first

        prefer_aspect = BUTTON_ASPECT
        if sample_button is not None:
            try:
                prefer_aspect = float(getattr(sample_button, "prefer_aspect", BUTTON_ASPECT))
            except Exception:
                prefer_aspect = BUTTON_ASPECT
        if prefer_aspect <= 0:
            prefer_aspect = BUTTON_ASPECT
        prefer_aspect = max(1.2, min(1.28, prefer_aspect))

        if sample_button is not None and hasattr(sample_button, "min_size"):
            min_btn_w, min_btn_h = sample_button.min_size()  # type: ignore[attr-defined]
        else:
            min_btn_h = NeoGhostButton.MIN_DIAMETER
            min_btn_w = int(round(min_btn_h * prefer_aspect))
        min_btn_h = max(NeoGhostButton.MIN_DIAMETER, int(min_btn_h))
        min_btn_w = max(int(round(min_btn_h * prefer_aspect)), int(min_btn_w))

        max_btn_w = int(getattr(sample_button, "max_width", min_btn_w * 2)) if sample_button else min_btn_w * 2
        max_btn_h = int(getattr(sample_button, "max_height", min_btn_h * 2)) if sample_button else min_btn_h * 2
        max_btn_w = max(min_btn_w, max_btn_w)
        max_btn_h = max(min_btn_h, max_btn_h)

        inner_width = max(0, width - SIDE_PAD * 2)
        col_gap = min(MAX_GAP, max(MIN_GAP, width // 48))
        row_gap = min(MAX_GAP, max(MIN_GAP, height // 42))

        max_candidate_cols = min(MAX_COLS, button_count)
        cols = 1
        for candidate in range(max_candidate_cols, 0, -1):
            rows_needed = math.ceil(button_count / candidate) if candidate else button_count
            if rows_needed > MAX_ROWS:
                continue
            usable_width = inner_width - (candidate - 1) * col_gap
            per_col = usable_width / candidate if candidate else inner_width
            if per_col >= min_btn_w or candidate == 1:
                cols = candidate
                break
        rows = max(1, min(MAX_ROWS, math.ceil(button_count / cols)))

        usable_width = max(0, inner_width - (cols - 1) * col_gap)
        per_col_width = usable_width / cols if cols else usable_width
        per_col_width = max(min_btn_w, min(max_btn_w, per_col_width))

        top_margin = max(18, int(height * 0.035))
        min_weight_height = max(160, int(height * 0.24))
        max_weight_height = max(min_weight_height, int(height * 0.36))
        available_after_margins = max(0, height - top_margin - SAFE_BOTTOM)

        weight_height = min(max_weight_height, int(height * 0.32))
        weight_height = max(min_weight_height, min(weight_height, available_after_margins))
        min_button_block = rows * min_btn_h + (rows - 1) * row_gap
        if weight_height + min_button_block > available_after_margins:
            excess = weight_height + min_button_block - available_after_margins
            if excess > 0:
                weight_height = max(min_weight_height, weight_height - excess)
        weight_height = max(min_weight_height, min(weight_height, available_after_margins))

        available_for_buttons = max(0, available_after_margins - weight_height)
        height_cap = available_for_buttons - (rows - 1) * row_gap
        height_cap = height_cap / rows if rows > 0 else height_cap
        if height_cap <= 0:
            height_cap = min_btn_h

        button_w = int(round(per_col_width))
        button_w = max(min_btn_w, min(max_btn_w, button_w))
        button_h = int(round(min(button_w / prefer_aspect, height_cap)))
        button_h = max(min_btn_h, min(max_btn_h, button_h))
        button_w = int(round(max(min_btn_w, min(max_btn_w, button_h * prefer_aspect))))
        if cols > 0 and usable_width > 0:
            per_col_limit = usable_width / cols
            button_w = min(button_w, int(per_col_limit))
            button_w = max(min_btn_w, button_w)
        button_h = int(round(max(min_btn_h, min(max_btn_h, button_w / prefer_aspect))))
        if height_cap > 0:
            button_h = min(button_h, int(height_cap))
        button_h = max(min_btn_h, min(max_btn_h, button_h))
        button_w = int(round(max(min_btn_w, min(max_btn_w, button_h * prefer_aspect))))
        if cols > 0 and usable_width > 0:
            per_col_limit = int(usable_width // cols)
            if per_col_limit > 0:
                button_w = min(button_w, per_col_limit)
                button_w = max(min_btn_w, button_w)

        button_block_height = rows * button_h + (rows - 1) * row_gap

        separator_height = max(6, min(10, int(height * 0.012)))
        separator_gap = max(10, row_gap // 2 + 4)
        weight_bottom_pad = max(12, row_gap // 2 + 4)
        space_below_weight = height - SAFE_BOTTOM - (
            top_margin + weight_height + weight_bottom_pad + separator_height + separator_gap
        )
        space_below_weight = max(0, space_below_weight)
        buttons_top_pad = max(0, int((space_below_weight - button_block_height) / 2))

        frame_height = max(button_block_height, rows * button_h + (rows - 1) * row_gap)
        frame_top = int(
            top_margin + weight_height + weight_bottom_pad + separator_height + separator_gap + buttons_top_pad
        )
        frame_bottom = frame_top + frame_height
        frame_bbox = (SIDE_PAD, frame_top, max(SIDE_PAD, width - SIDE_PAD), frame_bottom)

        value_font = min(132, max(54, int(weight_height * 0.58)))
        unit_font = min(value_font, max(32, int(value_font * 0.42)))

        metrics = ButtonLayoutMetrics(
            button_w=int(button_w),
            button_h=int(button_h),
            rows=rows,
            cols=cols,
            col_gap=col_gap,
            row_gap=row_gap,
            frame_height=max(frame_height, 0),
            frame_padding=(SIDE_PAD, 0, SIDE_PAD, 0),
            frame_top_pad=buttons_top_pad,
            frame_bottom_pad=SAFE_BOTTOM,
            frame_bbox=frame_bbox,
        )

        signature = (
            width,
            height,
            value_font,
            unit_font,
            int(weight_height),
            separator_height,
            separator_gap,
            metrics.button_w,
            metrics.button_h,
            metrics.rows,
            metrics.cols,
            metrics.col_gap,
            metrics.row_gap,
            top_margin,
            weight_bottom_pad,
            metrics.frame_top_pad,
        )
        if self._layout_signature == signature:
            return
        self._layout_signature = signature

        self._apply_weight_metrics(value_font, unit_font, int(weight_height), top_margin, weight_bottom_pad)
        self._apply_separator_metrics(separator_height, 0, separator_gap)
        self._apply_button_metrics(metrics)

        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug(
                "Home layout size=%dx%d buttons=%dx%d btn=%dx%d gaps=%d/%d frame_y=%d",
                width,
                height,
                metrics.cols,
                metrics.rows,
                metrics.button_w,
                metrics.button_h,
                metrics.col_gap,
                metrics.row_gap,
                metrics.frame_bbox[1],
            )

        self._queue_overlay_resize()

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
        unit_font = (family, unit_font_px)
        for label in (self._weight_glow, self._weight_label):
            label.configure(font=weight_font)
        for label in (self._weight_glow_unit, self._weight_unit_label):
            label.configure(font=unit_font)

        unit_pad = max(8, weight_font_px // 6)
        self._unit_label.grid_configure(padx=(unit_pad, 0))
        self._weight_glow_unit.grid_configure(padx=(unit_pad, 0))

        target_height = int(container_height)
        try:
            self._weight_container.configure(height=target_height)
        except Exception:
            pass
        self._weight_container.pack_configure(pady=(margin_top, margin_bottom))

    def _apply_separator_metrics(self, height_px: int, margin_top: int, margin_bottom: int) -> None:
        self._separator_container.pack_configure(pady=(margin_top, margin_bottom))
        self._separator_canvas.configure(height=height_px)
        self._redraw_separator()

    def _apply_button_metrics(self, metrics: ButtonLayoutMetrics) -> None:
        frame = getattr(self, "_buttons_frame", None)
        if frame is None or not self.buttons:
            return

        button_w = max(1, int(metrics.button_w))
        button_h = max(1, int(metrics.button_h))
        rows = max(1, int(metrics.rows))
        cols = max(1, int(metrics.cols))

        frame.configure(padding=metrics.frame_padding)
        frame.pack_configure(pady=(metrics.frame_top_pad, metrics.frame_bottom_pad))
        frame.configure(height=max(metrics.frame_height, rows * button_h + (rows - 1) * metrics.row_gap))
        frame.pack_propagate(False)
        frame.grid_propagate(False)

        for column in range(self._grid_columns):
            if column >= cols:
                frame.grid_columnconfigure(column, weight=0, minsize=0)
        for row in range(self._grid_rows):
            if row >= rows:
                frame.grid_rowconfigure(row, weight=0, minsize=0)

        for column in range(cols):
            frame.grid_columnconfigure(column, weight=1, minsize=button_w, uniform="home.quick_cols")
        for row in range(rows):
            frame.grid_rowconfigure(row, weight=1, minsize=button_h, uniform="home.quick_rows")

        self._grid_columns = cols
        self._grid_rows = rows

        half_col_gap = max(0, metrics.col_gap // 2)
        half_row_gap = max(0, metrics.row_gap // 2)
        lower_row_gap = max(0, metrics.row_gap - half_row_gap)

        for index, name in enumerate(self._button_order):
            button = self.buttons.get(name)
            if button is None:
                continue
            row = min(index // cols, max(rows - 1, 0))
            column = min(index % cols, max(cols - 1, 0))

            if cols <= 0:
                padx = (0, 0)
            elif column == 0:
                padx = (0, half_col_gap)
            elif column == cols - 1:
                padx = (half_col_gap, 0)
            else:
                padx = (half_col_gap, half_col_gap)

            if rows <= 0:
                pady = (0, 0)
            elif row == 0:
                pady = (0, lower_row_gap)
            elif row == rows - 1:
                pady = (half_row_gap, 0)
            else:
                pady = (half_row_gap, lower_row_gap)

            try:
                button.grid(row=row, column=column, padx=padx, pady=pady, sticky="")
            except Exception:
                continue

            try:
                button.resize(width=button_w, height=button_h)
            except Exception:
                button.configure(width=button_w, height=button_h)

            icon_name = self._button_icon_names.get(name)
            if icon_name:
                try:
                    icon_base = min(button_w, button_h)
                    icon_size = max(24, min(160, icon_base - 24))
                    icon_image = load_icon(icon_name, size=icon_size, target_diameter=icon_base)
                    button.configure(icon=icon_image, show_text=False)
                except Exception:
                    pass
            else:
                button.configure(icon=None, show_text=True)

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
        height = max(4, int(self._separator_canvas.cget("height") or 6))
        usable_width = max(12, width - 12)
        x0 = max(0, (width - usable_width) // 2)
        x1 = x0 + usable_width
        centre_y = height / 2
        if x1 <= x0:
            return
        self._separator_canvas.configure(width=width, height=height)
        draw_neon_separator(
            self._separator_canvas,
            x0 + 0.5,
            centre_y,
            max(x0 + 1.0, width - x0 - 0.5),
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
