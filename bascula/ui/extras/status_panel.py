import tkinter as tk
from bascula.ui.extras.modern_theme import THEME_MODERN as MT
class StatusPanel(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=MT.background)
        row = tk.Frame(self, bg=MT.background); row.pack(fill="x", padx=16, pady=8)
        self.cards = []
        for title, color in [("MAX","danger"),("MIN","info"),("PROM","accent"),("LECT.","primary")]:
            self.cards.append(self._card(row, title, color))
        self.maxv = 0.0; self.minv = 0.0; self.sumv = 0.0; self.count = 0
    def _card(self, parent, title, color_key):
        colors = {"danger":"#EF4444","info":"#06B6D4","accent":"#8B5CF6","primary":"#2563EB"}
        col = colors.get(color_key, MT.primary)
        card = tk.Frame(parent, bg=MT.surface, bd=1, relief="solid", highlightbackground=MT.surface_light, highlightthickness=1)
        card.pack(side="left", fill="x", expand=True, padx=4)
        tk.Label(card, text=title, font=("Segoe UI", 10, "bold"), fg=MT.text_light, bg=MT.surface).pack()
        val = tk.Label(card, text="0.0", font=("Segoe UI", 14, "bold"), fg=col, bg=MT.surface); val.pack(padx=8, pady=6); card.val = val
        return card
    def update(self, w: float):
        self.count += 1
        if w > self.maxv: self.maxv = w; self.cards[0].val.configure(text=f"{self.maxv:.1f}")
        if w < self.minv or self.minv == 0: self.minv = w; self.cards[1].val.configure(text=f"{self.minv:.1f}")
        self.sumv += w; prom = self.sumv / self.count
        self.cards[2].val.configure(text=f"{prom:.1f}")
        self.cards[3].val.configure(text=str(self.count))
    def reset(self):
        self.maxv = self.minv = self.sumv = 0.0; self.count = 0
        for i, t in enumerate(["0.0","0.0","0.0","0"]): self.cards[i].val.configure(text=t)
