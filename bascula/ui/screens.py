# -*- coding: utf-8 -*-
# bascula/ui/screens.py
# VERSIÓN FINAL: UI avanzada con cámara real y navegación corregida.

import tkinter as tk
from tkinter import ttk

from bascula.ui.widgets import (
    Card, BigButton, GhostButton, WeightLabel, Toast,
    StatusIndicator, KeypadPopup, bind_numeric_popup, bind_text_popup,
    COL_BG, COL_CARD, COL_TEXT, COL_MUTED, COL_SUCCESS, COL_WARN, COL_DANGER, COL_ACCENT, COL_BORDER,
    FS_TEXT, FS_TITLE, FS_CARD_TITLE, get_scaled_size
)

class BaseScreen(tk.Frame):
    """Clase base para todas las pantallas de la aplicación."""
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COL_BG, **kwargs)
        self.app = app
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
    def on_show(self): pass
    def on_hide(self): pass

class HomeScreen(BaseScreen):
    """Pantalla principal con visualización de peso, lista de alimentos y controles."""
    def __init__(self, parent, app, on_open_settings_menu):
        super().__init__(parent, app)
        self.on_open_settings_menu = on_open_settings_menu
        self.items = []; self._next_id = 1; self._selection_id = None; self._revert_timer = None
        self._stable = False
        
        self.grid_columnconfigure(0, weight=3, uniform="cols")
        self.grid_columnconfigure(1, weight=2, uniform="cols")
        self.grid_rowconfigure(0, weight=1)

        # --- Columna Izquierda: Peso ---
        card_weight = Card(self); card_weight.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        header_weight = tk.Frame(card_weight, bg=COL_CARD); header_weight.pack(fill="x")
        tk.Label(header_weight, text="Peso actual", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=10, pady=5)
        self.status_indicator = StatusIndicator(header_weight, size=16); self.status_indicator.pack(side="left")
        
        weight_frame = tk.Frame(card_weight, bg="#1a1f2e", highlightbackground=COL_BORDER, highlightthickness=1)
        weight_frame.pack(expand=True, fill="both", padx=10, pady=10)
        self.weight_lbl = WeightLabel(weight_frame, bg="#1a1f2e"); self.weight_lbl.pack(expand=True, fill="both")
        
        stf = tk.Frame(weight_frame, bg="#1a1f2e"); stf.pack(side="bottom", pady=5)
        self.stability_label = tk.Label(stf, text="Esperando señal...", bg="#1a1f2e", fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT))
        self.stability_label.pack()

        btns = tk.Frame(card_weight, bg=COL_CARD); btns.pack(fill="x", pady=5)
        for c in range(5): btns.columnconfigure(c, weight=1)
        btn_map = [("Tara", self._on_tara), ("Plato", self._on_plato), ("Añadir", self._on_add_item), ("Ajustes", self.on_open_settings_menu), ("Reiniciar", self._on_reset_session)]
        for i, (txt, cmd) in enumerate(btn_map):
            BigButton(btns, text=txt, command=cmd, micro=True).grid(row=0, column=i, sticky="ew", padx=4, pady=4)

        # --- Columna Derecha: UI sin cambios ---
        right = tk.Frame(self, bg=COL_BG); right.grid(row=0, column=1, sticky="nsew", padx=(0,10), pady=10)
        right.grid_rowconfigure(1, weight=1)
        self.card_nutrition = Card(right); self.card_nutrition.grid(row=0, column=0, sticky="new", pady=(0, 12))
        header_nut = tk.Frame(self.card_nutrition, bg=COL_CARD); header_nut.pack(fill="x")
        self.lbl_nut_title = tk.Label(header_nut, text="🥗 Totales", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_CARD_TITLE, "bold")); self.lbl_nut_title.pack(side="left")
        tk.Frame(self.card_nutrition, bg=COL_ACCENT, height=1).pack(fill="x", pady=4)
        grid = tk.Frame(self.card_nutrition, bg="#1a1f2e", highlightbackground=COL_BORDER, highlightthickness=1); grid.pack(fill="x", padx=8, pady=8)
        self._nut_labels = {}
        names = [("Peso (g)","grams"),("Calorías (kcal)","kcal"),("Carbs (g)","carbs"),("Proteínas (g)","protein"),("Grasas (g)","fat")]
        for r, (name, key) in enumerate(names):
            lbl = tk.Label(grid, text=name+":", bg="#1a1f2e", fg=COL_TEXT, anchor="w"); val = tk.Label(grid, text="—", bg="#1a1f2e", fg=COL_TEXT, anchor="e")
            lbl.grid(row=r, column=0, sticky="w", padx=10, pady=2); val.grid(row=r, column=1, sticky="e", padx=10, pady=2)
            self._nut_labels[key] = val
        self.card_items = Card(right); self.card_items.grid(row=1, column=0, sticky="nsew")
        GhostButton(self.card_items, text="🗑 Borrar seleccionado", command=self._on_delete_selected).pack(side="bottom", fill="x", pady=10)
        header_items = tk.Frame(self.card_items, bg=COL_CARD); header_items.pack(fill="x")
        tk.Label(header_items, text="🧾 Lista de alimentos", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(side="left")
        tk.Frame(self.card_items, bg=COL_ACCENT, height=1).pack(fill="x", pady=4)
        style = ttk.Style(self); style.theme_use('clam')
        style.configure('Dark.Treeview', background='#1a1f2e', foreground=COL_TEXT, fieldbackground='#1a1f2e', bordercolor=COL_BORDER, rowheight=25)
        style.map('Dark.Treeview', background=[('selected', '#2a3142')], foreground=[('selected', '#e8fff7')])
        style.configure('Dark.Treeview.Heading', background=COL_CARD, foreground=COL_ACCENT, relief='flat', font=("DejaVu Sans", 10, "bold"))
        tree_frame = tk.Frame(self.card_items, bg=COL_CARD); tree_frame.pack(fill="both", expand=True)
        cols = ("item","grams","kcal","carbs","protein","fat"); self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", style='Dark.Treeview')
        for c, title, width in [("item","Alimento",140), ("grams","g",60), ("kcal","kcal",60), ("carbs","C",60), ("protein","P",60), ("fat","G",60)]:
            self.tree.heading(c, text=title); self.tree.column(c, width=width, anchor="center")
        self.tree.pack(fill="both", expand=True); self.tree.bind("<<TreeviewSelect>>", self._on_select_item)
        self.toast = Toast(self); self.after(100, self._tick)

    def _fmt(self, grams: float) -> str:
        decimals = int(self.app.get_cfg().get("decimals", 0))
        return f"{grams:.{decimals}f} g"

    def _tick(self):
        """Función de bucle principal para actualizar el peso en la UI."""
        try:
            # Llama a la función centralizada en app.py
            net_weight = self.app.get_latest_weight()
            self.weight_lbl.config(text=self._fmt(net_weight))

            is_stable_now = abs(net_weight - getattr(self, '_last_stable_weight', net_weight)) < 1.5
            if is_stable_now != self._stable:
                self._stable = is_stable_now
                if self._stable:
                    self.stability_label.config(text="● Estable", fg=COL_SUCCESS)
                    self.status_indicator.set_status("active")
                else:
                    self.stability_label.config(text="◉ Midiendo...", fg=COL_WARN)
                    self.status_indicator.set_status("warning")
            setattr(self, '_last_stable_weight', net_weight)
        except Exception:
            self.status_indicator.set_status("inactive")
        finally:
            self.after(100, self._tick)

    def _on_tara(self):
        raw_val = self.app.get_reader().get_latest() if self.app.get_reader() else None
        if raw_val is None:
            self.toast.show("⚠ Sin lectura de la báscula", 1200, COL_WARN)
            return
        self.app.get_tare().set_tare(raw_val)
        self.toast.show("✓ Tara establecida", 1000, COL_SUCCESS)

    def _on_plato(self): self.toast.show("Función de Plato (pendiente)", 1000, COL_MUTED)

    def _on_add_item(self):
        """Lanza la ventana modal con la VISTA PREVIA DE LA CÁMARA REAL."""
        modal = tk.Toplevel(self); modal.configure(bg=COL_BG); modal.attributes("-topmost", True)
        modal.overrideredirect(True); modal.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        modal.transient(self.winfo_toplevel()); modal.grab_set()

        cont = Card(modal, min_width=800, min_height=600); cont.pack(fill="both", expand=True, padx=20, pady=20)
        tk.Label(cont, text="📷 Capturar Alimento", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(anchor="w")
        camera_area = tk.Frame(cont, bg="#000000", highlightbackground=COL_BORDER, highlightthickness=1); camera_area.pack(fill="both", expand=True, pady=10)

        if self.app.camera and self.app.camera.is_available():
            self.app.camera.start() # Inicia la cámara justo antes de mostrar la preview
            self.app.camera.attach_preview(camera_area)
        else:
            tk.Label(camera_area, text="Cámara no disponible", bg="#000000", fg=COL_DANGER, font=("DejaVu Sans", 14)).pack(expand=True)

        btn_row = tk.Frame(cont, bg=COL_CARD); btn_row.pack(fill="x", side="bottom", pady=(10,0))

        def _cleanup_and_close():
            if self.app.camera: self.app.camera.detach_preview()
            modal.destroy()

        def _capturar():
            try:
                img_path = self.app.capture_image()
                grams = self.app.get_latest_weight()
                data = self.app.request_nutrition(image_path=img_path, grams=grams)
                self._add_item_from_data(data)
            except Exception as e:
                self.toast.show(f"Error al capturar: {e}", 2500, COL_DANGER)
            finally:
                _cleanup_and_close()
        
        GhostButton(btn_row, text="Cancelar", command=_cleanup_and_close).pack(side="left", padx=10, pady=10)
        BigButton(btn_row, text="📸 Capturar", command=_capturar).pack(side="right", padx=10, pady=10)

    def _add_item_from_data(self, data: dict):
        item = {k: data.get(k, 0) for k in ["name", "grams", "kcal", "carbs", "protein", "fat"]}; item["id"] = self._next_id; self._next_id += 1; self.items.append(item)
        values = (f"{item['name']}", f"{item['grams']:.0f}", f"{item['kcal']:.0f}", f"{item['carbs']:.1f}", f"{item['protein']:.1f}", f"{item['fat']:.1f}")
        self.tree.insert("", "end", iid=str(item["id"]), values=values); self._show_item(item)
        if self._revert_timer: self.after_cancel(self._revert_timer);
        self._revert_timer = self.after(3000, self._show_totals)

    def _on_select_item(self, _evt=None):
        sel = self.tree.selection();
        if not sel: self._selection_id = None; self._show_totals(); return
        item = next((x for x in self.items if x["id"] == int(sel[0])), None)
        if item: self._selection_id = item["id"]; self._show_item(item)

    def _on_delete_selected(self):
        if not self._selection_id: self.toast.show("Selecciona un alimento para borrar", 1100, COL_MUTED); return
        self.tree.delete(str(self._selection_id)); self.items = [x for x in self.items if x["id"] != self._selection_id]
        self._selection_id = None; self._show_totals()

    def _on_reset_session(self):
        self.tree.delete(*self.tree.get_children()); self.items.clear(); self._selection_id = None; self._show_totals()
        self.toast.show("🔄 Sesión Reiniciada", 900, COL_SUCCESS)

    def _show_totals(self):
        self.lbl_nut_title.config(text="🥗 Totales"); totals = {k: sum(float(it.get(k,0)) for it in self.items) for k in self._nut_labels.keys()}; self._render_nut(totals)

    def _show_item(self, item): self.lbl_nut_title.config(text=f"🥗 {item.get('name', 'Detalle')}"); self._render_nut(item)

    def _render_nut(self, data):
        for k, lbl in self._nut_labels.items(): lbl.config(text=f"{data.get(k, 0):.{1 if k not in ['grams','kcal'] else 0}f}")

class SettingsMenuScreen(BaseScreen):
    # El resto del archivo no necesita cambios, solo se corrigen las llamadas a show_screen
    def __init__(self, parent, app):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="⚙ Ajustes", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="Inicio", command=lambda: self.app.show_screen('home'), micro=True).pack(side="right", padx=14)
        container = Card(self); container.pack(fill="both", expand=True, padx=14, pady=10)
        grid = tk.Frame(container, bg=COL_CARD); grid.pack(expand=True)
        for i in range(2): grid.grid_rowconfigure(i, weight=1); grid.grid_columnconfigure(i, weight=1)
        btn_map = [("Calibración", 'calib'), ("Wi-Fi", 'wifi'), ("API Key", 'apikey'), ("Otros", '_soon')]
        for i, (text, target) in enumerate(btn_map):
            cmd = (lambda t=target: self.app.show_screen(t)) if target != '_soon' else self._soon
            BigButton(grid, text=text, command=cmd, small=True).grid(row=i//2, column=i%2, sticky="nsew", padx=6, pady=6)
        self.toast = Toast(self)
    def _soon(self): self.toast.show("Próximamente…", 900, COL_MUTED)

class CalibScreen(BaseScreen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="⚖ Calibración", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=14)
        actions_right = tk.Frame(header, bg=COL_BG); actions_right.pack(side="right", padx=14)
        GhostButton(actions_right, text="Atrás", command=lambda:self.app.show_screen('settingsmenu'), micro=True).pack()
        body = Card(self); body.pack(fill="both", expand=True, padx=14, pady=10)
        # ... (resto del código sin cambios funcionales)
        live = tk.Frame(body, bg="#1a1f2e", highlightbackground=COL_BORDER, highlightthickness=1); live.pack(fill="x", pady=6, padx=6)
        tk.Label(live, text="Lectura actual:", bg="#1a1f2e", fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT, "bold")).pack(side="left", padx=8, pady=6)
        self.lbl_live = tk.Label(live, text="—", bg="#1a1f2e", fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT)); self.lbl_live.pack(side="left", pady=6)
        caprow = tk.Frame(body, bg=COL_CARD); caprow.pack(fill="x", pady=6)
        self._b0 = None; self._bw = None
        GhostButton(caprow, text="📍 Capturar Cero", command=self._cap_cero, micro=True).pack(side="left", padx=4)
        GhostButton(caprow, text="📍 Capturar con Patrón", command=self._cap_con_peso, micro=True).pack(side="left", padx=4)
        rowp = tk.Frame(body, bg=COL_CARD); rowp.pack(fill="x", pady=6, padx=6)
        tk.Label(rowp, text="Peso patrón (gramos):", bg=COL_CARD, fg=COL_TEXT).pack(side="left")
        self.var_patron = tk.StringVar(); ent = tk.Entry(rowp, textvariable=self.var_patron, bg="#1a1f2e", fg=COL_TEXT, width=12); ent.pack(side="left", padx=8); bind_numeric_popup(ent)
        BigButton(body, text="💾 Guardar", command=self._calc_save, micro=True).pack(anchor="e", pady=4, padx=6)
        self.toast = Toast(self); self.after(120, self._tick_live)
    def _tick_live(self):
        v = self.app.get_reader().get_latest() if self.app.get_reader() else None
        if v is not None: self.lbl_live.config(text=f"{v:.3f}")
        self.after(120, self._tick_live)
    def _promedio(self, n=15):
        r = self.app.get_reader(); vals = [r.get_latest() for _ in range(n) if r and r.get_latest() is not None]
        return sum(vals)/len(vals) if vals else None
    def _cap_cero(self): v=self._promedio(); self._b0=v; self.toast.show(f"✓ Cero: {v:.2f}", 1200)
    def _cap_con_peso(self): v=self._promedio(); self._bw=v; self.toast.show(f"✓ Patrón: {v:.2f}", 1200)
    def _calc_save(self):
        try: w = float(self.var_patron.get()); assert w > 0 and self._b0 is not None and self._bw is not None and abs(self._bw-self._b0)>1e-6
        except: self.toast.show("Error en datos de calibración", 1500, COL_DANGER); return
        factor = w / (self._bw-self._b0); self.app.get_tare().update_calib(factor); self.app.get_cfg()["calib_factor"]=factor; self.app.save_cfg()
        self.toast.show("✅ Calibración guardada", 1500, COL_SUCCESS); self.after(1600, lambda: self.app.show_screen('settingsmenu'))

class WifiScreen(BaseScreen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="📶 Conexión Wi-Fi", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="Atrás", command=lambda: self.app.show_screen('settingsmenu'), micro=True).pack(side="right", padx=14)
        body = Card(self); body.pack(fill="both", expand=True, padx=14, pady=10)
        form = tk.Frame(body, bg=COL_CARD); form.pack(fill="x", padx=6, pady=6)
        row_ssid = tk.Frame(form, bg=COL_CARD); row_ssid.pack(fill="x", pady=6)
        tk.Label(row_ssid, text="SSID:", bg=COL_CARD, fg=COL_TEXT, width=12, anchor="w").pack(side="left")
        self._ssid_var = tk.StringVar(value=self.app.get_cfg().get("wifi_ssid",""))
        self._ssid_entry = tk.Entry(row_ssid, textvariable=self._ssid_var, bg="#1a1f2e", fg=COL_TEXT)
        self._ssid_entry.pack(side="left", fill="x", expand=True); bind_text_popup(self._ssid_entry)
        row_psk = tk.Frame(form, bg=COL_CARD); row_psk.pack(fill="x", pady=6)
        tk.Label(row_psk, text="Contraseña:", bg=COL_CARD, fg=COL_TEXT, width=12, anchor="w").pack(side="left")
        self._psk_var = tk.StringVar(value=self.app.get_cfg().get("wifi_psk",""))
        self._psk_entry = tk.Entry(row_psk, textvariable=self._psk_var, show="•", bg="#1a1f2e", fg=COL_TEXT)
        self._psk_entry.pack(side="left", fill="x", expand=True); bind_text_popup(self._psk_entry)
        BigButton(body, text="Guardar", command=self._save, micro=True).pack(pady=10)
        self.toast = Toast(self)
    def _save(self): self.app.get_cfg()["wifi_ssid"]=self._ssid_var.get(); self.app.get_cfg()["wifi_psk"]=self._psk_var.get(); self.app.save_cfg(); self.toast.show("✓ Guardado", 1200)

class ApiKeyScreen(BaseScreen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="🗝 API Key ChatGPT", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="Atrás", command=lambda: self.app.show_screen('settingsmenu'), micro=True).pack(side="right", padx=14)
        body = Card(self); body.pack(fill="both", expand=True, padx=14, pady=10)
        row = tk.Frame(body, bg=COL_CARD); row.pack(fill="x", pady=8)
        tk.Label(row, text="API Key:", bg=COL_CARD, fg=COL_TEXT, width=12, anchor="w").pack(side="left")
        self._key_var = tk.StringVar(value=self.app.get_cfg().get("openai_api_key",""))
        self._key_entry = tk.Entry(row, textvariable=self._key_var, show="•", bg="#1a1f2e", fg=COL_TEXT)
        self._key_entry.pack(side="left", fill="x", expand=True); bind_text_popup(self._key_entry)
        BigButton(body, text="Guardar", command=self._save, micro=True).pack(pady=10)
        self.toast = Toast(self)
    def _save(self): self.app.get_cfg()["openai_api_key"]=self._key_var.get(); self.app.save_cfg(); self.toast.show("✓ Guardado", 1200)
