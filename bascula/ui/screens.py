# -*- coding: utf-8 -*-
# bascula/ui/screens.py - HOME con LISTA + NUTRICIÓN y cámara modal, teclado popup
import tkinter as tk
from tkinter import ttk

from bascula.ui.widgets import (
    Card, CardTitle, BigButton, GhostButton, WeightLabel, Toast, NumericKeypad,
    StatusIndicator, ScrollFrame, KeypadPopup, bind_numeric_popup,
    COL_BG, COL_CARD, COL_TEXT, COL_MUTED, COL_SUCCESS,
    COL_WARN, COL_DANGER, COL_ACCENT, COL_ACCENT_LIGHT, COL_BORDER,
    FS_TEXT, FS_TITLE, FS_CARD_TITLE, get_scaled_size
)

# ======== BASE ========
class BaseScreen(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COL_BG, **kwargs)
        self.app = app
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
    def on_show(self): pass
    def on_hide(self): pass

# ======== HOME ========
class HomeScreen(BaseScreen):
    """
    Diseño: Columna izquierda -> Peso (toda la altura).
             Columna derecha -> arriba Lista de alimentos, abajo Panel nutricional (totales o item seleccionado).
    'Añadir' abre cámara en modal de pantalla completa (simulada), captura y solicita nutrición (stub).
    """
    def __init__(self, parent, app, on_open_settings_menu):
        super().__init__(parent, app)
        self.on_open_settings_menu = on_open_settings_menu
        self.items = []          # [{'id':int,'name':str,'grams':float,'kcal':float,'carbs':float,'protein':float,'fat':float,'img':str}]
        self._next_id = 1
        self._selection_id = None
        self._revert_timer = None

        # Grid principal 2 columnas
        self.grid_columnconfigure(0, weight=3, uniform="cols")
        self.grid_columnconfigure(1, weight=2, uniform="cols")
        self.grid_rowconfigure(0, weight=1)

        # Izquierda: Peso
        self.card_weight = Card(self, min_width=700, min_height=400)
        self.card_weight.grid(row=0, column=0, sticky="nsew", padx=get_scaled_size(10), pady=get_scaled_size(10))

        header_weight = tk.Frame(self.card_weight, bg=COL_CARD); header_weight.pack(fill="x", pady=(0, get_scaled_size(6)))
        tk.Label(header_weight, text="Peso actual ●", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left")
        self.status_indicator = StatusIndicator(header_weight, size=16); self.status_indicator.pack(side="left", padx=(get_scaled_size(10),0)); self.status_indicator.set_status("active")
        tk.Frame(self.card_weight, bg=COL_ACCENT, height=2).pack(fill="x", pady=(0, get_scaled_size(8)))
        weight_frame = tk.Frame(self.card_weight, bg="#1a1f2e", highlightbackground=COL_BORDER, highlightthickness=1, relief="flat")
        weight_frame.pack(expand=True, fill="both", padx=get_scaled_size(6), pady=get_scaled_size(6))

        self.weight_lbl = WeightLabel(weight_frame); self.weight_lbl.configure(bg="#1a1f2e"); self.weight_lbl.pack(expand=True, fill="both")
        stf = tk.Frame(weight_frame, bg="#1a1f2e"); stf.pack(side="bottom", pady=(0, get_scaled_size(6)))
        self.stability_label = tk.Label(stf, text="● Estable", bg="#1a1f2e", fg=COL_SUCCESS, font=("DejaVu Sans", FS_TEXT)); self.stability_label.pack()

        # Botones cortos
        btns = tk.Frame(self.card_weight, bg=COL_CARD); btns.pack(fill="x", pady=(get_scaled_size(8),0))
        for c in range(4): btns.columnconfigure(c, weight=1, uniform="btns_row")
        for i, (txt, cmd) in enumerate([("Tara", self._on_tara), ("Plato", self._on_plato), ("Añadir", self._on_add_item), ("Ajustes", self.on_open_settings_menu)]):
            BigButton(btns, text=txt, command=cmd, micro=True).grid(row=0, column=i, sticky="nsew", padx=get_scaled_size(4), pady=(0, get_scaled_size(4)))

        # Derecha: Lista + Nutrición
        right = tk.Frame(self, bg=COL_BG); right.grid(row=0, column=1, sticky="nsew", padx=(0,get_scaled_size(10)), pady=get_scaled_size(10))
        right.grid_rowconfigure(0, weight=3, uniform="r"); right.grid_rowconfigure(1, weight=2, uniform="r"); right.grid_columnconfigure(0, weight=1)

        # Lista de alimentos
        self.card_items = Card(right, min_width=320, min_height=240); self.card_items.grid(row=0, column=0, sticky="nsew")
        header_items = tk.Frame(self.card_items, bg=COL_CARD); header_items.pack(fill="x")
        tk.Label(header_items, text="🧾 Lista de alimentos", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(side="left")
        tk.Frame(self.card_items, bg=COL_ACCENT, height=1).pack(fill="x", pady=(4,6))

        tree_frame = tk.Frame(self.card_items, bg=COL_CARD); tree_frame.pack(fill="both", expand=True)
        cols = ("item","grams","kcal","carbs","protein","fat")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        headings = {"item":"Alimento","grams":"g","kcal":"kcal","carbs":"C(g)","protein":"P(g)","fat":"G(g)"}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=70 if c!="item" else 140, anchor="center")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select_item)

        actions = tk.Frame(self.card_items, bg=COL_CARD); actions.pack(fill="x", pady=(6,0))
        GhostButton(actions, text="🗑 Borrar", command=self._on_delete_selected, micro=True).pack(side="left")

        # Panel nutricional
        self.card_nutrition = Card(right, min_width=320, min_height=200); self.card_nutrition.grid(row=1, column=0, sticky="nsew", pady=(get_scaled_size(10),0))
        header_nut = tk.Frame(self.card_nutrition, bg=COL_CARD); header_nut.pack(fill="x")
        self.lbl_nut_title = tk.Label(header_nut, text="🥗 Totales", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_CARD_TITLE, "bold"))
        self.lbl_nut_title.pack(side="left")
        tk.Frame(self.card_nutrition, bg=COL_ACCENT, height=1).pack(fill="x", pady=(4,6))

        self.nut_grid = tk.Frame(self.card_nutrition, bg="#1a1f2e", highlightbackground=COL_BORDER, highlightthickness=1, relief="flat")
        self.nut_grid.pack(fill="both", expand=True, padx=6, pady=6)
        self._nut_labels = {}
        for r, (name, key) in enumerate([("Peso (g)", "grams"), ("Calorías (kcal)", "kcal"), ("Carbohidratos (g)", "carbs"), ("Proteínas (g)", "protein"), ("Grasas (g)", "fat")]):
            row = tk.Frame(self.nut_grid, bg="#1a1f2e"); row.pack(fill="x", padx=8, pady=2)
            tk.Label(row, text=name+":", bg="#1a1f2e", fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT, "bold")).pack(side="left")
            val = tk.Label(row, text="—", bg="#1a1f2e", fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT)); val.pack(side="right")
            self._nut_labels[key] = val

        self.toast = Toast(self)

        # Estado lectura
        self._raw_actual = None; self._stable = False
        self.after(80, self._tick)

    # ===== Pesaje =====
    def _fmt(self, grams: float) -> str:
        cfg = self.app.get_cfg(); unit = cfg.get("unit","g"); decimals = max(0, int(cfg.get("decimals",0)))
        if unit == "kg":
            return f"{grams/1000.0:.{decimals}f} kg"
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
                        if not self._stable:
                            self._stable = True; self.stability_label.config(text="● Estable", fg=COL_SUCCESS)
                    else:
                        if self._stable:
                            self._stable = False; self.stability_label.config(text="◉ Midiendo...", fg=COL_WARN)
                    self._last_stable_weight = net
                    self.status_indicator.set_status("active")
                    updated = True
            if not updated:
                if self._raw_actual is None:
                    self.weight_lbl.config(text="0 g"); self.status_indicator.set_status("inactive"); self.stability_label.config(text="○ Sin señal", fg=COL_MUTED)
            self.after(80, self._tick)
        except Exception:
            self.after(150, self._tick)

    # ===== Botones =====
    def _on_tara(self):
        if self._raw_actual is None:
            self.toast.show("⚠ Sin lectura", ms=1200, color=COL_WARN); return
        self.app.get_tare().set_tare(self._raw_actual); self.toast.show("✓ Tara OK", ms=1000, color=COL_SUCCESS)

    def _on_plato(self):
        self.toast.show("🍽 Plato (pendiente)", ms=1000, color=COL_ACCENT)

    def _on_add_item(self):
        # Modal de cámara simulado
        modal = tk.Toplevel(self); modal.configure(bg=COL_BG); modal.attributes("-topmost", True)
        modal.transient(self.winfo_toplevel()); modal.grab_set(); modal.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        try: modal.overrideredirect(True)
        except Exception: pass

        cont = Card(modal, min_width=600, min_height=400); cont.pack(fill="both", expand=True, padx=20, pady=20)
        tk.Label(cont, text="📷 Cámara (simulada)", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(anchor="w")
        area = tk.Frame(cont, bg="#1a1f2e", highlightbackground=COL_BORDER, highlightthickness=1); area.pack(fill="both", expand=True, pady=10)
        tk.Label(area, text="Vista previa…", bg="#1a1f2e", fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT)).pack(expand=True)
        row = tk.Frame(cont, bg=COL_CARD); row.pack(fill="x")
        GhostButton(row, text="Cancelar", command=lambda:(modal.destroy()), micro=True).pack(side="left")
        def _capturar():
            modal.destroy()
            img_path = None
            try:
                img_path = self.app.capture_image()  # stub en app
            except Exception:
                img_path = None
            grams = self.app.get_latest_weight()
            # solicitar nutrición (stub)
            data = self.app.request_nutrition(image_path=img_path, grams=grams)
            self._add_item_from_data(data)
        BigButton(row, text="📸 Capturar", command=_capturar, micro=True).pack(side="right")

    # ===== Lista y nutrición =====
    def _add_item_from_data(self, data: dict):
        name = data.get("name","Alimento")
        grams = float(data.get("grams") or 0.0)
        kcal = float(data.get("kcal") or 0.0)
        carbs = float(data.get("carbs") or 0.0)
        protein = float(data.get("protein") or 0.0)
        fat = float(data.get("fat") or 0.0)
        img = data.get("image_path")
        item = {"id": self._next_id, "name": name, "grams": grams, "kcal": kcal, "carbs": carbs, "protein": protein, "fat": fat, "img": img}
        self._next_id += 1
        self.items.append(item)
        self.tree.insert("", "end", iid=str(item["id"]), values=(item["name"], f"{item['grams']:.0f}", f"{item['kcal']:.0f}", f"{item['carbs']:.1f}", f"{item['protein']:.1f}", f"{item['fat']:.1f}"))
        # mostrar item un instante y volver a totales
        self._show_item(item)
        if self._revert_timer: self.after_cancel(self._revert_timer)
        self._revert_timer = self.after(2000, self._show_totals)

    def _on_select_item(self, _evt=None):
        sel = self.tree.selection()
        if not sel:
            self._selection_id = None
            self._show_totals(); return
        iid = int(sel[0]); self._selection_id = iid
        item = next((x for x in self.items if x["id"]==iid), None)
        if item: self._show_item(item)

    def _on_delete_selected(self):
        sel = self.tree.selection()
        if not sel: return
        iid = int(sel[0])
        self.tree.delete(sel[0])
        self.items = [x for x in self.items if x["id"]!=iid]
        self._selection_id = None
        self._show_totals()

    def _show_totals(self):
        self.lbl_nut_title.config(text="🥗 Totales")
        totals = {"grams":0.0,"kcal":0.0,"carbs":0.0,"protein":0.0,"fat":0.0}
        for it in self.items:
            totals["grams"] += it["grams"]; totals["kcal"] += it["kcal"]; totals["carbs"] += it["carbs"]; totals["protein"] += it["protein"]; totals["fat"] += it["fat"]
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

# ======== AJUSTES (MENÚ) ========
class SettingsMenuScreen(BaseScreen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=(get_scaled_size(10),0))
        title_frame = tk.Frame(header, bg=COL_BG); title_frame.pack(side="left", padx=get_scaled_size(14))
        tk.Label(title_frame, text="⚙", bg=COL_BG, fg=COL_ACCENT, font=("DejaVu Sans", int(FS_TITLE*1.4))).pack(side="left", padx=(0,get_scaled_size(8)))
        tk.Label(title_frame, text="Ajustes", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left")
        GhostButton(header, text="← Volver", command=lambda:self.app.show_screen('home'), micro=True).pack(side="right", padx=get_scaled_size(14))
        tk.Frame(self, bg=COL_ACCENT, height=2).pack(fill="x", padx=get_scaled_size(14), pady=(get_scaled_size(6),0))
        container = Card(self, min_height=400); container.pack(fill="both", expand=True, padx=get_scaled_size(14), pady=get_scaled_size(10))
        grid = tk.Frame(container, bg=COL_CARD); grid.pack(expand=True)
        for r in range(2): grid.grid_rowconfigure(r, weight=1, uniform="menu")
        for c in range(2): grid.grid_columnconfigure(c, weight=1, uniform="menu")
        BigButton(grid, text="Calibración", command=lambda:self.app.show_screen('calib'), small=True).grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        BigButton(grid, text="Wi-Fi", command=lambda:self.app.show_screen('wifi'), small=True).grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        BigButton(grid, text="API Key", command=lambda:self.app.show_screen('apikey'), small=True).grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        BigButton(grid, text="Otros", command=lambda:self._soon(), small=True).grid(row=1, column=1, sticky="nsew", padx=6, pady=6)
        self.toast = Toast(self)
    def _soon(self): self.toast.show("Próximamente…", ms=900, color=COL_MUTED)

# ======== CALIBRACIÓN (usa keypad popup) ========
class CalibScreen(BaseScreen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=(get_scaled_size(10),0))
        title_frame = tk.Frame(header, bg=COL_BG); title_frame.pack(side="left", padx=get_scaled_size(14))
        tk.Label(title_frame, text="⚖", bg=COL_BG, fg=COL_ACCENT, font=("DejaVu Sans", int(FS_TITLE*1.4))).pack(side="left", padx=(0,get_scaled_size(8)))
        tk.Label(title_frame, text="Calibración", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left")
        GhostButton(header, text="← Ajustes", command=lambda:self.app.show_screen('settings_menu'), micro=True).pack(side="right", padx=get_scaled_size(14))
        tk.Frame(self, bg=COL_ACCENT, height=2).pack(fill="x", padx=get_scaled_size(14), pady=(get_scaled_size(6),0))
        body = Card(self, min_height=360); body.pack(fill="both", expand=True, padx=get_scaled_size(14), pady=get_scaled_size(10))

        # Lectura en vivo
        live = tk.Frame(body, bg="#1a1f2e", highlightbackground=COL_BORDER, highlightthickness=1); live.pack(fill="x", pady=6, padx=6)
        tk.Label(live, text="Lectura actual:", bg="#1a1f2e", fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT, "bold")).pack(side="left", padx=8, pady=6)
        self.lbl_live = tk.Label(live, text="—", bg="#1a1f2e", fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT)); self.lbl_live.pack(side="left", pady=6)

        # Capturas
        caprow = tk.Frame(body, bg=COL_CARD); caprow.pack(fill="x", pady=6)
        self._b0 = None; self._bw = None

        GhostButton(caprow, text="📍 Cero", command=self._cap_cero, micro=True).pack(side="left", padx=4)
        GhostButton(caprow, text="📍 Con patrón", command=self._cap_con_peso, micro=True).pack(side="left", padx=4)

        # Peso patrón con keypad popup
        rowp = tk.Frame(body, bg=COL_CARD); rowp.pack(fill="x", pady=6, padx=6)
        tk.Label(rowp, text="Peso patrón (g/kg según unidad):", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT)).pack(side="left")
        self.var_patron = tk.StringVar(value=""); ent = tk.Entry(rowp, textvariable=self.var_patron, bg="#1a1f2e", fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT), relief="flat", highlightbackground=COL_BORDER, highlightthickness=1, width=12)
        ent.pack(side="left", padx=8); bind_numeric_popup(ent, allow_dot=True)

        BigButton(body, text="💾 Guardar calibración", command=self._calc_save, micro=True).pack(anchor="e", pady=4, padx=6)

        self.toast = Toast(self)
        self.after(120, self._tick_live)

    def _tick_live(self):
        try:
            r = self.app.get_reader()
            if r is not None:
                v = r.get_latest()
                if v is not None: self.lbl_live.config(text=f"{v:.3f}")
        finally:
            self.after(120, self._tick_live)

    def _promedio(self, n=10):
        r = self.app.get_reader(); vals = []
        for _ in range(n):
            v = r.get_latest() if r else None
            if v is not None: vals.append(v)
            self.update(); self.after(30)
        return (sum(vals)/len(vals)) if vals else None

    def _cap_cero(self):
        v = self._promedio(10)
        if v is None: self.toast.show("⚠ Sin lectura", 1200, COL_WARN); return
        self._b0 = v; self.toast.show("✓ Cero OK", 900, COL_SUCCESS)

    def _cap_con_peso(self):
        v = self._promedio(12)
        if v is None: self.toast.show("⚠ Sin lectura patrón", 1200, COL_WARN); return
        self._bw = v; self.toast.show("✓ Patrón OK", 900, COL_SUCCESS)

    def _parse_patron(self):
        s = (self.var_patron.get() or "").strip().replace(",", ".")
        try:
            w = float(s); 
            if w <= 0: return None
            unit = self.app.get_cfg().get("unit","g")
            return w if unit=="g" else (w*1000.0)
        except Exception:
            return None

    def _calc_save(self):
        if self._b0 is None: self.toast.show("⚠ Falta Cero", 1200, COL_WARN); return
        if self._bw is None: self.toast.show("⚠ Falta Patrón", 1200, COL_WARN); return
        Wg = self._parse_patron()
        if Wg is None: self.toast.show("⚠ Peso inválido", 1200, COL_WARN); return
        delta = self._bw - self._b0
        if abs(delta) < 1e-9: self.toast.show("⚠ Diferencia pequeña", 1200, COL_WARN); return
        factor = Wg / delta
        try:
            self.app.get_tare().update_calib(factor)
            self.app.get_cfg()["calib_factor"] = factor
            self.app.save_cfg()
            self.toast.show("✅ Calibración guardada", 1500, COL_SUCCESS)
            self.after(800, lambda:self.app.show_screen('settings_menu'))
        except Exception:
            self.toast.show("❌ Error al guardar", 1500, COL_DANGER)

# ======== WIFI ========
class WifiScreen(BaseScreen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=(get_scaled_size(10),0))
        title_frame = tk.Frame(header, bg=COL_BG); title_frame.pack(side="left", padx=get_scaled_size(14))
        tk.Label(title_frame, text="📶", bg=COL_BG, fg=COL_ACCENT, font=("DejaVu Sans", int(FS_TITLE*1.4))).pack(side="left", padx=(0,get_scaled_size(8)))
        tk.Label(title_frame, text="Conexión Wi-Fi", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left")
        GhostButton(header, text="← Ajustes", command=lambda:self.app.show_screen('settings_menu'), micro=True).pack(side="right", padx=get_scaled_size(14))
        tk.Frame(self, bg=COL_ACCENT, height=2).pack(fill="x", padx=get_scaled_size(14), pady=(get_scaled_size(6),0))
        body = Card(self, min_height=300); body.pack(fill="both", expand=True, padx=get_scaled_size(14), pady=get_scaled_size(10))

        form = tk.Frame(body, bg=COL_CARD); form.pack(fill="x", padx=6, pady=6)
        row_ssid = tk.Frame(form, bg=COL_CARD); row_ssid.pack(fill="x", pady=6)
        tk.Label(row_ssid, text="SSID:", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT, "bold"), width=16, anchor="w").pack(side="left")
        self._ssid_var = tk.StringVar(value=self.app.get_cfg().get("wifi_ssid","")); tk.Entry(row_ssid, textvariable=self._ssid_var, bg="#1a1f2e", fg=COL_TEXT, insertbackground=COL_ACCENT, font=("DejaVu Sans", FS_TEXT), relief="flat", highlightbackground=COL_BORDER, highlightthickness=1).pack(side="left", fill="x", expand=True)
        row_psk = tk.Frame(form, bg=COL_CARD); row_psk.pack(fill="x", pady=6)
        tk.Label(row_psk, text="Contraseña:", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT, "bold"), width=16, anchor="w").pack(side="left")
        self._psk_var = tk.StringVar(value=self.app.get_cfg().get("wifi_psk","")); self._psk_entry = tk.Entry(row_psk, textvariable=self._psk_var, show="•", bg="#1a1f2e", fg=COL_TEXT, insertbackground=COL_ACCENT, font=("DejaVu Sans", FS_TEXT), relief="flat", highlightbackground=COL_BORDER, highlightthickness=1); self._psk_entry.pack(side="left", fill="x", expand=True)
        GhostButton(row_psk, text="👁", command=self._toggle_psk, micro=True).pack(side="left", padx=6)
        actions = tk.Frame(body, bg=COL_CARD); actions.pack(fill="x", pady=6)
        BigButton(actions, text="Guardar", command=self._save, micro=True).pack(side="left")
        BigButton(actions, text="Conectar", command=self._connect, micro=True).pack(side="left", padx=10)
        tip = tk.Label(body, text="Nota: la conexión real puede requerir privilegios del sistema. Esta pantalla guarda SSID/contraseña para que tu servicio de red los use.", bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT), wraplength=800, justify="left"); tip.pack(fill="x", pady=(10,0))
        self.toast = Toast(self)
    def _toggle_psk(self):
        self._psk_entry.config(show="" if self._psk_entry.cget("show")=="•" else "•")
    def _save(self):
        cfg = self.app.get_cfg(); cfg["wifi_ssid"] = self._ssid_var.get().strip(); cfg["wifi_psk"] = self._psk_var.get().strip(); self.app.save_cfg(); self.toast.show("✓ Guardado", 1200, COL_SUCCESS)
    def _connect(self):
        ok = False
        if hasattr(self.app, "wifi_connect"):
            try: ok = self.app.wifi_connect(self._ssid_var.get().strip(), self._psk_var.get().strip())
            except Exception: ok = False
        self.toast.show("🔌 Conexión solicitada" if ok else "ℹ Delegado al sistema", 1400, COL_MUTED)

# ======== API KEY ========
class ApiKeyScreen(BaseScreen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=(get_scaled_size(10),0))
        title_frame = tk.Frame(header, bg=COL_BG); title_frame.pack(side="left", padx=get_scaled_size(14))
        tk.Label(title_frame, text="🗝", bg=COL_BG, fg=COL_ACCENT, font=("DejaVu Sans", int(FS_TITLE*1.4))).pack(side="left", padx=(0,get_scaled_size(8)))
        tk.Label(title_frame, text="API Key ChatGPT", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left")
        GhostButton(header, text="← Ajustes", command=lambda:self.app.show_screen('settings_menu'), micro=True).pack(side="right", padx=get_scaled_size(14))
        tk.Frame(self, bg=COL_ACCENT, height=2).pack(fill="x", padx=get_scaled_size(14), pady=(get_scaled_size(6),0))
        body = Card(self, min_height=250); body.pack(fill="both", expand=True, padx=get_scaled_size(14), pady=get_scaled_size(10))
        row = tk.Frame(body, bg=COL_CARD); row.pack(fill="x", pady=8)
        tk.Label(row, text="API Key:", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT, "bold"), width=16, anchor="w").pack(side="left")
        self._key_var = tk.StringVar(value=self.app.get_cfg().get("openai_api_key",""))
        self._key_entry = tk.Entry(row, textvariable=self._key_var, show="•", bg="#1a1f2e", fg=COL_TEXT, insertbackground=COL_ACCENT, font=("DejaVu Sans", FS_TEXT), relief="flat", highlightbackground=COL_BORDER, highlightthickness=1)
        self._key_entry.pack(side="left", fill="x", expand=True)
        GhostButton(row, text="👁", command=self._toggle_key, micro=True).pack(side="left", padx=6)
        actions = tk.Frame(body, bg=COL_CARD); actions.pack(fill="x", pady=6)
        BigButton(actions, text="Guardar", command=self._save, micro=True).pack(side="left")
        BigButton(actions, text="Probar", command=self._test_local, micro=True).pack(side="left", padx=10)
        tip = tk.Label(body, text="Consejo: pega tu clave completa (p. ej. comienza por 'sk-'). La prueba local valida formato/longitud.", bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT), wraplength=820, justify="left"); tip.pack(fill="x", pady=(10,0))
        self.toast = Toast(self)
    def _toggle_key(self):
        self._key_entry.config(show="" if self._key_entry.cget("show")=="•" else "•")
    def _save(self):
        k = self._key_var.get().strip(); self.app.get_cfg()["openai_api_key"] = k; self.app.save_cfg(); self.toast.show("✓ API Key guardada", 1200, COL_SUCCESS)
    def _test_local(self):
        k = self._key_var.get().strip(); ok = len(k)>=20 and ("sk-" in k or k.startswith("sk-"))
        self.toast.show("✓ Formato parece correcto" if ok else "⚠ Clave sospechosa", 1100 if ok else 1300, COL_SUCCESS if ok else COL_WARN)
