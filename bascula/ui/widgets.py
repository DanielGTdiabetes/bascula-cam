"""Reusable Tk widgets for the modern UI."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

PALETTE = {
    "bg": "#f5f7fb",
    "panel": "#ffffff",
    "accent": "#0050d0",
    "accent_hover": "#1b6dff",
    "text": "#1f2430",
    "muted": "#6b7180",
}

FONT_LG = ("DejaVu Sans", 18, "bold")
FONT_MD = ("DejaVu Sans", 14, "bold")
FONT_SM = ("DejaVu Sans", 12)


class PrimaryButton(tk.Button):
    def __init__(self, master: tk.Misc, text: str, command, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            bg=PALETTE["accent"],
            fg="white",
            activebackground=PALETTE["accent_hover"],
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=22,
            pady=18,
            font=FONT_LG,
            cursor="hand2",
            highlightthickness=0,
            takefocus=0,
            **kwargs,
        )
        self.bind("<Enter>", lambda _e: self.configure(bg=PALETTE["accent_hover"]))
        self.bind("<Leave>", lambda _e: self.configure(bg=PALETTE["accent"]))


class ToolbarButton(tk.Button):
    def __init__(self, master: tk.Misc, text: str, command, **kwargs):
        super().__init__(
            master,
            text=text,
            command=command,
            bg=PALETTE["panel"],
            fg=PALETTE["accent"],
            activebackground=PALETTE["panel"],
            activeforeground=PALETTE["accent_hover"],
            font=FONT_MD,
            relief="flat",
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
            takefocus=0,
            **kwargs,
        )


class WeightDisplay(tk.Label):
    def __init__(self, master: tk.Misc, **kwargs):
        super().__init__(
            master,
            text="--",
            font=("DejaVu Sans", 120, "bold"),
            fg=PALETTE["text"],
            bg=PALETTE["panel"],
            anchor="center",
            **kwargs,
        )

    def update_value(self, value: float, unit: str) -> None:
        self.configure(text=f"{value:.0f} {unit}")


class TotalsTable(ttk.Treeview):
    def __init__(self, master: tk.Misc) -> None:
        columns = ("name", "weight", "carbs", "protein", "fat", "gi")
        super().__init__(
            master,
            columns=columns,
            show="headings",
            height=6,
        )
        headings = {
            "name": "Alimento",
            "weight": "Peso (g)",
            "carbs": "HC (g)",
            "protein": "Prot (g)",
            "fat": "Grasa (g)",
            "gi": "IG",
        }
        for cid, label in headings.items():
            self.heading(cid, text=label)
            self.column(cid, width=120, anchor="center")
        self.column("name", width=200, anchor="w")


__all__ = ["PrimaryButton", "ToolbarButton", "WeightDisplay", "TotalsTable", "PALETTE"]
