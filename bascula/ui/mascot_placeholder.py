"""Placeholder mascot drawing using vector primitives."""
from __future__ import annotations

import math
import tkinter as tk
from typing import Optional

from .theme_classic import COLORS, font


class MascotPlaceholder(tk.Canvas):
    def __init__(self, parent: tk.Widget, width: int = 320, height: int = 240) -> None:
        super().__init__(parent, width=width, height=height, bg=COLORS["surface"], highlightthickness=0)
        self._state = "idle"
        self._message_item: Optional[int] = None
        self._after_token: Optional[str] = None
        self._angle = 0.0
        self._draw_robot()

    def _draw_robot(self) -> None:
        self.delete("all")
        w = int(self.winfo_reqwidth())
        h = int(self.winfo_reqheight())
        cx = w // 2
        cy = h // 2
        body_width = min(w, h) * 0.5
        body_height = body_width * 0.9
        x0 = cx - body_width / 2
        y0 = cy - body_height / 2
        x1 = cx + body_width / 2
        y1 = cy + body_height / 2
        fill = COLORS["surface_alt"]
        outline = COLORS["accent"] if self._state in {"happy", "processing"} else COLORS["muted"]
        self.create_oval(x0, y0, x1, y1, fill=fill, outline=outline, width=4, tags="body")
        eye_radius = body_width * 0.08
        spacing = body_width * 0.2
        self.create_oval(cx - spacing - eye_radius, cy - eye_radius, cx - spacing + eye_radius, cy + eye_radius, fill=COLORS["accent"], outline="")
        self.create_oval(cx + spacing - eye_radius, cy - eye_radius, cx + spacing + eye_radius, cy + eye_radius, fill=COLORS["accent"], outline="")
        mouth_width = body_width * 0.4
        self.create_arc(cx - mouth_width / 2, cy + body_height * 0.1, cx + mouth_width / 2, cy + body_height * 0.4, start=200, extent=140, style=tk.ARC, outline=COLORS["muted"], width=3)
        self._message_item = None

    def configure_state(self, state: str) -> None:
        self._state = state
        self._draw_robot()

    def set_message(self, text: str | None) -> None:
        if self._message_item is not None:
            self.delete(self._message_item)
            self._message_item = None
        if not text:
            return
        self._message_item = self.create_text(
            self.winfo_reqwidth() // 2,
            24,
            text=text,
            font=font("sm"),
            fill=COLORS["text"],
            anchor="n",
        )

    def start(self) -> None:
        if self._after_token is None:
            self._schedule_next()

    def stop(self) -> None:
        if self._after_token is not None:
            try:
                self.after_cancel(self._after_token)
            except Exception:
                pass
            self._after_token = None

    def _schedule_next(self) -> None:
        self._after_token = self.after(80, self._tick)

    def _tick(self) -> None:
        self._angle += 0.2
        offset = math.sin(self._angle) * 6
        self.move("body", 0, offset)
        self.after(1, lambda: self.move("body", 0, -offset))
        self._schedule_next()


__all__ = ["MascotPlaceholder"]
