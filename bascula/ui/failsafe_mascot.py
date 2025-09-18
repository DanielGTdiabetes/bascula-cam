"""Mascot canvas optimized for low memory environments."""
from __future__ import annotations

import logging
import math
import tkinter as tk
from dataclasses import dataclass
from typing import Dict, Optional

from .theme_crt import CRT_COLORS, mono
from .simple_animations import AnimationManager

logger = logging.getLogger("bascula.ui.failsafe_mascot")

MASCOT_STATES: Dict[str, Dict[str, str]] = {
    "idle": {"color": CRT_COLORS["accent"], "symbol": "♥"},
    "listening": {"color": CRT_COLORS["accent_dim"], "symbol": "♪"},
    "processing": {"color": CRT_COLORS["accent"], "symbol": "⟳"},
    "happy": {"color": CRT_COLORS["accent_dim"], "symbol": "★"},
    "error": {"color": CRT_COLORS["accent_dim"], "symbol": "!"},
}


def _safe_color(value: Optional[str], fallback: str = CRT_COLORS["bg"]) -> str:
    if isinstance(value, str):
        value = value.strip()
        if value and value != "none":
            return value
    return fallback


@dataclass(slots=True)
class MascotState:
    color: str
    symbol: str


class MascotCanvas(tk.Canvas):
    """Vector mascot drawn on a single canvas to reuse objects."""

    def __init__(self, parent: tk.Widget, *, width: int = 360, height: int = 320, manager: Optional[AnimationManager] = None) -> None:
        bg = _safe_color(CRT_COLORS.get("bg"), CRT_COLORS["bg"])
        super().__init__(
            parent,
            width=width,
            height=height,
            highlightthickness=0,
            bd=0,
            bg=bg,
        )
        self.manager = manager or AnimationManager(self, max_parallel=2)
        self._state = "idle"
        self._breath_job: Optional[str] = None
        self._blink_job: Optional[str] = None
        self._build()
        self.configure_state("idle")
        self._schedule_idle()

    def _build(self) -> None:
        w = int(self.cget("width"))
        h = int(self.cget("height"))
        cx = w // 2
        cy = h // 2
        self.delete("all")
        body_w = int(w * 0.6)
        body_h = int(h * 0.55)
        radius = 24
        x0 = cx - body_w // 2
        y0 = cy - body_h // 2
        x1 = cx + body_w // 2
        y1 = cy + body_h // 2
        self.body = self.create_round_rect(x0, y0, x1, y1, radius, fill=MASCOT_STATES["idle"]["color"], outline="")
        screen_h = int(body_h * 0.35)
        screen_y0 = y0 + int(body_h * 0.18)
        screen_y1 = screen_y0 + screen_h
        self.screen = self.create_round_rect(x0 + 20, screen_y0, x1 - 20, screen_y1, 18, fill=CRT_COLORS["bg"], outline=CRT_COLORS["divider"], width=2)
        eye_w = 34
        eye_h = 18
        eye_y = screen_y0 - 30
        eye_gap = 46
        self.left_eye = self.create_oval(
            cx - eye_gap - eye_w // 2,
            eye_y,
            cx - eye_gap + eye_w // 2,
            eye_y + eye_h,
            fill=CRT_COLORS["bg"],
            outline=CRT_COLORS["divider"],
            width=2,
        )
        self.right_eye = self.create_oval(
            cx + eye_gap - eye_w // 2,
            eye_y,
            cx + eye_gap + eye_w // 2,
            eye_y + eye_h,
            fill=CRT_COLORS["bg"],
            outline=CRT_COLORS["divider"],
            width=2,
        )
        mouth_y = eye_y + 40
        self.mouth = self.create_arc(
            cx - 50,
            mouth_y,
            cx + 50,
            mouth_y + 60,
            start=200,
            extent=140,
            style="arc",
            outline=CRT_COLORS["divider"],
            width=3,
        )
        antenna_y = y0 - 30
        self.left_antenna = self.create_line(
            cx - body_w // 3,
            y0 + 10,
            cx - body_w // 3,
            antenna_y,
            fill=CRT_COLORS["accent"],
            width=4,
            capstyle="round",
        )
        self.right_antenna = self.create_line(
            cx + body_w // 3,
            y0 + 10,
            cx + body_w // 3,
            antenna_y,
            fill=CRT_COLORS["accent"],
            width=4,
            capstyle="round",
        )
        self.left_antenna_tip = self.create_oval(
            cx - body_w // 3 - 10,
            antenna_y - 10,
            cx - body_w // 3 + 10,
            antenna_y + 10,
            fill=CRT_COLORS["accent"],
            outline=CRT_COLORS["divider"],
        )
        self.right_antenna_tip = self.create_oval(
            cx + body_w // 3 - 10,
            antenna_y - 10,
            cx + body_w // 3 + 10,
            antenna_y + 10,
            fill=CRT_COLORS["accent"],
            outline=CRT_COLORS["divider"],
        )
        self.symbol_text = self.create_text(cx, screen_y0 + screen_h // 2, text="♥", fill=CRT_COLORS["text"], font=mono("lg"))

    def create_round_rect(self, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs) -> int:
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    def configure_state(self, state: str) -> None:
        data = MASCOT_STATES.get(state) or MASCOT_STATES["idle"]
        self._state = state if state in MASCOT_STATES else "idle"
        color = _safe_color(data.get("color"), MASCOT_STATES["idle"]["color"])
        symbol = data.get("symbol", MASCOT_STATES["idle"].get("symbol", "♥")) or "♥"
        try:
            self.itemconfigure(self.body, fill=color)
        except Exception:
            pass
        try:
            self.itemconfigure(self.symbol_text, text=symbol)
        except Exception:
            pass
        self._schedule_idle()

    def _schedule_idle(self) -> None:
        if self._breath_job is not None:
            try:
                self.after_cancel(self._breath_job)
            except Exception:
                pass
        if self._blink_job is not None:
            try:
                self.after_cancel(self._blink_job)
            except Exception:
                pass
        self._breath_job = self.after(600, self._breath)
        self._blink_job = self.after(3400, self._blink)

    def _breath(self) -> None:
        def _update(progress: float) -> None:
            offset = math.sin(progress * math.pi) * 2
            try:
                self.move(self.body, 0, offset)
                self.move(self.screen, 0, offset)
                self.move(self.symbol_text, 0, offset)
            except Exception:
                pass

        self.manager.schedule(self, duration=280, steps=4, updater=_update)
        self._breath_job = self.after(1800, self._breath)

    def _blink(self) -> None:
        def _update(progress: float) -> None:
            scale = max(0.1, 1.0 - progress)
            for item in (self.left_eye, self.right_eye):
                try:
                    coords = self.coords(item)
                    if len(coords) == 4:
                        x0, y0, x1, y1 = coords
                        cy = (y0 + y1) / 2
                        new_y0 = cy - (cy - y0) * scale
                        new_y1 = cy + (y1 - cy) * scale
                        self.coords(item, x0, new_y0, x1, new_y1)
                except Exception:
                    pass

        def _restore() -> None:
            for item in (self.left_eye, self.right_eye):
                try:
                    coords = self.coords(item)
                    if len(coords) == 4:
                        x0, y0, x1, y1 = coords
                        cy = (y0 + y1) / 2
                        height = max(1.0, (y1 - y0))
                        self.coords(item, x0, cy - height / 2, x1, cy + height / 2)
                except Exception:
                    pass

        self.manager.schedule(self, duration=160, steps=3, updater=_update, on_complete=_restore)
        self._blink_job = self.after(5200, self._blink)

    def set_error(self, message: str = "") -> None:
        logger.warning("Mascota en modo error: %s", message)
        self.configure_state("error")

    def resize(self, width: int, height: int) -> None:
        try:
            self.configure(width=width, height=height)
        except Exception:
            return
        self._build()
        self.configure_state(self._state)

    def destroy(self) -> None:
        if self._breath_job is not None:
            try:
                self.after_cancel(self._breath_job)
            except Exception:
                pass
        if self._blink_job is not None:
            try:
                self.after_cancel(self._blink_job)
            except Exception:
                pass
        super().destroy()


class MascotPlaceholder(tk.Label):
    """Fallback when Canvas creation fails."""

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(
            parent,
            text="🤖",
            font=("Arial", 96),
            bg=_safe_color(CRT_COLORS.get("bg")),
            fg=_safe_color(CRT_COLORS.get("accent"), CRT_COLORS["accent"]),
        )

    def configure_state(self, state: str) -> None:  # type: ignore[override]
        data = MASCOT_STATES.get(state) or MASCOT_STATES["idle"]
        self.configure(text=data.get("symbol", "♥") or "♥")

