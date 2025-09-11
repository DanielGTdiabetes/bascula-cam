import tkinter as tk
from tkinter import ttk
from bascula.ui.overlay_base import OverlayBase
from bascula.ui.widgets import COL_CARD, COL_TEXT, COL_ACCENT, COL_BORDER, FS_TEXT
from bascula.domain.foods import load_foods, search


class FavoritesOverlay(OverlayBase):
    def __init__(self, parent, app, on_add_item=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app
        self._on_add = on_add_item or (lambda item: None)
        c = self.content(); c.configure(padx=12, pady=12)
        top = tk.Frame(c, bg=COL_CARD); top.pack(fill='x')
        tk.Label(top, text='Añadir alimento', bg=COL_CARD, fg=COL_ACCENT).pack(side='left')
        self.var = tk.StringVar()
        ent = tk.Entry(top, textvariable=self.var, bg=COL_CARD, fg=COL_TEXT, insertbackground=COL_TEXT)
        ent.pack(side='left', fill='x', expand=True, padx=8)
        ent.bind('<KeyRelease>', lambda e: self._refresh())
        tk.Button(top, text='Cerrar', command=self.hide).pack(side='right')

        self.list = tk.Frame(c, bg=COL_CARD)
        self.list.pack(fill='both', expand=True, pady=(8,0))
        self._foods = load_foods()
        self._refresh()

    def _refresh(self):
        for w in self.list.winfo_children():
            w.destroy()
        q = self.var.get()
        matches = search(q, self._foods)
        for f in matches[:50]:
            row = tk.Frame(self.list, bg=COL_CARD, highlightbackground=COL_BORDER, highlightthickness=1)
            row.pack(fill='x', pady=3)
            tk.Label(row, text=f.name, bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT)).pack(side='left', padx=8)
            tk.Button(row, text='Añadir', command=lambda it=f: self._choose(it)).pack(side='right', padx=6)

    def _choose(self, item):
        try:
            self._on_add(item)
        finally:
            self.hide()

