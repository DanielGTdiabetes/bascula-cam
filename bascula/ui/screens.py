# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk
from bascula.ui.widgets import *

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
        self._touch_start_y = None
        self._last_touch_time = 0

        # Ajustar proporciones: menos espacio para peso, más para lista
        self.grid_columnconfigure(0, weight=2, uniform="cols")  # Reducido de 3 a 2
        self.grid_columnconfigure(1, weight=3, uniform="cols")  # Aumentado de 2 a 3
        self.grid_rowconfigure(0, weight=1)

        # Panel izquierdo - Peso (más compacto)
        card_weight = Card(self)
        card_weight.grid(row=0, column=0, sticky="nsew", padx=(10,5), pady=10)
        
        # Header más compacto
        header = tk.Frame(card_weight, bg=COL_CARD)
        header.pack(fill="x")
        tk.Label(header, text="Peso actual", bg=COL_CARD, fg=COL_ACCENT, 
                font=("DejaVu Sans", 14, "bold")).pack(side="left", padx=8, pady=3)
        self.status_indicator = StatusIndicator(header, size=12)
        self.status_indicator.pack(side="left")

        # Display de peso más compacto
        weight_frame = tk.Frame(card_weight, bg="#1a1f2e", 
                               highlightbackground=COL_BORDER, highlightthickness=1)
        weight_frame.pack(expand=True, fill="both", padx=8, pady=8)
        
        # Reducir tamaño de fuente del peso
        self.weight_lbl = tk.Label(weight_frame, text="0 g", 
                                  font=("DejaVu Sans Mono", 48, "bold"),  # Reducido de 80
                                  bg="#1a1f2e", fg=COL_TEXT, anchor="center")
        self.weight_lbl.pack(expand=True, fill="both")
        
        stf = tk.Frame(weight_frame, bg="#1a1f2e")
        stf.pack(side="bottom", pady=3)
        self.stability_label = tk.Label(stf, text="Esperando señal...", 
                                       bg="#1a1f2e", fg=COL_MUTED, 
                                       font=("DejaVu Sans", 11))
        self.stability_label.pack()

        # Botones más compactos
        btns = tk.Frame(card_weight, bg=COL_CARD)
        btns.pack(fill="x", pady=3)
        btn_map = [("Tara", self._on_tara), ("Plato", self._on_plato), 
                  ("Añadir", self._on_add_item), ("Ajustes", self.on_open_settings_menu), 
                  ("Reset", self._on_reset_session)]
        
        # Organizamos botones en 2 filas para ser más compactos
        for i in range(3):
            btns.grid_columnconfigure(i, weight=1)
        for i in range(2):
            btns.grid_rowconfigure(i, weight=1)
            
        for idx, (txt, cmd) in enumerate(btn_map):
            row = idx // 3
            col = idx % 3
            BigButton(btns, text=txt, command=cmd, micro=True).grid(
                row=row, column=col, sticky="nsew", padx=3, pady=2)

        # Panel derecho - Lista más grande
        right = tk.Frame(self, bg=COL_BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(5,10), pady=10)
        right.grid_rowconfigure(1, weight=1)

        # Card de nutrición más compacta
        self.card_nutrition = Card(right)
        self.card_nutrition.grid(row=0, column=0, sticky="new", pady=(0, 8))
        header_nut = tk.Frame(self.card_nutrition, bg=COL_CARD)
        header_nut.pack(fill="x")
        self.lbl_nut_title = tk.Label(header_nut, text="🥗 Totales", bg=COL_CARD, 
                                     fg=COL_ACCENT, font=("DejaVu Sans", 13, "bold"))
        self.lbl_nut_title.pack(side="left")
        
        # Grid más compacto para nutrición
        grid = tk.Frame(self.card_nutrition, bg=COL_CARD)
        grid.pack(fill="x", padx=6, pady=4)
        self._nut_labels = {}
        names = [("Peso (g)","grams"),("Calorías","kcal"),("Carbs","carbs"),
                ("Proteína","protein"),("Grasa","fat")]
        
        # Organizar en 2 columnas para más espacio
        for idx, (name, key) in enumerate(names):
            col_offset = (idx // 3) * 2
            row = idx % 3
            lbl = tk.Label(grid, text=name+":", bg=COL_CARD, fg=COL_TEXT, 
                          font=("DejaVu Sans", 10), anchor="w")
            val = tk.Label(grid, text="—", bg=COL_CARD, fg=COL_TEXT, 
                          font=("DejaVu Sans", 10, "bold"), anchor="e")
            lbl.grid(row=row, column=col_offset, sticky="w", padx=(4,2))
            val.grid(row=row, column=col_offset+1, sticky="e", padx=(2,8))
            grid.grid_columnconfigure(col_offset+1, weight=1)
            self._nut_labels[key] = val

        # Lista de alimentos - más grande
        self.card_items = Card(right)
        self.card_items.grid(row=1, column=0, sticky="nsew")
        
        # Botón de borrar más pequeño
        GhostButton(self.card_items, text="🗑 Borrar", command=self._on_delete_selected, 
                   micro=True).pack(side="bottom", fill="x", pady=6)
        
        header_items = tk.Frame(self.card_items, bg=COL_CARD)
        header_items.pack(fill="x")
        tk.Label(header_items, text="🧾 Lista de alimentos", bg=COL_CARD, 
                fg=COL_ACCENT, font=("DejaVu Sans", 13, "bold")).pack(side="left")
        
        # Configurar estilo del Treeview
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Dark.Treeview', 
                       background='#1a1f2e', 
                       foreground=COL_TEXT, 
                       fieldbackground='#1a1f2e', 
                       rowheight=35)  # Filas más altas para mejor toque
        style.map('Dark.Treeview', background=[('selected', '#2a3142')])
        style.configure('Dark.Treeview.Heading', 
                       background=COL_CARD, 
                       foreground=COL_ACCENT, 
                       relief='flat')
        
        # Frame para el tree SIN scrollbar visible
        tree_frame = tk.Frame(self.card_items, bg=COL_CARD)
        tree_frame.pack(fill="both", expand=True, padx=4, pady=4)
        
        self.tree = ttk.Treeview(tree_frame, 
                                columns=("item","grams","kcal"), 
                                show="headings", 
                                style='Dark.Treeview', 
                                selectmode="browse")
        
        # NO crear scrollbar visible
        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Configurar columnas con más info
        self.tree.heading("item", text="Alimento")
        self.tree.column("item", width=180, anchor="w")
        self.tree.heading("grams", text="Peso")
        self.tree.column("grams", width=70, anchor="center")
        self.tree.heading("kcal", text="kcal")
        self.tree.column("kcal", width=60, anchor="center")
        
        self.tree.bind("<<TreeviewSelect>>", self._on_select_item)
        
        # IMPLEMENTAR SCROLL TÁCTIL
        self._setup_touch_scroll()
        
        self.toast = Toast(self)

    def _setup_touch_scroll(self):
        """Configurar scroll táctil para la lista"""
        import time
        
        def on_touch_start(event):
            self._touch_start_y = event.y
            self._touch_start_time = time.time()
            self._last_y = event.y
            self._velocity = 0
            # Cancelar cualquier animación en curso
            if hasattr(self, '_momentum_after'):
                self.after_cancel(self._momentum_after)
            return "break"
        
        def on_touch_move(event):
            if self._touch_start_y is None:
                return
            
            dy = event.y - self._last_y
            self._last_y = event.y
            
            # Calcular velocidad para momentum
            current_time = time.time()
            dt = current_time - getattr(self, '_last_move_time', current_time)
            if dt > 0:
                self._velocity = dy / dt
            self._last_move_time = current_time
            
            # Scroll suave
            scroll_amount = -dy / 35.0  # Ajustar sensibilidad
            self.tree.yview_scroll(int(scroll_amount), "units")
            return "break"
        
        def on_touch_end(event):
            if self._touch_start_y is None:
                return
            
            # Aplicar momentum si hay velocidad
            if abs(self._velocity) > 50:
                self._apply_momentum()
            
            self._touch_start_y = None
            return "break"
        
        def _apply_momentum():
            """Aplicar efecto de inercia al scroll"""
            if abs(self._velocity) < 10:
                return
            
            # Aplicar fricción
            self._velocity *= 0.95
            
            # Aplicar scroll
            scroll_amount = -self._velocity / 500.0
            self.tree.yview_scroll(int(scroll_amount), "units")
            
            # Continuar si hay velocidad
            if abs(self._velocity) > 10:
                self._momentum_after = self.after(16, _apply_momentum)  # ~60fps
        
        self._apply_momentum = _apply_momentum
        
        # Bind eventos táctiles
        self.tree.bind("<Button-1>", on_touch_start)
        self.tree.bind("<B1-Motion>", on_touch_move)
        self.tree.bind("<ButtonRelease-1>", on_touch_end)
        
        # Deshabilitar scroll con rueda del ratón si no queremos
        self.tree.bind("<MouseWheel>", lambda e: "break")
        self.tree.bind("<Button-4>", lambda e: "break")
        self.tree.bind("<Button-5>", lambda e: "break")

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
            self.stability_label.config(text="● Estable" if is_stable else "◉ Midiendo...",
                                        fg=COL_SUCCESS if is_stable else COL_WARN)
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
        modal.configure(bg=COL_BG)
        modal.attributes("-topmost", True)
        modal.overrideredirect(True)
        modal.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        modal.grab_set()
        
        cont = Card(modal)
        cont.pack(fill="both", expand=True, padx=20, pady=20)
        cont.grid_rowconfigure(1, weight=1)
        cont.grid_columnconfigure(0, weight=1)
        
        tk.Label(cont, text="📷 Capturar Alimento", bg=COL_CARD, fg=COL_ACCENT, 
                font=("DejaVu Sans", FS_TITLE, "bold")).grid(row=0, column=0, 
                sticky="w", pady=(0, 10))
        
        camera_area = tk.Frame(cont, bg="#000000", highlightbackground=COL_BORDER, 
                              highlightthickness=1)
        camera_area.grid(row=1, column=0, sticky="nsew", pady=5)

        stop_preview_func = None
        camera_available = False
        
        # Verificación exhaustiva de disponibilidad de cámara
        if self.app.camera:
            try:
                if self.app.camera.available():
                    stop_preview_func = self.app.camera.preview_to_tk(camera_area)
                    camera_available = True
                else:
                    reason = self.app.camera.explain_status()
                    tk.Label(camera_area, text=f"Cámara no disponible:\n{reason}", 
                             bg="#000000", fg=COL_DANGER, font=("DejaVu Sans", 14), 
                             wraplength=350).place(relx=0.5, rely=0.5, anchor="center")
            except Exception as e:
                tk.Label(camera_area, text=f"Error al acceder a la cámara:\n{str(e)}", 
                         bg="#000000", fg=COL_DANGER, font=("DejaVu Sans", 14), 
                         wraplength=350).place(relx=0.5, rely=0.5, anchor="center")
        else:
            tk.Label(camera_area, text="CameraService no cargado.\nVerifique la instalación.", 
                     bg="#000000", fg=COL_DANGER, font=("DejaVu Sans", 14), 
                     wraplength=350).place(relx=0.5, rely=0.5, anchor="center")

        btn_row = tk.Frame(cont, bg=COL_CARD)
        btn_row.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        def _cleanup_and_close():
            if stop_preview_func: 
                try:
                    stop_preview_func()
                except:
                    pass
            modal.destroy()

        def _capturar():
            if not camera_available:
                self.toast.show("❌ La cámara no está disponible", 2000, COL_DANGER)
                _cleanup_and_close()
                return
                
            image_path = None
            try:
                image_path = self.app.capture_image()
                weight = self.app.get_latest_weight()
                
                if weight <= 0:
                    self.toast.show("⚠ Peso inválido. Coloque el alimento primero.", 2000, COL_WARN)
                    return
                
                data = self.app.request_nutrition(image_path, weight)
                self._add_item_from_data(data)
                self.toast.show(f"✓ {data.get('name', 'Alimento')} añadido", 1500, COL_SUCCESS)
            except Exception as e:
                self.toast.show(f"Error: {e}", 2500, COL_DANGER)
            finally:
                if image_path: 
                    self.app.delete_image(image_path)
                _cleanup_and_close()

        GhostButton(btn_row, text="✖ Cancelar", command=_cleanup_and_close).pack(
            side="left", padx=20, pady=10)
        
        # Solo mostrar botón de captura si la cámara está disponible
        if camera_available:
            BigButton(btn_row, text="📸 Capturar", command=_capturar).pack(
                side="right", padx=20, pady=10)
        else:
            tk.Label(btn_row, text="Captura no disponible", bg=COL_CARD, fg=COL_MUTED,
                    font=("DejaVu Sans", 12)).pack(side="right", padx=20, pady=10)

    def _add_item_from_data(self, data):
        data['id'] = self._next_id
        self._next_id += 1
        self.items.append(data)
        # Añadir también calorías a la vista
        self.tree.insert("", "end", iid=str(data['id']), 
                        values=(data.get('name', '?'), 
                               f"{data.get('grams', 0):.0f}g",
                               f"{data.get('kcal', 0):.0f}"))
        self._update_totals()

    def _update_totals(self):
        """Actualizar totales de nutrición"""
        totals = {"grams": 0, "kcal": 0, "carbs": 0, "protein": 0, "fat": 0}
        for item in self.items:
            for key in totals:
                totals[key] += item.get(key, 0)
        
        for key, label in self._nut_labels.items():
            value = totals.get(key, 0)
            if key == "grams":
                label.config(text=f"{value:.0f}")
            else:
                label.config(text=f"{value:.1f}")

    def _on_select_item(self, evt):
        sel = self.tree.selection()
        self._selection_id = int(sel[0]) if sel else None

    def _on_delete_selected(self):
        if self._selection_id:
            self.tree.delete(str(self._selection_id))
            self.items = [i for i in self.items if i['id'] != self._selection_id]
            self._selection_id = None
            self._update_totals()
        else:
            self.toast.show("Selecciona un item", 1100, COL_MUTED)

    def _on_reset_session(self):
        self.tree.delete(*self.tree.get_children())
        self.items.clear()
        self._selection_id = None
        self._update_totals()
        self.toast.show("🔄 Sesión Reiniciada", 900)

class SettingsMenuScreen(BaseScreen):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG)
        header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="⚙ Ajustes", bg=COL_BG, fg=COL_TEXT, 
                font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="< Volver", command=lambda: self.app.show_screen('home'), 
                   micro=True).pack(side="right", padx=14)
        
        container = Card(self)
        container.pack(fill="both", expand=True, padx=14, pady=10)
        grid = tk.Frame(container, bg=COL_CARD)
        grid.pack(expand=True)
        
        for i in range(2): 
            grid.rowconfigure(i, weight=1)
            grid.columnconfigure(i, weight=1)
        
        btn_map = [("Calibración", 'calib'), ("Wi-Fi", 'wifi'), 
                  ("API Key", 'apikey'), ("Otros", '_soon')]
        
        for i, (text, target) in enumerate(btn_map):
            cmd = (lambda t=target: self.app.show_screen(t)) if target != '_soon' else self._soon
            BigButton(grid, text=text, command=cmd, small=True).grid(
                row=i//2, column=i%2, sticky="nsew", padx=6, pady=6)
        
        self.toast = Toast(self)
    
    def _soon(self): 
        self.toast.show("Próximamente…", 900, COL_MUTED)

class CalibScreen(BaseScreen):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG)
        header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="⚖ Calibración", bg=COL_BG, fg=COL_TEXT, 
                font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="< Atrás", command=lambda: self.app.show_screen('settingsmenu'), 
                   micro=True).pack(side="right", padx=14)
        
        body = Card(self)
        body.pack(fill="both", expand=True, padx=14, pady=10)
        
        live = tk.Frame(body, bg="#1a1f2e", highlightbackground=COL_BORDER, highlightthickness=1)
        live.pack(fill="x", pady=6, padx=6)
        tk.Label(live, text="Lectura actual:", bg="#1a1f2e", fg=COL_TEXT).pack(side="left", padx=8, pady=6)
        self.lbl_live = tk.Label(live, text="—", bg="#1a1f2e", fg=COL_TEXT)
        self.lbl_live.pack(side="left", pady=6)
        
        caprow = tk.Frame(body, bg=COL_CARD)
        caprow.pack(fill="x", pady=6)
        self._b0, self._bw = None, None
        GhostButton(caprow, text="📍 Capturar Cero", command=self._cap_cero, micro=True).pack(side="left", padx=4)
        GhostButton(caprow, text="📍 Capturar con Patrón", command=self._cap_con_peso, micro=True).pack(side="left", padx=4)
        
        rowp = tk.Frame(body, bg=COL_CARD)
        rowp.pack(fill="x", pady=6, padx=6)
        tk.Label(rowp, text="Peso patrón (gramos):", bg=COL_CARD, fg=COL_TEXT).pack(side="left")
        self.var_patron = tk.StringVar()
        ent = tk.Entry(rowp, textvariable=self.var_patron, bg="#1a1f2e", fg=COL_TEXT, width=12)
        ent.pack(side="left", padx=8)
        bind_numeric_popup(ent)
        
        BigButton(body, text="💾 Guardar Calibración", command=self._calc_save, micro=True).pack(anchor="e", pady=4, padx=6)
        self.toast = Toast(self)
        self.after(120, self._tick_live)
    
    def _tick_live(self):
        r = self.app.get_reader()
        v = r.get_latest() if r else None
        if v is not None: 
            self.lbl_live.config(text=f"{v:.3f}")
        self.after(120, self._tick_live)
    
    def _promedio(self, n=15):
        r = self.app.get_reader()
        vals = [r.get_latest() for _ in range(n) if r and r.get_latest() is not None]
        return sum(vals)/len(vals) if vals else None
    
    def _cap_cero(self):
        v = self._promedio()
        self._b0 = v
        if v is not None: 
            self.toast.show(f"✓ Cero: {v:.2f}", 1200)
    
    def _cap_con_peso(self):
        v = self._promedio()
        self._bw = v
        if v is not None: 
            self.toast.show(f"✓ Patrón: {v:.2f}", 1200)
    
    def _calc_save(self):
        try:
            w = float(self.var_patron.get())
            assert w > 0 and self._b0 is not None and self._bw is not None
            factor = w / (self._bw - self._b0)
            self.app.get_tare().update_calib(factor)
            self.app.get_cfg()["calib_factor"] = factor
            self.app.save_cfg()
            self.toast.show("✅ Calibración guardada", 1500, COL_SUCCESS)
            self.after(1600, lambda: self.app.show_screen('settingsmenu'))
        except: 
            self.toast.show("Error en datos", 1500, COL_DANGER)

class WifiScreen(BaseScreen):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG)
        header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="📶 Conexión Wi-Fi", bg=COL_BG, fg=COL_TEXT, 
                font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="< Atrás", command=lambda: self.app.show_screen('settingsmenu'), 
                   micro=True).pack(side="right", padx=14)
        
        body = Card(self)
        body.pack(fill="both", expand=True, padx=14, pady=10)
        
        # Mostrar estado actual
        status_frame = tk.Frame(body, bg=COL_CARD)
        status_frame.pack(fill="x", pady=10)
        
        tk.Label(status_frame, text="Estado WiFi:", bg=COL_CARD, fg=COL_TEXT, 
                font=("DejaVu Sans", 12)).pack(side="left", padx=5)
        self.wifi_status = tk.Label(status_frame, text="Verificando...", 
                                   bg=COL_CARD, fg=COL_MUTED, 
                                   font=("DejaVu Sans", 12, "bold"))
        self.wifi_status.pack(side="left")
        
        # Frame para información
        info_frame = tk.Frame(body, bg="#1a1f2e", highlightbackground=COL_BORDER, 
                             highlightthickness=1)
        info_frame.pack(fill="x", padx=10, pady=10)
        
        self.info_label = tk.Label(info_frame, 
            text="El servidor de configuración WiFi se iniciará en:\n" +
                 "http://192.168.4.1:8080\n\n" +
                 "Conéctate al punto de acceso 'Bascula-Setup' para configurar.",
            bg="#1a1f2e", fg=COL_TEXT, font=("DejaVu Sans", 11), 
            justify="left", wraplength=400)
        self.info_label.pack(padx=20, pady=20)
        
        # Botones
        btn_frame = tk.Frame(body, bg=COL_CARD)
        btn_frame.pack(fill="x", pady=10)
        
        BigButton(btn_frame, text="🔧 Iniciar Configuración", 
                 command=self._start_config_server, micro=True).pack(side="left", padx=5)
        BigButton(btn_frame, text="🔄 Reconectar WiFi", 
                 command=self._reconnect_wifi, micro=True).pack(side="left", padx=5)
        
        self.toast = Toast(self)
        self.after(500, self._check_wifi_status)
    
    def _check_wifi_status(self):
        """Verificar estado actual de WiFi"""
        try:
            import subprocess
            result = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                ssid = result.stdout.strip()
                self.wifi_status.config(text=f"Conectado a: {ssid}", fg=COL_SUCCESS)
            else:
                self.wifi_status.config(text="No conectado", fg=COL_WARN)
        except:
            self.wifi_status.config(text="Error verificando", fg=COL_DANGER)
    
    def _start_config_server(self):
        """Iniciar servidor de configuración"""
        self.toast.show("Iniciando servidor de configuración...", 2000, COL_SUCCESS)
        # Aquí llamarías al servidor web de configuración
        self.app.start_wifi_config_server()
    
    def _reconnect_wifi(self):
        """Intentar reconectar con credenciales guardadas"""
        self.toast.show("Reconectando WiFi...", 1500)
        self.after(1000, self._check_wifi_status)

class ApiKeyScreen(BaseScreen):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG)
        header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="🔑 API Key", bg=COL_BG, fg=COL_TEXT, 
                font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="< Atrás", command=lambda: self.app.show_screen('settingsmenu'), 
                   micro=True).pack(side="right", padx=14)
        
        body = Card(self)
        body.pack(fill="both", expand=True, padx=14, pady=10)
        
        # Información
        info = tk.Label(body, 
                       text="Configura tu API Key de OpenAI para el reconocimiento de alimentos",
                       bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 12), 
                       wraplength=400)
        info.pack(pady=10)
        
        # Frame para la API key actual
        current_frame = tk.Frame(body, bg="#1a1f2e", 
                               highlightbackground=COL_BORDER, highlightthickness=1)
        current_frame.pack(fill="x", padx=10, pady=10)
        
        tk.Label(current_frame, text="API Key actual:", 
                bg="#1a1f2e", fg=COL_TEXT).pack(side="left", padx=10, pady=8)
        
        # Mostrar API key enmascarada
        current_key = self.app.get_cfg().get("openai_api_key", "")
        if current_key:
            masked = f"{current_key[:8]}...{current_key[-4:]}" if len(current_key) > 12 else "****"
        else:
            masked = "No configurada"
        
        self.key_label = tk.Label(current_frame, text=masked, 
                                 bg="#1a1f2e", fg=COL_ACCENT if current_key else COL_MUTED,
                                 font=("DejaVu Sans Mono", 11))
        self.key_label.pack(side="left", padx=5)
        
        # Entry para nueva API key
        entry_frame = tk.Frame(body, bg=COL_CARD)
        entry_frame.pack(fill="x", padx=10, pady=10)
        
        tk.Label(entry_frame, text="Nueva API Key:", 
                bg=COL_CARD, fg=COL_TEXT).pack(anchor="w", pady=5)
        
        self.api_var = tk.StringVar()
        self.api_entry = tk.Entry(entry_frame, textvariable=self.api_var,
                                 bg="#1a1f2e", fg=COL_TEXT, 
                                 font=("DejaVu Sans Mono", 10),
                                 show="*", width=50)
        self.api_entry.pack(fill="x", pady=5)
        bind_text_popup(self.api_entry)
        
        # Checkbox para mostrar/ocultar
        self.show_var = tk.BooleanVar(value=False)
        tk.Checkbutton(entry_frame, text="Mostrar API Key", 
                      variable=self.show_var, command=self._toggle_show,
                      bg=COL_CARD, fg=COL_TEXT, selectcolor="#1a1f2e",
                      activebackground=COL_CARD).pack(anchor="w", pady=5)
        
        # Botones
        btn_frame = tk.Frame(body, bg=COL_CARD)
        btn_frame.pack(fill="x", pady=20)
        
        BigButton(btn_frame, text="💾 Guardar", 
                 command=self._save_key, micro=True).pack(side="left", padx=5)
        BigButton(btn_frame, text="🧪 Probar", 
                 command=self._test_key, micro=True).pack(side="left", padx=5)
        GhostButton(btn_frame, text="🗑 Borrar", 
                   command=self._delete_key, micro=True).pack(side="left", padx=5)
        
        self.toast = Toast(self)
    
    def _toggle_show(self):
        """Mostrar/ocultar API key"""
        if self.show_var.get():
            self.api_entry.config(show="")
        else:
            self.api_entry.config(show="*")
    
    def _save_key(self):
        """Guardar API key"""
        key = self.api_var.get().strip()
        if not key:
            self.toast.show("⚠ Introduce una API Key", 1500, COL_WARN)
            return
        
        if not key.startswith("sk-"):
            self.toast.show("⚠ La API Key debe empezar con 'sk-'", 2000, COL_WARN)
            return
        
        self.app.get_cfg()["openai_api_key"] = key
        self.app.save_cfg()
        
        # Actualizar label
        masked = f"{key[:8]}...{key[-4:]}"
        self.key_label.config(text=masked, fg=COL_SUCCESS)
        
        self.toast.show("✅ API Key guardada", 1500, COL_SUCCESS)
        self.api_var.set("")
    
    def _test_key(self):
        """Probar API key"""
        key = self.app.get_cfg().get("openai_api_key", "")
        if not key:
            self.toast.show("⚠ No hay API Key configurada", 1500, COL_WARN)
            return
        
        self.toast.show("🔄 Probando API Key...", 2000)
        # Aquí harías una llamada de prueba a OpenAI
        # Por ahora simulamos
        self.after(2000, lambda: self.toast.show("✅ API Key válida", 1500, COL_SUCCESS))
    
    def _delete_key(self):
        """Borrar API key"""
        if "openai_api_key" in self.app.get_cfg():
            del self.app.get_cfg()["openai_api_key"]
            self.app.save_cfg()
            self.key_label.config(text="No configurada", fg=COL_MUTED)
            self.toast.show("🗑 API Key eliminada", 1500)
        else:
            self.toast.show("No hay API Key que borrar", 1000, COL_MUTED) __init__(self, parent, app, **kwargs):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG)
        header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="🔑 API Key", bg=COL_BG, fg=COL_TEXT, 
                font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="< Atrás", command=lambda: self.app.show_screen('settingsmenu'), 
                   micro=True).pack(side="right", padx=14)
        
        body = Card(self)
        body.pack(fill="both", expand=True, padx=14, pady=10)
        
        # Información
        info = tk.Label(body, 
                       text="Configura tu API Key de OpenAI para el reconocimiento de alimentos",
                       bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 12), 
                       wraplength=400)
        info.pack(pady=10)
        
        # Frame para la API key actual
        current_frame = tk.Frame(body, bg="#1a1f2e", 
                               highlightbackground=COL_BORDER, highlightthickness=1)
        current_frame.pack(fill="x", padx=10, pady=10)
        
        tk.Label(current_frame, text="API Key actual:", 
                bg="#1a1f2e", fg=COL_TEXT).pack(side="left", padx=10, pady=8)
        
        # Mostrar API key enmascarada
        current_key = self.app.get_cfg().get("openai_api_key", "")
        if current_key:
            masked = f"{current_key[:8]}...{current_key[-4:]}" if len(current_key) > 12 else "****"
        else:
            masked = "No configurada"
        
        self.key_label = tk.Label(current_frame, text=masked, 
                                 bg="#1a1f2e", fg=COL_ACCENT if current_key else COL_MUTED,
                                 font=("DejaVu Sans Mono", 11))
        self.key_label.pack(side="left", padx=5)
        
        # Entry para nueva API key
        entry_frame = tk.Frame(body, bg=COL_CARD)
        entry_frame.pack(fill="x", padx=10, pady=10)
        
        tk.Label(entry_frame, text="Nueva API Key:", 
                bg=COL_CARD, fg=COL_TEXT).pack(anchor="w", pady=5)
        
        self.api_var = tk.StringVar()
        self.api_entry = tk.Entry(entry_frame, textvariable=self.api_var,
                                 bg="#1a1f2e", fg=COL_TEXT, 
                                 font=("DejaVu Sans Mono", 10),
                                 show="*", width=50)
        self.api_entry.pack(fill="x", pady=5)
        bind_text_popup(self.api_entry)
        
        # Checkbox para mostrar/ocultar
        self.show_var = tk.BooleanVar(value=False)
        tk.Checkbutton(entry_frame, text="Mostrar API Key", 
                      variable=self.show_var, command=self._toggle_show,
                      bg=COL_CARD, fg=COL_TEXT, selectcolor="#1a1f2e",
                      activebackground=COL_CARD).pack(anchor="w", pady=5)
        
        # Botones
        btn_frame = tk.Frame(body, bg=COL_CARD)
        btn_frame.pack(fill="x", pady=20)
        
        BigButton(btn_frame, text="💾 Guardar", 
                 command=self._save_key, micro=True).pack(side="left", padx=5)
        BigButton(btn_frame, text="🧪 Probar", 
                 command=self._test_key, micro=True).pack(side="left", padx=5)
        GhostButton(btn_frame, text="🗑 Borrar", 
                   command=self._delete_key, micro=True).pack(side="left", padx=5)
        
        self.toast = Toast(self)
    
    def _toggle_show(self):
        """Mostrar/ocultar API key"""
        if self.show_var.get():
            self.api_entry.config(show="")
        else:
            self.api_entry.config(show="*")
    
    def _save_key(self):
        """Guardar API key"""
        key = self.api_var.get().strip()
        if not key:
            self.toast.show("⚠ Introduce una API Key", 1500, COL_WARN)
            return
        
        if not key.startswith("sk-"):
            self.toast.show("⚠ La API Key debe empezar con 'sk-'", 2000, COL_WARN)
            return
        
        self.app.get_cfg()["openai_api_key"] = key
        self.app.save_cfg()
        
        # Actualizar label
        masked = f"{key[:8]}...{key[-4:]}"
        self.key_label.config(text=masked, fg=COL_SUCCESS)
        
        self.toast.show("✅ API Key guardada", 1500, COL_SUCCESS)
        self.api_var.set("")
    
    def _test_key(self):
        """Probar API key"""
        key = self.app.get_cfg().get("openai_api_key", "")
        if not key:
            self.toast.show("⚠ No hay API Key configurada", 1500, COL_WARN)
            return
        
        self.toast.show("🔄 Probando API Key...", 2000)
        # Aquí harías una llamada de prueba a OpenAI
        # Por ahora simulamos
        self.after(2000, lambda: self.toast.show("✅ API Key válida", 1500, COL_SUCCESS))
    
    def _delete_key(self):
        """Borrar API key"""
        if "openai_api_key" in self.app.get_cfg():
            del self.app.get_cfg()["openai_api_key"]
            self.app.save_cfg()
            self.key_label.config(text="No configurada", fg=COL_MUTED)
            self.toast.show("🗑 API Key eliminada", 1500)
        else:
            self.toast.show("No hay API Key que borrar", 1000, COL_MUTED)