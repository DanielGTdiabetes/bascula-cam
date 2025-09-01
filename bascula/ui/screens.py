# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk
from bascula.ui.widgets import *

SHOW_SCROLLBAR = False  # Sin barra visible; scroll por gesto

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
        self.items, self._next_id, self._selection_id, self._stable = [], 1, None, False
        self._tick_after = None

        # Layout: más espacio para la lista (2:3)
        self.grid_columnconfigure(0, weight=2, uniform="cols")
        self.grid_columnconfigure(1, weight=3, uniform="cols")
        self.grid_rowconfigure(0, weight=1)

        # ---- Panel Peso (izquierda) ----
        card_weight = Card(self); card_weight.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        header = tk.Frame(card_weight, bg=COL_CARD); header.pack(fill="x")
        tk.Label(header, text="Peso actual", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(side="left", padx=10, pady=4)
        self.status_indicator = StatusIndicator(header, size=14); self.status_indicator.pack(side="left")

        weight_frame = tk.Frame(card_weight, bg="#1a1f2e", highlightbackground=COL_BORDER, highlightthickness=1); weight_frame.pack(expand=True, fill="both", padx=8, pady=8)
        self.weight_lbl = WeightLabel(weight_frame, bg="#1a1f2e"); self.weight_lbl.pack(expand=True, fill="both")
        stf = tk.Frame(weight_frame, bg="#1a1f2e"); stf.pack(side="bottom", pady=4)
        self.stability_label = tk.Label(stf, text="Esperando señal...", bg="#1a1f2e", fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT)); self.stability_label.pack()

        btns = tk.Frame(card_weight, bg=COL_CARD); btns.pack(fill="x", pady=4)
        btn_map = [("Tara", self._on_tara), ("Plato", self._on_plato), ("Añadir", self._on_add_item),
                   ("Ajustes", self.on_open_settings_menu), ("Reiniciar", self._on_reset_session)]
        for i, (txt, cmd) in enumerate(btn_map):
            BigButton(btns, text=txt, command=cmd, micro=True).grid(row=0, column=i, sticky="nsew", padx=3, pady=3)
            btns.grid_columnconfigure(i, weight=1)

        # ---- Panel derecho: Totales + Lista ----
        right = tk.Frame(self, bg=COL_BG); right.grid(row=0, column=1, sticky="nsew", padx=6, pady=10)
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1) # <-- LÍNEA CORREGIDA

        self.card_nutrition = Card(right); self.card_nutrition.grid(row=0, column=0, sticky="new", pady=(0, 10))
        header_nut = tk.Frame(self.card_nutrition, bg=COL_CARD); header_nut.pack(fill="x")
        self.lbl_nut_title = tk.Label(header_nut, text="🥗 Totales", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_CARD_TITLE, "bold")); self.lbl_nut_title.pack(side="left")
        grid = tk.Frame(self.card_nutrition, bg=COL_CARD); grid.pack(fill="x", padx=8, pady=8)
        self._nut_labels = {}
        names = [("Peso (g)","grams"),("Calorías","kcal"),("Carbs (g)","carbs"),("Proteína (g)","protein"),("Grasa (g)","fat")]
        for r, (name, key) in enumerate(names):
            lbl = tk.Label(grid, text=name+":", bg=COL_CARD, fg=COL_TEXT, anchor="w")
            val = tk.Label(grid, text="—", bg=COL_CARD, fg=COL_TEXT, anchor="e")
            lbl.grid(row=r, column=0, sticky="w"); val.grid(row=r, column=1, sticky="e"); grid.grid_columnconfigure(1, weight=1)
            self._nut_labels[key] = val

        self.card_items = Card(right); self.card_items.grid(row=1, column=0, sticky="nsew")
        GhostButton(self.card_items, text="🗑 Borrar seleccionado", command=self._on_delete_selected).pack(side="bottom", fill="x", pady=8)
        header_items = tk.Frame(self.card_items, bg=COL_CARD); header_items.pack(fill="x")
        tk.Label(header_items, text="🧾 Lista de alimentos", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(side="left")

        style = ttk.Style(self); style.theme_use('clam')
        style.configure('Dark.Treeview', background='#1a1f2e', foreground=COL_TEXT, fieldbackground='#1a1f2e', rowheight=27)
        style.map('Dark.Treeview', background=[('selected', '#2a3142')])
        style.configure('Dark.Treeview.Heading', background=COL_CARD, foreground=COL_ACCENT, relief='flat')

        tree_frame = tk.Frame(self.card_items, bg=COL_CARD); tree_frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tree_frame, columns=("item","grams"), show="headings", style='Dark.Treeview', selectmode="browse")
        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Sin barra visible: scroll por gesto (arrastre vertical)
        if SHOW_SCROLLBAR:
            style.configure('Dark.Vertical.TScrollbar', troughcolor='#141a26', background='#2a3142', darkcolor='#2a3142', lightcolor='#2a3142', arrowcolor=COL_TEXT, bordercolor='#141a26')
            vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview, style='Dark.Vertical.TScrollbar')
            self.tree.configure(yscrollcommand=vsb.set)
            vsb.grid(row=0, column=1, sticky="ns")
        else:
            self.tree.configure(yscrollcommand=lambda *args: None)
            self._drag_last_y = None
            self._drag_threshold = 5
            def _on_touch_start(e):
                self._drag_last_y = e.y
            def _on_touch_move(e):
                if self._drag_last_y is None: return
                dy = e.y - self._drag_last_y
                if abs(dy) >= self._drag_threshold:
                    steps = -1 if dy > 0 else 1
                    self.tree.yview_scroll(steps, "units")
                    self._drag_last_y = e.y
                    return "break"
            def _on_touch_end(e):
                self._drag_last_y = None
            self.tree.bind("<ButtonPress-1>", _on_touch_start)
            self.tree.bind("<B1-Motion>", _on_touch_move)
            self.tree.bind("<ButtonRelease-1>", _on_touch_end)

        self.tree.heading("item", text="Alimento"); self.tree.column("item", width=230, anchor="w", stretch=True)
        self.tree.heading("grams", text="Peso (g)"); self.tree.column("grams", width=110, anchor="center", stretch=False)

        self.tree.bind("<<TreeviewSelect>>", self._on_select_item)
        def _on_mousewheel(event):
            if event.delta:
                self.tree.yview_scroll(int(-1*(event.delta/120)), "units")
            return "break"
        self.tree.bind("<MouseWheel>", _on_mousewheel)
        self.tree.bind("<Button-4>", lambda e: self.tree.yview_scroll(-1, "units"))
        self.tree.bind("<Button-5>", lambda e: self.tree.yview_scroll( 1, "units"))

        self.toast = Toast(self)
        
    def on_show(self):
        if not self._tick_after:
            self._tick()

    def on_hide(self):
        if self._tick_after:
            self.after_cancel(self._tick_after)
            self._tick_after = None

    def _tick(self):
        net_weight = self.app.get_latest_weight()
        self.weight_lbl.config(text=f"{net_weight:.{self.app.get_cfg().get('decimals', 0)}f} g")
        is_stable = abs(net_weight - getattr(self, '_last_weight', net_weight)) < 1.5
        if is_stable != self._stable:
            self._stable = is_stable
            self.stability_label.config(text="● Estable" if is_stable else "◉ Midiendo...", fg=COL_SUCCESS if is_stable else COL_WARN)
            self.status_indicator.set_status("active" if is_stable else "warning")
        setattr(self, '_last_weight', net_weight)
        self._tick_after = self.after(100, self._tick)

    def _on_tara(self):
        reader = self.app.get_reader()
        if reader and reader.get_latest() is not None:
            self.app.get_tare().set_tare(reader.get_latest())
            self.toast.show("✓ Tara establecida", 1000)
        else:
            self.toast.show("⚠ Sin lectura de báscula", 1200, COL_WARN)

    def _on_plato(self):
        self.toast.show("Función no implementada", 1000, COL_MUTED)

    def _on_add_item(self):
        modal = tk.Toplevel(self)
        modal.configure(bg=COL_BG); modal.attributes("-topmost", True); modal.overrideredirect(True)
        modal.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0"); modal.grab_set()
        cont = Card(modal); cont.pack(fill="both", expand=True, padx=20, pady=20)
        cont.grid_rowconfigure(1, weight=1); cont.grid_columnconfigure(0, weight=1)
        tk.Label(cont, text="📷 Capturar Alimento", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_TITLE, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 10))
        camera_area = tk.Frame(cont, bg="#000000", highlightbackground=COL_BORDER, highlightthickness=1); camera_area.grid(row=1, column=0, sticky="nsew", pady=5)
        
        stop_preview_func = None
        if hasattr(self.app, "ensure_camera") and self.app.ensure_camera():
            stop_preview_func = self.app.camera.preview_to_tk(camera_area)
        else:
            reason = self.app.camera.explain_status() if getattr(self.app, "camera", None) else "CameraService no cargado."
            tk.Label(camera_area, text=f"Cámara no disponible:\n{reason}", bg="#000000", fg=COL_DANGER, font=("DejaVu Sans", 14), wraplength=350).place(relx=0.5, rely=0.5, anchor="center")

        btn_row = tk.Frame(cont, bg=COL_CARD); btn_row.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        def _cleanup_and_close():
            if stop_preview_func: stop_preview_func()
            modal.destroy()

        def _capturar():
            image_path = None
            try:
                image_path = self.app.capture_image()
                weight = self.app.get_latest_weight()
                data = self.app.request_nutrition(image_path, weight)
                self._add_item_from_data(data)
                self._recalc_totals()
                self.toast.show(f"✓ {data.get('name', 'Alimento')} añadido", 1500, COL_SUCCESS)
            except Exception as e:
                self.toast.show(f"Error: {e}", 2500, COL_DANGER)
            finally:
                if image_path: self.app.delete_image(image_path)
                _cleanup_and_close()

        GhostButton(btn_row, text="✖ Cancelar", command=_cleanup_and_close).pack(side="left", padx=20, pady=10)
        BigButton(btn_row, text="📸 Capturar", command=_capturar).pack(side="right", padx=20, pady=10)

    def _add_item_from_data(self, data):
        data['id'] = self._next_id; self._next_id += 1
        self.items.append(data)
        self.tree.insert("", "end", iid=str(data['id']), values=(data.get('name', '?'), f"{data.get('grams', 0):.0f}"))

    def _on_select_item(self, evt):
        sel = self.tree.selection()
        self._selection_id = sel[0] if sel else None

    def _on_delete_selected(self):
        if self._selection_id:
            try:
                self.tree.delete(self._selection_id)
            except Exception:
                pass
            self.items = [i for i in self.items if str(i['id']) != str(self._selection_id)]
            self._selection_id = None
            self._recalc_totals()
        else:
            self.toast.show("Selecciona un item", 1100, COL_MUTED)

    def _recalc_totals(self):
        grams = sum(i.get('grams', 0) for i in self.items)
        kcal = sum(i.get('kcal', 0) for i in self.items)
        carbs = sum(i.get('carbs', 0) for i in self.items)
        protein = sum(i.get('protein', 0) for i in self.items)
        fat = sum(i.get('fat', 0) for i in self.items)
        vals = {'grams': grams, 'kcal': kcal, 'carbs': carbs, 'protein': protein, 'fat': fat}
        for k, v in vals.items():
            self._nut_labels[k].config(text=f"{v:.0f}" if isinstance(v, (int, float)) else "—")

    def _on_reset_session(self):
        self.tree.delete(*self.tree.get_children())
        self.items.clear(); self._selection_id = None
        self._recalc_totals()
        self.toast.show("🔄 Sesión Reiniciada", 900)

class SettingsMenuScreen(BaseScreen):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="⚙ Ajustes", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="< Volver a Inicio", command=lambda: self.app.show_screen('home'), micro=True).pack(side="right", padx=14)
        container = Card(self); container.pack(fill="both", expand=True, padx=14, pady=10)
        grid = tk.Frame(container, bg=COL_CARD); grid.pack(expand=True)
        for i in range(2): grid.rowconfigure(i, weight=1); grid.columnconfigure(i, weight=1)
        btn_map = [("Calibración", 'calib'), ("Wi‑Fi", 'wifi'), ("API Key", 'apikey'), ("Otros", '_soon')]
        for i, (text, target) in enumerate(btn_map):
            cmd = (lambda t=target: self.app.show_screen(t)) if target != '_soon' else self._soon
            BigButton(grid, text=text, command=cmd, small=True).grid(row=i//2, column=i%2, sticky="nsew", padx=6, pady=6)
        self.toast = Toast(self)
    def _soon(self): self.toast.show("Próximamente…", 900, COL_MUTED)

class CalibScreen(BaseScreen):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="⚖ Calibración", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="< Atrás", command=lambda: self.app.show_screen('settingsmenu'), micro=True).pack(side="right", padx=14)
        body = Card(self); body.pack(fill="both", expand=True, padx=14, pady=10)
        live = tk.Frame(body, bg="#1a1f2e", highlightbackground=COL_BORDER, highlightthickness=1); live.pack(fill="x", pady=6, padx=6)
        tk.Label(live, text="Lectura actual:", bg="#1a1f2e", fg=COL_TEXT).pack(side="left", padx=8, pady=6)
        self.lbl_live = tk.Label(live, text="—", bg="#1a1f2e", fg=COL_TEXT); self.lbl_live.pack(side="left", pady=6)
        caprow = tk.Frame(body, bg=COL_CARD); caprow.pack(fill="x", pady=6)
        self._b0, self._bw = None, None
        GhostButton(caprow, text="📍 Capturar Cero", command=self._cap_cero, micro=True).pack(side="left", padx=4)
        GhostButton(caprow, text="📍 Capturar con Patrón", command=self._cap_con_peso, micro=True).pack(side="left", padx=4)
        rowp = tk.Frame(body, bg=COL_CARD); rowp.pack(fill="x", pady=6, padx=6)
        tk.Label(rowp, text="Peso patrón (gramos):", bg=COL_CARD, fg=COL_TEXT).pack(side="left")
        self.var_patron = tk.StringVar()
        ent = tk.Entry(rowp, textvariable=self.var_patron, bg="#1a1f2e", fg=COL_TEXT, width=12); ent.pack(side="left", padx=8)
        bind_numeric_popup(ent)
        BigButton(body, text="💾 Guardar Calibración", command=self._calc_save, micro=True).pack(anchor="e", pady=4, padx=6)
        self.toast = Toast(self); self.after(120, self._tick_live)
    def _tick_live(self):
        r = self.app.get_reader()
        v = r.get_latest() if r else None
        if v is not None: self.lbl_live.config(text=f"{v:.3f}")
        self.after(120, self._tick_live)
    def _promedio(self, n=15):
        r = self.app.get_reader(); vals = [r.get_latest() for _ in range(n) if r and r.get_latest() is not None]; return sum(vals)/len(vals) if vals else None
    def _cap_cero(self):
        v = self._promedio(); self._b0 = v
        if v is not None: self.toast.show(f"✓ Cero: {v:.2f}", 1200)
    def _cap_con_peso(self):
        v = self._promedio(); self._bw = v
        if v is not None: self.toast.show(f"✓ Patrón: {v:.2f}", 1200)
    def _calc_save(self):
        try:
            w = float(self.var_patron.get()); assert w > 0 and self._b0 is not None and self._bw is not None
            factor = w / (self._bw - self._b0); self.app.get_tare().update_calib(factor); self.app.get_cfg()["calib_factor"] = factor
            self.app.save_cfg(); self.toast.show("✅ Calibración guardada", 1500, COL_SUCCESS)
            self.after(1600, lambda: self.app.show_screen('settingsmenu'))
        except: self.toast.show("Error en datos", 1500, COL_DANGER)

class WifiScreen(BaseScreen):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="📶 Conexión Wi‑Fi", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="< Atrás", command=lambda: self.app.show_screen('settingsmenu'), micro=True).pack(side="right", padx=14)
        body = Card(self); body.pack(fill="both", expand=True, padx=14, pady=10)
        tk.Label(body, text="Usa la mini‑web: http://<IP>:8080 para configurar Wi‑Fi y API key.", bg=COL_CARD, fg=COL_TEXT).pack(anchor="w", padx=10, pady=6)

class ApiKeyScreen(BaseScreen):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="🗝 API Key", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="< Atrás", command=lambda: self.app.show_screen('settingsmenu'), micro=True).pack(side="right", padx=14)
        body = Card(self); body.pack(fill="both", expand=True, padx=14, pady=10)
        tk.Label(body, text="Guárdala desde la mini‑web: http://<IP>:8080", bg=COL_CARD, fg=COL_TEXT).pack(anchor="w", padx=10, pady=6)
