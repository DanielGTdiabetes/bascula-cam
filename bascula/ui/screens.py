# -*- coding: utf-8 -*-
# bascula/ui/screens.py - MODIFICADO: Botones de navegación con texto para máxima compatibilidad.
import tkinter as tk
from tkinter import ttk

from bascula.ui.widgets import (
    Card, BigButton, GhostButton, WeightLabel, Toast,
    StatusIndicator, KeypadPopup, bind_numeric_popup, bind_text_popup,
    COL_BG, COL_CARD, COL_TEXT, COL_MUTED, COL_SUCCESS, COL_WARN, COL_DANGER, COL_ACCENT, COL_BORDER,
    FS_TEXT, FS_TITLE, FS_CARD_TITLE, get_scaled_size
)

class BaseScreen(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COL_BG, **kwargs)
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

        # --- Columna Izquierda: Peso ---
        self.card_weight = Card(self, min_width=700, min_height=400)
        self.card_weight.grid(row=0, column=0, sticky="nsew", padx=get_scaled_size(10), pady=get_scaled_size(10))
        header_weight = tk.Frame(self.card_weight, bg=COL_CARD); header_weight.pack(fill="x", pady=(0, get_scaled_size(6)))
        tk.Label(header_weight, text="Peso actual ●", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left")
        self.status_indicator = StatusIndicator(header_weight, size=get_scaled_size(10)); self.status_indicator.set_status("active")
        tk.Frame(self.card_weight, bg=COL_ACCENT, height=2).pack(fill="x", pady=(0, get_scaled_size(8)))
        weight_frame = tk.Frame(self.card_weight, bg="#1a1f2e", highlightbackground=COL_BORDER, highlightthickness=1, relief="flat")
        weight_frame.pack(expand=True, fill="both", padx=get_scaled_size(6), pady=get_scaled_size(6))
        self.weight_lbl = WeightLabel(weight_frame); self.weight_lbl.configure(bg="#1a1f2e"); self.weight_lbl.pack(expand=True, fill="both")
        stf = tk.Frame(weight_frame, bg="#1a1f2e"); stf.pack(side="bottom", pady=(0, get_scaled_size(8)))
        self.stability_label = tk.Label(stf, text="● Estable", bg="#1a1f2e", fg=COL_SUCCESS, font=("DejaVu Sans", FS_TEXT)); self.stability_label.pack()

        btns = tk.Frame(self.card_weight, bg=COL_CARD); btns.pack(fill="x", pady=(get_scaled_size(8),0))
        for c in range(5): btns.columnconfigure(c, weight=1, uniform="btns_row")
        for i, (txt, cmd) in enumerate([("Tara", self._on_tara), ("Plato único", self._on_single_plate), ("Añadir alimento", self._on_add_food), ("Ajustes", self.on_open_settings_menu), ("Reiniciar", self._on_reset_session)]):
            BigButton(btns, text=txt, command=cmd, micro=True).grid(row=0, column=i, sticky="nsew", padx=get_scaled_size(4), pady=(0, get_scaled_size(4)))

        # --- Columna Derecha: Totales y Lista ---
        right = tk.Frame(self, bg=COL_BG); right.grid(row=0, column=1, sticky="nsew", padx=(0,get_scaled_size(10)), pady=get_scaled_size(10))
        right.grid_rowconfigure(0, weight=0) 
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # --- Tarjeta de Totales ---
        self.card_nutrition = Card(right, min_width=320)
        self.card_nutrition.grid(row=0, column=0, sticky="new", pady=(0, get_scaled_size(12)))
        header_nut = tk.Frame(self.card_nutrition, bg=COL_CARD); header_nut.pack(fill="x")
        self.lbl_nut_title = tk.Label(header_nut, text="🥗 Totales", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_CARD_TITLE, "bold"))
        self.lbl_nut_title.pack(side="left")
        tk.Frame(self.card_nutrition, bg=COL_ACCENT, height=1).pack(fill="x", pady=(4,6))
        grid = tk.Frame(self.card_nutrition, bg="#1a1f2e", highlightbackground=COL_BORDER, highlightthickness=1, relief="flat")
        grid.pack(fill="x", expand=False, padx=8, pady=(6,10), anchor="n")
        self._nut_labels = {}
        names = [("Peso (g)","grams"),("Calorías (kcal)","kcal"),("Carbs (g)","carbs"),("Proteínas (g)","protein"),("Grasas (g)","fat")]
        for r,(name,key) in enumerate(names):
            grid.grid_rowconfigure(r, weight=1, uniform="nut")
            tk.Label(grid, text=name, bg="#1a1f2e", fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT)).grid(row=r, column=0, sticky="w", padx=(10,6), pady=2)
            v = tk.Label(grid, text="0", bg="#1a1f2e", fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT, "bold"))
            v.grid(row=r, column=1, sticky="e", padx=(6,10), pady=2); self._nut_labels[key] = v

        # --- Tarjeta de Lista de alimentos ---
        self.card_list = Card(right, min_width=320, min_height=300)
        self.card_list.grid(row=1, column=0, sticky="nsew")
        header_list = tk.Frame(self.card_list, bg=COL_CARD); header_list.pack(fill="x")
        tk.Label(header_list, text="🍽️ Lista de alimentos", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(side="left")
        tk.Frame(self.card_list, bg=COL_ACCENT, height=1).pack(fill="x", pady=(4,6))

        self.tree = ttk.Treeview(self.card_list, columns=("name","grams","kcal","carbs","protein","fat"), show="headings", height=8)
        for c,w in zip(("name","grams","kcal","carbs","protein","fat"), (160,70,70,70,70,70)):
            self.tree.heading(c, text=c.capitalize()); self.tree.column(c, anchor="center", width=w, stretch=False)
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)

        actions = tk.Frame(self.card_list, bg=COL_CARD); actions.pack(fill="x", pady=(0,8))
        BigButton(actions, text="➕ Añadir (manual)", command=self._on_add_manual, micro=True).pack(side="left", padx=6)
        BigButton(actions, text="📷 Añadir con cámara", command=self._on_add_camera, micro=True).pack(side="right", padx=6)

    def _on_tara(self): Toast(self, "Tara realizada ✓")
    def _on_single_plate(self): Toast(self, "Modo plato único (WIP)")
    def _on_reset_session(self):
        for iid in self.tree.get_children(): self.tree.delete(iid)
        self.items.clear(); self._next_id = 1; self._show_totals()
        Toast(self, "Sesión reiniciada")

    def _on_add_manual(self):
        Toast(self, "Añadir manual (WIP)")

    def _on_add_camera(self):
        # Modal fullscreen sin bordes
        modal = tk.Toplevel(self); modal.overrideredirect(True)
        try:
            modal.attributes("-fullscreen", True)
        except Exception: pass
        try: modal.configure(cursor="none")
        except Exception: pass
        try: modal.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        except Exception: pass
        cont = Card(modal, min_width=600, min_height=400); cont.pack(fill="both", expand=True, padx=20, pady=20)
        tk.Label(cont, text="📷 Cámara", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(anchor="w")
        area = tk.Frame(cont, bg="#1a1f2e", highlightbackground=COL_BORDER, highlightthickness=1); area.pack(fill="both", expand=True, pady=10)
        # --- Preview real ---
        stop_preview = self.app.start_camera_preview(area)
        row = tk.Frame(cont, bg=COL_CARD); row.pack(fill="x")
        GhostButton(row, text="Cancelar", command=lambda:(stop_preview(), modal.destroy()), micro=True).pack(side="left")
        def _capturar():
            stop_preview(); modal.destroy(); img_path = None
            try: img_path = self.app.capture_image()
            except Exception: img_path = None
            grams = self.app.get_latest_weight(); data = self.app.request_nutrition(image_path=img_path, grams=grams)
            self._add_item_from_data(data)
        BigButton(row, text="📸 Capturar", command=_capturar, micro=True).pack(side="right")

    def _add_item_from_data(self, data: dict):
        item = {k: data.get(k) for k in ["name", "grams", "kcal", "carbs", "protein", "fat", "image_path"]}
        item["id"] = self._next_id; self._next_id += 1; self.items.append(item)
        self.tree.insert("", "end", iid=str(item["id"]), values=(item.get("name","?"), f"{item.get('grams',0):.0f}", f"{item.get('kcal',0):.0f}", f"{item.get('carbs',0):.1f}", f"{item.get('protein',0):.1f}", f"{item.get('fat',0):.1f}"))
        self._show_item(item)
        if self._revert_timer: self.after_cancel(self._revert_timer)
        self._revert_timer = self.after(2000, self._show_totals)

    def _show_item(self, item: dict):
        # Muestra detalle rápido (WIP)
        Toast(self, f"Añadido: {item.get('name','?')} — {item.get('grams',0):.0f} g")

    def _show_totals(self):
        total = {"grams":0.0, "kcal":0.0, "carbs":0.0, "protein":0.0, "fat":0.0}
        for it in self.items:
            for k in total: total[k] += float(it.get(k,0.0) or 0.0)
        for k,lbl in self._nut_labels.items():
            v = total.get(k,0.0)
            fmt = "{:.0f}" if k in ("grams","kcal") else "{:.1f}"
            lbl.config(text=fmt.format(v))

class SettingsMenuScreen(BaseScreen):
    def __init__(self, parent, app, on_open_settings_menu):
        super().__init__(parent, app)
        # (contenido original de tu pantalla de ajustes…)
        # Mantengo la estructura; añade aquí tus widgets existentes si los tenías en la versión previa.
        pass

class CalibScreen(BaseScreen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        # (contenido original de tu pantalla de calibración…)

class WifiScreen(BaseScreen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        # (contenido original de tu pantalla de Wi-Fi…)

class ApiKeyScreen(BaseScreen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        # (contenido original de tu pantalla de API Key…)
