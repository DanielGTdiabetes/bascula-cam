# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk
from bascula.ui.widgets import *

SHOW_SCROLLBAR = False  # Scroll con el dedo

class BaseScreen(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COL_BG, **kwargs)
        self.app = app
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
    def on_show(self): pass
    def on_hide(self): pass

class HomeScreen(BaseScreen):
    def __init__(self, parent, app, on_open_settings_menu):
        super().__init__(parent, app)
        self.on_open_settings_menu = on_open_settings_menu
        self.items, self._next_id, self._selection_id, self._stable = [], 1, None, False
        self._tick_after = None

        # Panel Peso
        card_weight = Card(self)
        card_weight.grid(row=0, column=0, sticky="nsew", padx=(10,6), pady=10)
        header = tk.Frame(card_weight, bg=COL_CARD); header.pack(fill="x")
        tk.Label(header, text="Peso actual", bg=COL_CARD, fg=COL_ACCENT,
                 font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(side="left", padx=10, pady=4)
        self.status_indicator = StatusIndicator(header, size=14); self.status_indicator.pack(side="left")

        weight_frame = tk.Frame(card_weight, bg="#1a1f2e", highlightbackground=COL_BORDER, highlightthickness=1)
        weight_frame.pack(expand=True, fill="both", padx=8, pady=8)
        self.weight_lbl = WeightLabel(weight_frame, bg="#1a1f2e"); self.weight_lbl.pack(expand=True, fill="both")
        stf = tk.Frame(weight_frame, bg="#1a1f2e"); stf.pack(side="bottom", pady=4)
        self.stability_label = tk.Label(stf, text="Esperando señal...", bg="#1a1f2e",
                                        fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT))
        self.stability_label.pack()

        btns = tk.Frame(card_weight, bg=COL_CARD); btns.pack(fill="x", pady=4)
        btn_map = [("Tara", self._on_tara), ("Plato", self._on_plato), ("Añadir", self._on_add_item),
                   ("Ajustes", self.on_open_settings_menu), ("Reiniciar", self._on_reset_session)]
        for i, (txt, cmd) in enumerate(btn_map):
            BigButton(btns, text=txt, command=cmd, micro=True).grid(row=0, column=i, sticky="nsew", padx=3, pady=3)
            btns.grid_columnconfigure(i, weight=1)

        # Panel derecho
        right = tk.Frame(self, bg=COL_BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(6,10), pady=10)
        right.grid_rowconfigure(0, weight=0)
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        self.card_nutrition = Card(right)
        self.card_nutrition.grid(row=0, column=0, sticky="new", pady=(0,10))
        header_nut = tk.Frame(self.card_nutrition, bg=COL_CARD); header_nut.pack(fill="x")
        tk.Label(header_nut, text="🥗 Totales", bg=COL_CARD, fg=COL_ACCENT,
                 font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(side="left")
        grid = tk.Frame(self.card_nutrition, bg=COL_CARD); grid.pack(fill="x", padx=8, pady=6)
        self._nut_labels = {}
        for name, key in [("Peso (g)","grams"),("Calorías","kcal"),("Carbs (g)","carbs"),
                          ("Proteína","protein"),("Grasa (g)","fat")]:
            lbl = tk.Label(grid, text=name+":", bg=COL_CARD, fg=COL_TEXT, anchor="w")
            val = tk.Label(grid, text="—", bg=COL_CARD, fg=COL_TEXT, anchor="e")
            lbl.pack(anchor="w"); val.pack(anchor="e")
            self._nut_labels[key] = val

        self.card_items = Card(right)
        self.card_items.grid(row=1, column=0, sticky="nsew")
        footer = tk.Frame(self.card_items, bg=COL_CARD); footer.pack(side="bottom", fill="x")
        GhostButton(footer, text="🗑 Borrar seleccionado", command=self._on_delete_selected).pack(side="right", padx=10, pady=8)
        header_items = tk.Frame(self.card_items, bg=COL_CARD); header_items.pack(fill="x")
        tk.Label(header_items, text="🧾 Lista de alimentos", bg=COL_CARD,
                 fg=COL_ACCENT, font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(side="left")

        style = ttk.Style(self); style.theme_use('clam')
        style.configure('Dark.Treeview', background='#1a1f2e', foreground=COL_TEXT,
                        fieldbackground='#1a1f2e', rowheight=30)
        style.map('Dark.Treeview', background=[('selected', '#2a3142')])
        style.configure('Dark.Treeview.Heading', background=COL_CARD, foreground=COL_ACCENT, relief='flat')

        tree_frame = tk.Frame(self.card_items, bg=COL_CARD); tree_frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tree_frame, columns=("item","grams"), show="headings",
                                 style='Dark.Treeview', selectmode="browse")
        self.tree.pack(fill="both", expand=True)

        if not SHOW_SCROLLBAR:
            self._drag_last_y = None
            def _on_touch_start(e): self._drag_last_y = e.y
            def _on_touch_move(e):
                if self._drag_last_y is None: return
                dy = e.y - self._drag_last_y
                if abs(dy) > 5:
                    self.tree.yview_scroll(-1 if dy > 0 else 1, "units")
                    self._drag_last_y = e.y
                    return "break"
            def _on_touch_end(e): self._drag_last_y = None
            self.tree.bind("<ButtonPress-1>", _on_touch_start)
            self.tree.bind("<B1-Motion>", _on_touch_move)
            self.tree.bind("<ButtonRelease-1>", _on_touch_end)

        self.tree.heading("item", text="Alimento")
        self.tree.heading("grams", text="Peso (g)")
        self.tree.column("item", stretch=True, anchor="w")
        self.tree.column("grams", width=110, anchor="center")

        self.tree.bind("<<TreeviewSelect>>", self._on_select_item)
        self.toast = Toast(self)

    # Métodos auxiliares...
    def on_show(self): 
        if not self._tick_after: self._tick()
    def on_hide(self):
        if self._tick_after:
            self.after_cancel(self._tick_after); self._tick_after = None
    def _tick(self):
        net_weight = self.app.get_latest_weight()
        self.weight_lbl.config(text=f"{net_weight:.{self.app.get_cfg().get('decimals', 0)}f} g")
        is_stable = abs(net_weight - getattr(self, '_last_weight', net_weight)) < 1.5
        if is_stable != self._stable:
            self._stable = is_stable
            self.stability_label.config(text="● Estable" if is_stable else "◉ Midiendo...",
                                        fg=COL_SUCCESS if is_stable else COL_WARN)
            self.status_indicator.set_status("active" if is_stable else "warning")
        setattr(self, '_last_weight', net_weight)
        self._tick_after = self.after(100, self._tick)
    def _on_tara(self): pass
    def _on_plato(self): pass
    def _on_add_item(self): pass
    def _on_select_item(self, evt): pass
    def _on_delete_selected(self): pass
    def _on_reset_session(self): pass
