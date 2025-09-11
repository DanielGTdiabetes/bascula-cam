from __future__ import annotations

import threading
import time
import tkinter as tk
from typing import Any, Dict, List, Optional
from tkinter import messagebox

from bascula.ui.overlay_base import OverlayBase
from bascula.ui.widgets import (
    COL_BG, COL_CARD, COL_CARD_HOVER, COL_TEXT, COL_ACCENT, COL_MUTED, COL_SUCCESS, COL_WARN,
    COL_BORDER, FS_TITLE, FS_TEXT, FS_BTN_SMALL, BigButton, GhostButton, Card, auto_apply_scaling,
)
from bascula.ui.widgets_mascota import MascotaCanvas
from bascula.ui.overlay_scanner import ScannerOverlay
from bascula.ui.anim_target import TargetLockAnimator
from bascula.services.off_lookup import fetch_off
from bascula.services.voice import VoiceService
from bascula.services.recipes import list_saved as recipes_list, load as recipe_load, generate_recipe, delete_saved
from bascula.domain.recipes import save_recipe


class RecipeOverlay(OverlayBase):
    """Modal overlay for step-by-step recipe mode with timers and scanning.

    - Does not block mainloop; uses after() and background threads for I/O.
    - Honors theme via widgets color constants.
    - Integrates with app.audio (beeps) and app.voice (TTS) if available.
    """

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app
        self._scanner: Optional[ScannerOverlay] = None

        self.recipe: Dict[str, Any] = {}
        self._step_idx = 0
        self._playing = False
        self._timer_after: Optional[str] = None
        self._timer_remaining: int = 0
        self._anim_canvas: Optional[tk.Frame] = None
        self._tts_enabled = True  # toggled by UI
        self._listening = False
        self._listen_autorepeat = True
        # Voz (usar app.voice si existe, si no crear local)
        self.voice: Optional[VoiceService] = getattr(self.app, 'voice', None) or VoiceService()

        c = self.content(); c.configure(padx=10, pady=10)
        auto_apply_scaling(c)

        # Layout: left = ingredients, right = step area
        grid = tk.Frame(c, bg=COL_CARD)
        grid.pack(fill='both', expand=True)
        grid.grid_columnconfigure(0, weight=1, minsize=280)
        grid.grid_columnconfigure(1, weight=2)
        grid.grid_rowconfigure(1, weight=1)

        # Header with title + controls
        header = tk.Frame(grid, bg=COL_CARD)
        header.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 6))
        self.title_lbl = tk.Label(header, text='Recetas', bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_TITLE, 'bold'))
        self.title_lbl.pack(side='left', padx=8)
        GhostButton(header, text='💾 Guardar', command=self._save_current, micro=True).pack(side='right', padx=4)
        GhostButton(header, text='Abrir guardada…', command=self._open_saved_popup, micro=True).pack(side='right', padx=4)
        GhostButton(header, text='Cerrar', command=self.hide, micro=True).pack(side='right', padx=4)

        # Left: Ingredients panel
        ingr_card = Card(grid)
        ingr_card.grid(row=1, column=0, sticky='nsew', padx=(0, 6))
        tk.Label(ingr_card, text='Ingredientes', bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_TEXT, 'bold')).pack(anchor='w', padx=8, pady=(8, 4))
        self.ingr_list = tk.Frame(ingr_card, bg=COL_CARD)
        self.ingr_list.pack(fill='both', expand=True, padx=6, pady=6)

        btns_ingr = tk.Frame(ingr_card, bg=COL_CARD)
        btns_ingr.pack(fill='x', pady=(0, 8))
        BigButton(btns_ingr, text='📷 Buscar ingrediente', small=True, command=self._open_scanner, bg=COL_ACCENT).pack(side='left', expand=True, fill='x', padx=4)
        GhostButton(btns_ingr, text='🔍 Detectar (visión)', micro=True, command=self._vision_detect_placeholder).pack(side='left', padx=4)

        # Right: Step area
        right = Card(grid)
        right.grid(row=1, column=1, sticky='nsew')
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(0, weight=1)

        self.step_canvas = tk.Canvas(right, bg=COL_CARD, highlightthickness=0)
        self.step_canvas.grid(row=0, column=0, sticky='nsew')
        self.step_text = self.step_canvas.create_text(20, 20, text='', anchor='nw', fill=COL_TEXT, font=("DejaVu Sans", FS_TITLE), width=10)

        ctrl = tk.Frame(right, bg=COL_CARD)
        ctrl.grid(row=1, column=0, sticky='ew', pady=(6, 8))
        self.play_btn = GhostButton(ctrl, text='▶️', micro=True, command=self._toggle_play)
        self.play_btn.pack(side='left', padx=4)
        self.pause_btn = GhostButton(ctrl, text='⏸️', micro=True, command=self._pause)
        self.pause_btn.pack(side='left', padx=4)
        GhostButton(ctrl, text='⏭️', micro=True, command=self._next_step).pack(side='left', padx=4)
        GhostButton(ctrl, text='↩️', micro=True, command=self._repeat_step).pack(side='left', padx=4)
        self.listen_btn = GhostButton(ctrl, text='🎤 Escuchar', micro=True, command=self._toggle_listen)
        self.listen_btn.pack(side='left', padx=4)
        self.timer_lbl = tk.Label(ctrl, text='', bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT))
        self.timer_lbl.pack(side='right', padx=8)
        self.tts_btn = GhostButton(ctrl, text='Voz ON', micro=True, command=self._toggle_tts)
        self.tts_btn.pack(side='right', padx=4)

        # Mascota area
        masc = Card(grid)
        masc.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(6, 0))
        self.mascota = MascotaCanvas(masc, bg=COL_CARD)
        self.mascota.configure(height=120)
        self.mascota.pack(fill='x', expand=False)
        # Conectar wakeword del app (si existe) y activar auto-escucha
        try:
            self.mascota.wakeword = getattr(self.app, 'wakeword', None)
        except Exception:
            pass
        self._wake_cooldown = 0
        self.after(600, self._wake_tick)

        # Start with blank state
        self._render_ingredients()
        self._render_step(animated=False)

    # ---- Public API ----
    def set_recipe(self, recipe: Dict[str, Any]) -> None:
        self.recipe = recipe or {}
        self._step_idx = 0
        self.title_lbl.configure(text=self.recipe.get('title') or 'Recetas')
        self._render_ingredients()
        self._render_step(animated=False)

    # ---- UI actions ----
    def _toggle_tts(self):
        self._tts_enabled = not self._tts_enabled
        self.tts_btn.configure(text=('Voz ON' if self._tts_enabled else 'Voz OFF'))

    def _toggle_play(self):
        if not self._playing:
            self._playing = True
            self._speak_current()
            self._start_timer_if_any()
        else:
            self._pause()

    def _pause(self):
        self._playing = False
        self._cancel_timer()

    def _next_step(self):
        self._cancel_timer()
        if not self.recipe:
            return
        self._step_idx = min(len(self.recipe.get('steps', [])) - 1, self._step_idx + 1)
        self._render_step(animated=True)
        if self._playing:
            self._speak_current(); self._start_timer_if_any()

    def _repeat_step(self):
        self._cancel_timer()
        self._render_step(animated=True)
        if self._playing:
            self._speak_current(); self._start_timer_if_any()

    def _open_scanner(self):
        if self._scanner is None:
            self._scanner = ScannerOverlay(self, self.app, on_result=self._on_scan_result, on_timeout=self._on_scan_timeout, timeout_ms=8000)
        self.mascota.set_state('process')
        self._scanner.show()

    def _on_scan_timeout(self):
        self.mascota.set_state('idle')

    def _on_scan_result(self, code: str):
        # Try to match barcode with ingredient having barcode field or fallback to mark the first pending
        def done_mark(label: str):
            try:
                TargetLockAnimator.run(self.step_canvas, label=label)
            except Exception:
                pass
            self._render_ingredients()
            self.mascota.set_state('idle')

        # Background OFF lookup (optional)
        def worker():
            prod = None
            try:
                prod = fetch_off(code)
            except Exception:
                prod = None

            def apply():
                name = None
                if prod and isinstance(prod, dict):
                    name = prod.get('product_name') or prod.get('generic_name')
                label = name or code
                # Match ingredient by barcode or mark first unmatched
                matched = False
                for it in (self.recipe.get('ingredients') or []):
                    if str(it.get('barcode') or '') == str(code) or (name and (name.lower() in (it.get('name') or '').lower())):
                        it['matched'] = True
                        matched = True
                        break
                if not matched:
                    for it in (self.recipe.get('ingredients') or []):
                        if not it.get('matched'):
                            it['matched'] = True
                            break
                done_mark(label)
            try:
                self.after(0, apply)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _vision_detect_placeholder(self):
        # Placeholder for future lightweight classifier; for now, mark first unmatched
        for it in (self.recipe.get('ingredients') or []):
            if not it.get('matched'):
                it['matched'] = True
                TargetLockAnimator.run(self.step_canvas, label=it.get('name') or 'Ingrediente')
                break
        self._render_ingredients()

    def _save_current(self):
        if self.recipe:
            save_recipe(self.recipe)
            try:
                from tkinter import messagebox
                messagebox.showinfo('Recetas', 'Receta guardada')
            except Exception:
                pass

    def _open_saved_popup(self):
        top = tk.Toplevel(self)
        try:
            top.attributes('-topmost', True)
        except Exception:
            pass
        top.transient(self.winfo_toplevel()); top.configure(bg=COL_BG)
        fr = Card(top, min_width=420, min_height=280)
        fr.pack(fill='both', expand=True, padx=10, pady=10)
        tk.Label(fr, text='Abrir receta guardada', bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_TITLE, 'bold')).pack(anchor='w', padx=8, pady=(8, 6))
        lst = tk.Listbox(fr, bg=COL_CARD_HOVER, fg=COL_TEXT)
        lst.pack(fill='both', expand=True, padx=8, pady=8)
        label_by_id = {}
        recipe_by_id: Dict[str, Dict[str, Any]] = {}

        def reload_list():
            lst.delete(0, 'end')
            label_by_id.clear()
            recs = recipes_list(limit=100)
            for r in recs:
                lab = f"{r.get('title')}  ({r.get('servings')} raciones)"
                lst.insert('end', lab)
                label_by_id[lab] = r.get('id')

        reload_list()
        def _open_sel():
            try:
                lab = lst.get(lst.curselection())
                rid = label_by_id.get(lab)
                r = recipe_load(rid) if rid else None
                if r:
                    self.set_recipe(r)
                    top.destroy()
            except Exception:
                pass
        # Filtro y controles
        filter_row = tk.Frame(fr, bg=COL_CARD); filter_row.pack(fill='x', pady=(0,6), padx=8)
        var_filter = tk.StringVar(value='')
        ent = tk.Entry(filter_row, textvariable=var_filter, bg=COL_CARD_HOVER, fg=COL_TEXT, insertbackground=COL_TEXT,
                       relief='flat', font=("DejaVu Sans", FS_TEXT))
        ent.pack(side='left', fill='x', expand=True)
        def _voice_filter():
            try:
                v = self.voice or VoiceService()
                def _got(t: str):
                    def _apply():
                        var_filter.set((t or '').strip())
                    try: self.after(0, _apply)
                    except Exception: pass
                v.start_listening(on_text=_got, duration=4)
            except Exception:
                pass
        GhostButton(filter_row, text='🎤 Voz', micro=True, command=_voice_filter).pack(side='left', padx=4)
        GhostButton(filter_row, text='Limpiar', micro=True, command=lambda: var_filter.set('')).pack(side='left', padx=4)

        # Preview de la receta seleccionada
        preview = Card(fr, min_height=120)
        preview.pack(fill='x', padx=8, pady=(0, 8))
        prev_lbl = tk.Label(preview, text='', bg=COL_CARD, fg=COL_TEXT, justify='left', anchor='w',
                            font=("DejaVu Sans", FS_TEXT), wraplength=520)
        prev_lbl.pack(fill='x', padx=8, pady=8)

        def _render_preview_by_id(rid: Optional[str]):
            try:
                if not rid:
                    prev_lbl.configure(text='')
                    return
                r = recipe_by_id.get(rid) or recipe_load(rid)
                if not r:
                    prev_lbl.configure(text='')
                    return
                title = str(r.get('title') or '')
                serv = int(r.get('servings') or 0)
                ings = r.get('ingredients') or []
                ing_list = ', '.join([str(i.get('name') or '') for i in ings[:5]])
                steps = r.get('steps') or []
                step_lines = []
                for st in steps[:3]:
                    n = st.get('n') or len(step_lines)+1
                    txt = str(st.get('text') or '')
                    step_lines.append(f"{n}. {txt}")
                preview_txt = f"{title}  ({serv} raciones)\nIngredientes: {ing_list}" + ("\n" + "\n".join(step_lines) if step_lines else "")
                prev_lbl.configure(text=preview_txt)
            except Exception:
                prev_lbl.configure(text='')

        btnrow = tk.Frame(fr, bg=COL_CARD); btnrow.pack(fill='x', pady=(0,8))
        GhostButton(btnrow, text='Abrir', micro=True, command=_open_sel).pack(side='left', padx=4)
        def _del_sel():
            try:
                lab = lst.get(lst.curselection())
                rid = label_by_id.get(lab)
                if not rid:
                    return
                if messagebox.askyesno('Recetas', '¿Eliminar la receta seleccionada?', parent=top):
                    if delete_saved(rid):
                        reload_list()
            except Exception:
                pass
        GhostButton(btnrow, text='Eliminar', micro=True, command=_del_sel).pack(side='left', padx=4)
        GhostButton(btnrow, text='Cerrar', micro=True, command=top.destroy).pack(side='right', padx=4)

        def reload_list():
            lst.delete(0, 'end')
            label_by_id.clear()
            recipe_by_id.clear()
            recs = recipes_list(limit=100)
            q = (var_filter.get() or '').strip().lower()
            for r in recs:
                rid = r.get('id')
                title = str(r.get('title') or '')
                # También buscar por ingredientes
                ingreds = r.get('ingredients') or []
                ing_text = ' '.join([str(i.get('name') or '') for i in ingreds]).lower()
                if q and (q not in title.lower()) and (q not in ing_text):
                    continue
                lab = f"{title}  ({r.get('servings')} raciones)"
                lst.insert('end', lab)
                label_by_id[lab] = rid
                if rid:
                    recipe_by_id[str(rid)] = r

        reload_list()
        # Refrescar al escribir
        var_filter.trace_add('write', lambda *_: reload_list())

        def _on_select(_evt=None):
            try:
                lab = lst.get(lst.curselection())
                rid = label_by_id.get(lab)
                _render_preview_by_id(rid)
            except Exception:
                _render_preview_by_id(None)
        lst.bind('<<ListboxSelect>>', _on_select)

    # ---- Rendering ----
    def _render_ingredients(self):
        for w in self.ingr_list.winfo_children():
            w.destroy()
        ings = self.recipe.get('ingredients') or []
        for it in ings:
            state = 'pend'
            if it.get('matched'):
                state = 'ok'
            elif it.get('alt'):
                state = 'alt'
            color = COL_MUTED if state == 'pend' else (COL_SUCCESS if state == 'ok' else COL_WARN)
            row = tk.Frame(self.ingr_list, bg=COL_CARD)
            row.pack(fill='x', padx=2, pady=2)
            tk.Label(row, text=it.get('name') or '-', bg=COL_CARD, fg=color, font=("DejaVu Sans", FS_TEXT)).pack(side='left')
            tk.Label(row, text=it.get('qty') or '', bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT)).pack(side='right')

    def _render_step(self, animated: bool = True):
        steps = self.recipe.get('steps') or []
        text = ''
        t_s = None
        if 0 <= self._step_idx < len(steps):
            st = steps[self._step_idx]
            text = st.get('text') or ''
            t_s = st.get('timer_s')
        self._render_step_text(text, animated=animated)
        if t_s and int(t_s) > 0:
            self.timer_lbl.configure(text=f"⏱ {int(t_s)} s (parado)")
            self._timer_remaining = int(t_s)
        else:
            self.timer_lbl.configure(text='')
            self._timer_remaining = 0

    def _render_step_text(self, text: str, animated: bool = True):
        # Smooth fade by quickly adjusting canvas text color alpha-like effect
        self.step_canvas.delete('all')
        w = max(10, self.step_canvas.winfo_width())
        self.step_text = self.step_canvas.create_text(16, 16, text=text, anchor='nw', fill=COL_TEXT, font=("DejaVu Sans", FS_TITLE), width=w-32)
        if animated:
            try:
                # simple slide-in from right
                for dx in range(40, -1, -8):
                    self.step_canvas.move(self.step_text, dx, 0)
                    self.step_canvas.update_idletasks()
                    self.step_canvas.after(12)
            except Exception:
                pass

    # ---- Timers and TTS ----
    def _start_timer_if_any(self):
        if self._timer_remaining <= 0:
            return
        self._tick_timer()

    def _tick_timer(self):
        if not self._playing:
            return
        if self._timer_remaining <= 0:
            self.timer_lbl.configure(text='')
            # Beep final (3 pares)
            try:
                if getattr(self.app, 'audio', None) is not None:
                    self.app.audio.play_event('timer_done')
            except Exception:
                pass
            return
        self.timer_lbl.configure(text=f"⏱ {self._timer_remaining} s")
        self._timer_remaining -= 1
        self._timer_after = self.after(1000, self._tick_timer)

    def _cancel_timer(self):
        if self._timer_after:
            try:
                self.after_cancel(self._timer_after)
            except Exception:
                pass
            self._timer_after = None

    def _speak_current(self):
        steps = self.recipe.get('steps') or []
        if not (0 <= self._step_idx < len(steps)):
            return
        text = steps[self._step_idx].get('text') or ''
        if not text:
            return
        if not self._tts_enabled:
            return
        # Mascota states: speak -> process -> idle
        try:
            self.mascota.set_state('process')
        except Exception:
            pass
        try:
            if self.voice is not None:
                self.voice.speak(text)
        except Exception:
            pass
        finally:
            try:
                # fall back to idle a bit later
                self.after(1500, lambda: self.mascota.set_state('idle'))
            except Exception:
                pass

    # ---- Generation helper (optional from external button) ----
    def generate_and_set(self, query: str, servings: int = 2, api_key: Optional[str] = None) -> None:
        self.title_lbl.configure(text='Generando…')
        def worker():
            r = None
            try:
                r = generate_recipe(query, servings=servings, api_key=api_key)
            except Exception:
                r = None
            def done():
                if r:
                    self.set_recipe(r)
                else:
                    self.title_lbl.configure(text='Recetas')
            try: self.after(0, done)
            except Exception: pass
        threading.Thread(target=worker, daemon=True).start()

    # ---- Voice commands ----
    def _toggle_listen(self):
        if not self._listening:
            self._start_listen()
        else:
            # No hard stop API; just disable autorepeat and update UI
            self._listen_autorepeat = False
            self._listening = False
            self.listen_btn.configure(text='🎤 Escuchar')
            try:
                self.mascota.set_state('idle')
            except Exception:
                pass

    def _start_listen(self, duration: int = 5):
        if self.voice is None or self._listening:
            return
        self._listening = True
        self._listen_autorepeat = True
        self.listen_btn.configure(text='🎙️ Escuchando…')
        try:
            self.mascota.set_state('listen')
        except Exception:
            pass
        ok = self.voice.start_listening(on_text=self._on_listen_text, duration=duration)
        if not ok:
            self._listening = False
            self.listen_btn.configure(text='🎤 Escuchar')

    def _on_listen_text(self, text: str):
        # Called from worker thread; bounce to main thread
        def apply():
            self._listening = False
            phrase = (text or '').strip()
            if not phrase:
                # Retry if auto
                if self._listen_autorepeat:
                    self.after(200, lambda: self._start_listen())
                else:
                    self.listen_btn.configure(text='🎤 Escuchar')
                    self.mascota.set_state('idle')
                return
            self.mascota.set_state('process')
            cmd = self._parse_command(phrase)
            handled = self._exec_command(cmd)
            # UI update
            self.listen_btn.configure(text='🎤 Escuchar')
            self.mascota.set_state('idle')
            if self._listen_autorepeat:
                # small delay and resume listening
                self.after(400, lambda: self._start_listen())
        try:
            self.after(0, apply)
        except Exception:
            pass

    def _parse_command(self, phrase: str) -> str:
        p = _normalize_es(phrase)
        # Common Spanish intents
        if any(w in p for w in ("siguiente", "siguente", "avanza", "adelante", "next")):
            return 'next'
        if any(w in p for w in ("atras", "atrás", "anterior", "previo", "previous")):
            return 'prev'
        if any(w in p for w in ("repite", "repetir", "otra vez", "de nuevo")):
            return 'repeat'
        if any(w in p for w in ("pausa", "pausar", "para", "parar", "alto", "stop")):
            return 'pause'
        if any(w in p for w in ("continua", "continuar", "seguir", "reanudar", "play", "empezar", "iniciar")):
            return 'play'
        if any(w in p for w in ("temporizador", "timer")) and any(w in p for w in ("inicia", "iniciar", "start")):
            return 'timer_start'
        if any(w in p for w in ("temporizador", "timer")) and any(w in p for w in ("para", "parar", "detener", "stop")):
            return 'timer_stop'
        return ''

    def _exec_command(self, cmd: str) -> bool:
        if cmd == 'next':
            self._next_step(); self._speak_confirm('Siguiente.'); return True
        if cmd == 'prev':
            # previous step
            self._cancel_timer()
            if self.recipe:
                self._step_idx = max(0, self._step_idx - 1)
                self._render_step(animated=True)
                if self._playing:
                    self._speak_current(); self._start_timer_if_any()
            self._speak_confirm('Atrás.'); return True
        if cmd == 'repeat':
            self._repeat_step(); self._speak_confirm('Repitiendo.'); return True
        if cmd == 'pause':
            self._pause(); self._speak_confirm('Pausa.'); return True
        if cmd == 'play':
            if not self._playing:
                self._toggle_play()
            else:
                self._speak_current()
            self._speak_confirm('Continuar.'); return True
        if cmd == 'timer_start':
            if self._timer_remaining > 0 and not self._playing:
                # start only timer (not autoplay)
                self._playing = True
                self._tick_timer()
            self._speak_confirm('Temporizador iniciado.'); return True
        if cmd == 'timer_stop':
            self._cancel_timer(); self._playing = False; self._speak_confirm('Temporizador detenido.'); return True
        return False

    def _speak_confirm(self, text: str) -> None:
        if not self._tts_enabled:
            return
        try:
            if self.voice is not None and text:
                self.voice.speak(text)
        except Exception:
            pass

    def _wake_tick(self):
        try:
            if self._wake_cooldown > 0:
                self._wake_cooldown -= 1
            ww = getattr(self.app, 'wakeword', None)
            if ww is not None and hasattr(ww, 'is_triggered'):
                if ww.is_triggered() and not self._listening and self._wake_cooldown <= 0:
                    self._start_listen()
                    self._wake_cooldown = 6  # ~3-4s de enfriamiento
        except Exception:
            pass
        finally:
            try:
                self.after(600, self._wake_tick)
            except Exception:
                pass


def _normalize_es(s: str) -> str:
    try:
        import unicodedata as _u
        s2 = ''.join(c for c in _u.normalize('NFD', s.lower()) if _u.category(c) != 'Mn')
        return s2
    except Exception:
        return s.lower()
