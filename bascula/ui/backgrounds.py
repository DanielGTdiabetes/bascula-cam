
import tkinter as tk

from .widgets import COL_BG, COL_GRID


def apply_holo_grid_background(root_or_frame: tk.Misc, cell_px: int = 50) -> None:
    """Dibuja una rejilla cian muy sutil como fondo. No altera el layout."""

    parent = root_or_frame
    canvas = tk.Canvas(parent, bg=COL_BG, highlightthickness=0, bd=0)
    canvas.place(relx=0, rely=0, relwidth=1, relheight=1)

    lines: list[int] = []

    def _redraw(_evt=None) -> None:
        nonlocal lines
        for line in lines:
            try:
                canvas.delete(line)
            except Exception:
                pass
        lines.clear()
        w = canvas.winfo_width() or 1024
        h = canvas.winfo_height() or 600
        step = max(20, int(cell_px))

        color = COL_GRID
        for x in range(0, w, step):
            lines.append(canvas.create_line(x, 0, x, h, fill=color))
        for y in range(0, h, step):
            lines.append(canvas.create_line(0, y, w, y, fill=color))
        canvas.lower("all")

    canvas.bind("<Configure>", _redraw)
    parent._holo_grid_canvas = canvas
