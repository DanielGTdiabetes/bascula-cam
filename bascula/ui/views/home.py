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
        self._decimals = 0

        self.on_tare: Callable[[], None] = lambda: None
        self.on_zero: Callable[[], None] = lambda: None
        self.on_toggle_units: Callable[[], None] = lambda: None
        self.on_open_food: Callable[[], None] = lambda: None
        self.on_open_recipes: Callable[[], None] = lambda: None
        self.on_open_timer: Callable[[], None] = lambda: None
        self.on_open_settings: Callable[[], None] = lambda: None
        self.on_set_decimals: Callable[[int], None] = lambda _: None

        self.configure(padx=SPACING["lg"], pady=SPACING["lg"])

        self._weight_var = tk.StringVar(value="0 g")
        self._weight_label = tk.Label(
            self,
            textvariable=self._weight_var,
            font=font_sans(48, "bold"),
            fg=COLORS["text"],
            bg=background,
        )
        self._weight_label.pack(anchor="center", pady=(0, SPACING["lg"]))

        status_frame = tk.Frame(self, bg=background)
        status_frame.pack(anchor="center", pady=(0, SPACING["md"]))

        self._stable_var = tk.StringVar(value="Inestable")
        self._stable_label = tk.Label(
            status_frame,
            textvariable=self._stable_var,
            font=font_sans(16, "bold"),
            fg=COLORS["danger"],
            bg=background,
        )
        self._stable_label.pack(side="left", padx=(0, SPACING["md"]))

        self._decimals_var = tk.IntVar(value=0)
        decimals_switch = tk.Checkbutton(
            status_frame,
            text="1 decimal",
            variable=self._decimals_var,
            command=self._handle_decimals_toggle,
            font=font_sans(14, "bold"),
            fg=COLORS["text"],
            selectcolor=COLORS["primary"],
            bg=background,
            activebackground=background,
            activeforeground=COLORS["text"],
            highlightthickness=0,
        )
        decimals_switch.pack(side="left")

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
    def update_weight(self, grams: float, stable: bool) -> None:
        self._last_grams = float(grams)
        self._stable_var.set("Estable" if stable else "Inestable")
        self._stable_label.configure(fg=COLORS["primary"] if stable else COLORS["danger"])
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

    def _handle_zero(self) -> None:
        self.on_zero()

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


__all__ = ["HomeView"]
