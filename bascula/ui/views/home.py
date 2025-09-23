"""Home view showing live weight and quick actions."""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Dict

from ..theme_neo import COLORS, FONTS, SPACING, font_sans


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
        weight_container = tk.Frame(self, bg=background, height=180)
        weight_container.pack(fill="x", pady=(0, SPACING["lg"]))
        weight_container.pack_propagate(False)
        self._weight_label = tk.Label(
            weight_container,
            textvariable=self._weight_var,
            font=FONTS["display"],
            fg=COLORS["fg"],
            bg=background,
        )
        self._weight_label.pack(expand=True)
        self._weight_label.name = "weight_display"  # type: ignore[attr-defined]
        if hasattr(self.controller, "register_widget"):
            self.controller.register_widget("weight_display", self._weight_label)

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
            fg=COLORS["fg"],
            selectcolor=COLORS["accent"],
            bg=background,
            activebackground=background,
            activeforeground=COLORS["fg"],
            highlightthickness=0,
        )
        decimals_switch.pack(side="left")

        buttons_frame = tk.Frame(self, bg=background)
        buttons_frame.pack(fill="both", expand=True)

        self.buttons: Dict[str, tk.Button] = {}

        button_specs = (
            ("btn_tare", "tara.png", "TARA", self._handle_tare),
            ("btn_zero", "cero.png", "CERO", self._handle_zero),
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
                button = tk.Button(
                    buttons_frame,
                    text=label,
                    font=FONTS["btn"],
                    fg=COLORS["fg"],
                    bg=COLORS["surface"],
                    activebackground=COLORS["accent"],
                    activeforeground=COLORS["bg"],
                    relief="flat",
                    highlightthickness=1,
                    bd=1,
                    padx=SPACING["md"],
                    pady=SPACING["md"],
                    command=command,
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
