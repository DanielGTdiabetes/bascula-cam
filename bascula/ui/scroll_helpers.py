"""Reusable scrollable container widgets for touch-friendly settings views."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .input_helpers import bind_touch_scroll
from .widgets import COL_BG, COL_PRIMARY, COL_ACCENT

__all__ = ["ScrollableFrame", "attach_holo_scrollbar"]


def attach_holo_scrollbar(parent: tk.Misc, target: tk.Misc, *, orient: str = "vertical"):
    style = ttk.Style(parent)
    bar_style = "Holo.Vertical.TScrollbar" if orient == "vertical" else "Holo.Horizontal.TScrollbar"
    style.configure(
        bar_style,
        background=COL_BG,
        troughcolor=COL_BG,
        bordercolor=COL_BG,
        arrowcolor=COL_PRIMARY,
        relief="flat",
    )
    style.map(bar_style, background=[("active", COL_ACCENT)])

    orientation = tk.VERTICAL if orient == "vertical" else tk.HORIZONTAL
    command = target.yview if orient == "vertical" else target.xview
    scrollbar = ttk.Scrollbar(parent, orient=orientation, style=bar_style, command=command)

    if hasattr(target, "configure"):
        if orient == "vertical":
            target.configure(yscrollcommand=scrollbar.set)
        else:
            target.configure(xscrollcommand=scrollbar.set)

    return scrollbar


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
