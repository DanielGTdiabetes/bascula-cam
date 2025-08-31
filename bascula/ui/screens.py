# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk

from bascula.ui.widgets import (
    Card, BigButton, GhostButton, WeightLabel, Toast, StatusIndicator,
    bind_numeric_popup, bind_text_popup,
    COL_BG, COL_CARD, COL_TEXT, COL_MUTED, COL_SUCCESS, COL_WARN, COL_ACCENT, COL_BORDER,
    FS_TEXT, FS_TITLE, FS_CARD_TITLE, get_scaled_size
)

class BaseScreen(tk.Frame):
    def __init__(self, parent, app, **kw):
        super().__init__(parent, bg=COL_BG, **kw)
        self.app = app
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
    def on_show(self): pass
    def on_hide(self): pass

class HomeScreen(BaseScreen):
    def __init__(self, parent, app, on_open_settings_menu):
        super().__init__(parent, app)
        self.on_open_settings_menu = on_open_settings_menu
        self.items = []; self._next_id = 1; self._selection_id = None; self._revert_timer = None

        self.grid_columnconfigure(0, weight=3, uniform="cols")
        self.grid_columnconfigure(1, weight=2, uniform="cols")
        self.grid_rowconfigure(0, weight=1)

        # ===== Columna izquierda (Peso) =====
        self.card_weight = Card(self, min_width=680, min_height=360)
        self.card_weight.grid(row=0, column=0, sticky="nsew", padx=get_scaled_size(10), pady=get_scaled_size(10))
        header_weight = tk.Frame(self.card_weight, bg=COL_CARD); header_weight.pack(fill="x", pady=(0, get_scaled_size(6)))
        tk.Label(header_weight, text="Peso actual ●", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left")
        self.status_indicator = StatusIndicator(header_weight, size=16); self.status_indicator.pack(side="left", padx=(get_scaled_size(10),0)); self.status_indicator.set_status("active")
        tk.Frame(self.card_weight, bg=COL_ACCENT, height=2).pack(fill="x", pady=(0, get_scaled_size(8)))

        weight_frame = tk.Frame(self.card_weight, bg="#1a1f2e", highlightbackground=COL_BORDER, highlightthickness=1, relief="flat")
        weight_frame.pack(expand=True, fill="both", padx=get_scaled_size(6), pady=get_scaled_size(6))
        self.weight_lbl = WeightLabel(weight_frame); self.weight_lbl.configure(bg="#1a1f2e"); self.weight_lbl.pack(expand=True, fill="both")
        stf = tk.Frame(weight_frame, bg="#1a1f2e"); stf.pack(side="bottom", pady=(0, get_scaled_size(8)))
        self.stability_label = tk.Label(stf, text="● Estable", bg="#1a1f2e", fg=COL_SUCCESS, font=("DejaVu Sans", FS_TEXT)); self.stability_label.pack()

        btns = tk.Frame(self.card_weight, bg=COL_CARD); btns.pack(fill="x", pady=(get_scaled_size(8),0))
        for c in range(5): btns.columnconfigure(c, weight=1, uniform="btns_row")
        for i, (txt, cmd) in enumerate([("Tara", self._on_tara), ("Plato", self._on_plato), ("Añadir", self._on_add_item),
                                        ("Ajustes", self.on_open_settings_menu), ("Reiniciar", self._on_reset_session)]):
            BigButton(btns, text=txt, command=cmd, micro=True).grid(row=0, column=i, sticky="nsew", padx=get_scaled_size(4), pady=(0, get_scaled_size(4)))

        # ===== Columna derecha =====
        right = tk.Frame(self, bg=COL_BG); right.grid(row=0, column=1, sticky="nsew", padx=(0,get_scaled_size(10)), pady=get_scaled_size(10))
        right.grid_rowconfigure(0, weight=5, uniform="r")  # Lista (más alta)
        right.grid_rowconfigure(1, weight=3, uniform="r")  # Nutrición
        right.grid_columnconfigure(0, weight=1)

        # Estilo Treeview
        style = ttk.Style(self)
        try: style.theme_use('clam')
        except Exception: pass
        style.configure('Dark.Treeview',
                        background='#1a1f2e', foreground=COL_TEXT, fieldbackground='#1a1f2e',
                        bordercolor=COL_BORDER, lightcolor=COL_BORDER, darkcolor=COL_BORDER,
                        rowheight=get_scaled_size(24))
        style.map('Dark.Treeview',
                  background=[('selected', '#2a3142')],
                  foreground=[('selected', '#e8fff7')])
        style.configure('Dark.Treeview.Heading', background=COL_CARD, foreground=COL_ACCENT, relief='flat')

        # --- Lista de alimentos (grid interno con acciones fijas) ---
        self.card_items = Card(right, min_width=320, min_height=220); self.card_items.grid(row=0, column=0, sticky="nsew")
        _root = tk.Frame(self.card_items, bg=COL_CARD); _root.pack(fill="both", expand=True)
        _root.grid_rowconfigure(0, weight=0); _root.grid_rowconfigure(1, weight=0)
        _root.grid_rowconfigure(2, weight=1); _root.grid_rowconfigure(3, weight=0)
        _root.grid_columnconfigure(0, weight=1)

        _h = tk.Frame(_root, bg=COL_CARD); _h.grid(row=0, column=0, sticky="ew")
        tk.Label(_h, text="🧾 Lista de alimentos", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(side="left")
        tk.Frame(_root, bg=COL_ACCENT, height=1).grid(row=1, column=0, sticky="ew", pady=(2,4))

        _tf = tk.Frame(_root, bg=COL_CARD); _tf.grid(row=2, column=0, sticky="nsew")
        cols=("item","grams","kcal","carbs","protein","fat")
        self.tree = ttk.Treeview(_tf, columns=cols, show="headings", selectmode="browse", style='Dark.Treeview')
        for c,t in [("item","Alimento"),("grams","g"),("kcal","kcal"),("carbs","C(g)"),("protein","P(g)"),("fat","G(g)")]:
            self.tree.heading(c, text=t); self.tree.column(c, width=70 if c!="item" else 140, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self._on_select_item)

        _act = tk.Frame(_root, bg=COL_CARD); _act.grid(row=3, column=0, sticky="ew", pady=(4,0))
        GhostButton(_act, text="🗑 Borrar", command=self._on_delete_selected, micro=True).pack(side="left")
        GhostButton(_act, text="🔄 Reiniciar", command=self._on_reset_session, micro=True).pack(side="right")

        # --- Nutrición (compacta para que quepan las 5 filas) ---
        self.card_nutrition = Card(right, min_width=320, min_height=260)
        self.card_nutrition.grid(row=1, column=0, sticky="nsew", pady=(get_scaled_size(8),0))
        header_nut = tk.Frame(self.card_nutrition, bg=COL_CARD); header_nut.pack(fill="x")
        self.lbl_nut_title = tk.Label(header_nut, text="🥗 Totales", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_CARD_TITLE, "bold"))
        self.lbl_nut_title.pack(side="left")
        tk.Frame(self.card_nutrition, bg=COL_ACCENT, height=1).pack(fill="x", pady=(2,4))

        grid = tk.Frame(self.card_nutrition, bg="#1a1f2e", highlightbackground=COL_BORDER, highlightthickness=1, relief="flat")
        grid.pack(fill="both", expand=True, padx=6, pady=(3,4), anchor="n")
        self._nut_labels = {}
        names = [("Peso (g)","grams"),("Calorías (kcal)","kcal"),("Carbohidratos (g)","carbs"),("Proteínas (g)","protein"),("Grasas (g)","fat")]
        for r,(name,key) in enumerate(names):
            grid.grid_rowconfigure(r, weight=1); grid.grid_columnconfigure(0, weight=1); grid.grid_columnconfigure(1, weight=1)
            lbl = tk.Label(grid, text=name+":", bg="#1a1f2e", fg=COL_TEXT, font=("DejaVu Sans", max(FS_TEXT-1,10)), anchor="w")
            val = tk.Label(grid, text="—", bg="#1a1f2e", fg=COL_TEXT, font=("DejaVu Sans", max(FS_TEXT-1,10)), anchor="e")
            lbl.grid(row=r, column=0, sticky="w", padx=8, pady=(1,1))
            val.grid(row=r, column=1, sticky="e", padx=8, pady=(1,1))
            self._nut_labels[key] = val

        self.toast = Toast(self)
        self._raw_actual = None; self._stable = False
        self.after(80, self._tick)

    def _fmt(self, grams: float) -> str:
        cfg = self.app.get_cfg(); unit = cfg.get("unit","g"); decimals = max(0, int(cfg.get("decimals",0)))
        if unit == "kg": return f"{grams/1000.0:.{decimals}f} kg"
        return f"{grams:.{decimals}f} g" if decimals>0 else f"{round(grams):.0f} g"

    def _tick(self):
        try:
            reader = self.app.get_reader(); smoother = self.app.get_smoother(); tare = self.app.get_tare()
            updated = False
            if reader is not None:
                val = reader.get_latest()
                if val is not None:
                    self._raw_actual = val
                    sm = smoother.add(val)
                    net = tare.compute_net(sm)
                    self.weight_lbl.config(text=self._fmt(net))
                    if abs(net - getattr(self, '_last_stable_weight', 0)) < 2.0:
                        if not self._stable: self._stable = True; self.stability_label.config(text="● Estable", fg=COL_SUCCESS)
                    else:
                        if self._stable: self._stable = False; self.stability_label.config(text="◉ Midiendo...", fg=COL_WARN)
                    self._last_stable_weight = net; self.status_indicator.set_status("active"); updated = True
            if not updated and self._raw_actual is None:
                self.weight_lbl.config(text="0 g"); self.status_indicator.set_status("inactive"); self.stability_label.config(text="○ Sin señal", fg=COL_MUTED)
            self.after(80, self._tick)
        except Exception:
            self.after(150, self._tick)

    def _on_tara(self):
        if self._raw_actual is None: self.toast.show("⚠ Sin lectura", 1200, COL_WARN); return
        self.app.get_tare().set_tare(self._raw_actual); self.toast.show("✓ Tara OK", 1000, COL_SUCCESS)

    def _on_plato(self):
        self.toast.show("🍽 Plato (pendiente)", 1000, COL_ACCENT)

    def _on_add_item(self):
        modal = tk.Toplevel(self); modal.configure(bg=COL_BG)
        try: modal.attributes("-topmost", True); modal.overrideredirect(True)
        except Exception: pass
        modal.transient(self.winfo_toplevel()); modal.grab_set(); modal.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        cont = Card(modal, min_width=600, min_height=400); cont.pack(fill="both", expand=True, padx=20, pady=20)
        tk.Label(cont, text="📷 Cámara (simulada)", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(anchor="w")
        area = tk.Frame(cont, bg="#1a1f2e", highlightbackground=COL_BORDER, highlightthickness=1); area.pack(fill="both", expand=True, pady=10)
        tk.Label(area, text="Vista previa…", bg="#1a1f2e", fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT)).pack(expand=True)
        row = tk.Frame(cont, bg=COL_CARD); row.pack(fill="x")
        GhostButton(row, text="Cancelar", command=lambda:modal.destroy(), micro=True).pack(side="left")
        def _capturar():
            modal.destroy()
            img_path = None
            try: img_path = self.app.capture_image()
            except Exception: img_path = None
            grams = self.app.get_latest_weight()
            data = self.app.request_nutrition(image_path=img_path, grams=grams)
            self._add_item_from_data(data)
        BigButton(row, text="📸 Capturar", command=_capturar, micro=True).pack(side="right")

    def _add_item_from_data(self, data: dict):
        name = data.get("name","Alimento"); grams = float(data.get("grams") or 0.0)
        kcal = float(data.get("kcal") or 0.0); carbs = float(data.get("carbs") or 0.0)
        protein = float(data.get("protein") or 0.0); fat = float(data.get("fat") or 0.0)
        img = data.get("image_path")
        item = {"id": self._next_id, "name": name, "grams": grams, "kcal": kcal, "carbs": carbs, "protein": protein, "fat": fat, "img": img}
        self._next_id += 1; self.items.append(item)
        self.tree.insert("", "end", iid=str(item["id"]), values=(item["name"], f"{item['grams']:.0f}", f"{item['kcal']:.0f}", f"{item['carbs']:.1f}", f"{item['protein']:.1f}", f"{item['fat']:.1f}"))
        self._show_item(item)
        if self._revert_timer: self.after_cancel(self._revert_timer)
        self._revert_timer = self.after(2000, self._show_totals)

    def _on_select_item(self, _evt=None):
        sel = self.tree.selection()
        if not sel: self._selection_id = None; self._show_totals(); return
        iid = int(sel[0]); self._selection_id = iid
        item = next((x for x in self.items if x["id"]==iid), None)
        if item: self._show_item(item)

    def _on_delete_selected(self):
        sel = self.tree.selection()
        if not sel: self.toast.show("Selecciona un alimento", 900, COL_MUTED); return
        iid = int(sel[0]); self.tree.delete(sel[0])
        self.items = [x for x in self.items if x["id"]!=iid]
        self._selection_id = None; self._show_totals()

    def _on_reset_session(self):
        self.tree.delete(*self.tree.get_children())
        self.items.clear()
        self._selection_id = None
        self._show_totals()
        self.toast.show("🔄 Reiniciado", 900, COL_SUCCESS)

    def _show_totals(self):
        self.lbl_nut_title.config(text="🥗 Totales")
        totals = {"grams":0.0,"kcal":0.0,"carbs":0.0,"protein":0.0,"fat":0.0}
        for it in self.items:
            totals["grams"] += it["grams"]; totals["kcal"] += it["kcal"]; totals["carbs"] += it["carbs"]
            totals["protein"] += it["protein"]; totals["fat"] += it["fat"]
        self._render_nut(totals)

    def _show_item(self, item):
        self.lbl_nut_title.config(text=f"🥗 {item['name']}")
        self._render_nut(item)

    def _render_nut(self, data):
        def fmt(v, d=1):
            try: return f"{float(v):.{d}f}"
            except Exception: return "—"
        self._nut_labels["grams"].config(text=fmt(data.get("grams",0),0))
        self._nut_labels["kcal"].config(text=fmt(data.get("kcal",0),0))
        self._nut_labels["carbs"].config(text=fmt(data.get("carbs",0)))
        self._nut_labels["protein"].config(text=fmt(data.get("protein",0)))
        self._nut_labels["fat"].config(text=fmt(data.get("fat",0)))

# Placeholders mínimos para compatibilidad con el App existente
class SettingsMenuScreen(BaseScreen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        Card(self).pack(fill="both", expand=True)
class CalibScreen(BaseScreen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        Card(self).pack(fill="both", expand=True)
class WifiScreen(BaseScreen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        Card(self).pack(fill="both", expand=True)
class ApiKeyScreen(BaseScreen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        Card(self).pack(fill="both", expand=True)
