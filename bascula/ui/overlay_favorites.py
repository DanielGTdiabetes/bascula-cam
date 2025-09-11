# bascula/ui/overlay_favorites.py
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional, List

from bascula.config.themes import T
from bascula.domain import foods as foods_dom
from bascula.ui.anim_target import TargetLockAnimator

CRT_BG = T("bg", "#000000")
CRT_FG = T("fg", "#00ff46")
CRT_ACC = T("accent", "#00ff46")
FONT = T("font", ("DejaVu Sans Mono", 12))

class FavoritesOverlay(tk.Frame):
    """
    Overlay de Favoritos + Autocompletar
    Llama animación TargetLock al seleccionar un alimento.
    """
    def __init__(self, master, on_add_food: Optional[Callable]=None, **kw):
        super().__init__(master, bg=CRT_BG, **kw)
        self.on_add_food = on_add_food
        self.anim = TargetLockAnimator(self.master)

        top = tk.Frame(self, bg=CRT_BG); top.pack(fill="x", padx=12, pady=(12,6))
        tk.Label(top, text="Mis Alimentos", bg=CRT_BG, fg=CRT_FG, font=(FONT[0], 14, "bold")).pack(side="left")

        self.entry = tk.Entry(self, bg=CRT_BG, fg=CRT_FG, insertbackground=CRT_FG, font=(FONT[0], 12))
        self.entry.pack(fill="x", padx=16, pady=6)
        self.entry.bind("<KeyRelease>", self._on_type)

        self.listbox = tk.Listbox(self, bg=CRT_BG, fg=CRT_FG, selectbackground=CRT_ACC, font=(FONT[0], 12), height=10)
        self.listbox.pack(fill="both", expand=True, padx=16, pady=(0,12))
        self.listbox.bind("<Double-1>", self._pick_selected)

        btns = tk.Frame(self, bg=CRT_BG); btns.pack(fill="x", padx=16, pady=(0,12))
        tk.Button(btns, text="Cerrar", command=self.close, bg=CRT_BG, fg=CRT_FG).pack(side="right")
        tk.Button(btns, text="Añadir", command=self._pick_selected, bg=CRT_BG, fg=CRT_FG).pack(side="right", padx=8)

        self._foods: List[foods_dom.Food] = list(foods_dom.load_foods())
        self._refresh_list(self._foods[:20])

    def open(self):
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.entry.focus_set()

    def close(self):
        self.place_forget()

    def _on_type(self, e=None):
        q = self.entry.get().strip()
        if not q:
            items = self._foods[:20]
        else:
            try:
                items = foods_dom.suggest(q, limit=20, prefer_favorites=True)
            except Exception:
                items = [f for f in self._foods if q.lower() in f.name.lower()][:20]
        self._refresh_list(items)

    def _refresh_list(self, items):
        self.listbox.delete(0, tk.END)
        self._last_items = items
        for f in items:
            star = "★ " if getattr(f, "favorite", False) else "  "
            self.listbox.insert(tk.END, f"{star}{getattr(f, 'name','(sin nombre)')}")

    def _pick_selected(self, e=None):
        if not getattr(self, "_last_items", None): return
        idx = self.listbox.curselection()
        if not idx: return
        food = self._last_items[idx[0]]
        # Animación de lock centrada con etiqueta = nombre
        self.anim.run(label=getattr(food, "name", "Alimento"))
        def _done():
            if callable(self.on_add_food):
                try:
                    self.on_add_food(food)
                except Exception:
                    pass
            self.close()
        self.after(700, _done)
