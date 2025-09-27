"""Reusable scrollable container widgets for touch-friendly settings views."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .input_helpers import bind_touch_scroll

__all__ = ["ScrollableFrame"]


class ScrollableFrame(tk.Frame):
    """Frame wrapper that adds vertical scrolling to large content blocks."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        bg: str = "#ffffff",
        scrollbar: bool = True,
        canvas_kwargs: dict | None = None,
    ) -> None:
        super().__init__(master, bg=bg)
        self._canvas = tk.Canvas(
            self,
            bg=bg,
            highlightthickness=0,
            bd=0,
            **(canvas_kwargs or {}),
        )
        self._canvas.pack(side="left", fill="both", expand=True)

        self._scrollbar = None
        if scrollbar:
            self._scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
            self._scrollbar.pack(side="right", fill="y")
            self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self.content = tk.Frame(self._canvas, bg=bg)
        self._window_id = self._canvas.create_window((0, 0), window=self.content, anchor="nw")

        self.content.bind("<Configure>", self._on_content_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        bind_touch_scroll(self._canvas, units_divisor=2, min_drag_px=3)

    # ------------------------------------------------------------------
    def _on_content_configure(self, event: tk.Event) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        try:
            self._canvas.itemconfigure(self._window_id, width=self._canvas.winfo_width())
        except Exception:
            pass

    def _on_canvas_configure(self, event: tk.Event) -> None:
        try:
            self._canvas.itemconfigure(self._window_id, width=event.width)
        except Exception:
            pass
