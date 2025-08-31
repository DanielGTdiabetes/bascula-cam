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

        # Más espacio a la derecha (lista): 1 : 3
        self.grid_columnconfigure(0, weight=1, uniform="cols")
        self.grid_columnconfigure(1, weight=3, uniform="cols")
        self.grid_rowconfigure(0, weight=1)

        # --- Panel izquierdo (peso) ---
        card_weight = Card(self); card_weight.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        header = tk.Frame(card_weight, bg=COL_CARD); header.pack(fill="x")
        tk.Label(header, text="Peso actual", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=10, pady=5)
        self.status_indicator = StatusIndicator(header, size=16); self.status_indicator.pack(side="left")

        weight_frame = tk.Frame(card_weight, bg="#1a1f2e", highlightbackground=COL_BORDER, highlightthickness=1)
        weight_frame.pack(expand=True, fill="both", padx=8, pady=8)
        self.weight_lbl = WeightLabel(weight_frame, bg="#1a1f2e"); self.weight_lbl.pack(expand=True, fill="both")
        stf = tk.Frame(weight_frame, bg="#1a1f2e"); stf.pack(side="bottom", pady=4)
        self.stability_label = tk.Label(stf, text="Esperando señal...", bg="#1a1f2e", fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT)); self.stability_label.pack()

        btns = tk.Frame(card_weight, bg=COL_CARD); btns.pack(fill="x", pady=4)
        btn_map = [("Tara", self._on_tara), ("Plato", self._on_plato), ("Añadir", self._on_add_item),
                   ("Ajustes", self.on_open_settings_menu), ("Reiniciar", self._on_reset_session)]
        for i, (txt, cmd) in enumerate(btn_map):
            BigButton(btns, text=txt, command=cmd, micro=True).grid(row=0, column=i, sticky="nsew", padx=4, pady=4)
            btns.grid_columnconfigure(i, weight=1)

        # --- Panel derecho (totales + lista) ---
        right = tk.Frame(self, bg=COL_BG); right.grid(row=0, column=1, sticky="nsew", padx=0, pady=8)  # SIN margen derecho
        right.grid_rowconfigure(1, weight=1)

        # Totales
        self.card_nutrition = Card(right); self.card_nutrition.grid(row=0, column=0, sticky="ew", pady=(0, 8))
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

        # Lista + Scrollbar (full width)
        self.card_items = Card(right); self.card_items.grid(row=1, column=0, sticky="nsew")  # sin padding extra
        self.card_items.grid_rowconfigure(1, weight=1)
        self.card_items.grid_columnconfigure(0, weight=1)

        header_items = tk.Frame(self.card_items, bg=COL_CARD); header_items.grid(row=0, column=0, sticky="ew", padx=0, pady=(0,4))
        header_items.grid_columnconfigure(0, weight=1)
        tk.Label(header_items, text="🧾 Lista de alimentos", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_CARD_TITLE, "bold")).grid(row=0, column=0, sticky="w")
        GhostButton(header_items, text="🗑 Borrar seleccionado", command=self._on_delete_selected, micro=True).grid(row=0, column=1, sticky="e", padx=6)

        # Estilos de tabla
        style = ttk.Style(self); style.theme_use('clam')
        style.configure('Dark.Treeview', background='#1a1f2e', foreground=COL_TEXT, fieldbackground='#1a1f2e', rowheight=34)
        style.map('Dark.Treeview', background=[('selected', '#2a3142')])
        style.configure('Dark.Treeview.Heading', background=COL_CARD, foreground=COL_ACCENT, relief='flat', font=("DejaVu Sans", 12, "bold"))

        # Contenedor de tabla a todo el ancho
        tree_frame = tk.Frame(self.card_items, bg=COL_CARD); tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)  # Treeview crece
        # Col 1 (scrollbar) sin weight para que quede a la derecha
        # Treeview + Scrollbar
        self.tree = ttk.Treeview(tree_frame, columns=("item","grams"), show="headings", style='Dark.Treeview', selectmode="browse")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        # Columnas: que la de "item" se ESTIRE para ocupar todo lo que sobra
        self.tree.heading("item", text="Alimento")
        self.tree.column("item", width=240, minwidth=120, anchor="w", stretch=True)
        self.tree.heading("grams", text="Peso (g)")
        self.tree.column("grams", width=110, minwidth=90, anchor="center", stretch=False)

        # Selección robusta
        self.tree.bind("<<TreeviewSelect>>", self._on_select_item)
        self.tree.bind("<ButtonRelease-1>", self._on_select_item)

        # Scroll con rueda del ratón
        def _on_mousewheel(event):
            if event.delta:
                self.tree.yview_scroll(int(-1*(event.delta/120)), "units")
            return "break"
        self.tree.bind("<MouseWheel>", _on_mousewheel)       # Windows/macOS
        self.tree.bind("<Button-4>", lambda e: self.tree.yview_scroll(-1, "units"))  # Linux X11 up
        self.tree.bind("<Button-5>", lambda e: self.tree.yview_scroll( 1, "units"))  # Linux X11 down

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
        modal.configure(bg=COL_BG); modal.attributes("-topmost", True); modal.overrideredirect(True)
        modal.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0"); modal.grab_set()
        cont = Card(modal); cont.pack(fill="both", expand=True, padx=20, pady=20)
        cont.grid_rowconfigure(1, weight=1); cont.grid_columnconfigure(0, weight=1)
        tk.Label(cont, text="📷 Capturar Alimento", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_TITLE, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 10))
        camera_area = tk.Frame(cont, bg="#000000", highlightbackground=COL_BORDER, highlightthickness=1); camera_area.grid(row=1, column=0, sticky="nsew", pady=5)

        stop_preview_func = None
        if self.app.camera and self.app.camera.available():
            stop_preview_func = self.app.camera.preview_to_tk(camera_area)
        else:
            reason = self.app.camera.explain_status() if self.app.camera else "CameraService no cargado."
            tk.Label(camera_area, text=f"Cámara no disponible:\n{reason}", 
                     bg="#000000", fg=COL_DANGER, font=("DejaVu Sans", 14), wraplength=350).place(relx=0.5, rely=0.5, anchor="center")

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
        self._selection_id = sel[0] if sel else None  # guardamos el iid como string

    def _on_delete_selected(self):
        if self._selection_id:
            try:
                self.tree.delete(self._selection_id)
            except Exception:
                pass
            self.items = [i for i in self.items if str(i['id']) != str(self._selection_id)]
            self._selection_id = None
        else:
            self.toast.show("Selecciona un item", 1100, COL_MUTED)

    def _on_reset_session(self):
        self.tree.delete(*self.tree.get_children())
        self.items.clear(); self._selection_id = None
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
        btn_map = [("Calibración", 'calib'), ("Wi-Fi", 'wifi'), ("API Key", 'apikey'), ("Otros", '_soon')]
        for i, (text, target) in enumerate(btn_map):
            cmd = (lambda t=target: self.app.show_screen(t)) if target != '_soon' else self._soon
            BigButton(grid, text=text, command=cmd, small=True).grid(row=i//2, column=i%2, sticky="nsew", padx=6, pady=6)
        self.toast = Toast(self)
    def _soon(self): self.toast.show("Próximamente…", 900, COL_MUTED)

class WifiScreen(BaseScreen):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="📶 Conexión Wi-Fi", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="< Atrás", command=lambda: self.app.show_screen('settingsmenu'), micro=True).pack(side="right", padx=14)
        body = Card(self); body.pack(fill="both", expand=True, padx=14, pady=10)
        tk.Label(body, text="Configuración Wi-Fi (Próximamente)", bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT)).pack(pady=20)

class ApiKeyScreen(BaseScreen):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="🗝 API Key", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="< Atrás", command=lambda: self.app.show_screen('settingsmenu'), micro=True).pack(side="right", padx=14)
        body = Card(self); body.pack(fill="both", expand=True, padx=14, pady=10)
        tk.Label(body, text="Configuración API Key (Próximamente)", bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT)).pack(pady=20)
