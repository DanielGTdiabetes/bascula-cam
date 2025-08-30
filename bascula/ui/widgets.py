# -*- coding: utf-8 -*-
import tkinter as tk

# Paleta
COL_BG = "#0f1115"
COL_CARD = "#151a22"
COL_TEXT = "#e5e7eb"
COL_MUTED = "#94a3b8"
COL_ACCENT = "#4f46e5"
COL_ACCENT_DARK = "#4338ca"
COL_SUCCESS = "#10b981"

class Card(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=COL_CARD, bd=0, highlightthickness=0, **kwargs)
        self.configure(padx=18, pady=18)

class BigButton(tk.Button):
    def __init__(self, parent, text, command, bg=COL_ACCENT, fg=COL_TEXT, **kwargs):
        super().__init__(parent, text=text, command=command, **kwargs)
        self.configure(
            bg=bg, fg=fg, activebackground=COL_ACCENT_DARK, activeforeground=fg,
            font=("DejaVu Sans", 24, "bold"),
            bd=0, padx=22, pady=12, relief="flat",
            highlightthickness=0, cursor="hand2"
        )

class GhostButton(tk.Button):
    def __init__(self, parent, text, command, **kwargs):
        super().__init__(parent, text=text, command=command, **kwargs)
        self.configure(
            bg=COL_CARD, fg=COL_TEXT,
            activebackground=COL_CARD, activeforeground=COL_TEXT,
            font=("DejaVu Sans", 20),
            bd=1, padx=18, pady=10, relief="ridge",
            highlightthickness=0, cursor="hand2"
        )

class WeightLabel(tk.Label):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(
            text="— g",
            font=("DejaVu Sans", 84, "bold"),
            bg=COL_CARD, fg=COL_TEXT
        )

class Toast(tk.Frame):
    """ Mensaje temporal tipo 'toast' (auto-oculta). """
    def __init__(self, parent):
        super().__init__(parent, bg="#1f2937", bd=0, highlightthickness=0)
        self._lbl = tk.Label(self, text="", bg="#1f2937", fg=COL_TEXT,
                             font=("DejaVu Sans", 20), padx=16, pady=10)
        self._lbl.pack()
        self._after_id = None
        self.place_forget()

    def show(self, text: str, ms: int = 2000, color=None):
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
        if color:
            self._lbl.config(fg=color)
        self._lbl.config(text=text)
        w = self.master.winfo_width()
        h = self.master.winfo_height()
        self.place(x=int(w//2), y=h-120, anchor="s")
        self.after(10, self._recenter)
        self._after_id = self.after(ms, self.hide)

    def _recenter(self):
        w = self.master.winfo_width()
        self.place_configure(x=int(w//2))

    def hide(self):
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
        self.place_forget()
