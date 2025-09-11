# bascula/ui/overlay_weight.py
import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable

from bascula.config.themes import T
from bascula.ui.anim_target import TargetLockAnimator

CRT_BG = T("bg", "#000000")
CRT_FG = T("fg", "#00ff46")
CRT_ACC = T("accent", "#00ff46")
FONT = T("font", ("DejaVu Sans Mono", 12))

class WeightOverlay(tk.Frame):
    """
    Overlay de peso en vivo con barra de estabilidad.
    Lanza animación breve al estabilizar.
    """
    def __init__(self, master, read_weight_cb: Callable[[], float], on_stable: Optional[Callable[[float], None]]=None, **kw):
        super().__init__(master, bg=CRT_BG, **kw)
        self.read_weight_cb = read_weight_cb
        self.on_stable = on_stable
        self._running = False
        self._samples = []
        self._stable = False
        self.anim = TargetLockAnimator(self.master)

        self.box = tk.Frame(self, bg=CRT_BG, highlightthickness=2, highlightbackground=CRT_ACC)
        self.box.place(relx=0.18, rely=0.18, relwidth=0.64, relheight=0.54)

        self.lbl = tk.Label(self.box, text="0.0 kg", bg=CRT_BG, fg=CRT_FG, font=(FONT[0], 48, "bold"))
        self.lbl.pack(expand=True)

        self.btn = tk.Button(self, text="Cerrar", command=self.close, bg=CRT_BG, fg=CRT_FG)
        self.btn.place(relx=0.86, rely=0.12)

    def open(self):
        if self._running: return
        self._running = True
        self._stable = False
        self._samples.clear()
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.after(0, self._loop_read)

    def close(self):
        self._running = False
        self.place_forget()

    def _loop_read(self):
        if not self._running: return
        try:
            kg = float(self.read_weight_cb())
        except Exception:
            kg = 0.0
        self.lbl.config(text=f"{kg:.1f} kg")
        self._samples.append(kg)
        if len(self._samples) > 12:
            self._samples.pop(0)
        self._check_stability()
        self.after(80, self._loop_read)

    def _check_stability(self):
        if self._stable: return
        if len(self._samples) < 8: return
        span = max(self._samples) - min(self._samples)
        if span <= 0.2:  # ~±100 g
            self._stable = True
            # animación breve de confirmación
            self.anim.run(label="Peso estabilizado")
            if callable(self.on_stable):
                try:
                    self.on_stable(self._samples[-1])
                except Exception:
                    pass
