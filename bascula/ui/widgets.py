from __future__ import annotations
import tkinter as tk

SIZE_MAP = {
    "md": {"padx": 10, "pady": 10, "font": ("Arial", 14, "bold")},
    "lg": {"padx": 12, "pady": 12, "font": ("Arial", 18, "bold")},
    "xl": {"padx": 16, "pady": 16, "font": ("Arial", 22, "bold")},
}


class ProButton(tk.Button):
    def __init__(self, master, text: str, size: str = "xl", **kwargs):
        cfg = SIZE_MAP.get(size, SIZE_MAP["xl"])
        super().__init__(master, text=text, font=cfg["font"], **kwargs)
        self.configure(padx=cfg["padx"], pady=cfg["pady"])


class WeightDisplay(tk.Label):
    def __init__(self, master, **kwargs):
        f = kwargs.pop("font", ("Arial", 48, "bold"))
        super().__init__(master, font=f, **kwargs)

    def set_weight(self, grams: float, stable: bool):
        txt = f"{grams:0.1f} g"
        self.configure(text=txt, fg=("#12a312" if stable else "#333333"))
