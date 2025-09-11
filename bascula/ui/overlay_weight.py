import tkinter as tk
from tkinter import ttk
from collections import deque
from bascula.ui.overlay_base import OverlayBase
from bascula.ui.widgets import COL_CARD, COL_TEXT, COL_ACCENT, FS_HUGE, FS_TEXT


class WeightOverlay(OverlayBase):
    """Overlay de peso en vivo con detección de estabilidad y beep."""
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app
        self._buf = deque(maxlen=10)
        self._tick_after = None
        c = self.content()
        c.configure(padx=18, pady=18)
        self.lbl = tk.Label(c, text="0 g", bg=COL_CARD, fg=COL_ACCENT,
                            font=("DejaVu Sans Mono", max(36, FS_HUGE//2), 'bold'))
        self.lbl.pack(padx=8, pady=8)
        self.stab = tk.Label(c, text="Moviendo…", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT))
        self.stab.pack(pady=(0, 6))
        btns = tk.Frame(c, bg=COL_CARD); btns.pack(pady=(6,0))
        tk.Button(btns, text="Cerrar", command=self.hide).pack(side='right')

    def show(self):
        super().show()
        self._start()

    def hide(self):
        super().hide()
        if self._tick_after:
            try: self.after_cancel(self._tick_after)
            except Exception: pass
            self._tick_after = None

    def _start(self):
        self._buf.clear()
        self._tick()

    def _get_weight(self) -> float:
        try:
            if self.app.reader and hasattr(self.app.reader, 'get_latest'):
                return float(self.app.reader.get_latest())
        except Exception:
            pass
        return 0.0

    def _tick(self):
        w = self._get_weight()
        self._buf.append(w)
        self.lbl.configure(text=f"{w:.0f} g")
        stable = self._is_stable()
        self.stab.configure(text=("Estable" if stable else "Moviendo…"))
        if stable:
            self._beep()
        self._tick_after = self.after(120, self._tick)

    def _is_stable(self) -> bool:
        if len(self._buf) < self._buf.maxlen:
            return False
        arr = list(self._buf)
        span = max(arr) - min(arr)
        return span <= 2.0  # +/- 1g

    def _beep(self):
        try:
            if hasattr(self.app, 'audio') and self.app.audio:
                self.app.audio.play_event('stable')
        except Exception:
            pass

