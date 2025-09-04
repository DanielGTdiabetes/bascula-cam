# -*- coding: utf-8 -*-
"""
Pantallas base (Home + Calibración) con UI limpia y estable.
"""
import tkinter as tk
from tkinter import ttk
from collections import deque
from bascula.ui.widgets import *  # Card, BigButton, GhostButton, Toast, bind_numeric_popup


class BaseScreen(tk.Frame):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=COL_BG, **kwargs)
        self.app = app
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def on_show(self):
        pass

    def on_hide(self):
        pass


class HomeScreen(BaseScreen):
    def __init__(self, parent, app, on_open_settings_menu):
        super().__init__(parent, app)
        self.on_open_settings_menu = on_open_settings_menu

        self.items = []  # [{id, name, grams, kcal, carbs, protein, fat}]
        self._next_id = 1
        self._selection_id = None
        self._tick_after = None
        self._wbuf = deque(maxlen=6)
        self._stable = False
        self._timer_remaining = 0
        self._timer_after = None

        # Layout principal: 3 columnas (peso, lista, nutrición)
        self.grid_columnconfigure(0, weight=3, uniform="cols")
        self.grid_columnconfigure(1, weight=4, uniform="cols")
        self.grid_columnconfigure(2, weight=2, uniform="cols")
        self.grid_rowconfigure(0, weight=1)

        # Panel izquierdo (peso + controles)
        left = tk.Frame(self, bg=COL_BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(10, 6), pady=10)
        left.grid_rowconfigure(1, weight=1)

        # Header
        header = tk.Frame(left, bg=COL_BG)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        tk.Label(header, text="Báscula Digital", bg=COL_BG, fg=COL_TEXT,
                 font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=8)
        self.timer_label = tk.Label(header, text="", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", 11))
        self.timer_label.pack(side="right")

        # Peso actual
        weight_card = Card(left)
        weight_card.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        weight_display = tk.Frame(weight_card, bg="#0f1420", relief="sunken", bd=1)
        weight_display.pack(fill="both", expand=True, padx=10, pady=10)
        self.weight_lbl = WeightLabel(weight_display, bg="#0f1420", fg=COL_ACCENT)
        self.weight_lbl.pack(fill="both", expand=True, padx=(12,8), pady=4)
        self.stability_label = tk.Label(weight_display, text="Esperando...", bg="#0f1420", fg=COL_MUTED,
                                        font=("DejaVu Sans", FS_TEXT))
        self.stability_label.pack(pady=(0, 10))

        # Botones principales (2x3)
        btns = tk.Frame(left, bg=COL_BG)
        btns.grid(row=2, column=0, sticky="ew")
        for i in range(3):
            btns.grid_columnconfigure(i, weight=1, uniform="btns")
        btn_map = [
            ("Tara", self._on_tara, 0, 0, COL_ACCENT),
            ("Añadir", self._on_add_item, 0, 1, "#00a884"),
            ("Temporizador", self._on_timer_open, 0, 2, "#ffa500"),
            ("Reiniciar", self._on_reset_session, 1, 0, "#6b7280"),
            ("Finalizar", self._on_finish_meal_open, 1, 1, "#3b82f6"),
            ("Ajustes", self.on_open_settings_menu, 1, 2, "#6b7280"),
        ]
        for text, cmd, r, c, color in btn_map:
            b = tk.Button(btns, text=text, command=cmd, bg=color, fg="white",
                          font=("DejaVu Sans", FS_BTN_SMALL, "bold"), bd=0, relief="flat", cursor="hand2")
            b.grid(row=r, column=c, sticky="nsew", padx=3, pady=3)

        # Compactar botones: usar símbolos y menos padding para que quepan
        try:
            overrides = {
                (0, 0): "Tara",
                (0, 1): "➕",
                (0, 2): "⏱",
                (1, 0): "↺",
                (1, 1): "✔",
                (1, 2): "⚙",
            }
            for child in btns.winfo_children():
                gi = child.grid_info(); key = (int(gi.get('row', 0)), int(gi.get('column', 0)))
                if key in overrides:
                    child.config(text=overrides[key], font=("DejaVu Sans", max(10, FS_BTN_SMALL-2), "bold"), padx=8, pady=8)
        except Exception:
            pass

        # Panel central (lista de alimentos)
        center = Card(self)
        center.grid(row=0, column=1, sticky="nsew", padx=6, pady=10)
        list_header = tk.Frame(center, bg=COL_CARD)
        list_header.pack(fill="x", padx=10, pady=(10, 5))
        tk.Label(list_header, text="Alimentos", bg=COL_CARD, fg=COL_ACCENT,
                 font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(side="left")
        self.item_count_label = tk.Label(list_header, text="0 items", bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT))
        self.item_count_label.pack(side="right")
        tree_frame = tk.Frame(center, bg=COL_CARD)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=5)
        style = ttk.Style(self); style.theme_use('clam')
        style.configure('Food.Treeview', background='#1a1f2e', foreground=COL_TEXT, fieldbackground='#1a1f2e', rowheight=28,
                        font=("DejaVu Sans", FS_LIST_ITEM))
        style.map('Food.Treeview', background=[('selected', '#2a3142')])
        style.configure('Food.Treeview.Heading', background=COL_CARD, foreground=COL_MUTED, font=("DejaVu Sans", FS_LIST_HEAD))
        self.tree = ttk.Treeview(tree_frame, columns=("item", "grams", "kcal"), show="headings", selectmode="browse", style='Food.Treeview')
        self.tree.heading("item", text="Alimento"); self.tree.column("item", width=200, anchor="w", stretch=True)
        self.tree.heading("grams", text="Peso"); self.tree.column("grams", width=80, anchor="center", stretch=False)
        self.tree.heading("kcal", text="Calorías"); self.tree.column("kcal", width=80, anchor="center", stretch=False)
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select_item)
        del_btn = tk.Button(center, text="Eliminar seleccionado", command=self._on_delete_selected,
                            bg=COL_DANGER, fg="white", font=("DejaVu Sans", FS_TEXT), bd=0, relief="flat", cursor="hand2")
        del_btn.pack(fill="x", padx=10, pady=(5, 10))

        # Panel derecho (totales + consejos)
        right = tk.Frame(self, bg=COL_BG)
        right.grid(row=0, column=2, sticky="nsew", padx=(6, 10), pady=10)
        right.grid_rowconfigure(1, weight=1)

        totals = Card(right); totals.pack(fill="x", pady=(0, 10))
        tk.Label(totals, text="Totales", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(padx=10, pady=(10, 5))
        grid = tk.Frame(totals, bg=COL_CARD); grid.pack(fill="x", padx=10, pady=10)
        self._nut_labels = {}
        for name, key, unit in [("Peso total", "grams", "g"), ("Calorías", "kcal", "kcal"), ("Carbohidratos", "carbs", "g"),
                                 ("Proteínas", "protein", "g"), ("Grasas", "fat", "g")]:
            row = tk.Frame(grid, bg=COL_CARD); row.pack(fill="x", pady=3)
            tk.Label(row, text=name, bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT)).pack(side="left")
            val = tk.Label(row, text="0", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT, "bold"))
            val.pack(side="right"); tk.Label(row, text=f" {unit}", bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT-1)).pack(side="right")
            self._nut_labels[key] = val

        tips = Card(right); tips.pack(fill="both", expand=True)
        tk.Label(tips, text="Consejos", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(padx=10, pady=(10, 5))
        self.tips_text = tk.Text(tips, bg="#1a1f2e", fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT-1), height=8, wrap="word", relief="flat", state="disabled")
        self.tips_text.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        self._update_tips("1) Coloca el recipiente vacío\n2) Presiona 'Tara' para poner a cero\n3) Añade alimentos uno por uno")

        self.toast = Toast(self)

    # --- lifecycle ---
    def on_show(self):
        if not self._tick_after:
            self._tick()

    def on_hide(self):
        if self._tick_after:
            self.after_cancel(self._tick_after)
            self._tick_after = None

    # --- actions ---
    def _on_tara(self):
        reader = self.app.get_reader()
        v = reader.get_latest() if reader else None
        if v is not None:
            self.app.get_tare().set_tare(v)
            self.toast.show("Tara establecida", 1000)
            self._update_tips("Tara en cero. Añade el alimento.")
        else:
            self.toast.show("Sin lectura de báscula", 1200, COL_WARN)

    def _on_add_item(self):
        self.toast.show("Capturando...", 900)

        def _bg():
            image_path = None
            try:
                weight = self.app.get_latest_weight()
                if hasattr(self.app, "ensure_camera") and self.app.ensure_camera():
                    image_path = self.app.capture_image()
                data = self.app.request_nutrition(image_path, weight)
            except Exception as e:
                self.after(0, lambda: self.toast.show(f"Error: {e}", 2000, COL_DANGER))
                return
            finally:
                if image_path:
                    try:
                        self.app.delete_image(image_path)
                    except Exception:
                        pass

            def _apply():
                self._add_item_from_data(data)
                self._recalc_totals()
                self.toast.show(f"{data.get('name','Alimento')} añadido", 1400, COL_SUCCESS)
            self.after(0, _apply)

        import threading
        threading.Thread(target=_bg, daemon=True).start()

    def _add_item_from_data(self, data):
        data = dict(data)
        data['id'] = self._next_id; self._next_id += 1
        self.items.append(data)
        self.tree.insert("", "end", iid=str(data['id']), values=(data.get('name', '?'), f"{data.get('grams', 0):.0f} g", f"{data.get('kcal', 0):.0f}"))

    def _on_select_item(self, _evt=None):
        sel = self.tree.selection()
        self._selection_id = sel[0] if sel else None

    def _on_delete_selected(self):
        if self._selection_id:
            try:
                self.tree.delete(self._selection_id)
            except Exception:
                pass
            self.items = [i for i in self.items if str(i.get('id')) != str(self._selection_id)]
            self._selection_id = None
            self._recalc_totals()
            self.toast.show("Elemento eliminado", 900)
        else:
            self.toast.show("Selecciona un elemento", 1100, COL_MUTED)

    def _on_reset_session(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.items.clear(); self._selection_id = None
        self._recalc_totals()
        self.toast.show("Sesión reiniciada", 900)

    def _on_timer_open(self):
        if self._timer_after:
            try:
                self.after_cancel(self._timer_after)
            except Exception:
                pass
            self._timer_after = None

        def apply_it():
            try:
                secs = max(1, int(var.get()))
            except Exception:
                secs = 60
            self._timer_remaining = secs
            self._schedule_timer_tick()

        var = tk.StringVar(value="60")
        KeypadPopup(self, title="Segundos (1-3600)", initial=var.get(), allow_dot=False,
                    on_accept=lambda v: (var.set(v), apply_it()))

    def _schedule_timer_tick(self):
        if self._timer_after:
            self.after_cancel(self._timer_after)
        self._timer_after = self.after(1000, self._timer_tick)

    def _timer_tick(self):
        self._timer_remaining -= 1
        if self._timer_remaining <= 0:
            self.timer_label.configure(text="Tiempo!")
            self.toast.show("Tiempo finalizado", 1500)
            if hasattr(self.app, 'get_audio') and self.app.get_audio():
                self.app.get_audio().play_event('timer_done')
            self.after(3000, lambda: self.timer_label.configure(text=""))
            return
        self.timer_label.configure(text=f"{self._fmt_sec(self._timer_remaining)}")
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
        modal = tk.Toplevel(self); modal.configure(bg=COL_BG)
        modal.attributes("-topmost", True); modal.overrideredirect(True); modal.update_idletasks()
        w, h = 520, 420
        x = (modal.winfo_screenwidth() - w) // 2; y = (modal.winfo_screenheight() - h) // 2
        modal.geometry(f"{w}x{h}+{x}+{y}"); modal.grab_set()
        cont = Card(modal); cont.pack(fill="both", expand=True, padx=20, pady=20)
        tk.Label(cont, text="Resumen Nutricional", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(pady=(5, 10))
        body = tk.Frame(cont, bg=COL_CARD); body.pack(fill="both", expand=True, padx=15)
        rows = [("Peso total", totals['grams'], 'g'), ("Calorías", totals['kcal'], 'kcal'), ("Carbohidratos", totals['carbs'], 'g'),
                ("Proteínas", totals['protein'], 'g'), ("Grasas", totals['fat'], 'g')]
        for label, value, unit in rows:
            r = tk.Frame(body, bg=COL_CARD); r.pack(fill="x", pady=4)
            tk.Label(r, text=label, bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT)).pack(side="left")
            tk.Label(r, text=f"{value:.0f} {unit}", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT, "bold")).pack(side="right")
        btns = tk.Frame(cont, bg=COL_CARD); btns.pack(fill="x", pady=(10, 5))
        tk.Button(btns, text="Cerrar", command=modal.destroy, bg=COL_BORDER, fg=COL_TEXT,
                  font=("DejaVu Sans", FS_BTN_SMALL), bd=0, relief="flat", cursor="hand2").pack(side="left", padx=5)
        tk.Button(btns, text="Reiniciar sesión", command=lambda: (self._on_reset_session(), modal.destroy()),
                  bg="#3b82f6", fg="white", font=("DejaVu Sans", FS_BTN_SMALL, "bold"), bd=0, relief="flat", cursor="hand2").pack(side="right", padx=5)

    # --- helpers ---
    def _update_tips(self, text: str):
        self.tips_text.config(state="normal")
        self.tips_text.delete(1.0, "end")
        self.tips_text.insert(1.0, text)
        self.tips_text.config(state="disabled")

    def _tick(self):
        net_weight = self.app.get_latest_weight()
        decimals = int(self.app.get_cfg().get('decimals', 0) or 0)
        try:
            self.weight_lbl.config(text=f"{net_weight:.{decimals}f} g")
        except Exception:
            # Fallback si el formato da error
            self.weight_lbl.config(text=f"{net_weight:.2f} g")
        # Ajuste de fuente por cambio de cifras (evita corte de la 'g')
        try:
            if hasattr(self.weight_lbl, "_fit_text"):
                self.weight_lbl._fit_text()
        except Exception:
            pass
        # Estabilidad: simple ventana deslizante
        self._wbuf.append(net_weight)
        thr = 1.0
        is_stable = (len(self._wbuf) >= 3) and ((max(self._wbuf) - min(self._wbuf)) < thr)
        if is_stable != self._stable:
            self._stable = is_stable
            self.stability_label.config(text=("Estable" if is_stable else "Midiendo..."), fg=(COL_SUCCESS if is_stable else COL_WARN))
        self.item_count_label.config(text=f"{len(self.items)} items")
        self._tick_after = self.after(100, self._tick)

    def _recalc_totals(self):
        grams = sum(i.get('grams', 0) for i in self.items)
        kcal = sum(i.get('kcal', 0) for i in self.items)
        carbs = sum(i.get('carbs', 0) for i in self.items)
        protein = sum(i.get('protein', 0) for i in self.items)
        fat = sum(i.get('fat', 0) for i in self.items)
        vals = {'grams': grams, 'kcal': kcal, 'carbs': carbs, 'protein': protein, 'fat': fat}
        for k, v in vals.items():
            if k in self._nut_labels:
                self._nut_labels[k].config(text=f"{v:.0f}")


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
        v = self._promedio(); self._b0 = v
        if v is not None:
            self.toast.show(f"Cero: {v:.2f}", 1200)

    def _cap_con_peso(self):
        v = self._promedio(); self._bw = v
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

