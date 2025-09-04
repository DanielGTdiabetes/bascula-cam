# -*- coding: utf-8 -*-
"""
Pantallas rediseñadas con UI limpia y estructurada
"""
import tkinter as tk
from tkinter import ttk
import json
from pathlib import Path
from bascula.ui.widgets import *
from collections import deque

# Configuración de grid más espaciada
GRID_PAD = 12
SECTION_PAD = 20

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
        self.items = []
        self._next_id = 1
        self._selection_id = None
        self._stable = False
        self._tick_after = None
        self._wbuf = deque(maxlen=6)
        
        # Layout principal: 3 columnas con proporciones mejoradas
        self.grid_columnconfigure(0, weight=3, uniform="cols")  # Panel peso
        self.grid_columnconfigure(1, weight=4, uniform="cols")  # Lista alimentos
        self.grid_columnconfigure(2, weight=2, uniform="cols")  # Panel nutrición
        self.grid_rowconfigure(0, weight=1)
        
        # === PANEL IZQUIERDO: PESO Y CONTROLES ===
        left_panel = tk.Frame(self, bg=COL_BG)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(GRID_PAD, 6), pady=GRID_PAD)
        left_panel.grid_rowconfigure(1, weight=1)  # Card peso expansible
        left_panel.grid_columnconfigure(0, weight=1)
        
        # Header compacto con estado
        header_frame = tk.Frame(left_panel, bg=COL_BG)
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        
        title_row = tk.Frame(header_frame, bg=COL_BG)
        title_row.pack(fill="x")
        
        tk.Label(title_row, text="⚖", bg=COL_BG, fg=COL_ACCENT, 
                font=("DejaVu Sans", 24)).pack(side="left")
        tk.Label(title_row, text="Báscula Digital", bg=COL_BG, fg=COL_TEXT, 
                font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=8)
        
        # Botón de sonido en esquina
        self._mute_btn = tk.Button(title_row, text="🔊", bg=COL_BG, fg=COL_TEXT,
                                  font=("DejaVu Sans", 16), bd=0, cursor="hand2",
                                  command=self._toggle_mute)
        self._mute_btn.pack(side="right", padx=4)
        
        # Indicadores de estado (glucosa, timer) en segunda fila
        status_row = tk.Frame(header_frame, bg=COL_BG)
        status_row.pack(fill="x", pady=(4, 0))
        
        self.bg_label = tk.Label(status_row, text="", bg=COL_BG, fg=COL_TEXT, 
                                font=("DejaVu Sans", 11))
        self.bg_label.pack(side="left")
        
        self.timer_label = tk.Label(status_row, text="", bg=COL_BG, fg=COL_TEXT,
                                   font=("DejaVu Sans", 11))
        self.timer_label.pack(side="right")
        self._timer_remaining = 0
        self._timer_after = None
        
        # Card de peso mejorado
        weight_card = Card(left_panel)
        weight_card.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        
        # Display de peso centrado y grande
        weight_display = tk.Frame(weight_card, bg="#0f1420", relief="sunken", bd=2)
        weight_display.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.weight_lbl = tk.Label(weight_display, text="0 g", bg="#0f1420", fg=COL_ACCENT,
                                  font=("DejaVu Sans Mono", FS_HUGE, "bold"))
        self.weight_lbl.pack(expand=True)
        
        self.stability_label = tk.Label(weight_display, text="Esperando...", 
                                       bg="#0f1420", fg=COL_MUTED, 
                                       font=("DejaVu Sans", FS_TEXT))
        self.stability_label.pack(pady=(0, 10))
        
        # Grid de botones principales (2x3)
        btn_frame = tk.Frame(left_panel, bg=COL_BG)
        btn_frame.grid(row=2, column=0, sticky="ew")
        
        for i in range(3):
            btn_frame.grid_columnconfigure(i, weight=1, uniform="btns")
        
        btn_config = [
            ("⟲ Tara", self._on_tara, 0, 0, COL_ACCENT),
            ("➕ Añadir", self._on_add_item, 0, 1, "#00a884"),
            ("⏱ Timer", self._on_timer_open, 0, 2, "#ffa500"),
            ("🔄 Reiniciar", self._on_reset_session, 1, 0, "#6b7280"),
            ("📊 Finalizar", self._on_finish_meal_open, 1, 1, "#3b82f6"),
            ("⚙ Ajustes", self.on_open_settings_menu, 1, 2, "#6b7280"),
        ]
        
        for text, cmd, row, col, color in btn_config:
            btn = tk.Button(btn_frame, text=text, command=cmd, bg=color, fg="white",
                          font=("DejaVu Sans", FS_BTN_SMALL, "bold"), bd=0, 
                          relief="flat", cursor="hand2")
            btn.grid(row=row, column=col, sticky="nsew", padx=3, pady=3)
            btn.bind("<Enter>", lambda e, b=btn, c=color: b.config(bg=self._lighten(c)))
            btn.bind("<Leave>", lambda e, b=btn, c=color: b.config(bg=c))
        
        # === PANEL CENTRAL: LISTA DE ALIMENTOS ===
        center_panel = Card(self)
        center_panel.grid(row=0, column=1, sticky="nsew", padx=6, pady=GRID_PAD)
        
        # Header de lista
        list_header = tk.Frame(center_panel, bg=COL_CARD)
        list_header.pack(fill="x", padx=10, pady=(10, 5))
        
        tk.Label(list_header, text="🥗 Alimentos", bg=COL_CARD, fg=COL_ACCENT,
                font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(side="left")
        
        item_count = tk.Label(list_header, text="0 items", bg=COL_CARD, fg=COL_MUTED,
                            font=("DejaVu Sans", FS_TEXT))
        item_count.pack(side="right")
        self.item_count_label = item_count
        
        # TreeView mejorado
        tree_frame = tk.Frame(center_panel, bg=COL_CARD)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Estilo mejorado para TreeView
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Food.Treeview',
                       background='#1a1f2e',
                       foreground=COL_TEXT,
                       fieldbackground='#1a1f2e',
                       rowheight=36,
                       font=("DejaVu Sans", FS_LIST_ITEM))
        style.map('Food.Treeview',
                 background=[('selected', '#2563eb')])
        style.configure('Food.Treeview.Heading',
                       background='#1a1f2e',
                       foreground=COL_ACCENT,
                       relief='flat',
                       font=("DejaVu Sans", FS_LIST_HEAD, "bold"))
        
        self.tree = ttk.Treeview(tree_frame, 
                                columns=("item", "grams", "kcal"),
                                show="headings",
                                style='Food.Treeview',
                                selectmode="browse")
        
        self.tree.heading("item", text="Alimento")
        self.tree.heading("grams", text="Peso")
        self.tree.heading("kcal", text="Calorías")
        
        self.tree.column("item", width=200, anchor="w", stretch=True)
        self.tree.column("grams", width=80, anchor="center", stretch=False)
        self.tree.column("kcal", width=80, anchor="center", stretch=False)
        
        self.tree.pack(side="left", fill="both", expand=True)
        
        # Scrollbar estilizada
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Botón de eliminar seleccionado
        delete_btn = tk.Button(center_panel, text="🗑 Eliminar seleccionado",
                             command=self._on_delete_selected,
                             bg=COL_DANGER, fg="white",
                             font=("DejaVu Sans", FS_TEXT),
                             bd=0, relief="flat", cursor="hand2")
        delete_btn.pack(fill="x", padx=10, pady=(5, 10))
        
        self.tree.bind("<<TreeviewSelect>>", self._on_select_item)
        
        # === PANEL DERECHO: NUTRICIÓN ===
        right_panel = tk.Frame(self, bg=COL_BG)
        right_panel.grid(row=0, column=2, sticky="nsew", padx=(6, GRID_PAD), pady=GRID_PAD)
        right_panel.grid_rowconfigure(1, weight=1)
        
        # Card de totales nutricionales
        nutrition_card = Card(right_panel)
        nutrition_card.pack(fill="x", pady=(0, 10))
        
        tk.Label(nutrition_card, text="📊 Totales", bg=COL_CARD, fg=COL_ACCENT,
                font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(padx=10, pady=(10, 5))
        
        # Grid de valores nutricionales mejorado
        nut_grid = tk.Frame(nutrition_card, bg=COL_CARD)
        nut_grid.pack(fill="x", padx=10, pady=10)
        
        self._nut_labels = {}
        nutrients = [
            ("Peso total", "grams", "g", "#00d4aa"),
            ("Calorías", "kcal", "kcal", "#ffa500"),
            ("Carbohidratos", "carbs", "g", "#3b82f6"),
            ("Proteínas", "protein", "g", "#ec4899"),
            ("Grasas", "fat", "g", "#f59e0b"),
        ]
        
        for i, (name, key, unit, color) in enumerate(nutrients):
            row_frame = tk.Frame(nut_grid, bg=COL_CARD)
            row_frame.pack(fill="x", pady=3)
            
            # Indicador de color
            color_dot = tk.Label(row_frame, text="●", bg=COL_CARD, fg=color,
                                font=("DejaVu Sans", 10))
            color_dot.pack(side="left", padx=(0, 5))
            
            # Nombre
            tk.Label(row_frame, text=name, bg=COL_CARD, fg=COL_TEXT,
                    font=("DejaVu Sans", FS_TEXT)).pack(side="left")
            
            # Valor alineado a la derecha
            val_frame = tk.Frame(row_frame, bg=COL_CARD)
            val_frame.pack(side="right")
            
            val = tk.Label(val_frame, text="0", bg=COL_CARD, fg=COL_TEXT,
                         font=("DejaVu Sans", FS_TEXT, "bold"))
            val.pack(side="left")
            
            tk.Label(val_frame, text=f" {unit}", bg=COL_CARD, fg=COL_MUTED,
                    font=("DejaVu Sans", FS_TEXT-1)).pack(side="left")
            
            self._nut_labels[key] = val
        
        # Panel de información adicional
        info_card = Card(right_panel)
        info_card.pack(fill="both", expand=True)
        
        tk.Label(info_card, text="💡 Consejos", bg=COL_CARD, fg=COL_ACCENT,
                font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(padx=10, pady=(10, 5))
        
        self.tips_text = tk.Text(info_card, bg="#1a1f2e", fg=COL_TEXT,
                                font=("DejaVu Sans", FS_TEXT-1),
                                height=8, wrap="word", relief="flat",
                                state="disabled")
        self.tips_text.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        
        self._update_tips("• Coloca el recipiente vacío\n• Presiona 'Tara' para poner a cero\n• Añade alimentos uno por uno")
        
        # Toast notifications
        self.toast = Toast(self)
        
        # Variables de estado adicionales
        self._bg_last_fetch = 0
        self._bg_fetching = False
        self._ns_units = None
        self._ns_units_last = 0
        
    def _lighten(self, color):
        """Aclara un color hex para hover effects"""
        try:
            if color.startswith("#"):
                r = int(color[1:3], 16)
                g = int(color[3:5], 16)
                b = int(color[5:7], 16)
                # Aclarar un 20%
                r = min(255, int(r * 1.2))
                g = min(255, int(g * 1.2))
                b = min(255, int(b * 1.2))
                return f"#{r:02x}{g:02x}{b:02x}"
        except:
            pass
        return color
    
    def _update_tips(self, text):
        """Actualiza el panel de consejos"""
        self.tips_text.config(state="normal")
        self.tips_text.delete(1.0, "end")
        self.tips_text.insert(1.0, text)
        self.tips_text.config(state="disabled")
    
    def on_show(self):
        if not self._tick_after:
            self._tick()
    
    def on_hide(self):
        if self._tick_after:
            self.after_cancel(self._tick_after)
            self._tick_after = None
    
    def _tick(self):
        net_weight = self.app.get_latest_weight()
        decimals = self.app.get_cfg().get('decimals', 0)
        self.weight_lbl.config(text=f"{net_weight:.{decimals}f} g")
        
        self._wbuf.append(net_weight)
        threshold = 1.0
        is_stable = (len(self._wbuf) >= 3) and ((max(self._wbuf) - min(self._wbuf)) < threshold)
        
        if is_stable != self._stable:
            self._stable = is_stable
            if is_stable:
                self.stability_label.config(text="✓ Estable", fg=COL_SUCCESS)
                self._update_tips("Peso estable detectado\n• Presiona 'Añadir' para capturar\n• O añade más alimento")
            else:
                self.stability_label.config(text="Midiendo...", fg=COL_WARN)
        
        # Actualizar contador de items
        self.item_count_label.config(text=f"{len(self.items)} items")
        
        self._tick_after = self.after(100, self._tick)
    
    def _toggle_mute(self):
        cfg = self.app.get_cfg()
        enabled = not bool(cfg.get('sound_enabled', True))
        cfg['sound_enabled'] = enabled
        self.app.save_cfg()
        
        if hasattr(self.app, 'get_audio') and self.app.get_audio():
            self.app.get_audio().set_enabled(enabled)
        
        self._mute_btn.configure(text=("🔊" if enabled else "🔇"))
        self.toast.show("Sonido: " + ("ON" if enabled else "OFF"), 900)
    
    def _on_tara(self):
        reader = self.app.get_reader()
        if reader and reader.get_latest() is not None:
            self.app.get_tare().set_tare(reader.get_latest())
            self.toast.show("✓ Tara establecida", 1000)
            self._update_tips("Tara establecida en cero\n• Ahora añade el alimento\n• El peso se mostrará neto")
        else:
            self.toast.show("⚠ Sin lectura de báscula", 1200, COL_WARN)
    
    def _on_add_item(self):
        self.toast.show("Capturando...", 900)
        
        def _bg():
            image_path = None
            try:
                if hasattr(self.app, "ensure_camera") and self.app.ensure_camera():
                    image_path = self.app.capture_image()
                    weight = self.app.get_latest_weight()
                    data = self.app.request_nutrition(image_path, weight)
                else:
                    # Sin cámara, usar datos simulados
                    weight = self.app.get_latest_weight()
                    data = {
                        "name": "Alimento",
                        "grams": weight,
                        "kcal": round(weight * 1.5),
                        "carbs": round(weight * 0.2),
                        "protein": round(weight * 0.1),
                        "fat": round(weight * 0.05)
                    }
            except Exception as e:
                self.after(0, lambda: self.toast.show(f"Error: {e}", 2200, COL_DANGER))
                if image_path:
                    try: self.app.delete_image(image_path)
                    except: pass
                return
            
            def _apply():
                try:
                    self._add_item_from_data(data)
                    self._recalc_totals()
                    self.toast.show(f"✓ {data.get('name','Alimento')} añadido", 1400, COL_SUCCESS)
                    self._update_tips(f"Añadido: {data.get('name')}\n• Continúa añadiendo más\n• O finaliza para ver resumen")
                finally:
                    if image_path:
                        try: self.app.delete_image(image_path)
                        except: pass
            
            self.after(0, _apply)
        
        import threading
        threading.Thread(target=_bg, daemon=True).start()
    
    def _add_item_from_data(self, data):
        data['id'] = self._next_id
        self._next_id += 1
        self.items.append(data)
        
        self.tree.insert("", "end", iid=str(data['id']), 
                        values=(data.get('name', '?'),
                               f"{data.get('grams', 0):.0f} g",
                               f"{data.get('kcal', 0):.0f}"))
    
    def _on_select_item(self, evt):
        sel = self.tree.selection()
        self._selection_id = sel[0] if sel else None
    
    def _on_delete_selected(self):
        if self._selection_id:
            try:
                self.tree.delete(self._selection_id)
            except:
                pass
            self.items = [i for i in self.items if str(i['id']) != str(self._selection_id)]
            self._selection_id = None
            self._recalc_totals()
            self.toast.show("Elemento eliminado", 900)
        else:
            self.toast.show("Selecciona un elemento", 1100, COL_MUTED)
    
    def _recalc_totals(self):
        totals = {
            'grams': sum(i.get('grams', 0) for i in self.items),
            'kcal': sum(i.get('kcal', 0) for i in self.items),
            'carbs': sum(i.get('carbs', 0) for i in self.items),
            'protein': sum(i.get('protein', 0) for i in self.items),
            'fat': sum(i.get('fat', 0) for i in self.items),
        }
        
        for k, v in totals.items():
            if k in self._nut_labels:
                self._nut_labels[k].config(text=f"{v:.0f}")
    
    def _on_reset_session(self):
        self.tree.delete(*self.tree.get_children())
        self.items.clear()
        self._selection_id = None
        self._recalc_totals()
        self.toast.show("🔄 Sesión reiniciada", 900)
        self._update_tips("Sesión reiniciada\n• Lista de alimentos vacía\n• Listo para nueva medición")
    
    def _on_timer_open(self):
        try:
            from bascula.ui.widgets import TimerPopup
            def _acc(sec=None):
                if sec and sec > 0:
                    self._start_small_timer(sec)
            TimerPopup(self, on_accept=_acc)
        except Exception as e:
            self.toast.show(f"Error: {e}", 1500, COL_DANGER)
    
    def _start_small_timer(self, seconds: int):
        self._timer_remaining = max(1, int(seconds))
        if self.timer_label:
            self.timer_label.configure(text=f"⏱ {self._fmt_sec(self._timer_remaining)}")
        self._schedule_timer_tick()
    
    def _schedule_timer_tick(self):
        if self._timer_after:
            self.after_cancel(self._timer_after)
        self._timer_after = self.after(1000, self._timer_tick)
    
    def _timer_tick(self):
        self._timer_remaining -= 1
        if self._timer_remaining <= 0:
            self.timer_label.configure(text="⏰ Tiempo!", fg=COL_ACCENT)
            self.toast.show("⏰ Tiempo finalizado", 1500)
            if hasattr(self.app, 'get_audio') and self.app.get_audio():
                self.app.get_audio().play_event('timer_done')
            self.after(3000, lambda: self.timer_label.configure(text=""))
            return
        
        self.timer_label.configure(text=f"⏱ {self._fmt_sec(self._timer_remaining)}")
        self._schedule_timer_tick()
    
    def _fmt_sec(self, s: int) -> str:
        m, ss = divmod(max(0, int(s)), 60)
        return f"{m:02d}:{ss:02d}"
    
    def _on_finish_meal_open(self):
        if not self.items:
            self.toast.show("No hay alimentos para finalizar", 1200, COL_WARN)
            return
        
        totals = {
            'grams': sum(i.get('grams', 0) for i in self.items),
            'kcal': sum(i.get('kcal', 0) for i in self.items),
            'carbs': sum(i.get('carbs', 0) for i in self.items),
            'protein': sum(i.get('protein', 0) for i in self.items),
            'fat': sum(i.get('fat', 0) for i in self.items),
        }
        
        # Modal de resumen mejorado
        modal = tk.Toplevel(self)
        modal.configure(bg=COL_BG)
        modal.attributes("-topmost", True)
        modal.overrideredirect(True)
        
        # Centrar modal
        modal.update_idletasks()
        w, h = 600, 500
        x = (modal.winfo_screenwidth() - w) // 2
        y = (modal.winfo_screenheight() - h) // 2
        modal.geometry(f"{w}x{h}+{x}+{y}")
        modal.grab_set()
        
        cont = Card(modal)
        cont.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        header = tk.Frame(cont, bg=COL_CARD)
        header.pack(fill="x", padx=15, pady=(15, 10))
        
        tk.Label(header, text="📊 Resumen Nutricional", bg=COL_CARD, fg=COL_ACCENT,
                font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left")
        
        # Close button
        close_x = tk.Button(header, text="✕", bg=COL_CARD, fg=COL_MUTED,
                          font=("DejaVu Sans", 16), bd=0, cursor="hand2",
                          command=modal.destroy)
        close_x.pack(side="right")
        
        # Contenido
        content = tk.Frame(cont, bg=COL_CARD)
        content.pack(fill="both", expand=True, padx=15)
        
        # Grid de valores con diseño mejorado
        for i, (label, value, unit, color) in enumerate([
            ("Peso total", totals['grams'], "g", "#00d4aa"),
            ("Calorías", totals['kcal'], "kcal", "#ffa500"),
            ("Carbohidratos", totals['carbs'], "g", "#3b82f6"),
            ("Proteínas", totals['protein'], "g", "#ec4899"),
            ("Grasas", totals['fat'], "g", "#f59e0b"),
        ]):
            row = tk.Frame(content, bg=COL_CARD)
            row.pack(fill="x", pady=5)
            
            # Color indicator
            tk.Label(row, text="●", bg=COL_CARD, fg=color,
                    font=("DejaVu Sans", 14)).pack(side="left", padx=(0, 8))
            
            # Label
            tk.Label(row, text=label, bg=COL_CARD, fg=COL_TEXT,
                    font=("DejaVu Sans", FS_TEXT)).pack(side="left")
            
            # Value
            val_text = f"{value:.0f} {unit}"
            tk.Label(row, text=val_text, bg=COL_CARD, fg=COL_TEXT,
                    font=("DejaVu Sans", FS_TEXT, "bold")).pack(side="right")
        
        # Opciones Nightscout (si está habilitado)
        if self.app.get_cfg().get('diabetic_mode', False):
            ns_frame = tk.Frame(content, bg=COL_CARD)
            ns_frame.pack(fill="x", pady=(20, 10))
            
            tk.Label(ns_frame, text="Nightscout:", bg=COL_CARD, fg=COL_ACCENT,
                    font=("DejaVu Sans", FS_TEXT, "bold")).pack(anchor="w", pady=(0, 5))
            
            self.var_send_ns = tk.BooleanVar(value=False)
            ttk.Checkbutton(ns_frame, text="Enviar a Nightscout",
                           variable=self.var_send_ns).pack(anchor="w")
        
        # Botones de acción
        btn_frame = tk.Frame(cont, bg=COL_CARD)
        btn_frame.pack(fill="x", padx=15, pady=(10, 15))
        
        def _close_and_reset():
            self._on_reset_session()
            modal.destroy()
        
        tk.Button(btn_frame, text="Cerrar", command=modal.destroy,
                 bg=COL_BORDER, fg=COL_TEXT, font=("DejaVu Sans", FS_BTN_SMALL),
                 bd=0, relief="flat", cursor="hand2").pack(side="left", padx=5)
        
        tk.Button(btn_frame, text="Reiniciar sesión", command=_close_and_reset,
                 bg="#3b82f6", fg="white", font=("DejaVu Sans", FS_BTN_SMALL, "bold"),
                 bd=0, relief="flat", cursor="hand2").pack(side="right", padx=5)

class CalibScreen(BaseScreen):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="Calibración", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="< Atrás", command=lambda: self.app.show_screen('settingsmenu'), micro=True).pack(side="right", padx=14)
        body = Card(self); body.pack(fill="both", expand=True, padx=14, pady=10)
        live = tk.Frame(body, bg="#1a1f2e", highlightbackground=COL_BORDER, highlightthickness=1); live.pack(fill="x", pady=6, padx=6)
        tk.Label(live, text="Lectura actual:", bg="#1a1f2e", fg=COL_TEXT).pack(side="left", padx=8, pady=6)
        self.lbl_live = tk.Label(live, text="-", bg="#1a1f2e", fg=COL_TEXT); self.lbl_live.pack(side="left", pady=6)
        caprow = tk.Frame(body, bg=COL_CARD); caprow.pack(fill="x", pady=6)
        self._b0, self._bw = None, None
        GhostButton(caprow, text="Capturar cero", command=self._cap_cero, micro=True).pack(side="left", padx=4)
        GhostButton(caprow, text="Capturar con patrón", command=self._cap_con_peso, micro=True).pack(side="left", padx=4)
        rowp = tk.Frame(body, bg=COL_CARD); rowp.pack(fill="x", pady=6, padx=6)
        tk.Label(rowp, text="Peso patrón (gramos):", bg=COL_CARD, fg=COL_TEXT).pack(side="left")
        self.var_patron = tk.StringVar()
        ent = tk.Entry(rowp, textvariable=self.var_patron, bg="#1a1f2e", fg=COL_TEXT, width=12); ent.pack(side="left", padx=8)
        try:
            bind_numeric_popup(ent)
        except Exception:
            pass
        BigButton(body, text="Guardar calibración", command=self._calc_save, micro=True).pack(anchor="e", pady=4, padx=6)
        self.toast = Toast(self); self.after(120, self._tick_live)

    def _tick_live(self):
        r = self.app.get_reader()
        v = r.get_latest() if r else None
        if v is not None:
            try:
                self.lbl_live.config(text=f"{v:.3f}")
            except Exception:
                self.lbl_live.config(text=str(v))
        self.after(120, self._tick_live)

    def _promedio(self, n=15):
        r = self.app.get_reader()
        vals = [r.get_latest() for _ in range(n) if r and r.get_latest() is not None]
        return sum(vals)/len(vals) if vals else None

    def _cap_cero(self):
        v = self._promedio()
        self._b0 = v
        if v is not None:
            self.toast.show(f"Cero: {v:.2f}", 1200)

    def _cap_con_peso(self):
        v = self._promedio()
        self._bw = v
        if v is not None:
            self.toast.show(f"Patrón: {v:.2f}", 1200)

    def _calc_save(self):
        try:
            w = float(self.var_patron.get())
            assert w > 0 and self._b0 is not None and self._bw is not None
            factor = w / (self._bw - self._b0)
            self.app.get_tare().update_calib(factor)
            self.app.get_cfg()["calib_factor"] = factor
            self.app.save_cfg()
            self.toast.show("Calibración guardada", 1500, COL_SUCCESS)
            self.after(1600, lambda: self.app.show_screen('settingsmenu'))
        except Exception:
            self.toast.show("Error en datos", 1500, COL_DANGER)
