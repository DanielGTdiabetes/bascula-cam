import tkinter as tk
from bascula.ui.overlay_base import OverlayBase
from bascula.ui.widgets import COL_CARD, COL_TEXT, COL_ACCENT, FS_TITLE, FS_TEXT


class TimerOverlay(OverlayBase):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app
        self._remaining = 0
        self._after = None
        c = self.content(); c.configure(padx=12, pady=12)
        self.lbl = tk.Label(c, text='00:00', bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans Mono", FS_TITLE, 'bold'))
        self.lbl.pack(pady=8)
        btns = tk.Frame(c, bg=COL_CARD); btns.pack()
        for sec in (60, 300, 600, 900):
            tk.Button(btns, text=f"{sec//60} min", command=lambda s=sec: self.start(s)).pack(side='left', padx=4)
        tk.Button(c, text='Cerrar', command=self.hide).pack(pady=(6,0))

    def show(self):
        super().show()

    def hide(self):
        super().hide()
        if self._after:
            try: self.after_cancel(self._after)
            except Exception: pass
            self._after = None

    def start(self, seconds: int):
        self._remaining = int(seconds)
        self._tick()

    def _tick(self):
        m, s = divmod(max(0, self._remaining), 60)
        self.lbl.configure(text=f"{m:02d}:{s:02d}")
        if self._remaining <= 0:
            self._beep()
            return
        self._remaining -= 1
        self._after = self.after(1000, self._tick)

    def _beep(self):
        # 3 pares de tonos
        try:
            au = getattr(self.app, 'audio', None)
            if au:
                for _ in range(3):
                    au.play_event('timer_beep')
        except Exception:
            pass

