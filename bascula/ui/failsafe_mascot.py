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

        body_w = int(w * 0.58)
        body_h = int(h * 0.5)
        head_h = int(h * 0.28)
        radius = 28
        x0 = cx - body_w // 2
        x1 = cx + body_w // 2
        body_y0 = cy - body_h // 2 + int(head_h * 0.35)
        body_y1 = body_y0 + body_h

        accent = MASCOT_STATES["idle"]["color"]
        accent_dim = CRT_COLORS["accent_dim"]
        divider = CRT_COLORS["divider"]
        bg = CRT_COLORS["bg"]

        # base glow shadow
        base_w = int(body_w * 0.9)
        base_y0 = body_y1 + 24
        self.base_glow = self.create_oval(
            cx - base_w // 2,
            base_y0,
            cx + base_w // 2,
            base_y0 + 28,
            outline="",
            fill=_safe_color(CRT_COLORS.get("shadow"), "#001903"),
        )

        # legs and feet
        leg_width = 18
        leg_height = int(body_h * 0.42)
        leg_y0 = body_y1 - 12
        leg_y1 = leg_y0 + leg_height
        foot_w = 70
        foot_h = 26
        foot_y0 = leg_y1 - 14

        self.left_leg = self.create_line(
            cx - body_w * 0.22,
            leg_y0,
            cx - body_w * 0.22,
            leg_y1,
            fill=accent,
            width=leg_width,
            capstyle="round",
        )
        self.right_leg = self.create_line(
            cx + body_w * 0.22,
            leg_y0,
            cx + body_w * 0.22,
            leg_y1,
            fill=accent,
            width=leg_width,
            capstyle="round",
        )
        self.left_foot = self.create_round_rect(
            cx - body_w * 0.22 - foot_w // 2,
            foot_y0,
            cx - body_w * 0.22 + foot_w // 2,
            foot_y0 + foot_h,
            12,
            fill=accent_dim,
            outline="",
        )
        self.right_foot = self.create_round_rect(
            cx + body_w * 0.22 - foot_w // 2,
            foot_y0,
            cx + body_w * 0.22 + foot_w // 2,
            foot_y0 + foot_h,
            12,
            fill=accent_dim,
            outline="",
        )

        # Torso and head
        head_y1 = body_y0 + int(head_h * 0.9)
        head_y0 = head_y1 - head_h
        head_x0 = cx - int(body_w * 0.62)
        head_x1 = cx + int(body_w * 0.62)
        self.head = self.create_round_rect(head_x0, head_y0, head_x1, head_y1, radius, fill=accent, outline="")

        visor_inset = 26
        visor_y0 = head_y0 + 32
        visor_y1 = head_y1 - 32
        self.visor = self.create_round_rect(
            head_x0 + visor_inset,
            visor_y0,
            head_x1 - visor_inset,
            visor_y1,
            22,
            fill=bg,
            outline=divider,
            width=3,
        )

        # Eyes and mouth line details
        eye_w = 46
        eye_h = 22
        eye_y = visor_y0 + 24
        eye_gap = 58
        self.left_eye = self.create_oval(
            cx - eye_gap - eye_w // 2,
            eye_y,
            cx - eye_gap + eye_w // 2,
            eye_y + eye_h,
            fill=bg,
            outline=divider,
            width=3,
        )
        self.right_eye = self.create_oval(
            cx + eye_gap - eye_w // 2,
            eye_y,
            cx + eye_gap + eye_w // 2,
            eye_y + eye_h,
            fill=bg,
            outline=divider,
            width=3,
        )

        mouth_y = eye_y + 50
        self.mouth = self.create_arc(
            cx - 64,
            mouth_y,
            cx + 64,
            mouth_y + 80,
            start=200,
            extent=140,
            style="arc",
            outline=divider,
            width=4,
        )

        # Torso block with inset screen
        self.body = self.create_round_rect(x0, body_y0, x1, body_y1, radius, fill=accent, outline="")
        inner_inset = 24
        screen_y0 = body_y0 + 34
        screen_y1 = screen_y0 + int(body_h * 0.44)
        self.screen_frame = self.create_round_rect(
            x0 + inner_inset,
            screen_y0,
            x1 - inner_inset,
            screen_y1,
            18,
            fill=bg,
            outline=divider,
            width=3,
        )

        # cardio wave
        wave_width = self.coords(self.screen_frame)
        if len(wave_width) >= 8:
            sf_x0 = wave_width[0]
            sf_y0 = wave_width[1]
            sf_x1 = wave_width[4]
            sf_y1 = wave_width[5]
        else:
            sf_x0 = x0 + inner_inset
            sf_x1 = x1 - inner_inset
            sf_y0 = screen_y0
            sf_y1 = screen_y1
        wave_y = sf_y0 + (sf_y1 - sf_y0) * 0.6
        wave_points = [
            sf_x0 + 12,
            wave_y,
            sf_x0 + 48,
            wave_y,
            sf_x0 + 74,
            wave_y - 22,
            sf_x0 + 98,
            wave_y + 18,
            sf_x0 + 132,
            wave_y,
            sf_x1 - 48,
            wave_y,
            sf_x1 - 24,
            wave_y,
        ]
        self.screen_wave = self.create_line(
            *wave_points,
            fill=divider,
            width=5,
            smooth=True,
        )

        info_font = mono("md")
        try:
            self.symbol_text = self.create_text(
                cx,
                sf_y0 + (sf_y1 - sf_y0) * 0.28,
                text="♥",
                fill=divider,
                font=info_font,
            )
        except Exception:
            fallback_font = ("Arial", 32, "bold")
            self.symbol_text = self.create_text(
                cx,
                sf_y0 + (sf_y1 - sf_y0) * 0.28,
                text="♥",
                fill=divider,
                font=fallback_font,
            )

        # control buttons imitation on torso
        button_y = screen_y1 + 36
        button_radius = 14
        self.left_button = self.create_oval(
            x0 + inner_inset,
            button_y,
            x0 + inner_inset + button_radius * 2,
            button_y + button_radius * 2,
            fill=accent_dim,
            outline="",
        )
        self.right_button = self.create_oval(
            x1 - inner_inset - button_radius * 2,
            button_y,
            x1 - inner_inset,
            button_y + button_radius * 2,
            fill=divider,
            outline="",
        )

        # arms with joints
        arm_y = body_y0 + body_h * 0.45
        arm_length = body_w * 0.8
        elbow_offset = 46
        self.left_arm = self.create_line(
            x0 - 24,
            arm_y,
            x0 - arm_length * 0.5,
            arm_y + elbow_offset,
            fill=accent_dim,
            width=16,
            smooth=True,
            capstyle="round",
        )
        self.right_arm = self.create_line(
            x1 + 24,
            arm_y,
            x1 + arm_length * 0.5,
            arm_y + elbow_offset,
            fill=accent_dim,
            width=16,
            smooth=True,
            capstyle="round",
        )

        # antenna and tips
        antenna_y = head_y0 - 36
        self.left_antenna = self.create_line(
            cx - body_w * 0.28,
            head_y0 + 12,
            cx - body_w * 0.28,
            antenna_y,
            fill=divider,
            width=5,
            capstyle="round",
        )
        self.right_antenna = self.create_line(
            cx + body_w * 0.28,
            head_y0 + 12,
            cx + body_w * 0.28,
            antenna_y,
            fill=divider,
            width=5,
            capstyle="round",
        )
        self.left_antenna_tip = self.create_oval(
            cx - body_w * 0.28 - 12,
            antenna_y - 12,
            cx - body_w * 0.28 + 12,
            antenna_y + 12,
            fill=divider,
            outline="",
        )
        self.right_antenna_tip = self.create_oval(
            cx + body_w * 0.28 - 12,
            antenna_y - 12,
            cx + body_w * 0.28 + 12,
            antenna_y + 12,
            fill=divider,
            outline="",
        )

        self._breath_targets = [
            self.body,
            self.head,
            self.screen_frame,
            self.visor,
            self.symbol_text,
            self.screen_wave,
            self.left_button,
            self.right_button,
            self.left_arm,
            self.right_arm,
            self.left_leg,
            self.right_leg,
            self.left_foot,
            self.right_foot,
            self.left_antenna,
            self.right_antenna,
            self.left_antenna_tip,
            self.right_antenna_tip,
        ]

        self._eye_base = {
            self.left_eye: self.coords(self.left_eye),
            self.right_eye: self.coords(self.right_eye),
        }

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
        detail_color = _safe_color(CRT_COLORS.get("divider"), color)
        accent_detail = _safe_color(CRT_COLORS.get("accent_dim"), color)
        for item in (
            getattr(self, "body", None),
            getattr(self, "head", None),
            getattr(self, "left_leg", None),
            getattr(self, "right_leg", None),
            getattr(self, "left_foot", None),
            getattr(self, "right_foot", None),
        ):
            if item is None:
                continue
            try:
                self.itemconfigure(item, fill=color)
            except Exception:
                continue
        for item in (
            getattr(self, "left_button", None),
            getattr(self, "left_arm", None),
            getattr(self, "right_arm", None),
        ):
            if item is None:
                continue
            try:
                self.itemconfigure(item, fill=accent_detail)
            except Exception:
                continue
        for item in (
            getattr(self, "screen_wave", None),
            getattr(self, "right_button", None),
            getattr(self, "left_antenna", None),
            getattr(self, "right_antenna", None),
            getattr(self, "left_antenna_tip", None),
            getattr(self, "right_antenna_tip", None),
        ):
            if item is None:
                continue
            try:
                self.itemconfigure(item, fill=detail_color)
            except Exception:
                continue
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
            offset = math.sin(progress * math.pi) * 2.4
            for item in getattr(self, "_breath_targets", []):
                try:
                    self.move(item, 0, offset)
                except Exception:
                    continue

        self.manager.schedule(self, duration=280, steps=4, updater=_update)
        self._breath_job = self.after(1800, self._breath)

    def _blink(self) -> None:
        def _update(progress: float) -> None:
            scale = max(0.1, 1.0 - progress)
            for item in (self.left_eye, self.right_eye):
                try:
                    base = self._eye_base.get(item)
                    if not base or len(base) != 4:
                        continue
                    x0, y0, x1, y1 = base
                    cy = (y0 + y1) / 2
                    half_height = (y1 - y0) / 2
                    new_half = max(1.0, half_height * scale)
                    self.coords(item, x0, cy - new_half, x1, cy + new_half)
                except Exception:
                    continue

        def _restore() -> None:
            for item in (self.left_eye, self.right_eye):
                try:
                    base = self._eye_base.get(item)
                    if base and len(base) == 4:
                        self.coords(item, *base)
                except Exception:
                    continue

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

