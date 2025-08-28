import tkinter as tk
from bascula.ui.widgets import ProButton
from bascula.config.theme import THEME


class NumericKeyboard(tk.Toplevel):
    def __init__(self, parent, title="Entrada", initial=""):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=THEME.background)
        self.transient(parent)
        self.grab_set()
        self.result = None

        self.var = tk.StringVar(value=str(initial))
        e = tk.Entry(self, textvariable=self.var, font=("Arial", 18), justify="center", relief="solid", bd=1)
        e.pack(fill="x", padx=20, pady=12, ipady=8)
        e.focus_set()

        grid = tk.Frame(self, bg=THEME.background)
        grid.pack(padx=20, pady=10)
        # ASCII-only labels to avoid encoding/rendering issues on some environments
        keys = [["7", "8", "9"], ["4", "5", "6"], ["1", "2", "3"], ["0", ".", "DEL"]]
        for r, row in enumerate(keys):
            for c, k in enumerate(row):
                cmd = (lambda ch=k: self._add(ch)) if k != "DEL" else self._back
                ProButton(grid, text=k, command=cmd, width=6).grid(row=r, column=c, padx=4, pady=4, sticky="nsew")

        ProButton(self, text="ENTER / ACEPTAR", command=self._ok, kind="success").pack(
            fill="x", padx=20, pady=(0, 10)
        )
        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<Escape>", lambda _e: self._cancel())

    def _add(self, ch):
        self.var.set(self.var.get() + ch)

    def _back(self):
        self.var.set(self.var.get()[:-1])

    def _ok(self):
        self.result = self.var.get()
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()

