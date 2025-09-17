"""Simple mascot drawing used on the home screen."""
from __future__ import annotations

import tkinter as tk


class MascotaCanvas(tk.Canvas):
    """Canvas that draws a friendly pixel-style mascot."""

    def __init__(self, master: tk.Misc, width: int = 220, height: int = 220, **kwargs) -> None:
        super().__init__(master, width=width, height=height, highlightthickness=0, **kwargs)
        self.configure(bg="#000000")
        self._draw_mascot()

    def _draw_mascot(self) -> None:
        body_color = "#00FF66"
        accent = "#00FF99"

        self.delete("all")
        # Body
        self.create_oval(30, 60, 190, 200, fill=body_color, outline=accent, width=4)
        # Head
        self.create_oval(50, 10, 170, 130, fill=body_color, outline=accent, width=4)
        # Eyes
        self.create_oval(80, 50, 100, 70, fill="#001a0c", outline=accent)
        self.create_oval(140, 50, 160, 70, fill="#001a0c", outline=accent)
        self.create_rectangle(85, 90, 155, 110, fill="#001a0c", outline=accent)
        # Legs
        self.create_rectangle(70, 200, 100, 220, fill=body_color, outline=accent, width=4)
        self.create_rectangle(130, 200, 160, 220, fill=body_color, outline=accent, width=4)

    def refresh(self) -> None:
        """Redraw the mascot."""
        self._draw_mascot()
