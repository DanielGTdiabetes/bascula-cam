import tkinter as tk
from bascula.ui.extras.modern_theme import THEME_MODERN as MT
class AnimatedWeightDisplay(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=MT.background)
        card = tk.Frame(self, bg=MT.surface, bd=1, relief="solid",
                        highlightbackground=MT.surface_light, highlightthickness=1)
        card.pack(fill="both", expand=True, padx=16, pady=10)
        inner = tk.Frame(card, bg=MT.surface); inner.pack(fill="both", expand=True, padx=24, pady=20)
        self.var = tk.StringVar(value="0.0")
        self.lbl = tk.Label(inner, textvariable=self.var, font=("Segoe UI", 64, "bold"), fg=MT.success, bg=MT.surface)
        self.lbl.pack()
        bottom = tk.Frame(inner, bg=MT.surface); bottom.pack(fill="x", pady=(16,0))
        self.unit = tk.Label(bottom, text="GRAMOS", font=("Segoe UI", 14, "bold"), fg=MT.primary, bg=MT.surface); self.unit.pack(side="left")
        right = tk.Frame(bottom, bg=MT.surface); right.pack(side="right")
        self.stab = tk.Label(right, text="● MIDIENDO", font=("Segoe UI", 11, "bold"), fg=MT.warning, bg=MT.surface); self.stab.pack()
        barf = tk.Frame(right, bg=MT.surface, height=4); barf.pack(fill="x", pady=(6,0))
        self.bar = tk.Frame(barf, bg=MT.primary, height=4); self.bar.pack(side="left")
        self.current = 0.0; self.target = 0.0; self.anim = False
    def set(self, value: float, stable: bool, confidence: float):
        self.target = value
        if abs(self.target - self.current) < 1.0:
            if not self.anim:
                self.anim = True; self._animate()
        else:
            self.current = self.target; self._paint()
        self.stab.configure(text="● ESTABLE" if stable else "● MIDIENDO", fg=MT.success if stable else MT.warning)
        self.bar.configure(width=max(8, int(max(0.0, min(1.0, confidence))*100)))
    def _animate(self):
        if abs(self.target - self.current) > 0.05:
            diff = self.target - self.current; self.current += diff*0.3; self._paint(); self.after(50, self._animate)
        else:
            self.current = self.target; self._paint(); self.anim = False
    def _paint(self):
        self.var.set(f"{self.current:.1f}")
        col = MT.success if self.current >= 0.5 else (MT.danger if self.current < 0 else MT.text_light)
        self.lbl.configure(fg=col)
