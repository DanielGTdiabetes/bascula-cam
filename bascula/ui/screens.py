# -*- coding: utf-8 -*-
"""
Pantallas base (Home + Calibración) con UI limpia y estable.
"""
import tkinter as tk
import os, json, time
from tkinter import ttk
from collections import deque
from bascula.ui.widgets import *  # Card, BigButton, GhostButton, Toast, bind_numeric_popup, ScrollingBanner
from bascula.domain.foods import Food, load_foods

# Alturas fijas para evitar "bombeo" por reflow del área de peso:
WEIGHT_CARD_HEIGHT = 260   # px (ajustable si quieres más/menos alto)
WEIGHT_DISPLAY_HEIGHT = 240  # px (ligeramente menor para dejar margen interior)


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


def _safe_audio_icon(cfg: dict) -> str:
    try:
        no_emoji = bool(cfg.get('no_emoji', False)) or bool(os.environ.get('BASCULA_NO_EMOJI'))
        enabled = bool(cfg.get('sound_enabled', True))
    except Exception:
        no_emoji = bool(os.environ.get('BASCULA_NO_EMOJI'))
        enabled = True
    if no_emoji:
        return 'ON' if enabled else 'OFF'
    return '🔊' if enabled else '🔇'


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
        # BG (glucosa)
        self._bg_after = None
        self._last_bg_zone = None
        self._bg_snooze_until = 0
        self._last_detection = None
        try:
            self._detection_active = bool(self.app.get_cfg().get('vision_autosuggest_enabled', False))
        except Exception:
            self._detection_active = False
        self._foods = []
        self._vision_aliases = {}

        # Hacemos _fit_text() del peso solo una vez para evitar reflow con 2 decimales
        self._did_fit_weight = False

        # Layout principal: 2 columnas (peso, nutrición + lista)
        self.grid_columnconfigure(0, weight=4, minsize=get_scaled_size(360))
        self.grid_columnconfigure(1, weight=5)
        self.grid_rowconfigure(0, weight=1)

        # Panel izquierdo (peso + controles)
        left = tk.Frame(self, bg=COL_BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(10, 6), pady=10)
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        # Header
        header = tk.Frame(left, bg=COL_BG)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        tk.Label(
            header,
            text="PESO",  # <--- CAMBIO solicitado
            bg=COL_BG, fg=COL_TEXT,
            font=("DejaVu Sans", FS_TITLE, "bold")
        ).pack(side="left", padx=8)
        self.audio_btn = tk.Button(
            header, text=_safe_audio_icon(self.app.get_cfg()), command=self._toggle_audio,
            bg=COL_BG, fg=COL_TEXT, bd=0, relief="flat", cursor="hand2",
            font=("DejaVu Sans", 12, "bold"), highlightthickness=0, width=3
        )
        self.audio_btn.pack(side="right", padx=(0, 4))
        initial_bg = "" if not bool(self.app.get_cfg().get('diabetic_mode', False)) else "BG N/D"
        self.bg_label = tk.Label(header, text=initial_bg, bg=COL_BG, fg=COL_MUTED, font=("DejaVu Sans", 12, "bold"))
        self.bg_label.pack(side="right", padx=(0, 8))
        self.timer_label = tk.Label(header, text="", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", 11))
        self.timer_label.pack(side="right")
        try:
            GhostButton(header, text='Snooze', micro=True, command=self._bg_snooze).pack(side='right', padx=(0,6))
        except Exception:
            pass

        # Peso actual (con alturas fijas para eliminar 'bombeo')
        weight_card = Card(left)
        weight_card.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        # Forzar altura fija del card y evitar que los hijos lo cambien
        weight_card.configure(height=WEIGHT_CARD_HEIGHT)
        weight_card.pack_propagate(False)

        weight_display = tk.Frame(weight_card, bg="#0f1420", relief="sunken", bd=1)
        weight_display.pack(fill="both", expand=True, padx=10, pady=10)
        # Fijamos altura interna y evitamos propagación
        weight_display.configure(height=WEIGHT_DISPLAY_HEIGHT)
        weight_display.pack_propagate(False)

        self.weight_lbl = WeightLabel(weight_display, bg="#0f1420", fg=COL_ACCENT)
        # No cambiamos fuente; mantenemos anclaje centrado
        self.weight_lbl.pack(fill="both", expand=True, padx=(12, 4), pady=4)
        self.weight_lbl.configure(anchor="center")

        self.stability_label = tk.Label(
            weight_display,
            text="Esperando...",
            bg="#0f1420", fg=COL_MUTED,
            font=("DejaVu Sans", FS_TEXT)
        )
        self.stability_label.pack(pady=(0, 10))

        # Botones principales
        btns = tk.Frame(left, bg=COL_BG)
        btns.grid(row=2, column=0, sticky="ew")
        for i in range(3):
            btns.grid_rowconfigure(i, weight=1)
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
            b = BigButton(btns, text=text, command=cmd, bg=color, small=True)
            b.grid(row=r, column=c, sticky="nsew", padx=3, pady=3)

        # Nueva acción: modo Recetas (fila extra)
        try:
            rb = BigButton(btns, text="🍳 Recetas", command=self._open_recipes, bg="#3b82f6", small=True)
            rb.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=3, pady=(6, 3))
        except Exception:
            pass

        # Sugerencia proactiva (IA Visión)
        self.suggestion_frame = tk.Frame(left, bg=COL_BG)
        self.suggestion_frame.grid(row=3, column=0, sticky='ew', pady=4)

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
                gi = child.grid_info()
                key = (int(gi.get('row', 0)), int(gi.get('column', 0)))
                if key in overrides:
                    child.config(text=overrides[key], font=("DejaVu Sans", max(10, FS_BTN_SMALL - 2), "bold"))
        except Exception:
            pass

        # --- Panel derecho ---
        right = tk.Frame(self, bg=COL_BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 10), pady=10)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=0)  # banner, altura fija
        right.grid_rowconfigure(2, weight=1)  # lista de alimentos

        # Panel superior para Totales
        top_right_frame = tk.Frame(right, bg=COL_BG)
        top_right_frame.grid(row=0, column=0, sticky="new")
        top_right_frame.grid_columnconfigure(0, weight=1)

        # Totales
        totals = Card(top_right_frame)
        totals.grid(row=0, column=0, sticky="nsew", padx=(0, 6))  # Ocupa todo el ancho
        tk.Label(
            totals, text="Totales", bg=COL_CARD, fg=COL_ACCENT,
            font=("DejaVu Sans", FS_CARD_TITLE, "bold")
        ).pack(padx=10, pady=(10, 5), anchor="w")

        totals_grid = tk.Frame(totals, bg=COL_CARD)
        totals_grid.pack(fill="x", padx=10, pady=5)
        totals_grid.grid_columnconfigure(0, weight=1)
        totals_grid.grid_columnconfigure(1, minsize=60)
        totals_grid.grid_columnconfigure(2, weight=0)

        self._nut_labels = {}
        nut_items = [
            ("Peso total", "grams", "g"),
            ("Calorías", "kcal", "kcal"),
            ("Carbohidratos", "carbs", "g"),
            ("Proteínas", "protein", "g"),
            ("Grasas", "fat", "g"),
        ]

        for i, (name, key, unit) in enumerate(nut_items):
            tk.Label(totals_grid, text=name, bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT)).grid(
                row=i, column=0, sticky="w", pady=1
            )
            val_label = tk.Label(
                totals_grid, text="0", bg=COL_CARD, fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT, "bold"), anchor="e"
            )
            val_label.grid(row=i, column=1, sticky="e", padx=4)
            tk.Label(totals_grid, text=unit, bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT - 1)).grid(
                row=i, column=2, sticky="w"
            )
            self._nut_labels[key] = val_label

        # ---------------------------
        # Banner de consejos (altura fija 18 px, misma fuente)
        # ---------------------------
        tips_banner_card = Card(right)
        tips_banner_card.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        tips_banner_card.configure(height=18)
        tips_banner_card.pack_propagate(False)

        _bnr_wrap = tk.Frame(tips_banner_card, bg=COL_CARD)
        _bnr_wrap.pack(fill="both", expand=True, padx=2, pady=0)

        self.tips_banner = ScrollingBanner(_bnr_wrap, bg=COL_CARD)
        self.tips_banner.pack(fill="x", expand=True)

        # Panel de alimentos (debajo de totales y banner)
        center = Card(right)
        center.grid(row=2, column=0, sticky="nsew", pady=(10, 0))  # Fila 2
        list_header = tk.Frame(center, bg=COL_CARD)
        list_header.pack(fill="x", padx=10, pady=(10, 5))
        tk.Label(list_header, text="Alimentos", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(
            side="left"
        )
        self.item_count_label = tk.Label(list_header, text="0 items", bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT))
        self.item_count_label.pack(side="right")
        tree_frame = tk.Frame(center, bg=COL_CARD)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=5)
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure(
            'Food.Treeview',
            background='#1a1f2e', foreground=COL_TEXT,
            fieldbackground='#1a1f2e', rowheight=28,
            font=("DejaVu Sans", FS_LIST_ITEM)
        )
        style.map('Food.Treeview', background=[('selected', '#2a3142')])
        style.configure('Food.Treeview.Heading', background=COL_CARD, foreground=COL_MUTED, font=("DejaVu Sans", FS_LIST_HEAD))
        self.tree = ttk.Treeview(
            tree_frame,
            columns=("item", "grams", "kcal", "carbs", "protein", "fat"),
            show="headings", selectmode="browse", style='Food.Treeview'
        )
        self.tree.heading("item", text="Alimento"); self.tree.column("item", width=180, anchor="w", stretch=True)
        self.tree.heading("grams", text="Peso"); self.tree.column("grams", width=70, anchor="center")
        # ---- Abreviaciones solicitadas + más ancho para que quepa bien ----
        self.tree.heading("kcal", text="Kcal"); self.tree.column("kcal", width=85, anchor="center")
        self.tree.heading("carbs", text="Carbs"); self.tree.column("carbs", width=70, anchor="center")
        self.tree.heading("protein", text="Prot."); self.tree.column("protein", width=85, anchor="center")
        self.tree.heading("fat", text="Grasas"); self.tree.column("fat", width=70, anchor="center")
        # -------------------------------------------------------------------
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select_item)
        del_btn = tk.Button(
            center, text="Eliminar seleccionado", command=self._on_delete_selected,
            bg=COL_DANGER, fg="white", font=("DejaVu Sans", FS_TEXT), bd=0, relief="flat", cursor="hand2"
        )
        del_btn.pack(fill="x", padx=10, pady=(5, 10))

        self._update_tips("1) Coloca recipiente, 2) Pulsa 'Tara', 3) Añade alimento")
        self.toast = Toast(self)

        # Overlays adicionales
        try:
            from bascula.ui.overlay_recipe import RecipeOverlay
            self._ov_recipe = RecipeOverlay(self, self.app)
        except Exception:
            self._ov_recipe = None

    # --- lifecycle ---
    def on_show(self):
        if not self._tick_after:
            self._tick()
        self._start_bg_poll()
        try:
            if not self._foods:
                self._foods = load_foods()
        except Exception:
            self._foods = []
        # Cargar alias de visión si existen
        try:
            from pathlib import Path as _P
            _p = _P.home() / '.config' / 'bascula' / 'vision_aliases.json'
            if _p.exists():
                import json as _json
                self._vision_aliases = _json.loads(_p.read_text(encoding='utf-8')) or {}
            else:
                self._vision_aliases = {}
        except Exception:
            self._vision_aliases = {}
        try:
            if self._detection_active:
                self.after(800, self._detection_loop)
        except Exception:
            pass

    def on_hide(self):
        if self._tick_after:
            self.after_cancel(self._tick_after)
            self._tick_after = None
        if self._bg_after:
            try:
                self.after_cancel(self._bg_after)
            except Exception:
                pass
            self._bg_after = None

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
        self.tree.insert("", "end", iid=str(data['id']), values=(
            data.get('name', '?'),
            f"{data.get('grams', 0):.0f}g",
            f"{data.get('kcal', 0):.0f}",
            f"{data.get('carbs', 0):.1f}",
            f"{data.get('protein', 0):.1f}",
            f"{data.get('fat', 0):.1f}"
        ))

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
        self.items.clear()
        self._selection_id = None
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
            au = getattr(self.app, 'get_audio', lambda: None)()
            if au:
                try:
                    au.play_event('timer_done')
                except Exception:
                    pass
            self.after(3000, lambda: self.timer_label.configure(text=""))
            return
        self.timer_label.configure(text=f"{self._fmt_sec(self._timer_remaining)}")
        self._schedule_timer_tick()

    def _fmt_sec(self, s: int) -> str:
        m, ss = divmod(max(0, int(s)), 60)
        return f"{m:02d}:{ss:02d}"

    # --- Recetas ---
    def _open_recipes(self):
        if getattr(self, '_ov_recipe', None) is None:
            try:
                from bascula.ui.overlay_recipe import RecipeOverlay
                self._ov_recipe = RecipeOverlay(self, self.app)
            except Exception:
                self.toast.show("Recetas no disponibles", 1400, COL_WARN)
                return

        # Popup to query/generate or open saved
        top = tk.Toplevel(self)
        try: top.attributes('-topmost', True)
        except Exception: pass
        top.transient(self.winfo_toplevel()); top.configure(bg=COL_BG)
        card = Card(top, min_width=480, min_height=200)
        card.pack(fill='both', expand=True, padx=10, pady=10)
        tk.Label(card, text='Modo Recetas', bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_TITLE, 'bold')).pack(anchor='w', padx=8, pady=(8, 4))
        tk.Label(card, text='¿Qué te apetece cocinar?', bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT)).pack(anchor='w', padx=8)
        var_q = tk.StringVar(value='Pollo al curry')
        ent = tk.Entry(card, textvariable=var_q, bg=COL_CARD_HOVER, fg=COL_TEXT, insertbackground=COL_TEXT,
                       relief='flat', font=("DejaVu Sans", FS_TEXT))
        ent.pack(fill='x', padx=8, pady=8)
        btns = tk.Frame(card, bg=COL_CARD); btns.pack(fill='x', pady=(4, 8))

        def _voice_query():
            try:
                v = getattr(self.app, 'get_voice', lambda: None)()
                if v is None:
                    raise RuntimeError('no voice')
                def _got(t: str):
                    try:
                        self.after(0, lambda: var_q.set((t or '').strip()))
                    except Exception:
                        pass
                v.start_listening(on_text=_got, duration=4)
            except Exception:
                pass

        def _gen():
            q = (var_q.get() or '').strip()
            api_key = (self.app.get_cfg() or {}).get('openai_api_key')
            self._ov_recipe.generate_and_set(q, servings=2, api_key=api_key)
            self._ov_recipe.show()
            top.destroy()

        def _open_saved():
            self._ov_recipe.show()
            try:
                self._ov_recipe._open_saved_popup()
            except Exception:
                pass
            top.destroy()

        BigButton(btns, text='Generar con IA', command=_gen, bg=COL_ACCENT, small=True).pack(side='left', expand=True, fill='x', padx=4)
        GhostButton(btns, text='🎤 Voz', command=_voice_query, micro=True).pack(side='left', padx=4)
        GhostButton(btns, text='Abrir guardada…', command=_open_saved, micro=True).pack(side='left', padx=4)
        GhostButton(btns, text='Cancelar', command=top.destroy, micro=True).pack(side='right', padx=4)

    def _audio_icon(self) -> str:
        return _safe_audio_icon(self.app.get_cfg())

    def _toggle_audio(self):
        try:
            cfg = self.app.get_cfg()
            new_en = not bool(cfg.get('sound_enabled', True))
            cfg['sound_enabled'] = new_en
            self.app.save_cfg()
            if hasattr(self.app, 'get_audio') and self.app.get_audio():
                self.app.get_audio().set_enabled(new_en)
            if hasattr(self, 'audio_btn'):
                self.audio_btn.config(text=self._audio_icon())
            self.toast.show("Sonido: " + ("ON" if new_en else "OFF"), 900)
        except Exception:
            pass

    def _read_ns_cfg(self):
        try:
            from pathlib import Path
            _cfg_env = os.environ.get('BASCULA_CFG_DIR', '').strip()
            cfg_dir = Path(_cfg_env) if _cfg_env else (Path.home() / '.config' / 'bascula')
            p = cfg_dir / 'nightscout.json'
            if p.exists():
                return json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            pass
        return {}

    def _ns_enabled(self):
        try:
            return bool(self.app.get_cfg().get('diabetic_mode', False))
        except Exception:
            return False
    
    def _bg_snooze(self):
        try:
            mins = int(self.app.get_cfg().get('bg_snooze_minutes', 15) or 15)
        except Exception:
            mins = 15
        self._bg_snooze_until = time.time() + (max(1, mins) * 60)
        try:
            self.toast.show(f"BG snooze {mins} min", 1200)
        except Exception:
            pass

    def _bg_is_dnd_active(self, cfg: dict) -> bool:
        try:
            if not bool(cfg.get('bg_dnd_enabled', False)):
                return False
            start = str(cfg.get('bg_dnd_start', '22:00'))
            end = str(cfg.get('bg_dnd_end', '07:00'))
            def _hm(x):
                try:
                    hh, mm = x.split(':'); return (int(hh) % 24) * 60 + (int(mm) % 60)
                except Exception:
                    return 0
            now = time.localtime()
            cur = now.tm_hour * 60 + now.tm_min
            s = _hm(start); e = _hm(end)
            if s == e:
                return False
            if s < e:
                return s <= cur < e
            # overnight window
            return cur >= s or cur < e
        except Exception:
            return False

    def _start_bg_poll(self):
        if not self._ns_enabled():
            self.bg_label.config(text="", fg=COL_MUTED)
            return
        self._poll_bg()

    def _zone_for_bg(self, mgdl: float):
        try:
            v = float(mgdl)
        except Exception:
            return 'nd'
        try:
            cfg = self.app.get_cfg() or {}
            low = float(cfg.get('bg_low_threshold', 70))
            warn = float(cfg.get('bg_warn_threshold', 180))
            high = float(cfg.get('bg_high_threshold', 250))
        except Exception:
            low, warn, high = 70.0, 180.0, 250.0
        if v < low:
            return 'low'
        if v > high:
            return 'high'
        if v > warn:
            return 'warn'
        return 'ok'

    def _color_for_zone(self, zone: str):
        return {'low': COL_DANGER, 'high': COL_DANGER, 'warn': COL_WARN, 'ok': COL_SUCCESS}.get(zone, COL_MUTED)

    def _poll_bg(self):
        if self._bg_after:
            try:
                self.after_cancel(self._bg_after)
            except Exception:
                pass
            self._bg_after = None
        if not self._ns_enabled():
            return

        data = self._read_ns_cfg()
        url = (data.get('url') or '').strip().rstrip('/')
        token = (data.get('token') or '').strip()
        if not url:
            self.bg_label.config(text="", fg=COL_MUTED)
            self._bg_after = self.after(60000, self._poll_bg)
            return

        def work():
            try:
                import requests
                mgdl = None
                direction = None
                params = {'count': 1}
                if token:
                    params['token'] = token
                r = requests.get(f"{url}/api/v1/entries.json", params=params, timeout=4)
                if r.ok:
                    j = r.json()
                    if isinstance(j, list) and j:
                        e = j[0]
                        mgdl = e.get('sgv') or e.get('glucose') or e.get('mgdl')
                        direction = e.get('direction')

                def apply():
                    if mgdl is None:
                        self.bg_label.config(text="", fg=COL_MUTED)
                    else:
                        zone = self._zone_for_bg(mgdl)
                        col = self._color_for_zone(zone)
                        arrow = {
                            'DoubleUp': '↑↑', 'SingleUp': '↑', 'FortyFiveUp': '↗',
                            'Flat': '→', 'FortyFiveDown': '↘', 'SingleDown': '↓', 'DoubleDown': '↓↓'
                        }.get(direction or 'Flat', '')
                        try:
                            txt = f"BG {int(float(mgdl))} mg/dL {arrow}".strip()
                        except Exception:
                            txt = f"BG {mgdl} mg/dL {arrow}".strip()
                        self.bg_label.config(text=txt, fg=col)

                        au = getattr(self.app, 'get_audio', lambda: None)()
                        cfg = self.app.get_cfg() or {}
                        alerts_on = bool(cfg.get('bg_alerts_enabled', True))
                        ann_on_alert = bool(cfg.get('bg_announce_on_alert', True))
                        ann_every = bool(cfg.get('bg_announce_every', False))
                        # DND + Snooze gating
                        snoozed = time.time() < getattr(self, '_bg_snooze_until', 0)
                        dnd_active = self._bg_is_dnd_active(cfg)
                        allow_low = bool(cfg.get('bg_dnd_allow_low_override', True))
                        dnd_mute = dnd_active and not (allow_low and zone == 'low')
                        if alerts_on and not snoozed and not dnd_mute and zone in ('low', 'high') and zone != self._last_bg_zone and au:
                            try:
                                au.play_event('bg_low' if zone == 'low' else 'bg_high')
                            except Exception:
                                pass
                        if au:
                            try:
                                voice_on = bool(cfg.get('voice_enabled', False))
                                announce_allowed = (not snoozed) and (not dnd_active or (allow_low and zone == 'low'))
                                if voice_on and announce_allowed and (ann_every or (ann_on_alert and zone != self._last_bg_zone and zone in ('low','high','warn'))):
                                    au.speak_event('announce_bg', n=int(float(mgdl)))
                            except Exception:
                                pass
                        self._last_bg_zone = zone

                    self._bg_after = self.after(60000, self._poll_bg)

                self.after(0, apply)
            except Exception:
                self.after(0, lambda: (
                    self.bg_label.config(text="", fg=COL_MUTED),
                    setattr(self, '_bg_after', self.after(60000, self._poll_bg))
                ))

        import threading
        threading.Thread(target=work, daemon=True).start()

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
        # --- Voz: anunciar totales si la voz BG está activada ---
        try:
            cfg = self.app.get_cfg() or {}
            if bool(cfg.get('voice_enabled', False)):
                au = getattr(self.app, 'get_audio', lambda: None)()
                if au and hasattr(au, 'speak_event'):
                    au.speak_event('meal_totals',
                                   g=int(totals['grams'] or 0),
                                   k=int(totals['kcal'] or 0),
                                   c=int(totals['carbs'] or 0),
                                   p=int(totals['protein'] or 0),
                                   f=int(totals['fat'] or 0))
        except Exception:
            pass

        modal = tk.Toplevel(self)
        modal.configure(bg=COL_BG)
        modal.attributes("-topmost", True)
        modal.overrideredirect(True)
        modal.update_idletasks()
        w, h = 520, 420
        x = (modal.winfo_screenwidth() - w) // 2
        y = (modal.winfo_screenheight() - h) // 2
        modal.geometry(f"{w}x{h}+{x}+{y}")
        modal.grab_set()
        cont = Card(modal)
        cont.pack(fill="both", expand=True, padx=20, pady=20)
        tk.Label(cont, text="Resumen Nutricional", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(
            pady=(5, 10)
        )
        body = tk.Frame(cont, bg=COL_CARD)
        body.pack(fill="both", expand=True, padx=15)
        rows = [
            ("Peso total", totals['grams'], 'g'),
            ("Calorías", totals['kcal'], 'kcal'),
            ("Carbohidratos", totals['carbs'], 'g'),
            ("Proteínas", totals['protein'], 'g'),
            ("Grasas", totals['fat'], 'g'),
        ]
        for label, value, unit in rows:
            r = tk.Frame(body, bg=COL_CARD)
            r.pack(fill="x", pady=4)
            tk.Label(r, text=label, bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT)).pack(side="left")
            tk.Label(r, text=f"{value:.0f} {unit}", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT, "bold")).pack(side="right")

        # Opción: enviar a Nightscout
        ns_row = tk.Frame(cont, bg=COL_CARD)
        ns_row.pack(fill='x', pady=(4, 2))
        self._var_send_ns = tk.BooleanVar(value=bool(self.app.get_cfg().get('send_to_ns_default', False)))
        tk.Checkbutton(ns_row, text='Enviar a Nightscout', variable=self._var_send_ns,
                       bg=COL_CARD, fg=COL_TEXT, selectcolor=COL_CARD, activebackground=COL_CARD,
                       font=("DejaVu Sans", FS_TEXT)).pack(anchor='w', padx=10)
        # Acciones
        def _save_meal():
            try:
                from pathlib import Path
                import json, datetime, uuid
                base = Path.home() / '.config' / 'bascula'
                base.mkdir(parents=True, exist_ok=True)
                p = base / 'meals.jsonl'
                meal = {
                    'id': uuid.uuid4().hex,
                    'created_at': datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
                    'items': self.items,
                    'totals': {k: float(v) for k, v in totals.items()},
                }
                with open(p, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(meal, ensure_ascii=False) + "\n")
                try:
                    from bascula.services.retention import prune_jsonl
                    cfg = self.app.get_cfg() or {}
                    prune_jsonl(p,
                               max_days=int(cfg.get('meals_max_days', 180) or 0),
                               max_entries=int(cfg.get('meals_max_entries', 1000) or 0),
                               max_bytes=int(cfg.get('meals_max_bytes', 5_000_000) or 0))
                except Exception:
                    pass

                # Enviar a Nightscout si procede
                try:
                    if bool(self._var_send_ns.get()):
                        ns_cfg_path = base / 'nightscout.json'
                        if ns_cfg_path.exists():
                            ns_cfg = json.loads(ns_cfg_path.read_text(encoding='utf-8'))
                            url = (ns_cfg.get('url') or '').strip()
                            token = (ns_cfg.get('token') or '').strip()
                        else:
                            url = ''
                            token = ''
                        # Payload básico de tratamiento tipo Meal (carbs)
                        payload = {
                            'eventType': 'Meal',
                            'carbs': float(totals['carbs'] or 0),
                            'created_at': meal['created_at'],
                            'notes': f"BasculaCam: kcal={int(totals['kcal'] or 0)}, prot={int(totals['protein'] or 0)}, fat={int(totals['fat'] or 0)}",
                            'enteredBy': 'BasculaCam',
                            'externalId': f"meal:{meal['id']}",
                        }
                        try:
                            from bascula.services.treatments import post_treatment
                            ok = post_treatment(url, token, payload)
                            if ok:
                                self.toast.show('Enviado a Nightscout', 1000, COL_SUCCESS)
                            else:
                                self.toast.show('Encolado para Nightscout', 1200, COL_WARN)
                        except Exception:
                            self.toast.show('Error enviando a Nightscout', 1400, COL_WARN)
                except Exception:
                    pass
                self.toast.show('Comida guardada', 1100, COL_SUCCESS)
            except Exception as e:
                self.toast.show(f'Error al guardar: {e}', 1600, COL_DANGER)

        btns = tk.Frame(cont, bg=COL_CARD)
        btns.pack(fill="x", pady=(10, 5))
        tk.Button(
            btns, text="Cerrar", command=modal.destroy, bg=COL_BORDER, fg=COL_TEXT,
            font=("DejaVu Sans", FS_BTN_SMALL), bd=0, relief="flat", cursor="hand2"
        ).pack(side="left", padx=5)
        tk.Button(
            btns, text="Guardar comida", command=_save_meal,
            bg=COL_ACCENT, fg="white", font=("DejaVu Sans", FS_BTN_SMALL, "bold"), bd=0, relief="flat", cursor="hand2"
        ).pack(side="left", padx=5)
        tk.Button(
            btns, text="Reiniciar sesión", command=lambda: (self._on_reset_session(), modal.destroy()),
            bg="#3b82f6", fg="white", font=("DejaVu Sans", FS_BTN_SMALL, "bold"), bd=0, relief="flat", cursor="hand2"
        ).pack(side="right", padx=5)

    def _update_tips(self, text: str):
        self.tips_banner.set_text(text.replace('\n', ' '))

    def _tick(self):
        net_weight = self.app.get_latest_weight()
        decimals = int(self.app.get_cfg().get('decimals', 0) or 0)
        if decimals > 1:
            decimals = 1
        try:
            self.weight_lbl.config(text=f"{net_weight:.{decimals}f}g")
        except Exception:
            self.weight_lbl.config(text=f"{net_weight:.2f}g")

        # Auto-fit solo la primera vez que se pinta
        try:
            if not self._did_fit_weight and hasattr(self.weight_lbl, "_fit_text"):
                self.weight_lbl._fit_text()
                self._did_fit_weight = True
        except Exception:
            pass

        self._wbuf.append(net_weight)
        thr = 1.0
        is_stable = (len(self._wbuf) >= 3) and ((max(self._wbuf) - min(self._wbuf)) < thr)
        if is_stable != self._stable:
            self._stable = is_stable
            self.stability_label.config(text=("Estable" if is_stable else "Midiendo..."), fg=(COL_SUCCESS if is_stable else COL_WARN))
            if not is_stable:
                self._clear_suggestion()
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

    # --- Visión proactiva (clasificación TFLite) ---
    def _detection_loop(self):
        try:
            if not self._detection_active:
                return
            vs = getattr(self.app, 'vision_service', None)
            cam = getattr(self.app, 'camera', None)
            if not vs or not cam:
                self.after(1500, self._detection_loop)
                return
            min_w = 0.0
            try:
                min_w = float(self.app.get_cfg().get('vision_min_weight_g', 20) or 20)
            except Exception:
                min_w = 20.0
            if self._stable and self.app.get_latest_weight() >= min_w:
                img = cam.grab_frame() if hasattr(cam, 'grab_frame') else None
                if img is not None:
                    res = vs.classify_image(img)
                    if res and res != self._last_detection:
                        self._last_detection = res
                        label, _ = res
                        self._show_suggestion(label)
            self.after(800, self._detection_loop)
        except Exception:
            try:
                self.after(1200, self._detection_loop)
            except Exception:
                pass

    def _clear_suggestion(self):
        try:
            for w in list(self.suggestion_frame.winfo_children()):
                w.destroy()
        except Exception:
            pass

    def _show_suggestion(self, label: str):
        self._clear_suggestion()
        food = self._find_food_by_name(label)
        if not food:
            return
        def _add():
            try:
                weight = max(0.0, float(self.app.get_latest_weight()))
            except Exception:
                weight = 0.0
            if weight <= 0.0:
                return
            data = {
                'name': food.name,
                'grams': weight,
                'kcal': (food.kcal / 100.0) * weight,
                'carbs': (food.carbs / 100.0) * weight,
                'protein': (food.protein / 100.0) * weight,
                'fat': (food.fat / 100.0) * weight,
            }
            self._add_item_from_data(data)
            self._recalc_totals()
            try:
                self.toast.show(f"{food.name} añadido", 1400, COL_SUCCESS)
            except Exception:
                pass
            self._clear_suggestion()
        try:
            txt = f"¿Añadir {food.name}?"
            BigButton(self.suggestion_frame, text=txt, command=_add, bg=COL_ACCENT, small=True).pack(fill='x')
        except Exception:
            pass

    def _find_food_by_name(self, name: str):
        # Aplicar alias si está configurado
        raw = (name or '').strip()
        alias = None
        try:
            alias = (self._vision_aliases.get(raw.lower()) or self._vision_aliases.get(raw)) if isinstance(self._vision_aliases, dict) else None
        except Exception:
            alias = None
        n = (str(alias or raw)).strip().lower()
        if not n:
            return None
        # Prefer exact/startswith
        for f in (self._foods or []):
            try:
                fn = f.name.lower()
                if fn.startswith(n) or n.startswith(fn):
                    return f
            except Exception:
                pass
        for f in (self._foods or []):
            try:
                fn = f.name.lower()
                if n in fn or fn in n:
                    return f
            except Exception:
                pass
        return None


class CalibScreen(BaseScreen):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG)
        header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="Calibración", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(
            side="left", padx=14
        )
        GhostButton(header, text="< Atrás", command=lambda: self.app.show_screen('settingsmenu'), micro=True).pack(
            side="right", padx=14
        )
        try:
            btn_audio = tk.Button(
                header,
                text=_safe_audio_icon(self.app.get_cfg()),
                command=lambda: self._toggle_audio_from_header(btn_audio),
                bg=COL_BG, fg=COL_TEXT, bd=0, relief="flat", cursor="hand2",
                font=("DejaVu Sans", 12, "bold"), highlightthickness=0, width=3
            )
            btn_audio.pack(side="right", padx=(0, 6))
        except Exception:
            pass

        body = Card(self)
        body.pack(fill="both", expand=True, padx=14, pady=10)
        live = tk.Frame(body, bg="#1a1f2e", highlightbackground=COL_BORDER, highlightthickness=1)
        live.pack(fill="x", pady=6, padx=6)
        tk.Label(live, text="Lectura actual:", bg="#1a1f2e", fg=COL_TEXT).pack(side="left", padx=8, pady=6)
        self.lbl_live = tk.Label(live, text="-", bg="#1a1f2e", fg=COL_TEXT)
        self.lbl_live.pack(side="left", pady=6)

        caprow = tk.Frame(body, bg=COL_CARD)
        caprow.pack(fill="x", pady=6)
        self._b0, self._bw = None, None
        GhostButton(caprow, text="Capturar cero", command=self._cap_cero, micro=True).pack(side="left", padx=4)
        GhostButton(caprow, text="Capturar con patrón", command=self._cap_con_peso, micro=True).pack(side="left", padx=4)

        rowp = tk.Frame(body, bg=COL_CARD)
        rowp.pack(fill="x", pady=6, padx=6)
        tk.Label(rowp, text="Peso patrón (gramos):", bg=COL_CARD, fg=COL_TEXT).pack(side="left")
        self.var_patron = tk.StringVar()
        ent = tk.Entry(rowp, textvariable=self.var_patron, bg="#1a1f2e", fg=COL_TEXT, width=12)
        ent.pack(side="left", padx=8)
        try:
            bind_numeric_popup(ent)
        except Exception:
            pass
        try:
            GhostButton(
                rowp, text="Teclado",
                command=lambda: KeypadPopup(
                    self, title="Peso patrón (g)", initial=(self.var_patron.get() or "0"),
                    allow_dot=True, on_accept=lambda v: self.var_patron.set(v)
                ),
                micro=True
            ).pack(side="left", padx=6)
        except Exception:
            pass

        BigButton(body, text="Guardar calibración", command=self._calc_save, micro=True).pack(anchor="e", pady=4, padx=6)
        self.toast = Toast(self)
        self.after(120, self._tick_live)

        # Vincula teclado numérico a las entradas de Calibración
        try:
            from bascula.ui.widgets import bind_numeric_entry
            for w in self.winfo_children():
                for ch in getattr(w, 'winfo_children', lambda: [])():
                    if isinstance(ch, (ttk.Entry, tk.Entry)):
                        bind_numeric_entry(ch, decimals=2)
        except Exception:
            pass

    def _toggle_audio_from_header(self, btn):
        try:
            cfg = self.app.get_cfg()
            new_en = not bool(cfg.get('sound_enabled', True))
            cfg['sound_enabled'] = new_en
            self.app.save_cfg()
            if hasattr(self.app, 'get_audio') and self.app.get_audio():
                self.app.get_audio().set_enabled(new_en)
            try:
                btn.config(text=_safe_audio_icon(cfg))
            except Exception:
                pass
            self.toast.show("Sonido: " + ("ON" if new_en else "OFF"), 900)
        except Exception:
            pass

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
        return sum(vals) / len(vals) if vals else None

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
