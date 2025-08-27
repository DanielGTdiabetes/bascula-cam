from __future__ import annotations
import tkinter as tk
from .widgets import ProButton

class OnScreenKeyboard(tk.Frame):
    def __init__(self, master, big: bool = True, on_submit=None, on_change=None):
        super().__init__(master)
        self.on_submit = on_submit
        self.on_change = on_change
        self.var = tk.StringVar(value="")
        entry_font = ("Arial", 22, "bold") if big else ("Arial", 14)
        self.entry = tk.Entry(self, textvariable=self.var, font=entry_font, justify="center")
        self.entry.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=10)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=1)

        keys = [
            ["1","2","3"],
            ["4","5","6"],
            ["7","8","9"],
            ["←","0","ENTER"],
        ]

        for r, row in enumerate(keys, start=1):
            for c, key in enumerate(row):
                btn = ProButton(self, text=key, size="xl" if big else "lg", command=lambda k=key: self._press(k))
                btn.grid(row=r, column=c, sticky="nsew", padx=6, pady=6)

        for i in range(3):
            self.rowconfigure(i+1, weight=1)

    def _press(self, key: str):
        if key == "ENTER":
            if callable(self.on_submit):
                self.on_submit(self.var.get())
            return
        if key == "←":
            cur = self.var.get()
            self.var.set(cur[:-1])
        else:
            self.var.set(self.var.get() + key)
        if callable(self.on_change):
            self.on_change(self.var.get())

    def get(self) -> str:
        return self.var.get()

    def set(self, value: str):
        self.var.set(value or "")
