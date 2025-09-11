import tkinter as tk
from bascula.ui.widgets import COL_BG, COL_CARD, COL_TEXT, COL_ACCENT, FS_TITLE, COL_BORDER, FS_TEXT
from bascula.ui.widgets_mascota import MascotaCanvas
from bascula.ui.overlay_weight import WeightOverlay
from bascula.ui.overlay_favorites import FavoritesOverlay
from bascula.ui.overlay_scanner import ScannerOverlay
from bascula.ui.overlay_timer import TimerOverlay
from bascula.ui.screens import BaseScreen
from bascula.services.voice import VoiceService
from bascula.services.off_lookup import fetch_off
from bascula.domain.foods import upsert_from_off
from pathlib import Path
import json, threading


class FocusScreen(BaseScreen):
    """Pantalla principal en modo Focus: Mascota al centro y overlays bajo demanda."""
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        center = tk.Frame(self, bg=COL_BG)
        center.grid(row=0, column=0, sticky='nsew')
        center.grid_columnconfigure(0, weight=1)
        center.grid_rowconfigure(1, weight=1)

        header = tk.Frame(center, bg=COL_BG)
        header.grid(row=0, column=0, pady=(10, 6), sticky='ew')
        tk.Label(header, text='Focus Mode', bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, 'bold')).pack(side='left', padx=12)
        tk.Button(header, text='⚙', command=lambda: self.app.show_screen('settingsmenu'), bg=COL_BG, fg=COL_TEXT, bd=0).pack(side='right', padx=8)

        body = tk.Frame(center, bg=COL_BG)
        body.grid(row=1, column=0, sticky='nsew')
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self.mascota = MascotaCanvas(body, bg=COL_BG)
        try:
            # Attach wake word engine if enabled
            self.mascota.wakeword = getattr(self.app, 'wakeword', None)
        except Exception:
            pass
        self.mascota.grid(row=0, column=0, sticky='nsew')

        footer = tk.Frame(center, bg=COL_BG)
        footer.grid(row=2, column=0, pady=(6, 12))
        tk.Button(footer, text='Pesar', command=self._open_weight).pack(side='left', padx=4)
        tk.Button(footer, text='Favoritos', command=self._open_favs).pack(side='left', padx=4)
        tk.Button(footer, text='Escanear', command=self._open_scan).pack(side='left', padx=4)
        tk.Button(footer, text='Temporizador', command=self._open_timer).pack(side='left', padx=4)
        tk.Button(footer, text='🎤 Escuchar', command=self._toggle_listen).pack(side='left', padx=8)

        # Prepare overlays
        self._ov_weight = WeightOverlay(self, self.app)
        self._ov_favs = FavoritesOverlay(self, self.app, on_add_item=self._on_add_food)
        self._ov_scan = ScannerOverlay(self, self.app, on_result=self._on_scan_v2, on_timeout=self._on_scan_timeout, timeout_ms=12000)
        self._ov_timer = TimerOverlay(self, self.app)

        # Voz
        self.voice = VoiceService()
        self._awaiting_cmd = False

    def _open_weight(self):
        self.mascota.set_state('process')
        self._ov_weight.show()

    def _open_favs(self):
        self.mascota.set_state('listen')
        self._ov_favs.show()

    def _open_scan(self):
        self.mascota.set_state('process')
        self._ov_scan.show()

    def _open_timer(self):
        self.mascota.set_state('idle')
        self._ov_timer.show()

    def _on_add_food(self, item):
        try:
            # Hook: add item to current session if exists
            pass
        finally:
            self.mascota.set_state('idle')

    def _on_scan(self, code: str):
        # Hook: search by barcode
        self.mascota.set_state('idle')
        # Aquí podríamos abrir favoritos prefiltrados o resolver producto

    def _on_scan_timeout(self):
        self.mascota.set_state('idle')

    # v2: background OFF lookup + add/discard dialog
    def _on_scan_v2(self, code: str):
        self.mascota.set_state('process')
        def worker():
            prod = None
            try:
                prod = fetch_off(code)
            except Exception:
                prod = None
            def done():
                if not prod:
                    self.mascota.set_state('idle')
                    try:
                        from tkinter import messagebox
                        messagebox.showinfo('Escáner', 'Producto no encontrado')
                    except Exception:
                        pass
                    return
                entry = upsert_from_off(prod) or {}
                name = (entry.get('name') or (prod.get('product_name') if isinstance(prod, dict) else None) or code)
                macros = entry.get('macros_100') or {}
                self._ask_add_to_favorites(name, macros, entry)
            try:
                self.after(0, done)
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def _ask_add_to_favorites(self, name: str, macros: dict, entry: dict):
        top = tk.Toplevel(self)
        try:
            top.attributes('-topmost', True)
        except Exception:
            pass
        top.transient(self.winfo_toplevel())
        top.configure(bg=COL_BG)
        top.title('Resultado escáner')
        fr = tk.Frame(top, bg=COL_CARD, highlightbackground=COL_BORDER, highlightthickness=1)
        fr.pack(fill='both', expand=True, padx=12, pady=12)
        tk.Label(fr, text=name, bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, 'bold')).pack(anchor='w')
        details = f"kcal:{macros.get('kcal',0)}  HC:{macros.get('carbs',0)}  Prot:{macros.get('protein',0)}  Gr:{macros.get('fat',0)} (por 100g)"
        tk.Label(fr, text=details, bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT)).pack(anchor='w', pady=(4,8))
        btns = tk.Frame(fr, bg=COL_CARD); btns.pack(fill='x', pady=(6,0))
        def _add():
            self._add_to_favorites_file(entry)
            try:
                from tkinter import messagebox
                messagebox.showinfo('Favoritos', 'Añadido a favoritos')
            except Exception:
                pass
            top.destroy()
            self.mascota.set_state('idle')
        def _discard():
            top.destroy()
            self.mascota.set_state('idle')
        tk.Button(btns, text='Añadir a favoritos', command=_add, bg=COL_ACCENT, fg='white').pack(side='left', padx=6)
        tk.Button(btns, text='Descartar', command=_discard).pack(side='right', padx=6)

    def _add_to_favorites_file(self, off_entry: dict):
        try:
            name = off_entry.get('name') or ''
            macros = off_entry.get('macros_100') or {}
            item = {
                'id': off_entry.get('id') or name,
                'name': name,
                'kcal': float(macros.get('kcal') or 0),
                'carbs': float(macros.get('carbs') or 0),
                'protein': float(macros.get('protein') or 0),
                'fat': float(macros.get('fat') or 0),
            }
        except Exception:
            return
        path = Path.home() / '.config' / 'bascula' / 'foods.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        data = []
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            data = []
        out = []
        seen = False
        for d in data:
            try:
                if d.get('id') == item['id'] or (d.get('name') == item['name'] and item['name']):
                    out.append(item); seen = True
                else:
                    out.append(d)
            except Exception:
                out.append(d)
        if not seen:
            out.append(item)
        try:
            path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception:
            pass

    # ---- Voz ----
    def _toggle_listen(self):
        if self.voice.is_listening():
            # No hay stop directo (script externo). Solo feedback.
            return
        self.mascota.set_state('listen')
        self._awaiting_cmd = True
        try:
            cfg = self.app.get_cfg()
            dev = (cfg.get('mic_device') or None)
            dur = int(cfg.get('mic_duration', 3) or 3)
            rate = int(cfg.get('mic_rate', 16000) or 16000)
        except Exception:
            dev = None; dur = 3; rate = 16000
        self.voice.start_listening(lambda txt: self.after(0, lambda: self._handle_voice(txt)), device=dev, duration=dur, rate=rate)

    def _handle_voice(self, text: str):
        text = (text or '').strip().lower()
        if not text:
            self.mascota.set_state('idle')
            return
        self.mascota.set_state('process')
        action = self._parse_command(text)
        said = None
        if action == 'weigh':
            self._open_weight(); said = 'Abriendo peso'
        elif action == 'favorites':
            self._open_favs(); said = 'Abriendo favoritos'
        elif action == 'scan':
            self._open_scan(); said = 'Abriendo escáner'
        elif action == 'timer':
            self._open_timer(); said = 'Abriendo temporizador'
        elif action == 'close':
            self._close_overlays(); said = 'Cerrando'
        elif action == 'settings':
            self.app.show_screen('settingsmenu'); said = 'Ajustes'
        else:
            said = 'No entendí'
        if said:
            try: self.voice.speak(said)
            except Exception: pass
        # Volver a idle si no hay overlay abierto que cambie el estado
        if action not in ('weigh', 'scan'):
            self.mascota.set_state('idle')

    def _parse_command(self, text: str) -> str:
        t = text
        # Sinónimos básicos en castellano
        if any(k in t for k in ['pesar', 'peso', 'báscula', 'balanza']):
            return 'weigh'
        if any(k in t for k in ['favorito', 'favoritos', 'buscar', 'alimento', 'comida']):
            return 'favorites'
        if any(k in t for k in ['escáner', 'escanear', 'scanner', 'codigo', 'código']):
            return 'scan'
        if any(k in t for k in ['temporizador', 'timer', 'cronómetro', 'cronometro']):
            return 'timer'
        if any(k in t for k in ['cerrar', 'salir', 'ocultar']):
            return 'close'
        if any(k in t for k in ['ajustes', 'configuración', 'configuracion', 'settings']):
            return 'settings'
        return ''

    def _close_overlays(self):
        try: self._ov_weight.hide()
        except Exception: pass
        try: self._ov_favs.hide()
        except Exception: pass
        try: self._ov_scan.hide()
        except Exception: pass
        try: self._ov_timer.hide()
        except Exception: pass
