"""Home view showing live weight and quick actions."""
from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Dict

from ..theme_neo import SPACING
from ..theme_holo import (
    COLOR_ACCENT,
    COLOR_BG,
    COLOR_PRIMARY,
    COLOR_SURFACE,
    COLOR_TEXT,
    FONT_DIGITS,
    FONT_BODY_BOLD,
    neon_border,
)


LOGGER = logging.getLogger(__name__)


class HomeView(ttk.Frame):
    """Main landing view displaying current weight and shortcuts."""

    def __init__(self, parent: tk.Misc, controller: object, **kwargs: object) -> None:
        kwargs.pop("bg", None)
        super().__init__(parent, **kwargs)

        self.controller = controller
        self._units = "g"
        self._last_grams = 0.0
        self._decimals = 0

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

        self._weight_var = tk.StringVar(value="0 g")
        weight_container = ttk.Frame(self, style="Home.Weight.TFrame")
        weight_container.configure(height=180)
        weight_container.pack(fill="x", pady=(0, SPACING["lg"]))
        weight_container.pack_propagate(False)
        glow = ttk.Label(weight_container, textvariable=self._weight_var, style="Home.WeightGlow.TLabel")
        glow.place(relx=0.5, rely=0.52, anchor="center")
        glow.lower()
        self._weight_glow = glow

        self._weight_label = ttk.Label(weight_container, textvariable=self._weight_var, style="Home.WeightPrimary.TLabel")
        self._weight_label.place(relx=0.5, rely=0.5, anchor="center")
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

        buttons_frame = ttk.Frame(self, style="Home.Buttons.TFrame")
        buttons_frame.pack(fill="both", expand=True)
        self._buttons_border = neon_border(buttons_frame, padding=8, radius=24)

        self.buttons: Dict[str, tk.Misc] = {}
        self._tara_long_press_job: str | None = None
        self._tara_long_press_triggered = False

        button_specs = (
            ("btn_tare", "tara.png", "TARA", self._handle_tare),
            ("btn_swap", "swap.png", "g↔ml", self._handle_toggle_units),
            ("btn_food", "food.png", "Alimentos", self._handle_open_food),
            ("btn_recipe", "recipe.png", "Recetas", self._handle_open_recipes),
            ("btn_timer", "timer.png", "Temporizador", self._handle_open_timer),
            ("btn_settings", "settings.png", "Ajustes", self._handle_open_settings),
        )

        for index, (name, icon, label, command) in enumerate(button_specs):
            icon_path = None
            if hasattr(self.controller, "icon_path"):
                icon_path = self.controller.icon_path(icon)
            button = None
            if hasattr(self.controller, "make_icon_button"):
                button = self.controller.make_icon_button(
                    buttons_frame,
                    icon_path,
                    label,
                    name=name,
                    command=command,
                    row=index // 3,
                    column=index % 3,
                    sticky="nsew",
                )
            if button is None:
                button = ttk.Button(
                    buttons_frame,
                    text=label,
                    command=command,
                    style="Holo.Circular.TButton",
                    padding=SPACING["sm"],
                )
                button.grid(
                    row=index // 3,
                    column=index % 3,
                    padx=SPACING["sm"],
                    pady=SPACING["sm"],
                    sticky="nsew",
                )
                button.name = name  # type: ignore[attr-defined]
                if hasattr(self.controller, "register_widget"):
                    self.controller.register_widget(name, button)
            self.buttons[name] = button
            row = index // 3
            column = index % 3
            buttons_frame.grid_columnconfigure(column, weight=1, minsize=120)

        for row_index in range((len(button_specs) + 2) // 3):
            buttons_frame.grid_rowconfigure(row_index, weight=1, minsize=120)

        self._configure_tare_long_press()

    # ------------------------------------------------------------------
    def update_weight(self, grams: float, stable: bool) -> None:
        self._last_grams = float(grams)
        self._stable_var.set("Estable" if stable else "Inestable")
        self._stable_label.configure(foreground=COLOR_PRIMARY if stable else COLOR_ACCENT)
        self._refresh_display()

    def toggle_units(self) -> str:
        self._units = "ml" if self._units == "g" else "g"
        self._refresh_display()
        return self._units

    # ------------------------------------------------------------------
    def _grams_to_ml(self, grams: float) -> float:
        try:
            density = float(getattr(self.controller.scale, "density", 1.0))  # type: ignore[attr-defined]
            if density <= 0:
                density = 1.0
        except Exception:
            density = 1.0
        return grams / density

    def _refresh_display(self) -> None:
        decimals = 1 if self._decimals else 0
        grams = self._last_grams
        if self._units == "g":
            self._weight_var.set(f"{grams:.{decimals}f} g")
        else:
            self._weight_var.set(f"{self._grams_to_ml(grams):.{decimals}f} ml")

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
