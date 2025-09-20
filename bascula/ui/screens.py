# -*- coding: utf-8 -*-
"""
Pantallas base (Home + Calibración) con UI limpia y estable.
"""
import tkinter as tk
import os, json, time
from tkinter import ttk
from collections import deque
from typing import Dict
from bascula.ui.widgets import * # Card, BigButton, GhostButton, Toast, bind_numeric_popup, ScrollingBanner
try:
    from bascula.ui.widgets_textfx import TypewriterLabel
except Exception:
    TypewriterLabel = None  # type: ignore
from bascula.domain.foods import Food, load_foods
from bascula.domain.session import WeighSession, SessionItem
from bascula.domain.gi_index import lookup_gi
from bascula.services.nutrition import make_item
from bascula.ui.overlay_bolus import BolusOverlay

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
        try:
            # Auto-asociar teclados de texto a entradas que no los tengan
            from bascula.ui.widgets import auto_bind_text_keyboards
            auto_bind_text_keyboards(self)
        except Exception:
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
        self.mascota = getattr(app, 'mascota', None)
        if self.mascota is None:
            self.mascota = getattr(app, 'mascota_instance', None)

        # --- buffers/suscripción ---
        self._last_weight = 0.0
        self._last_stable = False
        self._subscribed = False
        self._reader = None
        self._subscribe_to_reader()

        self.session = WeighSession()
        self._tree_map: Dict[str, SessionItem] = {}
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

        self.settings_btn = tk.Button(
            header, text='⚙', command=self.on_open_settings_menu,
            bg=COL_BG, fg=COL_TEXT, bd=0, relief='flat', highlightthickness=0,
            font=("DejaVu Sans", FS_TITLE, 'bold'), cursor="hand2"
        )
        self.settings_btn.pack(side='right', padx=(0, 8))

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
        for i in range(4):
            btns.grid_rowconfigure(i, weight=1)
        for i in range(2):
            btns.grid_columnconfigure(i, weight=1, uniform="btns")

        btn_map = [
            ("Tara", self._on_tara, 0, 0, COL_ACCENT),
            ("Añadir", self._on_add_item, 0, 1, "#00a884"),
            ("Temporizador", self._on_timer_open, 1, 0, "#ffa500"),
            ("Reiniciar", self._on_reset_session, 1, 1, "#6b7280"),
            ("Finalizar", self._on_finish_meal_open, 2, 0, "#3b82f6", 2),
        ]
        for text, cmd, r, c, color, *span in btn_map:
            b = BigButton(btns, text=text, command=cmd, bg=color, small=True)
            col_span = span[0] if span else 1
            b.grid(row=r, column=c, columnspan=col_span, sticky="nsew", padx=3, pady=3)

        # Sugerencia proactiva (IA Visión)
        self.suggestion_frame = tk.Frame(left, bg=COL_BG)
        self.suggestion_frame.grid(row=3, column=0, sticky='ew', pady=4)

        footer = tk.Frame(left, bg=COL_BG)
        footer.grid(row=4, column=0, sticky='ew', pady=(6, 0))
        BigButton(footer, text='🍳 Recetas', command=self._open_recipes, small=True).pack(side='left', padx=4)

        try:
            overrides = {
                (0, 0): "Tara",
                (0, 1): "➕",
                (1, 0): "⏱",
                (1, 1): "↺",
                (2, 0): "✔",
            }
            for child in btns.winfo_children():
                gi = child.grid_info()
                key = (int(gi.get('row', 0)), int(gi.get('column', 0)))
                if key in overrides:
                    child.config(text=overrides[key], font=("DejaVu Sans", max(12, FS_BTN_SMALL - 2), "bold"))
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
        ).pack(padx=10, pady=(10, 4), anchor="w")

        self._total_carbs_lbl = tk.Label(
            totals,
            text="0.0 g Hidratos",
            bg=COL_CARD,
            fg=COL_ACCENT,
            font=("DejaVu Sans", FS_TITLE, "bold"),
        )
        self._total_carbs_lbl.pack(padx=10, anchor="w")

        totals_grid = tk.Frame(totals, bg=COL_CARD)
        totals_grid.pack(fill="x", padx=10, pady=(6, 10))
        totals_grid.grid_columnconfigure(0, weight=1)
        totals_grid.grid_columnconfigure(1, minsize=70)
        totals_grid.grid_columnconfigure(2, weight=0)

        self._nut_labels = {}
        self._nut_meta = {}
        nut_items = [
            ("Peso total", "grams", "g", 0),
            ("Calorías", "kcal", "kcal", 0),
            ("Proteínas", "protein_g", "g", 1),
            ("Grasas", "fat_g", "g", 1),
        ]

        for i, (name, key, unit, decimals) in enumerate(nut_items):
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
            self._nut_meta[key] = int(decimals)

        # ---------------------------
        # Banner de consejos (altura fija 18 px, misma fuente)
        # ---------------------------
        tips_banner_card = Card(right)
        tips_banner_card.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        tips_banner_card.configure(height=18)
        tips_banner_card.pack_propagate(False)

        _bnr_wrap = tk.Frame(tips_banner_card, bg=COL_CARD)
        _bnr_wrap.pack(fill="both", expand=True, padx=2, pady=0)

        # Tips banner: usar Typewriter si está activado; fallback a ScrollingBanner
        use_fx = False
        try:
            use_fx = bool(self.app.get_cfg().get('textfx_enabled', True)) and (TypewriterLabel is not None)
        except Exception:
            use_fx = False
        self._tips_is_fx = use_fx
        if use_fx:
            self.tips_label = TypewriterLabel(_bnr_wrap, text="", enabled=True, speed_ms=40, blink_ms=600, bg=COL_CARD, fg=COL_TEXT, anchor="w")
            self.tips_label.pack(fill="x", expand=True)
            self.tips_banner = None
        else:
            self.tips_banner = ScrollingBanner(_bnr_wrap, bg=COL_CARD)
            self.tips_banner.pack(fill="x", expand=True)
            self.tips_label = None

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
            columns=("item", "grams", "carbs", "gi", "kcal", "protein", "fat"),
            show="headings", selectmode="browse", style='Food.Treeview'
        )
        self.tree.heading("item", text="Alimento"); self.tree.column("item", width=200, anchor="w", stretch=True)
        self.tree.heading("grams", text="g"); self.tree.column("grams", width=70, anchor="center")
        self.tree.heading("carbs", text="Hidratos"); self.tree.column("carbs", width=80, anchor="center")
        self.tree.heading("gi", text="IG"); self.tree.column("gi", width=60, anchor="center")
        self.tree.heading("kcal", text="kcal"); self.tree.column("kcal", width=80, anchor="center")
        self.tree.heading("protein", text="Prot."); self.tree.column("protein", width=85, anchor="center")
        self.tree.heading("fat", text="Grasa"); self.tree.column("fat", width=70, anchor="center")
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

    # --- lifecycle ---
    def on_show(self):
        # Asegurarse de que el bucle de actualización se inicia
        if not self._tick_after:
            self._tick()
        if not self._subscribed:
            self._subscribe_to_reader()
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

    def _on_weight(self, grams: float, stable: bool):
        """Callback desde ScaleService: guarda último peso neto y estabilidad."""
        try:
            w = max(0.0, float(grams))
            self._last_weight = w
            self._last_stable = bool(stable)
        except Exception:
            pass

    def _subscribe_to_reader(self):
        try:
            reader = None
            if hasattr(self.app, "get_reader"):
                reader = self.app.get_reader()
            if not reader:
                reader = getattr(self.app, "reader", None)
            if reader and reader is not self._reader and hasattr(reader, "subscribe"):
                reader.subscribe(self._on_weight)
                self._reader = reader
                self._subscribed = True
            elif reader is self._reader:
                # Ya suscrito previamente
                self._subscribed = True
            else:
                self._subscribed = False
        except Exception:
            self._subscribed = False

    # --- actions ---
    def _on_tara(self):
        try:
            reader = self.app.get_reader()
            if not reader or not hasattr(reader, 'tare'):
                self.toast.show("Báscula no disponible", 1200, "#ff6b6b")
                return
            ok = reader.tare()
            if ok:
                self.toast.show("Tara establecida", 1000, "#00d4aa")
                self._update_tips("Tara en cero. Añade el alimento.")
                if hasattr(self.app, 'log'):
                    self.app.log.info("Tara ejecutada desde pantalla principal")
            else:
                self.toast.show("No se pudo tara", 1200, "#ff6b6b")
        except Exception as e:
            if hasattr(self.app, 'log'):
                self.app.log.error(f"Error en _on_tara: {e}")
            self.toast.show("Sin lectura de báscula", 1200, "#ff6b6b")

    def _on_add_item(self):
        self.toast.show("Capturando...", 900)

        def _bg():
            image_path = None
            try:
                # Usa el peso del callback
                weight = self._last_weight
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
                item = self._add_item_from_data(data)
                if item:
                    self._recalc_totals()
                    self.toast.show(f"{item.name} añadido", 1400, COL_SUCCESS)
            self.after(0, _apply)

        import threading
        threading.Thread(target=_bg, daemon=True).start()

    def _add_item_from_data(self, data):
        payload = dict(data or {})
        name = payload.get('name') or 'Alimento'
        grams = float(payload.get('grams') or payload.get('weight') or self._last_weight or 0.0)
        source = payload.get('source') or payload.get('origin') or 'manual'
        per100 = payload.get('per100g') or payload.get('per100') or {}
        item: SessionItem
        if isinstance(per100, dict) and per100:
            item = make_item(name, grams, per100, source=source)
        else:
            carbs = payload.get('carbs_g', payload.get('carbs', 0.0))
            protein = payload.get('protein_g', payload.get('protein', 0.0))
            fat = payload.get('fat_g', payload.get('fat', 0.0))
            kcal = payload.get('kcal', payload.get('calories', 0.0))
            gi = payload.get('gi')
            if gi is None:
                gi = lookup_gi(name)
            item = SessionItem(
                name=str(name),
                grams=float(grams),
                carbs_g=float(carbs or 0.0),
                kcal=float(kcal or 0.0),
                protein_g=float(protein or 0.0),
                fat_g=float(fat or 0.0),
                gi=gi if gi is None or isinstance(gi, int) else None,
                source=str(source or 'manual'),
            )
        if item.gi is None:
            item.gi = lookup_gi(item.name)
        self.session.add(item)
        iid = str(self._next_id)
        self._next_id += 1
        self._tree_map[iid] = item
        self.tree.insert("", "end", iid=iid, values=(
            item.name,
            f"{item.grams:.0f}",
            f"{item.carbs_g:.1f}",
            (item.gi if item.gi is not None else "-"),
            f"{item.kcal:.0f}",
            f"{item.protein_g:.1f}",
            f"{item.fat_g:.1f}",
        ))
        self._update_item_count()
        return item

    def _on_select_item(self, _evt=None):
        sel = self.tree.selection()
        self._selection_id = sel[0] if sel else None

    def _on_delete_selected(self):
        if not self._selection_id:
            self.toast.show("Selecciona un elemento", 1100, COL_MUTED)
            return
        iid = self._selection_id
        item = self._tree_map.pop(iid, None)
        try:
            self.tree.delete(iid)
        except Exception:
            pass
        if item is not None:
            for idx, existing in enumerate(self.session.items):
                if existing is item:
                    self.session.remove(idx)
                    break
        self._selection_id = None
        self._update_item_count()
        self._recalc_totals()
        self.toast.show("Elemento eliminado", 900)

    def _on_reset_session(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.session.clear()
        self._tree_map.clear()
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
        try:
            from bascula.ui.overlay_recipe import RecipeOverlay
            # feedback mascota
            try: self.mascota.set_state('happy')
            except Exception: pass
            RecipeOverlay(self, self.app).show()
        except Exception as e:
            try: self.toast.show(f"Recetas no disponibles: {e}", 2000, COL_WARN)
            except Exception: pass

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
                            # Actualiza etiqueta BG
                            if mgdl is None:
                                self.bg_label.config(text="", fg=COL_MUTED)
                                zone = 'nd'
                                col = COL_MUTED
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

                            # Sonidos/voz y lógica de zonas
                            au = getattr(self.app, 'get_audio', lambda: None)()
                            cfg = self.app.get_cfg() or {}
                            alerts_on = bool(cfg.get('bg_alerts_enabled', True))
                            ann_on_alert = bool(cfg.get('bg_announce_on_alert', True))
                            ann_every = bool(cfg.get('bg_announce_every', False))

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
                                        if mgdl is not None:
                                            au.speak_event('announce_bg', n=int(float(mgdl)))
                                except Exception:
                                    pass

                            # --- Recovery flow (15/15) ---
                            try:
                                st = getattr(self.app, 'state', None)
                                if st is not None and mgdl is not None:
                                    res = st.update_bg(float(mgdl), direction)
                                    was_low = (self._last_bg_zone == 'low')
                                    now_safe = (zone in ('ok', 'warn'))
                                    if res.get('normalized') and was_low and now_safe:
                                        try: self._stop_timer_if_running()
                                        except Exception: pass
                                        try: st.clear_hypo_flow()
                                        except Exception: pass
                                        try:
                                            m = getattr(self.app, 'mascota_instance', None)
                                            if m and hasattr(m, 'play_recovery_animation'):
                                                m.play_recovery_animation(2000)
                                        except Exception: pass
                                        try: self.toast.show('Glucosa normalizada. Toma hidratos de acción lenta', 2400, COL_SUCCESS)
                                        except Exception: pass
                                    if res.get('cancel_recovery') or zone == 'low':
                                        try:
                                            m = getattr(self.app, 'mascota_instance', None)
                                            if m and hasattr(m, 'set_alarm'):
                                                m.set_alarm()
                                            if st:
                                                st.hypo_modal_open = True
                                        except Exception: pass
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

    def _stop_timer_if_running(self):
        # Cancela el temporizador local y limpia etiqueta
        if self._timer_after:
            try:
                self.after_cancel(self._timer_after)
            except Exception:
                pass
            self._timer_after = None
        self._timer_remaining = 0
        try:
            self.timer_label.configure(text="")
        except Exception:
            pass

    def _on_finish_meal_open(self):
        if not self.session.items:
            self.toast.show("No hay alimentos para finalizar", 1200, COL_WARN)
            return
        try:
            cfg = self.app.get_cfg() or {}
            if bool(cfg.get('voice_enabled', False)):
                au = getattr(self.app, 'get_audio', lambda: None)()
                if au and hasattr(au, 'speak_event'):
                    totals = self.session.totals()
                    au.speak_event(
                        'meal_totals',
                        g=int(totals['grams'] or 0),
                        k=int(totals['kcal'] or 0),
                        c=int(totals['carbs_g'] or 0),
                        p=int(totals['protein_g'] or 0),
                        f=int(totals['fat_g'] or 0)
                    )
        except Exception:
            pass

        overlay = BolusOverlay(self, self.app, self.session, on_finalize=self._on_finalize_session)
        overlay.show()

    def _on_finalize_session(self, result):
        try:
            success = bool(result.get('success', True))
        except Exception:
            success = True
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.session.clear()
        self._tree_map.clear()
        self._selection_id = None
        self._recalc_totals()
        if success:
            self.toast.show("Comida finalizada", 1400, COL_SUCCESS)

    def _update_tips(self, text: str):
        msg = (text or '').replace('\n', ' ')
        try:
            if getattr(self, '_tips_is_fx', False) and getattr(self, 'tips_label', None) is not None:
                self.tips_label.set_text(msg)
            elif getattr(self, 'tips_banner', None) is not None:
                self.tips_banner.set_text(msg)
        except Exception:
            pass

    def _tick(self):
        try:
            if not self._subscribed:
                self._subscribe_to_reader()
            # 1) Peso: usar callback si hay suscripción; si no, fallback al getter
            net_weight = float(self._last_weight or 0.0)
            if (not self._subscribed) and hasattr(self.app, "get_latest_weight"):
                # respaldo en caliente si no hay callbacks
                v = self.app.get_latest_weight()
                if v is not None:
                    net_weight = float(v)
            self._wbuf.append(net_weight)

            # Formatear y mostrar peso
            decimals = int(self.app.get_cfg().get('decimals', 0) or 0)
            decimals = min(max(0, decimals), 1) # Limitar a 0 o 1 decimal
            self.weight_lbl.config(text=f"{net_weight:.{decimals}f}g")

            # 2) Estabilidad: usar flag del callback si hay; si no, ventana
            if self._subscribed:
                is_stable = bool(self._last_stable)
            else:
                is_stable = False
                if len(self._wbuf) == self._wbuf.maxlen:
                    thr = float(self.app.get_cfg().get('stability_threshold_g', 1.0))
                    is_stable = (max(self._wbuf) - min(self._wbuf)) < thr

            if is_stable != self._stable:
                self._stable = is_stable
                self.stability_label.config(text=("Estable" if is_stable else "Midiendo..."), fg=("#00d4aa" if is_stable else "#ffa500"))
                if not is_stable:
                    self._clear_suggestion()
                else:
                    # Beep de estabilidad
                    au = getattr(self.app, 'get_audio', lambda: None)()
                    if au:
                        try: au.play_event('weight_stable_beep')
                        except Exception: pass

            if hasattr(self.app, 'log'):
                self.app.log.debug(f"Tick: net_weight={net_weight}, stable={is_stable}")

        except Exception as e:
            if hasattr(self.app, 'log'):
                self.app.log.error(f"Error en _tick: {e}")
            self.weight_lbl.config(text="Error", fg="#ff6b6b")

        # Reprogramar tick (como en actual, pero 120ms para smooth)
        self._tick_after = self.after(120, self._tick)

    def _recalc_totals(self):
        totals = self.session.totals()
        self._total_carbs_lbl.config(text=f"{totals['carbs_g']:.1f} g Hidratos")
        for key, label in self._nut_labels.items():
            value = float(totals.get(key, 0.0) or 0.0)
            decimals = int(self._nut_meta.get(key, 0)) if hasattr(self, '_nut_meta') else 0
            fmt = f"{{value:.{decimals}f}}"
            label.config(text=fmt.format(value=value))
        self._update_item_count()

    def _update_item_count(self):
        count = len(self.session.items)
        label = f"{count} item" if count == 1 else f"{count} items"
        try:
            self.item_count_label.config(text=label)
        except Exception:
            pass

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
            
            # Usar el peso del callback si hay suscripción; fallback al getter
            v = self._last_weight if self._subscribed else (getattr(self.app, 'get_latest_weight', lambda: None)() or None)
            
            if self._stable and (v is not None) and float(v) >= min_w:
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
                if self._subscribed:
                    weight = max(0.0, float(self._last_weight))
                else:
                    weight = max(0.0, float(getattr(self.app, 'get_latest_weight', lambda: 0.0)() or 0.0))
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
        try:
            reader = self.app.get_reader()
            raw_value = reader.get_latest() if reader and hasattr(reader, 'get_latest') else None
            if raw_value is not None:
                self.lbl_live.config(text=f"{raw_value:.3f}")
                self.app.log.debug(f"Calib tick: raw={raw_value}")
            else:
                self.lbl_live.config(text="-")
        except Exception as e:
            self.app.log.error(f"Error calib tick: {e}")
            self.lbl_live.config(text="-")
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
            if w <= 0 or self._b0 is None or self._bw is None:
                raise ValueError("Datos inválidos")
            factor = w / (self._bw - self._b0)
            self.app.set_calibration_factor(factor, persist=True)
            # Enviar comando C al ESP32
            reader = self.app.get_reader()
            if reader and hasattr(reader, 'send_command'):
                reader.send_command(f"C:{factor}")
            self.toast.show("Calibración guardada", 1500, "#00d4aa")
            self.app.log.info(f"Calib saved: factor={factor}")
            self.after(1600, lambda: self.app.show_screen('settingsmenu'))
        except ValueError as ve:
            self.toast.show(f"Error: {ve}", 1500, "#ff6b6b")
        except Exception as e:
            self.toast.show("Error en datos", 1500, "#ff6b6b")
            self.app.log.error(f"Error calc_save: {e}")
