# -*- coding: utf-8 -*-
# bascula/ui/screens.py - MODIFICADO: Popup de cámara con previsualización en vivo.
import tkinter as tk
from tkinter import ttk

from bascula.ui.widgets import (
    Card, BigButton, GhostButton, WeightLabel, Toast,
    StatusIndicator, KeypadPopup, bind_numeric_popup, bind_text_popup,
    COL_BG, COL_CARD, COL_TEXT, COL_MUTED, COL_SUCCESS, COL_WARN, DANGER, ACCENT, BORDER,
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

        # ... (el resto de la UI de HomeScreen se mantiene igual hasta _on_add_item) ...
        # --- Columna Izquierda: Peso ---
        self.card_weight = Card(self, min_width=700, min_height=400)
        self.card_weight.grid(row=0, column=0, sticky="nsew", padx=get_scaled_size(10), pady=get_scaled_size(10))
        header_weight = tk.Frame(self.card_weight, bg=COL_CARD); header_weight.pack(fill="x", pady=(0, get_scaled_size(6)))
        tk.Label(header_weight, text="Peso actual ●", bg=COL_CARD, fg=ACCENT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left")
        self.status_indicator = StatusIndicator(header_weight, size=16); self.status_indicator.pack(side="left", padx=(get_scaled_size(10),0)); self.status_indicator.set_status("active")
        tk.Frame(self.card_weight, bg=ACCENT, height=2).pack(fill="x", pady=(0, get_scaled_size(8)))
        weight_frame = tk.Frame(self.card_weight, bg="#1a1f2e", highlightbackground=BORDER, highlightthickness=1, relief="flat")
        weight_frame.pack(expand=True, fill="both", padx=get_scaled_size(6), pady=get_scaled_size(6))
        self.weight_lbl = WeightLabel(weight_frame); self.weight_lbl.configure(bg="#1a1f2e"); self.weight_lbl.pack(expand=True, fill="both")
        stf = tk.Frame(weight_frame, bg="#1a1f2e"); stf.pack(side="bottom", pady=(0, get_scaled_size(8)))
        self.stability_label = tk.Label(stf, text="● Estable", bg="#1a1f2e", fg=COL_SUCCESS, font=("DejaVu Sans", FS_TEXT)); self.stability_label.pack()

        btns = tk.Frame(self.card_weight, bg=COL_CARD); btns.pack(fill="x", pady=(get_scaled_size(8),0))
        for c in range(5): btns.columnconfigure(c, weight=1, uniform="btns_row")
        for i, (txt, cmd) in enumerate([("Tara", self._on_tara), ("Plato", self._on_plato), ("Añadir", self._on_add_item), ("Ajustes", self.on_open_settings_menu), ("Reiniciar", self._on_reset_session)]):
            BigButton(btns, text=txt, command=cmd, micro=True).grid(row=0, column=i, sticky="nsew", padx=get_scaled_size(4), pady=(0, get_scaled_size(4)))

        # --- Columna Derecha: Totales y Lista ---
        right = tk.Frame(self, bg=COL_BG); right.grid(row=0, column=1, sticky="nsew", padx=(0,get_scaled_size(10)), pady=get_scaled_size(10))
        right.grid_rowconfigure(0, weight=0) 
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        self.card_nutrition = Card(right, min_width=320)
        self.card_nutrition.grid(row=0, column=0, sticky="new", pady=(0, get_scaled_size(12)))
        header_nut = tk.Frame(self.card_nutrition, bg=COL_CARD); header_nut.pack(fill="x")
        self.lbl_nut_title = tk.Label(header_nut, text="🥗 Totales", bg=COL_CARD, fg=ACCENT, font=("DejaVu Sans", FS_CARD_TITLE, "bold"))
        self.lbl_nut_title.pack(side="left")
        tk.Frame(self.card_nutrition, bg=ACCENT, height=1).pack(fill="x", pady=(4,6))
        grid = tk.Frame(self.card_nutrition, bg="#1a1f2e", highlightbackground=BORDER, highlightthickness=1, relief="flat")
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
        tk.Label(header_items, text="🧾 Lista de alimentos", bg=COL_CARD, fg=ACCENT, font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(side="left")
        tk.Frame(self.card_items, bg=ACCENT, height=1).pack(fill="x", pady=(4,6))
        style = ttk.Style(self)
        try: style.theme_use('clam')
        except Exception: pass
        style.configure('Dark.Treeview', background='#1a1f2e', foreground=COL_TEXT, fieldbackground='#1a1f2e', bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER, rowheight=get_scaled_size(24))
        style.map('Dark.Treeview', background=[('selected', '#2a3142')], foreground=[('selected', '#e8fff7')])
        style.configure('Dark.Treeview.Heading', background=COL_CARD, foreground=ACCENT, relief='flat')
        tree_frame = tk.Frame(self.card_items, bg=COL_CARD); tree_frame.pack(fill="both", expand=True)
        cols = ("item","grams","kcal","carbs","protein","fat")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse", style='Dark.Treeview')
        for c, title in [("item","Alimento"),("grams","g"),("kcal","kcal"),("carbs","C(g)"),("protein","P(g)"),("fat","G(g)")]:
            self.tree.heading(c, text=title); self.tree.column(c, width=70 if c!="item" else 140, anchor="center")
        self.tree.pack(fill="both", expand=True); self.tree.bind("<<TreeviewSelect>>", self._on_select_item)
        
        self.toast = Toast(self); self._raw_actual = None; self._stable = False; self.after(80, self._tick)

    # ... (métodos _fmt, _tick, _on_tara, _on_plato se mantienen igual) ...

    def _on_add_item(self):
        self.app.start_camera_preview()
        
        # Crear un Toplevel para los botones de control sobre la preview
        modal = tk.Toplevel(self)
        modal.configure(bg=COL_BG)
        modal.attributes("-topmost", True)
        modal.overrideredirect(True)
        
        # Posicionar la ventana de control en la parte inferior central
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = 400, 100
        modal.geometry(f"{w}x{h}+{ (sw-w)//2 }+{ sh - h - 20 }")
        
        modal.transient(self.winfo_toplevel())
        modal.grab_set()

        cont = Card(modal, min_width=w, min_height=h)
        cont.pack(fill="both", expand=True, padx=10, pady=10)
        
        row = tk.Frame(cont, bg=COL_CARD)
        row.pack(fill="both", expand=True)
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, weight=1)
        row.rowconfigure(0, weight=1)

        def on_cancel():
            self.app.stop_camera_preview()
            modal.destroy()

        def on_capture():
            self.app.stop_camera_preview()
            modal.destroy()
            
            # Espera un instante para que la preview se cierre
            self.after(100, self._process_capture)

        GhostButton(row, text="Cancelar", command=on_cancel, micro=False).grid(row=0, column=0, sticky="nsew", padx=5)
        BigButton(row, text="📸 Capturar", command=on_capture, micro=False).grid(row=0, column=1, sticky="nsew", padx=5)
    
    def _process_capture(self):
        img_path = self.app.capture_image()
        grams = self.app.get_latest_weight()
        data = self.app.request_nutrition(image_path=img_path, grams=grams)
        self._add_item_from_data(data)

    # ... (el resto de la clase HomeScreen y las otras clases de Screens se mantienen igual) ...
