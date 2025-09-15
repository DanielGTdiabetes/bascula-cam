import tkinter as tk
from typing import Optional
from bascula.ui.widgets import COL_CARD, COL_ACCENT, COL_TEXT, COL_BORDER


class TargetLockAnimator:
    """Simple crosshair + label animation for 'target detected'.

    Usage: TargetLockAnimator.run(parent_canvas_or_frame, label='ingrediente')
    Non-blocking: uses after() and cleans itself.
    """

    @staticmethod
    def run(parent: tk.Misc, label: str = "") -> None:
        try:
            w = parent.winfo_width() or 320
            h = parent.winfo_height() or 240
        except Exception:
            w, h = 320, 240

        try:
            cv = tk.Canvas(parent, bg=COL_CARD, highlightthickness=0)
            cv.place(relx=0.5, rely=0.5, anchor='center', width=int(min(w, 360)), height=int(min(h, 260)))
        except Exception:
            return

        # Draw crosshair and animated pulsating ring
        cx = (cv.winfo_reqwidth() // 2)
        cy = (cv.winfo_reqheight() // 2)
        r0 = 20
        ring = cv.create_oval(cx - r0, cy - r0, cx + r0, cy + r0, outline=COL_ACCENT, width=2)
        cv.create_line(cx - 40, cy, cx + 40, cy, fill=COL_ACCENT)
        cv.create_line(cx, cy - 40, cx, cy + 40, fill=COL_ACCENT)
        if label:
            cv.create_text(cx, cy + 56, text=str(label), fill=COL_TEXT, font=("DejaVu Sans", 14, 'bold'))

        life = {'i': 0}

        def tick():
            try:
                life['i'] += 1
                r = r0 + (life['i'] % 12)
                cv.coords(ring, cx - r, cy - r, cx + r, cy + r)
                if life['i'] < 36:
                    cv.after(50, tick)
                else:
                    cv.destroy()
            except Exception:
                pass
        tick()


class TargetAnimator:
    """Animación de recuadro objetivo con pulso y barrido."""
    def __init__(self, canvas: tk.Canvas, rect_xyxy, colors: Optional[dict] = None):
        self.canvas = canvas
        self.rect = rect_xyxy
        self.colors = colors or {}
        accent = self.colors.get('accent', COL_ACCENT)
        x1, y1, x2, y2 = rect_xyxy
        self.border_id = canvas.create_rectangle(x1, y1, x2, y2, outline=accent, width=2)
        self._pulse_after = None
        self._pulse_idx = 0

    def pulse(self, period_ms: int = 800) -> None:
        widths = [2, 3, 4, 3]
        step = max(1, period_ms // len(widths))

        def tick() -> None:
            try:
                self.canvas.itemconfigure(self.border_id, width=widths[self._pulse_idx % len(widths)])
                self._pulse_idx += 1
                self._pulse_after = self.canvas.after(step, tick)
            except Exception:
                pass
        tick()

    def sweep(self, duration_ms: int = 400) -> None:
        x1, y1, x2, y2 = self.rect
        accent = self.colors.get('accent', COL_ACCENT)
        bar = self.canvas.create_rectangle(x1, y1, x1, y2, fill=accent, width=0, stipple='gray25')
        steps = max(1, duration_ms // 16)

        def tick(i: int = 0) -> None:
            try:
                progress = i / steps
                x = x1 + (x2 - x1) * progress
                self.canvas.coords(bar, x1, y1, x, y2)
                if i < steps:
                    self.canvas.after(16, tick, i + 1)
                else:
                    self.canvas.delete(bar)
            except Exception:
                pass
        tick()
