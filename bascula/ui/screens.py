# -*- coding: utf-8 -*-
# bascula/ui/screens.py - CÓDIGO COMPLETO CON IMPORTACIÓN CORREGIDA
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
        self.grid_rowconfigure(0, weight=1); self.grid_columnconfigure(0, weight=1)

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
        self.status_indicator = StatusIndicator(header_weight, size=16); self.status_indicator.pack(side="left", padx=(get_scaled_size(10),0))
        tk.Frame(self.card_weight, bg=COL_ACCENT, height=2).pack(fill="x", pady=(0, get_scaled_size(8)))
        weight_frame = tk.Frame(self.card_weight, bg="#1a1f2e", highlightbackground=COL_BORDER, highlightthickness=1, relief="flat")
        weight_frame.pack(expand=True, fill="both", padx=get_scaled_size(6), pady=get_scaled_size(6))
        self.weight_lbl = WeightLabel(weight_frame, bg="#1a1f2e"); self.weight_lbl.pack(expand=True, fill="both")
        stf = tk.Frame(weight_frame, bg="#1a1f2e"); stf.pack(side="bottom", pady=(0, get_scaled_size(8)))
        self.stability_label = tk.Label(stf, text="● Estable", bg="#1a1f2e", fg=COL_SUCCESS, font=("DejaVu Sans", FS_TEXT)); self.stability_label.pack()

        btns = tk.Frame(self.card_weight, bg=COL_CARD); btns.pack(fill="x", pady=(get_scaled_size(8),0))
        for c in range(5): btns.columnconfigure(c, weight=1, uniform="btns_row")
        for i, (txt, cmd) in enumerate([("Tara", self._on_tara), ("Plato", self._on_plato), ("Añadir", self._on_add_item), ("Ajustes", self.on_open_settings_menu), ("Reiniciar", self._on_reset_session)]):
            BigButton(btns, text=txt, command=cmd, micro=True).grid(row=0, column=i, sticky="nsew", padx=get_scaled_size(4), pady=(0, get_scaled_size(4)))

        # --- Columna Derecha: Totales y Lista ---
        right = tk.Frame(self, bg=COL_BG); right.grid(row=0, column=1, sticky="nsew", padx=(0,get_scaled_size(10)), pady=get_scaled_size(10))
        right.grid_rowconfigure(0, weight=0); right.grid_rowconfigure(1, weight=1); right.grid_columnconfigure(0, weight=1)

        self.card_nutrition = Card(right, min_width=320)
        self.card_nutrition.grid(row=0, column=0, sticky="new", pady=(0, get_scaled_size(12)))
        header_nut = tk.Frame(self.card_nutrition, bg=COL_CARD); header_nut.pack(fill="x")
        self.lbl_nut_title = tk.Label(header_nut, text="🥗 Totales", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_CARD_TITLE, "bold"))
        self.lbl_nut_title.pack(side="left")
        tk.Frame(self.card_nutrition, bg=COL_ACCENT, height=1).pack(fill="x", pady=(4,6))
        grid = tk.Frame(self.card_nutrition, bg="#1a1f2e", highlightbackground=COL_BORDER, highlightthickness=1, relief="flat")
        grid.pack(fill="x", expand=False, padx=8, pady=(6,10), anchor="n")
        self._nut_labels = {}
        names = [("Peso (g)","grams"),("Calorías (kcal)","kcal"),("Carbohidratos (g)","carbs"),("Proteínas (g)","protein"),("Grasas (g)","fat")]
        for r,(name,key) in enumerate(names):
            grid.grid_rowconfigure(r, weight=1); grid.grid_columnconfigure(0, weight=1); grid.grid_columnconfigure(1, weight=1)
            lbl = tk.Label(grid, text=name+":", bg="#1a1f2e", fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT), anchor="w")
            val = tk.Label(grid, text="—", bg="#1a1f2e", fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT), anchor="e")
            lbl.grid(row=r, column=0, sticky="w", padx=10, pady=(3,3))
            val.grid(row=r, column=1, sticky="e", padx=10, pady=(3,3))
            self._nut_labels[key] = val

        self.card_items = Card(right, min_width=320, min_height=240); self.card_items.grid(row=1, column=0, sticky="nsew")
        GhostButton(self.card_items, text="🗑 Borrar seleccionado", command=self._on_delete_selected, micro=False).pack(side="bottom", fill="x", pady=(get_scaled_size(10), 0))
        header_items = tk.Frame(self.card_items, bg=COL_CARD); header_items.pack(fill="x")
        tk.Label(header_items, text="🧾 Lista de alimentos", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(side="left")
        tk.Frame(self.card_items, bg=COL_ACCENT, height=1).pack(fill="x", pady=(4,6))
        style = ttk.Style(self); style.theme_use('clam')
        style.configure('Dark.Treeview', background='#1a1f2e', foreground=COL_TEXT, fieldbackground='#1a1f2e', bordercolor=COL_BORDER, lightcolor=COL_BORDER, darkcolor=COL_BORDER, rowheight=get_scaled_size(24))
        style.map('Dark.Treeview', background=[('selected', '#2a3142')], foreground=[('selected', '#e8fff7')])
        style.configure('Dark.Treeview.Heading', background=COL_CARD, foreground=COL_ACCENT, relief='flat')
        tree_frame = tk.Frame(self.card_items, bg=COL_CARD); tree_frame.pack(fill="both", expand=True)
        cols = ("item","grams","kcal","carbs","protein","fat"); self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse", style='Dark.Treeview')
        for c, title in [("item","Alimento"),("grams","g"),("kcal","kcal"),("carbs","C(g)"),("protein","P(g)"),("fat","G(g)")]:
            self.tree.heading(c, text=title); self.tree.column(c, width=70 if c!="item" else 140, anchor="center")
        self.tree.pack(fill="both", expand=True); self.tree.bind("<<TreeviewSelect>>", self._on_select_item)
        
        self.toast = Toast(self); self.after(80, self._tick)

    def _fmt(self, grams: float) -> str:
        cfg = self.app.get_cfg(); unit = cfg.get("unit","g"); decimals = max(0, int(cfg.get("decimals",0)))
        if unit == "kg": return f"{grams/1000.0:.{decimals}f} kg"
        return f"{grams:.{decimals}f} g" if decimals>0 else f"{round(grams):.0f} g"

    def _tick(self):
        try:
            net_weight = self.app.get_latest_weight()
            is_stable = self.app.get_stability()
            self.weight_lbl.config(text=self._fmt(net_weight))
            self.stability_label.config(text=f"● {'Estable' if is_stable else 'Midiendo...'}", fg=COL_SUCCESS if is_stable else COL_WARN)
            reader_ok = self.app.get_reader() and self.app.get_reader()._ser is not None
            self.status_indicator.set_status("active" if reader_ok else "inactive")
            if not reader_ok: self.stability_label.config(text="○ Sin señal", fg=COL_MUTED)
        except Exception: pass
        finally: self.after(80, self._tick)

    def _on_tara(self):
        reader = self.app.get_reader()
        if not reader: self.toast.show("⚠ Sin báscula", 1200, COL_WARN); return
        if reader.tare(): self.toast.show("✓ Tara OK", 1000, COL_SUCCESS)
        else: self.toast.show("❌ Error de tara", 1200, COL_DANGER)
    
    def _on_plato(self): self.toast.show("🍽 Plato (pendiente)", 1000, COL_ACCENT)

    def _on_add_item(self):
        self.app.start_camera_preview()
        modal = tk.Toplevel(self)
        modal.configure(bg=COL_BG); modal.attributes("-topmost", True); modal.overrideredirect(True)
        sw,sh = self.winfo_screenwidth(), self.winfo_screenheight(); w, h = 400, 100
        modal.geometry(f"{w}x{h}+{ (sw-w)//2 }+{ sh - h - 20 }")
        modal.transient(self.winfo_toplevel()); modal.grab_set()
        cont = Card(modal, min_width=w, min_height=h); cont.pack(fill="both", expand=True, padx=10, pady=10)
        row = tk.Frame(cont, bg=COL_CARD); row.pack(fill="both", expand=True)
        row.columnconfigure(0, weight=1); row.columnconfigure(1, weight=1); row.rowconfigure(0, weight=1)
        def on_cancel(): self.app.stop_camera_preview(); modal.destroy()
        def on_capture(): self.app.stop_camera_preview(); modal.destroy(); self.after(100, self._process_capture)
        GhostButton(row, text="Cancelar", command=on_cancel, micro=False).grid(row=0, column=0, sticky="nsew", padx=5)
        BigButton(row, text="📸 Capturar", command=on_capture, micro=False).grid(row=0, column=1, sticky="nsew", padx=5)
    
    def _process_capture(self):
        img_path = self.app.capture_image(); grams = self.app.get_latest_weight()
        data = self.app.request_nutrition(image_path=img_path, grams=grams)
        self._add_item_from_data(data)

    def _add_item_from_data(self, data: dict):
        item = {k: data.get(k) for k in ["name", "grams", "kcal", "carbs", "protein", "fat", "image_path"]}
        item["id"] = self._next_id; self._next_id += 1; self.items.append(item)
        self.tree.insert("", "end", iid=str(item["id"]), values=(item.get("name","?"), f"{item.get('grams',0):.0f}", f"{item.get('kcal',0):.0f}", f"{item.get('carbs',0):.1f}", f"{item.get('protein',0):.1f}", f"{item.get('fat',0):.1f}"))
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
        if not sel: self.toast.show("Selecciona un alimento para borrar", 1100, COL_MUTED); return
        iid = int(sel[0]); self.tree.delete(sel[0])
        self.items = [x for x in self.items if x["id"]!=iid]
        self._selection_id = None; self._show_totals()

    def _on_reset_session(self):
        self.tree.delete(*self.tree.get_children()); self.items.clear()
        self._selection_id = None; self._show_totals(); self.toast.show("🔄 Sesión Reiniciada", 900, COL_SUCCESS)

    def _show_totals(self):
        self.lbl_nut_title.config(text="🥗 Totales")
        totals = {"grams":0.0,"kcal":0.0,"carbs":0.0,"protein":0.0,"fat":0.0}
        for it in self.items:
            for k in totals: totals[k] += it.get(k, 0.0)
        self._render_nut(totals)

    def _show_item(self, item): self.lbl_nut_title.config(text=f"🥗 {item.get('name', '?')}"); self._render_nut(item)

    def _render_nut(self, data):
        def fmt(v, d=1): return f"{float(v):.{d}f}" if isinstance(v, (int, float)) else "—"
        for k, v_label in self._nut_labels.items():
            decimals = 0 if k in ["grams", "kcal"] else 1
            v_label.config(text=fmt(data.get(k, 0), decimals))

class SettingsMenuScreen(BaseScreen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=(get_scaled_size(10),0))
        t = tk.Frame(header, bg=COL_BG); t.pack(side="left", padx=get_scaled_size(14))
        tk.Label(t, text="⚙", bg=COL_BG, fg=COL_ACCENT, font=("DejaVu Sans", int(FS_TITLE*1.4))).pack(side="left", padx=(0,get_scaled_size(8)))
        tk.Label(t, text="Ajustes", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left")
        actions_right = tk.Frame(header, bg=COL_BG); actions_right.pack(side="right", padx=get_scaled_size(14))
        GhostButton(actions_right, text="Inicio", command=lambda: self.app.show_screen('home'), micro=True).pack()
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
    def _soon(self): self.toast.show("Próximamente…", 900, COL_MUTED)

class CalibScreen(BaseScreen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=(get_scaled_size(10),0))
        t = tk.Frame(header, bg=COL_BG); t.pack(side="left", padx=get_scaled_size(14))
        tk.Label(t, text="⚖", bg=COL_BG, fg=COL_ACCENT, font=("DejaVu Sans", int(FS_TITLE*1.4))).pack(side="left", padx=(0,get_scaled_size(8)))
        tk.Label(t, text="Calibración", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left")
        actions_right = tk.Frame(header, bg=COL_BG); actions_right.pack(side="right", padx=get_scaled_size(14))
        GhostButton(actions_right, text="Inicio", command=lambda: self.app.show_screen('home'), micro=True).pack(side="right", padx=(get_scaled_size(6), 0))
        GhostButton(actions_right, text="Atrás", command=lambda:self.app.show_screen('settings_menu'), micro=True).pack(side="right")
        tk.Frame(self, bg=COL_ACCENT, height=2).pack(fill="x", padx=get_scaled_size(14), pady=(get_scaled_size(6),0))
        body = Card(self, min_height=360); body.pack(fill="both", expand=True, padx=get_scaled_size(14), pady=get_scaled_size(10))
        rowp = tk.Frame(body, bg=COL_CARD); rowp.pack(fill="x", pady=6, padx=6)
        tk.Label(rowp, text="Peso patrón (gramos):", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT)).pack(side="left")
        self.var_patron = tk.StringVar(value="")
        ent = tk.Entry(rowp, textvariable=self.var_patron, bg="#1a1f2e", fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT), relief="flat", highlightbackground=COL_BORDER, highlightthickness=1, width=12)
        ent.pack(side="left", padx=8); bind_numeric_popup(ent, allow_dot=True)
        BigButton(body, text="💾 Calibrar con este peso", command=self._calc_save, micro=True).pack(anchor="e", pady=4, padx=6)
        self.toast = Toast(self)

    def _parse_patron(self):
        s = (self.var_patron.get() or "").strip().replace(",", ".")
        try:
            w = float(s)
            return w if w > 0 else None
        except Exception: return None

    def _calc_save(self):
        reader = self.app.get_reader()
        if not reader:
            self.toast.show("⚠ Sin báscula conectada", 1200, COL_WARN)
            return
        Wg = self._parse_patron()
        if Wg is None:
            self.toast.show("⚠ Peso patrón inválido", 1200, COL_WARN)
            return
        if reader.calibrate(Wg):
            self.toast.show("✅ Comando de calibración enviado", 1500, COL_SUCCESS)
            self.after(800, lambda:self.app.show_screen('settings_menu'))
        else:
            self.toast.show("❌ Error al enviar comando", 1500, COL_DANGER)

class WifiScreen(BaseScreen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=(get_scaled_size(10),0))
        t = tk.Frame(header, bg=COL_BG); t.pack(side="left", padx=get_scaled_size(14))
        tk.Label(t, text="📶", bg=COL_BG, fg=COL_ACCENT, font=("DejaVu Sans", int(FS_TITLE*1.4))).pack(side="left", padx=(0,get_scaled_size(8)))
        tk.Label(t, text="Conexión Wi-Fi", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left")
        actions_right = tk.Frame(header, bg=COL_BG); actions_right.pack(side="right", padx=get_scaled_size(14))
        GhostButton(actions_right, text="Inicio", command=lambda: self.app.show_screen('home'), micro=True).pack(side="right", padx=(get_scaled_size(6), 0))
        GhostButton(actions_right, text="Atrás", command=lambda:self.app.show_screen('settings_menu'), micro=True).pack(side="right")
        tk.Frame(self, bg=COL_ACCENT, height=2).pack(fill="x", padx=get_scaled_size(14), pady=(get_scaled_size(6),0))
        body = Card(self, min_height=340); body.pack(fill="both", expand=True, padx=get_scaled_size(14), pady=get_scaled_size(10))
        form = tk.Frame(body, bg=COL_CARD); form.pack(fill="x", padx=6, pady=6)
        row_ssid = tk.Frame(form, bg=COL_CARD); row_ssid.pack(fill="x", pady=6)
        tk.Label(row_ssid, text="SSID:", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT, "bold"), width=16, anchor="w").pack(side="left")
        self._ssid_var = tk.StringVar(value=self.app.get_cfg().get("wifi_ssid",""))
        self._ssid_entry = tk.Entry(row_ssid, textvariable=self._ssid_var, bg="#1a1f2e", fg=COL_TEXT, insertbackground=COL_ACCENT, font=("DejaVu Sans", FS_TEXT), relief="flat", highlightbackground=COL_BORDER, highlightthickness=1)
        self._ssid_entry.pack(side="left", fill="x", expand=True); bind_text_popup(self._ssid_entry)
        GhostButton(row_ssid, text="🔍 Buscar", command=self._scan_networks, micro=True).pack(side="left", padx=6)
        row_psk = tk.Frame(form, bg=COL_CARD); row_psk.pack(fill="x", pady=6)
        tk.Label(row_psk, text="Contraseña:", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT, "bold"), width=16, anchor="w").pack(side="left")
        self._psk_var = tk.StringVar(value=self.app.get_cfg().get("wifi_psk",""))
        self._psk_entry = tk.Entry(row_psk, textvariable=self._psk_var, show="•", bg="#1a1f2e", fg=COL_TEXT, insertbackground=COL_ACCENT, font=("DejaVu Sans", FS_TEXT), relief="flat", highlightbackground=COL_BORDER, highlightthickness=1)
        self._psk_entry.pack(side="left", fill="x", expand=True); bind_text_popup(self._psk_entry)
        GhostButton(row_psk, text="👁", command=self._toggle_psk, micro=True).pack(side="left", padx=6)
        actions = tk.Frame(body, bg=COL_CARD); actions.pack(fill="x", pady=8)
        BigButton(actions, text="Guardar", command=self._save, micro=True).pack(side="left")
        self.toast = Toast(self)
    def _toggle_psk(self): self._psk_entry.config(show="" if self._psk_entry.cget("show")=="•" else "•")
    def _save(self):
        cfg = self.app.get_cfg(); cfg["wifi_ssid"] = self._ssid_var.get().strip(); cfg["wifi_psk"] = self._psk_var.get().strip()
        self.app.save_cfg(); self.toast.show("✓ Credenciales guardadas", 1200, COL_SUCCESS)
    def _scan_networks(self): self.toast.show("Búsqueda de redes no implementada", 1200, COL_MUTED)

class ApiKeyScreen(BaseScreen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=(get_scaled_size(10),0))
        t = tk.Frame(header, bg=COL_BG); t.pack(side="left", padx=get_scaled_size(14))
        tk.Label(t, text="🗝", bg=COL_BG, fg=COL_ACCENT, font=("DejaVu Sans", int(FS_TITLE*1.4))).pack(side="left", padx=(0,get_scaled_size(8)))
        tk.Label(t, text="API Key ChatGPT", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left")
        actions_right = tk.Frame(header, bg=COL_BG); actions_right.pack(side="right", padx=get_scaled_size(14))
        GhostButton(actions_right, text="Inicio", command=lambda: self.app.show_screen('home'), micro=True).pack(side="right", padx=(get_scaled_size(6), 0))
        GhostButton(actions_right, text="Atrás", command=lambda:self.app.show_screen('settings_menu'), micro=True).pack(side="right")
        tk.Frame(self, bg=COL_ACCENT, height=2).pack(fill="x", padx=get_scaled_size(14), pady=(get_scaled_size(6),0))
        body = Card(self, min_height=260); body.pack(fill="both", expand=True, padx=get_scaled_size(14), pady=get_scaled_size(10))
        row = tk.Frame(body, bg=COL_CARD); row.pack(fill="x", pady=8)
        tk.Label(row, text="API Key:", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT, "bold"), width=16, anchor="w").pack(side="left")
        self._key_var = tk.StringVar(value=self.app.get_cfg().get("openai_api_key",""))
        self._key_entry = tk.Entry(row, textvariable=self._key_var, show="•", bg="#1a1f2e", fg=COL_TEXT, insertbackground=COL_ACCENT, font=("DejaVu Sans", FS_TEXT), relief="flat", highlightbackground=COL_BORDER, highlightthickness=1)
        self._key_entry.pack(side="left", fill="x", expand=True); bind_text_popup(self._key_entry)
        GhostButton(row, text="👁", command=self._toggle_key, micro=True).pack(side="left", padx=6)
        actions = tk.Frame(body, bg=COL_CARD); actions.pack(fill="x", pady=6)
        BigButton(actions, text="Guardar", command=self._save, micro=True).pack(side="left")
        BigButton(actions, text="Probar", command=self._test_local, micro=True).pack(side="left", padx=10)
        tip = tk.Label(body, text="Consejo: pega tu clave completa. La prueba local valida el formato.", bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT), wraplength=820, justify="left")
        tip.pack(fill="x", pady=(10,0)); self.toast = Toast(self)

    def _toggle_key(self): self._key_entry.config(show="" if self._key_entry.cget("show")=="•" else "•")
    def _save(self):
        k = self._key_var.get().strip(); self.app.get_cfg()["openai_api_key"] = k; self.app.save_cfg()
        self.toast.show("✓ API Key guardada", 1200, COL_SUCCESS)
    def _test_local(self):
        k = self._key_var.get().strip(); ok = len(k) >= 20 and ("sk-" in k or k.startswith("sk-"))
        self.toast.show("✓ Formato parece correcto" if ok else "⚠ Clave sospechosa", 1100 if ok else 1300, COL_SUCCESS if ok else COL_WARN)
