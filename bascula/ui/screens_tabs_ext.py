# -*- coding: utf-8 -*-
"""
Pantalla de ajustes rediseñada con navegación por pestañas y organización clara
"""
import tkinter as tk
from tkinter import ttk
import os, json, subprocess, socket
from pathlib import Path
from bascula.services.retention import prune_jsonl
from bascula.ui.widgets import *
from bascula.ui.screens import BaseScreen

try:
    import requests
except:
    requests = None

try:
    import qrcode
    from PIL import Image, ImageTk
    _QR_OK = True
except:
    _QR_OK = False

BASE_URL = os.environ.get('BASCULA_WEB_URL', 'http://127.0.0.1:8080')

class TabbedSettingsMenuScreen(BaseScreen):
    """Pantalla de ajustes con navegación por pestañas"""
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app)
        
        # Header principal
        header = tk.Frame(self, bg=COL_BG)
        header.pack(fill="x", padx=20, pady=(15, 10))
        
        tk.Label(header, text="⚙", bg=COL_BG, fg=COL_ACCENT,
                font=("DejaVu Sans", 28)).pack(side="left")
        tk.Label(header, text="Configuración", bg=COL_BG, fg=COL_TEXT,
                font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=10)
        
        # Botón volver
        back_btn = tk.Button(header, text="← Volver", command=lambda: self.app.show_screen('home'),
                           bg=COL_BORDER, fg=COL_TEXT, font=("DejaVu Sans", FS_BTN_SMALL),
                           bd=0, relief="flat", cursor="hand2")
        # Añadimos botón discreto para silenciar/activar audio
        self._audio_btn = tk.Button(header,
                                    text=("🔊" if self.app.get_cfg().get('sound_enabled', True) else "🔇"),
                                    command=self._toggle_audio,
                                    bg=COL_BG, fg=COL_TEXT,
                                    bd=0, relief="flat", cursor="hand2",
                                    font=("DejaVu Sans", 12, "bold"), highlightthickness=0, width=3)
        self._audio_btn.pack(side="right", padx=(0, 8))
        # Normalizamos el icono (emoji o texto) según cfg/entorno
        try:
            self._audio_btn.config(text=self._audio_icon())
        except Exception:
            pass
        back_btn.pack(side="right")
        
        # Container principal con pestañas
        main_container = Card(self)
        main_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Notebook para pestañas
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Estilo para las pestañas
        
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Settings.TNotebook', background=COL_CARD, borderwidth=0)
        style.configure('Settings.TNotebook.Tab',
                       background=COL_CARD,
                       foreground=COL_TEXT,
                       padding=[20, 10],
                       font=("DejaVu Sans", FS_TEXT))
        # === Estilos táctiles globales (scrollbars/combos/checks) ===
        try:
            # Scrollbars más gruesas para tacto
            style.configure('Vertical.TScrollbar', width=24)
            style.configure('Horizontal.TScrollbar', width=24)
            # Combobox, Checkbutton y Radiobutton más grandes
            style.configure('Big.TCombobox', padding=8, arrowsize=24)
            style.configure('Big.TCheckbutton', padding=8)
            style.configure('Big.TRadiobutton', padding=8)
        except Exception:
            pass
        style.map('Settings.TNotebook.Tab',
                 background=[('selected', COL_ACCENT)],
                 foreground=[('selected', 'white')])
# === Estilos táctiles globales (scrollbars/combos/checks) ===
        try:
            # Scrollbars más gruesas para tacto
            style.configure('Vertical.TScrollbar', width=24)
            style.configure('Horizontal.TScrollbar', width=24)
            # Combobox, Checkbutton y Radiobutton más grandes
            style.configure('Big.TCombobox', padding=8, arrowsize=24)
            style.configure('Big.TCheckbutton', padding=8)
            style.configure('Big.TRadiobutton', padding=8)
        except Exception:
            pass
        
        # Crear pestañas
        self._create_general_tab()
        self._create_scale_tab()
        self._create_network_tab()
        self._create_diabetes_tab()
        self._create_storage_tab()
        self._create_about_tab()
        self._create_ota_tab()
        
        self.toast = Toast(self)

    # ---- helpers: UI layout ----
    def _add_section_header(self, parent, text, top_pad=20):
        """Añade un encabezado de sección con separador."""
        try:
            tk.Frame(parent, height=1, bg=COL_BORDER).pack(fill="x", pady=(top_pad, 10))
            tk.Label(parent, text=text, bg=COL_CARD, fg=COL_ACCENT,
                     font=("DejaVu Sans", FS_CARD_TITLE, "bold")).pack(anchor="w")
        except Exception:
            pass

    def _create_option_row(self, parent):
        """Crea un contenedor estándar para una fila de opción."""
        fr = tk.Frame(parent, bg=COL_CARD)
        fr.pack(fill="x", pady=5)
        return fr

    # ---- handlers: General tab ----
    def _toggle_sound(self):
        try:
            cfg = self.app.get_cfg()
            cfg['sound_enabled'] = bool(self.var_sound.get())
            self.app.save_cfg()
            if hasattr(self.app, 'get_audio') and self.app.get_audio():
                self.app.get_audio().set_enabled(cfg['sound_enabled'])
            try:
                if hasattr(self, '_audio_btn'):
                    self._audio_btn.config(text=("🔊" if cfg['sound_enabled'] else "🔇"))
            except Exception:
                pass
            self.toast.show("Sonido: " + ("ON" if cfg['sound_enabled'] else "OFF"), 900)
        except Exception:
            pass

    def _apply_sound_theme(self):
        try:
            theme = (self.var_theme.get() or '').strip()
            if theme not in ("beep", "voice_es"):
                return
            cfg = self.app.get_cfg(); cfg['sound_theme'] = theme; self.app.save_cfg()
            if hasattr(self.app, 'get_audio') and self.app.get_audio():
                self.app.get_audio().set_theme(theme)
            self.toast.show("Tema sonido: " + theme, 900)
        except Exception:
            pass

    # Toggle rápido desde el icono del header
    def _toggle_audio(self):
        try:
            cfg = self.app.get_cfg()
            new_en = not bool(cfg.get('sound_enabled', True))
            cfg['sound_enabled'] = new_en
            self.app.save_cfg()
            if hasattr(self.app, 'get_audio') and self.app.get_audio():
                self.app.get_audio().set_enabled(new_en)
            if hasattr(self, '_audio_btn'):
                self._audio_btn.config(text=self._audio_icon())
            try:
                if hasattr(self, 'var_sound'):
                    self.var_sound.set(new_en)
            except Exception:
                pass
            self.toast.show("Sonido: " + ("ON" if new_en else "OFF"), 900)
        except Exception:
            pass

    def _audio_icon(self) -> str:
        try:
            no_emoji = bool(self.app.get_cfg().get('no_emoji', False)) or bool(os.environ.get('BASCULA_NO_EMOJI'))
            en = bool(self.app.get_cfg().get('sound_enabled', True))
        except Exception:
            no_emoji = bool(os.environ.get('BASCULA_NO_EMOJI'))
            en = True
        if no_emoji:
            return 'ON' if en else 'OFF'
        return '🔊' if en else '🔇'

    def _test_sound(self):
        try:
            au = self.app.get_audio()
        except Exception:
            au = None
        # Probar beep (si está activado)
        try:
            if au and bool(self.app.get_cfg().get('sound_enabled', True)):
                au.play_event('tare_ok')  # beep corto de prueba
        except Exception:
            pass
        # Probar voz: SIEMPRE intentamos hablar para validar la instalación TTS,
        # independientemente del toggle de voz (BG), porque esto es una "prueba de dispositivo".
        try:
            if au:
                if hasattr(au, 'speak_event'):
                    au.speak_event('announce_bg', n=123)
                else:
                    au.play_event('announce_bg')
        except Exception:
            pass
        # Feedback si no hay espeak-ng detectado
        try:
            import shutil
            if shutil.which('espeak-ng') is None and shutil.which('espeak') is None:
                self.toast.show("TTS no disponible: instala espeak-ng/mbrola", 2000, COL_WARN)
            else:
                self.toast.show("Prueba de sonido ejecutada", 900)
        except Exception:
            self.toast.show("Prueba de sonido ejecutada", 900)
        # Mostrar diagnóstico en toast (voz candidata y dispositivo)
        try:
            if au and hasattr(au, 'tts_diag'):
                d = au.tts_diag()
                self.toast.show(f"TTS: espeak={'sí' if d.get('espeak') else 'no'}, mbrola={'sí' if d.get('mbrola') else 'no'}, voz={d.get('voice')}, aplay={d.get('aplay_device') or 'default'}", 2500)
        except Exception:
            pass




    def _apply_decimals(self):
        try:
            cfg = self.app.get_cfg()
            cfg['decimals'] = int(self.var_decimals.get())
            self.app.save_cfg()
            self.toast.show(f"Decimales: {cfg['decimals']}", 900)
        except Exception:
            pass

    def _apply_unit(self):
        try:
            cfg = self.app.get_cfg(); unit = (self.var_unit.get() or 'g')
            cfg['unit'] = unit; self.app.save_cfg()
            self.toast.show(f"Unidad: {unit}", 900)
        except Exception:
            pass

    # ---- handlers: Scale tab ----
    def _apply_smoothing(self):
        try:
            val = int(self.var_smoothing.get())
            if hasattr(self, 'smooth_label'):
                self.smooth_label.config(text=str(val))
            cfg = self.app.get_cfg(); cfg['smoothing'] = max(1, min(50, val)); self.app.save_cfg()
        except Exception:
            pass

    # ---- handlers: Network tab ----
    def _get_current_ip(self):
        ip = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.2)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        except Exception:
            pass
        finally:
            try: s.close()
            except Exception: pass
        if not ip:
            try:
                out = subprocess.check_output(["/bin/sh", "-lc", "hostname -I | awk '{print $1}'"], text=True, timeout=1).strip()
                ip = out or None
            except Exception:
                ip = None
        return ip

    def _read_pin(self) -> str:
        try:
            p = Path.home() / ".config" / "bascula" / "pin.txt"
            if p.exists():
                return p.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            pass
        return "N/D"

    def _refresh_network(self):
        try:
            if hasattr(self, 'pin_label'):
                self.pin_label.config(text=self._read_pin())
            ip = self._get_current_ip()
            self.toast.show("Red: " + (ip or "Sin IP"), 900)
        except Exception:
            pass

    # ---- handlers: Diabetes tab ----
    def _check_nightscout(self) -> bool:
        try:
            p = Path.home() / ".config" / "bascula" / "nightscout.json"
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
                return bool((data.get('url') or '').strip())
        except Exception:
            pass
        return False

    def _save_diabetes_params(self):
        try:
            cfg = self.app.get_cfg()
            def to_num(s, d):
                try: return float(s)
                except Exception: return d
            cfg['target_bg_mgdl'] = int(to_num(self.param_vars.get('target_bg_mgdl').get(), 110))
            cfg['isf_mgdl_per_u'] = int(to_num(self.param_vars.get('isf_mgdl_per_u').get(), 50))
            cfg['carb_ratio_g_per_u'] = int(to_num(self.param_vars.get('carb_ratio_g_per_u').get(), 10))
            cfg['dia_hours'] = int(to_num(self.param_vars.get('dia_hours').get(), 4))
            self.app.save_cfg()
            self.toast.show("Parámetros guardados", 1000, COL_SUCCESS)
        except Exception as e:
            self.toast.show(f"Error: {e}", 1300, COL_DANGER)

    def _save_diabetes_params_ext(self):
        """Guarda parámetros de bolo y los ajustes de BG (umbrales y avisos)."""
        try:
            # guardar parámetros existentes
            self._save_diabetes_params()
        except Exception:
            pass
        try:
            cfg = self.app.get_cfg()
            def to_int(v, d):
                try:
                    return int(float(v))
                except Exception:
                    return d
            # Umbrales
            if hasattr(self, 'bg_vars'):
                try:
                    cfg['bg_low_threshold'] = to_int(self.bg_vars.get('bg_low_threshold').get(), 70)
                except Exception:
                    cfg['bg_low_threshold'] = 70
                try:
                    cfg['bg_warn_threshold'] = to_int(self.bg_vars.get('bg_warn_threshold').get(), 180)
                except Exception:
                    cfg['bg_warn_threshold'] = 180
                try:
                    cfg['bg_high_threshold'] = to_int(self.bg_vars.get('bg_high_threshold').get(), 250)
                except Exception:
                    cfg['bg_high_threshold'] = 250
                if cfg['bg_warn_threshold'] <= cfg['bg_low_threshold']:
                    cfg['bg_warn_threshold'] = cfg['bg_low_threshold'] + 10
                if cfg['bg_high_threshold'] <= cfg['bg_warn_threshold']:
                    cfg['bg_high_threshold'] = cfg['bg_warn_threshold'] + 20
            # Toggles
            try:
                cfg['bg_alerts_enabled'] = bool(self.var_bg_alerts.get())
            except Exception:
                pass
            try:
                cfg['bg_announce_on_alert'] = bool(self.var_bg_announce.get())
            except Exception:
                pass
            try:
                cfg['bg_announce_every'] = bool(self.var_bg_every.get())
            except Exception:
                pass
            self.app.save_cfg()
            self.toast.show("Parámetros BG guardados", 900)
        except Exception as e:
            self.toast.show(f"BG error: {e}", 1300, COL_DANGER)

    def _toggle_dm(self):
        try:
            cfg = self.app.get_cfg()
            cfg['diabetic_mode'] = bool(self.var_dm.get())
            self.app.save_cfg()
            try:
                # Habilitar/deshabilitar botón Nightscout si existe
                if hasattr(self, 'ns_config_btn') and self.ns_config_btn:
                    self.ns_config_btn.configure(state=("normal" if cfg['diabetic_mode'] else "disabled"))
            except Exception:
                pass
            self.toast.show("Modo diabético: " + ("ON" if cfg['diabetic_mode'] else "OFF"), 900)
        except Exception:
            pass

    # ---- handlers: Storage tab ----
    def _apply_retention(self):
        try:
            vals = {
                'meals_max_days': int(self.ret_vars.get('meals_max_days').get()),
                'meals_max_entries': int(self.ret_vars.get('meals_max_entries').get()),
            }
            mb = int(self.ret_vars.get('meals_max_bytes').get())
            vals['meals_max_bytes'] = max(0, mb) * 1_000_000
            cfg = self.app.get_cfg(); cfg.update(vals); self.app.save_cfg()
            self.toast.show("Retención aplicada", 900)
        except Exception as e:
            self.toast.show(f"Error: {e}", 1300, COL_DANGER)

    def _clear_history(self):
        try:
            path = Path.home() / '.config' / 'bascula' / 'meals.jsonl'
            if not path.exists():
                self.toast.show("Sin histórico", 900)
                return
            cfg = self.app.get_cfg()
            prune_jsonl(
                path,
                max_days=int(cfg.get('meals_max_days', 0) or 0),
                max_entries=int(cfg.get('meals_max_entries', 0) or 0),
                max_bytes=int(cfg.get('meals_max_bytes', 0) or 0),
            )
            self.toast.show("Histórico limpiado", 1000, COL_SUCCESS)
        except Exception as e:
            self.toast.show(f"Error: {e}", 1300, COL_DANGER)

    def _apply_keep_photos(self):
        try:
            cfg = self.app.get_cfg(); cfg['keep_photos'] = bool(self.var_keep_photos.get()); self.app.save_cfg()
            self.toast.show("Fotos: " + ("mantener" if cfg['keep_photos'] else "no guardar"), 900)
        except Exception:
            pass

    def _clear_photos(self):
        try:
            st = Path.home() / '.bascula' / 'photos' / 'staging'
            n = 0
            if st.exists():
                for p in st.glob('*.jpg'):
                    try:
                        p.unlink(); n += 1
                    except Exception:
                        pass
            self.toast.show(f"Fotos eliminadas: {n}", 900)
        except Exception:
            pass
    
    def _create_general_tab(self):
        """Pestaña de configuración general"""
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="🎯 General")
        
        sf = TouchScrollableFrame(tab, bg=COL_CARD)
        sf.pack(fill="both", expand=True, padx=20, pady=15)
        scroll_frame = sf.inner
        
        # === Sección: Interfaz ===
        self._add_section_header(scroll_frame, "Interfaz de Usuario")
        
        # Sonido
        sound_frame = self._create_option_row(scroll_frame)
        tk.Label(sound_frame, text="Sonido:", bg=COL_CARD, fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(0, 10))
        
        self.var_sound = tk.BooleanVar(value=self.app.get_cfg().get('sound_enabled', True))
        sound_check = ttk.Checkbutton(sound_frame, text="Activado", variable=self.var_sound,
                                     command=self._toggle_sound, style='Big.TCheckbutton')
        sound_check.pack(side="left")
        
        # Tema de sonido
        self.var_theme = tk.StringVar(value=self.app.get_cfg().get('sound_theme', 'beep'))
        theme_combo = ttk.Combobox(sound_frame, textvariable=self.var_theme,
                                  values=["beep", "voice_es"], width=10, state="readonly", style='Big.TCombobox')
        theme_combo.pack(side="left", padx=(20, 10))
        theme_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_sound_theme())
        
        test_btn = tk.Button(sound_frame, text="Probar", command=self._test_sound,
                           bg=COL_ACCENT, fg="white", font=("DejaVu Sans", FS_TEXT),
                           bd=0, relief="flat", cursor="hand2", padx=15)
        test_btn.pack(side="left")
        
        # Decimales
        decimal_frame = self._create_option_row(scroll_frame)
        tk.Label(decimal_frame, text="Decimales en peso:", bg=COL_CARD, fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(0, 10))
        
        self.var_decimals = tk.IntVar(value=self.app.get_cfg().get('decimals', 0))
        for i in range(2):
            rb = ttk.Radiobutton(decimal_frame, text=str(i, style='Big.TRadiobutton'), variable=self.var_decimals,
                               value=i, command=self._apply_decimals)
            rb.pack(side="left", padx=5)
        # Unidades: forzado a gramos (selector eliminado)
        try:
            cfg = self.app.get_cfg(); cfg['unit'] = 'g'; self.app.save_cfg()
        except Exception:
            pass

    
    def _create_scale_tab(self):
        """Pestaña de configuración de báscula"""
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="⚖ Báscula")
        
        # Contenido desplazable para evitar que la última línea quede oculta
        sf = TouchScrollableFrame(tab, bg=COL_CARD)
        sf.pack(fill="both", expand=True, padx=20, pady=15)
        content = sf.inner
        
        # === Sección: Calibración ===
        self._add_section_header(content, "Calibración")
        
        cal_info = tk.Frame(content, bg="#1a1f2e", relief="ridge", bd=1)
        cal_info.pack(fill="x", pady=10)
        cal_info_inner = tk.Frame(cal_info, bg="#1a1f2e")
        cal_info_inner.pack(padx=15, pady=10)
        
        tk.Label(cal_info_inner, text="Factor actual:", bg="#1a1f2e", fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)).grid(row=0, column=0, sticky="w", pady=2)
        self.cal_factor_label = tk.Label(cal_info_inner, 
                                        text=f"{self.app.get_cfg().get('calib_factor', 1.0):.6f}",
                                        bg="#1a1f2e", fg=COL_ACCENT,
                                        font=("DejaVu Sans Mono", FS_TEXT, "bold"))
        self.cal_factor_label.grid(row=0, column=1, sticky="w", padx=20, pady=2)
        
        tk.Label(cal_info_inner, text="Puerto serie:", bg="#1a1f2e", fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)).grid(row=1, column=0, sticky="w", pady=2)
        tk.Label(cal_info_inner, text=self.app.get_cfg().get('port', '/dev/serial0'),
                bg="#1a1f2e", fg=COL_MUTED,
                font=("DejaVu Sans Mono", FS_TEXT)).grid(row=1, column=1, sticky="w", padx=20, pady=2)
        
        cal_btn = tk.Button(content, text="⚖ Iniciar Calibración",
                          command=lambda: self.app.show_screen('calib'),
                          bg=COL_ACCENT, fg="white",
                          font=("DejaVu Sans", FS_BTN_SMALL, "bold"),
                          bd=0, relief="flat", cursor="hand2", padx=20, pady=10)
        cal_btn.pack(pady=10)
        
        # === Sección: Filtrado ===
        self._add_section_header(content, "Filtrado de Señal", top_pad=30)
        
        smooth_frame = self._create_option_row(content)
        tk.Label(smooth_frame, text="Suavizado (muestras):", bg=COL_CARD, fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(0, 10))
        
        self.var_smoothing = tk.IntVar(value=self.app.get_cfg().get('smoothing', 5))
        smooth_scale = ttk.Scale(smooth_frame, from_=1, to=20,
                               variable=self.var_smoothing, orient="horizontal",
                               length=200, command=lambda v: self._apply_smoothing())
        smooth_scale.pack(side="left", padx=10)
        
        self.smooth_label = tk.Label(smooth_frame, text=str(self.var_smoothing.get()),
                                    bg=COL_CARD, fg=COL_ACCENT,
                                    font=("DejaVu Sans", FS_TEXT, "bold"))
        self.smooth_label.pack(side="left", padx=5)
    
    def _create_network_tab(self):
        """Pestaña de configuración de red"""
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="📡 Red")
        
        sf = TouchScrollableFrame(tab, bg=COL_CARD)
        sf.pack(fill="both", expand=True, padx=20, pady=15)
        content = sf.inner
        
        # === Sección: Estado de Red ===
        self._add_section_header(content, "Estado de Conexión")
        
        status_frame = tk.Frame(content, bg="#1a1f2e", relief="ridge", bd=1)
        status_frame.pack(fill="x", pady=10)
        status_inner = tk.Frame(status_frame, bg="#1a1f2e")
        status_inner.pack(padx=15, pady=10)
        
        # Detectar IP actual
        ip = self._get_current_ip()
        
        tk.Label(status_inner, text="IP Local:", bg="#1a1f2e", fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)).grid(row=0, column=0, sticky="w", pady=2)
        tk.Label(status_inner, text=ip if ip else "No conectado",
                bg="#1a1f2e", fg=(COL_SUCCESS if ip else COL_WARN),
                font=("DejaVu Sans Mono", FS_TEXT, "bold")).grid(row=0, column=1, padx=20, pady=2)
        
        # === Sección: Mini-Web ===
        self._add_section_header(content, "Panel Web", top_pad=20)
        
        web_frame = self._create_option_row(content)
        tk.Label(web_frame, text="URL:", bg=COL_CARD, fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(0, 10))
        
        url = f"http://{ip if ip else 'localhost'}:8080"
        url_label = tk.Label(web_frame, text=url, bg=COL_CARD, fg=COL_ACCENT,
                           font=("DejaVu Sans Mono", FS_TEXT))
        url_label.pack(side="left")
        
        # PIN
        pin_frame = self._create_option_row(content)
        tk.Label(pin_frame, text="PIN:", bg=COL_CARD, fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(0, 10))
        
        pin = self._read_pin()
        self.pin_label = tk.Label(pin_frame, text=pin, bg=COL_CARD, fg=COL_ACCENT,
                                 font=("DejaVu Sans Mono", FS_TEXT, "bold"))
        self.pin_label.pack(side="left", padx=(0, 20))
        
        refresh_btn = tk.Button(pin_frame, text="Actualizar", command=self._refresh_network,
                              bg=COL_BORDER, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT),
                              bd=0, relief="flat", cursor="hand2", padx=15)
        refresh_btn.pack(side="left")
        
        # QR Code si está disponible
        if _QR_OK and ip:
            qr_frame = tk.Frame(content, bg=COL_CARD)
            qr_frame.pack(pady=20)
            
            try:
                qr = qrcode.QRCode(border=1, box_size=3)
                qr.add_data(url)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
                img = img.resize((150, 150))
                photo = ImageTk.PhotoImage(img)
                
                qr_label = tk.Label(qr_frame, image=photo, bg=COL_CARD)
                qr_label.image = photo  # Keep reference
                qr_label.pack()
                
                tk.Label(qr_frame, text="Escanea para acceder desde el móvil",
                        bg=COL_CARD, fg=COL_MUTED,
                        font=("DejaVu Sans", FS_TEXT-1)).pack(pady=(5, 0))
            except:
                pass
        
        # Botones de configuración
        btn_frame = tk.Frame(content, bg=COL_CARD)
        btn_frame.pack(pady=20)
        
        wifi_btn = tk.Button(btn_frame, text="📶 Configurar Wi-Fi",
                           command=lambda: self.app.show_screen('wifi'),
                           bg="#3b82f6", fg="white",
                           font=("DejaVu Sans", FS_BTN_SMALL, "bold"),
                           bd=0, relief="flat", cursor="hand2", padx=20, pady=10)
        wifi_btn.pack(side="left", padx=5)
        
        api_btn = tk.Button(btn_frame, text="🔑 API Key",
                          command=lambda: self.app.show_screen('apikey'),
                          bg="#6b7280", fg="white",
                          font=("DejaVu Sans", FS_BTN_SMALL, "bold"),
                          bd=0, relief="flat", cursor="hand2", padx=20, pady=10)
        api_btn.pack(side="left", padx=5)
    
    def _create_diabetes_tab(self):
        """Pestaña de configuración para diabéticos"""
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="💉 Diabetes")
        
        sf = TouchScrollableFrame(tab, bg=COL_CARD)
        sf.pack(fill="both", expand=True, padx=20, pady=15)
        content = sf.inner
        
        # === Modo Diabético ===
        self._add_section_header(content, "Modo Diabético")
        
        dm_frame = self._create_option_row(content)
        self.var_dm = tk.BooleanVar(value=self.app.get_cfg().get('diabetic_mode', False))
        dm_check = ttk.Checkbutton(dm_frame, text="Activar modo diabético (experimental, style='Big.TCheckbutton')",
                                  variable=self.var_dm, command=self._toggle_dm)
        dm_check.pack(side="left")
        
        tk.Label(dm_frame, text="⚠ No es consejo médico", bg=COL_CARD, fg=COL_WARN,
                font=("DejaVu Sans", FS_TEXT-1)).pack(side="left", padx=20)
        
        # === Nightscout ===
        self._add_section_header(content, "Nightscout", top_pad=30)
        
        ns_info = tk.Frame(content, bg="#1a1f2e", relief="ridge", bd=1)
        ns_info.pack(fill="x", pady=10)
        ns_inner = tk.Frame(ns_info, bg="#1a1f2e")
        ns_inner.pack(padx=15, pady=10)
        
        # Check Nightscout status
        ns_configured = self._check_nightscout()
        
        tk.Label(ns_inner, text="Estado:", bg="#1a1f2e", fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)).grid(row=0, column=0, sticky="w", pady=2)
        tk.Label(ns_inner, text="Configurado" if ns_configured else "No configurado",
                bg="#1a1f2e", fg=(COL_SUCCESS if ns_configured else COL_WARN),
                font=("DejaVu Sans", FS_TEXT, "bold")).grid(row=0, column=1, padx=20, pady=2)
        
        ns_btn = tk.Button(content, text="⚙ Configurar Nightscout",
                         command=lambda: self.app.show_screen('nightscout'),
                         bg=COL_ACCENT, fg="white",
                         font=("DejaVu Sans", FS_BTN_SMALL, "bold"),
                         bd=0, relief="flat", cursor="hand2", padx=20, pady=10,
                         state=("normal" if self.var_dm.get() else "disabled"))
        ns_btn.pack(pady=10)
        self.ns_config_btn = ns_btn
        
        # === Parámetros de Bolo ===
        self._add_section_header(content, "Parámetros de Bolo", top_pad=30)
        
        params_frame = tk.Frame(content, bg=COL_CARD)
        params_frame.pack(fill="x", pady=10)
        
        # Grid de parámetros
        params = [
            ("Objetivo (mg/dL)", 'target_bg_mgdl', 110),
            ("ISF (mg/dL/U)", 'isf_mgdl_per_u', 50),
            ("Ratio HC (g/U)", 'carb_ratio_g_per_u', 10),
            ("DIA (horas)", 'dia_hours', 4),
        ]
        
        self.param_vars = {}
        for i, (label, key, default) in enumerate(params):
            row = i // 2
            col = i % 2
            
            frame = tk.Frame(params_frame, bg=COL_CARD)
            frame.grid(row=row, column=col, padx=10, pady=5, sticky="w")
            
            tk.Label(frame, text=label, bg=COL_CARD, fg=COL_TEXT,
                    font=("DejaVu Sans", FS_TEXT)).pack(anchor="w")
            
            var = tk.StringVar(value=str(self.app.get_cfg().get(key, default)))
            entry = tk.Entry(frame, textvariable=var, width=10,
                           bg="#1a1f2e", fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT),
                           relief="flat", bd=5)
            entry.pack(anchor="w", pady=2)
            
            self.param_vars[key] = var

        # === Glucosa (BG) ===
        self._add_section_header(content, "Glucosa (BG)", top_pad=30)

        # Umbrales (mg/dL)
        thr_frame = tk.Frame(content, bg=COL_CARD)
        thr_frame.pack(fill="x", pady=6)
        tk.Label(thr_frame, text="Umbrales (mg/dL):", bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(0, 10))

        self.bg_vars = {}
        def _mk_thr(label, key, default, width=6):
            fr = tk.Frame(thr_frame, bg=COL_CARD)
            fr.pack(side="left", padx=8)
            tk.Label(fr, text=label, bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT-1)).pack(anchor="w")
            v = tk.StringVar(value=str(self.app.get_cfg().get(key, default)))
            e = tk.Entry(fr, textvariable=v, width=width, bg="#1a1f2e", fg=COL_TEXT,
                         font=("DejaVu Sans", FS_TEXT-1), relief="flat", bd=4)
            e.pack(anchor="w")
            try:
                bind_numeric_popup(e)
            except Exception:
                pass
            try:
                GhostButton(fr, text="Teclado",
                            command=lambda k=key, _v=v, _label=label: KeypadPopup(
                                self, title=f"{_label} (mg/dL)",
                                initial=(_v.get() or "0"),
                                allow_dot=False,
                                on_accept=lambda s: _v.set(str(int(float(s))))),
                            micro=True).pack(anchor="w", pady=(2,0))
            except Exception:
                pass

            self.bg_vars[key] = v

        _mk_thr("Baja <", 'bg_low_threshold', 70)
        _mk_thr("Advertencia >", 'bg_warn_threshold', 180)
        _mk_thr("Alta >", 'bg_high_threshold', 250)

        # Alertas
        alerts_frame = tk.Frame(content, bg=COL_CARD)
        alerts_frame.pack(fill="x", pady=6)
        self.var_bg_alerts = tk.BooleanVar(value=bool(self.app.get_cfg().get('bg_alerts_enabled', True)))
        self.var_bg_announce = tk.BooleanVar(value=bool(self.app.get_cfg().get('bg_announce_on_alert', True)))
        self.var_bg_every = tk.BooleanVar(value=bool(self.app.get_cfg().get('bg_announce_every', False)))
        ttk.Checkbutton(alerts_frame, text="Alertas sonoras en baja/alta", variable=self.var_bg_alerts, style='Big.TCheckbutton').pack(side="left")
        ttk.Checkbutton(alerts_frame, text="Anunciar valor al entrar en alerta", variable=self.var_bg_announce, style='Big.TCheckbutton').pack(side="left", padx=12)
        self.chk_bg_every = ttk.Checkbutton(alerts_frame, text="Anunciar cada lectura", variable=self.var_bg_every, style='Big.TCheckbutton')
        self.chk_bg_every.pack(side="left", padx=12)

        # Voz TTS independiente para BG
        self.var_voice_disabled = tk.BooleanVar(value=not bool(self.app.get_cfg().get('voice_enabled', False)))
        voice_row = tk.Frame(content, bg=COL_CARD)
        voice_row.pack(fill="x", pady=(0, 6))
        tk.Label(voice_row, text="Desactivar voz modo diabetes:", bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(0, 10))
        ttk.Checkbutton(voice_row, text="", variable=self.var_voice_disabled,
                        command=self._toggle_voice_disabled
                        , style='Big.TCheckbutton').pack(side="left")


        save_params_btn = tk.Button(content, text="💾 Guardar Parámetros",
                                   command=self._save_diabetes_params_ext,
                                   bg="#3b82f6", fg="white",
                                   font=("DejaVu Sans", FS_BTN_SMALL, "bold"),
                                   bd=0, relief="flat", cursor="hand2", padx=20, pady=10)
        save_params_btn.pack(pady=10)
    
    def _create_storage_tab(self):
        """Pestaña de almacenamiento y datos"""
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="💾 Datos")
        
        sf = TouchScrollableFrame(tab, bg=COL_CARD)
        sf.pack(fill="both", expand=True, padx=20, pady=15)
        content = sf.inner
        
        # === Histórico de Comidas ===
        self._add_section_header(content, "Histórico de Comidas")
        
        hist_frame = tk.Frame(content, bg=COL_CARD)
        hist_frame.pack(fill="x", pady=10)
        
        # Estadísticas
        stats_frame = tk.Frame(hist_frame, bg="#1a1f2e", relief="ridge", bd=1)
        stats_frame.pack(fill="x", pady=5)
        stats_inner = tk.Frame(stats_frame, bg="#1a1f2e")
        stats_inner.pack(padx=15, pady=10)
        
        meals_path = Path.home() / '.config' / 'bascula' / 'meals.jsonl'
        if meals_path.exists():
            size = meals_path.stat().st_size
            try:
                with open(meals_path, 'r', encoding='utf-8', errors='ignore') as f:
                    count = sum(1 for _ in f)
            except:
                count = 0
        else:
            size = 0
            count = 0
        
        tk.Label(stats_inner, text="Entradas:", bg="#1a1f2e", fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)).grid(row=0, column=0, sticky="w", pady=2)
        tk.Label(stats_inner, text=str(count), bg="#1a1f2e", fg=COL_ACCENT,
                font=("DejaVu Sans", FS_TEXT, "bold")).grid(row=0, column=1, padx=20, pady=2)
        
        tk.Label(stats_inner, text="Tamaño:", bg="#1a1f2e", fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)).grid(row=1, column=0, sticky="w", pady=2)
        tk.Label(stats_inner, text=f"{size/1_000_000:.2f} MB", bg="#1a1f2e", fg=COL_ACCENT,
                font=("DejaVu Sans", FS_TEXT, "bold")).grid(row=1, column=1, padx=20, pady=2)
        
        # Configuración de retención
        ret_frame = tk.Frame(content, bg=COL_CARD)
        ret_frame.pack(fill="x", pady=10)
        
        tk.Label(ret_frame, text="Retención:", bg=COL_CARD, fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT, "bold")).pack(anchor="w", pady=5)
        
        ret_grid = tk.Frame(ret_frame, bg=COL_CARD)
        ret_grid.pack(fill="x")
        
        self.ret_vars = {}
        ret_params = [
            ("Días máximo", 'meals_max_days', 180),
            ("Entradas máximo", 'meals_max_entries', 1000),
            ("Tamaño máximo (MB)", 'meals_max_bytes', 5),
        ]
        
        for i, (label, key, default) in enumerate(ret_params):
            frame = tk.Frame(ret_grid, bg=COL_CARD)
            frame.grid(row=i//2, column=i%2, padx=10, pady=5, sticky="w")
            
            tk.Label(frame, text=label, bg=COL_CARD, fg=COL_TEXT,
                    font=("DejaVu Sans", FS_TEXT)).pack(side="left")
            
            val = default if key != 'meals_max_bytes' else self.app.get_cfg().get(key, default*1_000_000)//1_000_000
            var = tk.StringVar(value=str(val))
            entry = tk.Entry(frame, textvariable=var, width=8,
                           bg="#1a1f2e", fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT),
                           relief="flat", bd=3)
            entry.pack(side="left", padx=10)
            
            self.ret_vars[key] = var
        
        # Botones de acción
        action_frame = tk.Frame(content, bg=COL_CARD)
        action_frame.pack(pady=15)
        
        apply_btn = tk.Button(action_frame, text="Aplicar Retención",
                            command=self._apply_retention,
                            bg="#3b82f6", fg="white",
                            font=("DejaVu Sans", FS_BTN_SMALL),
                            bd=0, relief="flat", cursor="hand2", padx=15, pady=8)
        apply_btn.pack(side="left", padx=5)
        
        clear_btn = tk.Button(action_frame, text="Limpiar Histórico",
                            command=self._clear_history,
                            bg=COL_DANGER, fg="white",
                            font=("DejaVu Sans", FS_BTN_SMALL),
                            bd=0, relief="flat", cursor="hand2", padx=15, pady=8)
        clear_btn.pack(side="left", padx=5)
        
        # === Fotos ===
        self._add_section_header(content, "Fotos Temporales", top_pad=30)
        
        photos_frame = self._create_option_row(content)
        self.var_keep_photos = tk.BooleanVar(value=self.app.get_cfg().get('keep_photos', False))
        photos_check = ttk.Checkbutton(photos_frame, 
                                      text="Mantener fotos entre reinicios",
                                      variable=self.var_keep_photos,
                                      command=self._apply_keep_photos, style='Big.TCheckbutton')
        photos_check.pack(side="left")
        
        clear_photos_btn = tk.Button(photos_frame, text="Limpiar Fotos",
                                    command=self._clear_photos,
                                    bg=COL_DANGER, fg="white",
                                    font=("DejaVu Sans", FS_TEXT),
                                    bd=0, relief="flat", cursor="hand2", padx=15)
        clear_photos_btn.pack(side="right")
    
    def _create_about_tab(self):
        """Pestaña de información"""
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="ℹ Acerca de")
        
        content = tk.Frame(tab, bg=COL_CARD)
        content.pack(fill="both", expand=True, padx=20, pady=15)
        
        # Logo y título
        title_frame = tk.Frame(content, bg=COL_CARD)
        title_frame.pack(pady=20)
        
        tk.Label(title_frame, text="⚖", bg=COL_CARD, fg=COL_ACCENT,
                font=("DejaVu Sans", 48)).pack()
        tk.Label(title_frame, text="Báscula Digital Pro", bg=COL_CARD, fg=COL_TEXT,
                font=("DejaVu Sans", FS_TITLE+2, "bold")).pack(pady=(10, 5))
        tk.Label(title_frame, text="v1.0.0", bg=COL_CARD, fg=COL_MUTED,
                font=("DejaVu Sans", FS_TEXT)).pack()
        
        # Info
        info_frame = tk.Frame(content, bg=COL_CARD)
        info_frame.pack(fill="x", padx=10, pady=10)
        tk.Label(info_frame, text="Proyecto: Bascula Digital Pro", bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", FS_TEXT)).pack(anchor="w")
        tk.Label(info_frame, text="Daniel Gonzalez Tellols y mi correo danieltellols@yahoo.es", bg=COL_CARD, fg=COL_MUTED,
                 font=("DejaVu Sans", FS_TEXT-1)).pack(anchor="w")

    def _create_ota_tab(self):
        """Pestaña de Actualizaciones (OTA)"""
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="⬇ OTA")

        content = tk.Frame(tab, bg=COL_CARD)
        content.pack(fill="both", expand=True, padx=20, pady=15)

        title = tk.Frame(content, bg=COL_CARD)
        title.pack(pady=(5, 10))
        tk.Label(title, text="Actualizaciones (OTA)", bg=COL_CARD, fg=COL_ACCENT,
                 font=("DejaVu Sans", FS_TITLE, "bold")).pack()

        # Version actual
        try:
            self._about_version_var = tk.StringVar(value=self._version_text())
        except Exception:
            self._about_version_var = tk.StringVar(value="versión desconocida")
        tk.Label(content, textvariable=self._about_version_var, bg=COL_CARD, fg=COL_MUTED,
                 font=("DejaVu Sans", FS_TEXT)).pack()

        # Estado
        self._ota_status = tk.StringVar(value="Listo")
        tk.Label(content, textvariable=self._ota_status, bg=COL_CARD, fg=COL_MUTED,
                 font=("DejaVu Sans", FS_TEXT-1)).pack(anchor="w", pady=(10, 0))

        # Opción: reiniciar mini-web automáticamente
        self._auto_restart_web = tk.BooleanVar(value=True)
        tk.Checkbutton(content,
                       text="Reiniciar mini‑web automáticamente tras actualizar",
                       variable=self._auto_restart_web,
                       bg=COL_CARD, fg=COL_TEXT, selectcolor=COL_CARD,
                       activebackground=COL_CARD, activeforeground=COL_TEXT,
                       font=("DejaVu Sans", FS_TEXT)).pack(anchor="w", pady=(6, 0))

        # Botones
        btns = tk.Frame(content, bg=COL_CARD)
        btns.pack(anchor="w", pady=(8, 0))
        self._btn_check = tk.Button(btns, text="Comprobar actualizacion", command=self._ota_check,
                                    bg="#3b82f6", fg="white", bd=0, relief="flat",
                                    font=("DejaVu Sans", FS_BTN_SMALL), cursor="hand2", padx=12, pady=6)
        self._btn_check.pack(side="left", padx=(0, 8))
        self._btn_update = tk.Button(btns, text="Actualizar ahora", command=self._ota_update,
                                     bg=COL_ACCENT, fg="white", bd=0, relief="flat",
                                     font=("DejaVu Sans", FS_BTN_SMALL), cursor="hand2", padx=12, pady=6)
        self._btn_update.pack(side="left")

        # Botón para reiniciar mini-web manualmente
        self._btn_restart_web = tk.Button(btns, text="Reiniciar mini‑web",
                                          command=self._restart_miniweb,
                                          bg=COL_BORDER, fg=COL_TEXT, bd=0, relief="flat",
                                          font=("DejaVu Sans", FS_BTN_SMALL), cursor="hand2", padx=12, pady=6)
        self._btn_restart_web.pack(side="left", padx=(8, 0))

        tk.Label(content,
                 text="Nota: la mini-web se actualiza tras reiniciar o manualmente.",
                 bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT-2)).pack(anchor="w", pady=(10, 0))

    # ==== OTA helpers ====
    def _repo_root(self) -> Path:
        try:
            return Path(__file__).resolve().parents[2]
        except Exception:
            return Path.cwd()

    def _version_text(self) -> str:
        import subprocess
        cwd = str(self._repo_root())
        try:
            sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=cwd, text=True).strip()
            br = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd, text=True).strip()
            return f"{br} @ {sha}"
        except Exception:
            return "versión desconocida"

    def _set_ota_status(self, text: str):
        try:
            self._ota_status.set(text)
        except Exception:
            pass

    def _enable_ota_buttons(self, enabled: bool):
        try:
            state = ("normal" if enabled else "disabled")
            self._btn_check.config(state=state)
            self._btn_update.config(state=state)
        except Exception:
            pass

    def _ota_check(self):
        import subprocess
        cwd = str(self._repo_root())
        self._set_ota_status("Comprobando...")
        try:
            subprocess.run(["git", "fetch", "--all", "--tags"], cwd=cwd, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                upstream = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "@{u}"], cwd=cwd, text=True).strip()
            except Exception:
                upstream = "origin/main"
            local = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=cwd, text=True).strip()
            remote = subprocess.check_output(["git", "rev-parse", upstream], cwd=cwd, text=True).strip()
            if local == remote:
                self._set_ota_status(f"Sin novedades. {self._version_text()}")
            else:
                self._set_ota_status(f"Disponible: {remote[:7]} (local {local[:7]})")
        except Exception as e:
            self._set_ota_status(f"Error al comprobar: {e}")

    def _ota_update(self):
        import threading
        self._enable_ota_buttons(False)
        self._set_ota_status("Actualizando...")
        threading.Thread(target=self._ota_update_bg, daemon=True).start()

    def _ota_update_bg(self):
        import subprocess, sys, os, shlex

        def run(cmd, **kw):
            # Helper con timeout, captura y check
            kw.setdefault("cwd", cwd)
            kw.setdefault("text", True)
            kw.setdefault("capture_output", True)
            kw.setdefault("timeout", 90)
            p = subprocess.run(cmd, **kw)
            if kw.get("check", True) and p.returncode != 0:
                raise RuntimeError("CMD: " + shlex.join(cmd) + "\nOUT: " + str(p.stdout) + "\nERR: " + str(p.stderr))
            return p

        def status_dirty():
            # `--porcelain` lista cambios tracked/untracked
            p = run(["git", "status", "--porcelain"], check=False)
            return bool(p.stdout.strip())

        def upstream_ref():
            try:
                p = run(["git", "rev-parse", "--abbrev-ref", "@{u}"], check=True)
                return p.stdout.strip()
            except Exception:
                return "origin/main"

        def version_sha(ref):
            return run(["git", "rev-parse", ref]).stdout.strip()

        # === Inicio ===
        cwd = str(self._repo_root())
        py = sys.executable
        old_rev = None

        try:
            self.root.after(0, lambda: self._set_ota_status("Verificando repositorio..."))
            # Comprobar que es repo
            run(["git", "rev-parse", "--is-inside-work-tree"])

            # Asegurar conectividad a remoto (rápida)
            self.root.after(0, lambda: self._set_ota_status("Comprobando remoto..."))
            run(["git", "ls-remote"], timeout=60)

            # Estado limpio (tracked + untracked)
            if status_dirty():
                self.root.after(0, lambda: self._set_ota_status("Cambios locales detectados. Haz 'git stash' o commitea antes de actualizar."))
                return

            old_rev = version_sha("HEAD")

            # Fetch + tags + prune
            self.root.after(0, lambda: self._set_ota_status("Descargando actualizaciones..."))
            run(["git", "fetch", "--prune", "--tags"])

            up = upstream_ref()
            new_rev = version_sha(up)

            if old_rev == new_rev:
                self.root.after(0, lambda: self._set_ota_status("Ya estás en la última versión."))
                return

            # Intento fast-forward (si fallara, hacemos reset duro a @{u})
            self.root.after(0, lambda: self._set_ota_status("Actualizando rama (ff-only)..."))
            p_merge = run(["git", "merge", "--ff-only", up], check=False)
            if p_merge.returncode != 0:
                # Política: “exacto a remoto”
                self.root.after(0, lambda: self._set_ota_status("No fast-forward. Forzando sincronización con remoto..."))
                run(["git", "reset", "--hard", up])

            # Limpieza opcional de ignorados (cache/build)
            try:
                self.root.after(0, lambda: self._set_ota_status("Limpiando archivos ignorados..."))
                run(["git", "clean", "-fdX"], check=False)
            except Exception:
                pass  # no crítico

            # Submódulos (si existieran)
            try:
                run(["git", "submodule", "update", "--init", "--recursive"], check=False)
            except Exception:
                pass

            # Dependencias
            self.root.after(0, lambda: self._set_ota_status("Actualizando dependencias..."))
            req = os.path.join(cwd, "requirements.txt")
            if os.path.exists(req):
                run([py, "-m", "pip", "install", "--upgrade", "--no-cache-dir", "-r", req], check=False)

            # Smoke test robusto
            self.root.after(0, lambda: self._set_ota_status("Verificando la aplicación..."))
            # 1) Compilar .py
            run([py, '-c', "import py_compile, glob; files=[f for f in glob.glob('**/*.py', recursive=True) if '.git/' not in f]; py_compile.compile('main.py'); list(map(py_compile.compile, files))"])

            # 2) Imports críticos mínimos (sin levantar GUI)
            run([py, '-c', 'import bascula.services.scale, bascula.ui.screens, bascula.domain.filters; print("OK")'])

            # OK → refrescar versión en “Acerca de”
            self.root.after(0, lambda: self._about_version_var.set(self._version_text()))

            # Mini-web opcional
            try:
                auto_var = getattr(self, "_auto_restart_web", None)
                auto_restart = bool(auto_var.get()) if auto_var is not None else False
            except Exception:
                auto_restart = False

            if auto_restart:
                ok = self._restart_miniweb(bg=True)
                if ok:
                    self.root.after(0, lambda: self._set_ota_status("Actualizado y mini-web reiniciada."))
                else:
                    self.root.after(0, lambda: self._set_ota_status("Actualizado. No se pudo reiniciar la mini-web."))
            else:
                self.root.after(0, lambda: self._set_ota_status("Actualizado. Reinicia la aplicación para aplicar cambios."))

        except Exception as e:
            # Rollback
            self.root.after(0, lambda: self._set_ota_status("Error: " + str(e) + "\nIniciando rollback..."))
            try:
                if old_rev:
                    run(["git", "reset", "--hard", old_rev], check=True)
                    req = os.path.join(cwd, "requirements.txt")
                    if os.path.exists(req):
                        subprocess.run([py, "-m", "pip", "install", "--upgrade", "--no-cache-dir", "-r", req], cwd=cwd, text=True, capture_output=True, timeout=120)
                    self.root.after(0, lambda: self._set_ota_status("Rollback completado. Repositorio restaurado."))
            except Exception as rollback_e:
                self.root.after(0, lambda: self._set_ota_status("Fallo crítico: " + str(e) + ". Rollback también falló: " + str(rollback_e) + ". Repositorio en estado incierto."))
        finally:
            self.root.after(0, lambda: self._enable_ota_buttons(True))