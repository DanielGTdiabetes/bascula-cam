"""Home view showing live weight and quick actions."""
from __future__ import annotations

import tkinter as tk
from typing import Callable

from ..theme_neo import COLORS, SPACING, font_sans


class HomeView(tk.Frame):
    """Main landing view displaying current weight and shortcuts."""

    def __init__(self, parent: tk.Misc, controller: object, **kwargs: object) -> None:
        background = kwargs.pop("bg", COLORS["bg"])
        super().__init__(parent, bg=background, **kwargs)

        self.controller = controller
        self._units = "g"
        self._last_grams = 0.0

        self.on_tare: Callable[[], None] = lambda: None
        self.on_zero: Callable[[], None] = lambda: None
        self.on_toggle_units: Callable[[], None] = lambda: None
        self.on_open_food: Callable[[], None] = lambda: None
        self.on_open_recipes: Callable[[], None] = lambda: None
        self.on_open_timer: Callable[[], None] = lambda: None
        self.on_open_settings: Callable[[], None] = lambda: None

        self.configure(padx=SPACING["lg"], pady=SPACING["lg"])

        self._weight_var = tk.StringVar(value="0.0 g")
        self._weight_label = tk.Label(
            self,
            textvariable=self._weight_var,
            font=font_sans(48, "bold"),
            fg=COLORS["text"],
            bg=background,
        )
        self._weight_label.pack(anchor="center", pady=(0, SPACING["lg"]))

        buttons_frame = tk.Frame(self, bg=background)
        buttons_frame.pack(fill="both", expand=True)

        button_specs = (
            ("TARA", self._handle_tare),
            ("CERO", self._handle_zero),
            ("g↔ml", self._handle_toggle_units),
            ("Alimentos", self._handle_open_food),
            ("Recetas", self._handle_open_recipes),
            ("Temporizador", self._handle_open_timer),
            ("Ajustes", self._handle_open_settings),
        )

        for index, (label, command) in enumerate(button_specs):
            button = tk.Button(
                buttons_frame,
                text=label,
                font=font_sans(18, "bold"),
                fg=COLORS["text"],
                bg=COLORS["surface"],
                activebackground=COLORS["primary"],
                activeforeground=COLORS["bg"],
                relief="flat",
                highlightthickness=0,
                bd=0,
                padx=SPACING["md"],
                pady=SPACING["sm"],
                command=command,
            )
            row = index // 3
            column = index % 3
            button.grid(
                row=row,
                column=column,
                padx=SPACING["sm"],
                pady=SPACING["sm"],
                sticky="nsew",
            )
            buttons_frame.grid_columnconfigure(column, weight=1)

        for row_index in range((len(button_specs) + 2) // 3):
            buttons_frame.grid_rowconfigure(row_index, weight=1)

    # ------------------------------------------------------------------
    def set_weight_g(self, grams: float) -> None:
        self._last_grams = float(grams)
        if self._units == "g":
            self._weight_var.set(f"{grams:.1f} g")
        else:
            self._weight_var.set(f"{self._grams_to_ml(grams):.1f} ml")

    def toggle_units(self) -> None:
        self._units = "ml" if self._units == "g" else "g"
        try:
            self.set_weight_g(self.controller.scale.net_weight)  # type: ignore[attr-defined]
        except Exception:
            self.set_weight_g(self._last_grams)

    # ------------------------------------------------------------------
    def _grams_to_ml(self, grams: float) -> float:
        try:
            density = float(getattr(self.controller.scale, "density", 1.0))  # type: ignore[attr-defined]
            if density <= 0:
                density = 1.0
        except Exception:
            density = 1.0
        return grams / density

    # ------------------------------------------------------------------
    def _handle_tare(self) -> None:
        self.on_tare()

    def _handle_zero(self) -> None:
        self.on_zero()

    def _handle_toggle_units(self) -> None:
        self.on_toggle_units()

    def _handle_open_food(self) -> None:
        self.on_open_food()

    def _handle_open_recipes(self) -> None:
        self.on_open_recipes()

    def _handle_open_timer(self) -> None:
        self.on_open_timer()

    def _handle_open_settings(self) -> None:
        self.on_open_settings()


__all__ = ["HomeView"]
