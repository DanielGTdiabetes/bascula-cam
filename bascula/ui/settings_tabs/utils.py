"""Shared helpers for settings tabs."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from bascula.ui.widgets import COL_CARD


def create_scrollable_tab(
    notebook: ttk.Notebook,
    title: str,
    *,
    padding: tuple[int, int] = (16, 12),
    bg: str = COL_CARD,
):
    """Create a tab with an auto-updating vertical scrollbar."""

    tab = tk.Frame(notebook, bg=bg)
    notebook.add(tab, text=title)

    container = tk.Frame(tab, bg=bg)
    container.pack(fill="both", expand=True)

    canvas = tk.Canvas(container, bg=bg, highlightthickness=0, bd=0)
    canvas.pack(side="left", fill="both", expand=True)

    scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
    scrollbar.pack(side="right", fill="y")

    canvas.configure(yscrollcommand=scrollbar.set)

    inner = tk.Frame(canvas, bg=bg)
    canvas.create_window((0, 0), window=inner, anchor="nw")

    def _update_scrollregion(_event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))
        try:
            if inner.winfo_reqheight() <= canvas.winfo_height():
                scrollbar.pack_forget()
            else:
                if not scrollbar.winfo_ismapped():
                    scrollbar.pack(side="right", fill="y")
        except Exception:
            pass

    inner.bind("<Configure>", _update_scrollregion)

    def _on_mousewheel(event: tk.Event) -> None:
        delta = 0
        if event.num == 4:
            delta = -1
        elif event.num == 5:
            delta = 1
        elif event.delta:
            delta = int(-event.delta / 120)
        if delta:
            canvas.yview_scroll(delta, "units")

    inner.bind("<MouseWheel>", _on_mousewheel, add=True)
    inner.bind("<Button-4>", _on_mousewheel, add=True)
    inner.bind("<Button-5>", _on_mousewheel, add=True)

    drag_state = {"y": None}

    def _start_drag(event: tk.Event) -> None:
        drag_state["y"] = event.y

    def _drag(event: tk.Event) -> None:
        if drag_state["y"] is None:
            return
        dy = event.y - drag_state["y"]
        if abs(dy) < 4:
            return
        canvas.yview_scroll(int(-dy / 20), "units")
        drag_state["y"] = event.y

    def _end_drag(_event: tk.Event) -> None:
        drag_state["y"] = None

    inner.bind("<ButtonPress-1>", _start_drag, add=True)
    inner.bind("<B1-Motion>", _drag, add=True)
    inner.bind("<ButtonRelease-1>", _end_drag, add=True)

    content = tk.Frame(inner, bg=bg)
    content.pack(fill="both", expand=True, padx=padding[0], pady=padding[1])

    return content
