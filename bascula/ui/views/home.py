"""Home view for the modern Báscula UI."""
from __future__ import annotations

import os
import tkinter as tk
from typing import Iterable, Sequence

from ..theme_neo import COLORS, SPACING, font_sans

BUTTONS: Sequence[tuple[str, str]] = (
    ("TARA", "Tara"),
    ("CERO", "Cero"),
    ("g↔ml", "g↔ml"),
    ("Alimentos", "Alimentos"),
    ("Recetas", "Recetas"),
    ("Temporizador", "Temporizador"),
    ("Ajustes", "Ajustes"),
)


class HomeView(tk.Frame):
    """Default landing view showing weight and quick actions."""

    def __init__(self, master: tk.Misc | None = None, **kwargs):
        background = kwargs.pop("bg", COLORS["bg"])
        super().__init__(master, bg=background, **kwargs)

        self.configure(padx=SPACING["lg"], pady=SPACING["lg"])

        self.weight_label = tk.Label(
            self,
            text=self._initial_weight_text(),
            font=font_sans(48, "bold"),
            fg=COLORS["text"],
            bg=background,
        )
        self.weight_label.pack(anchor="center", pady=(0, SPACING["lg"]))

        buttons_frame = tk.Frame(self, bg=background)
        buttons_frame.pack(fill="both", expand=True)

        self.quick_buttons: list[tk.Button] = []
        for index, (identifier, label) in enumerate(self._button_labels()):
            btn = tk.Button(
                buttons_frame,
                text=label,
                name=identifier.lower(),
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
            )
            row = index // 3
            column = index % 3
            btn.grid(
                row=row,
                column=column,
                padx=SPACING["sm"],
                pady=SPACING["sm"],
                sticky="nsew",
            )
            buttons_frame.grid_columnconfigure(column, weight=1)
            self.quick_buttons.append(btn)

        # Ensure rows expand evenly
        for row_index in range((len(self.quick_buttons) + 2) // 3):
            buttons_frame.grid_rowconfigure(row_index, weight=1)

    @staticmethod
    def _initial_weight_text() -> str:
        return os.environ.get("BASCULA_UI_WEIGHT_PLACEHOLDER", "0.000 g")

    @staticmethod
    def _button_labels() -> Iterable[tuple[str, str]]:
        return BUTTONS
