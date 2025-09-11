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
        # SAFE: init style before first use to avoid NameError/UnboundLocalError
        self.style = ttk.Style()
        try:
            self.style.theme_use('clam')
        except Exception:
            pass
        style = self.style

        # === Estilos globales (tema, scrollbars, controles táctiles) ===
        try:
            style
        except NameError:
            style = ttk.Style()
            try:
                style.theme_use("clam")
            except Exception:
                pass

        try:
            style.configure("Vertical.TScrollbar", width=28)
            style.configure("Horizontal.TScrollbar", width=28)
            style.configure("Vertical.TScrollbar", troughcolor=COL_BG, background=COL_ACCENT, bordercolor=COL_BG, lightcolor=COL_ACCENT, darkcolor=COL_ACCENT)
            style.configure("Horizontal.TScrollbar", troughcolor=COL_BG, background=COL_ACCENT, bordercolor=COL_BG, lightcolor=COL_ACCENT, darkcolor=COL_ACCENT)
            style.map("Vertical.TScrollbar", background=[("active", COL_ACCENT), ("!active", COL_ACCENT)], troughcolor=[("!active", COL_BG), ("active", COL_BG)])
            style.map("Horizontal.TScrollbar", background=[("active", COL_ACCENT), ("!active", COL_ACCENT)], troughcolor=[("!active", COL_BG), ("active", COL_BG)])
        except Exception:
            pass

        try:
            style.configure("Big.TCheckbutton", padding=(14, 10), background=COL_CARD, foreground=COL_TEXT, font=("DejaVu Sans", FS_TEXT))
            style.configure("Big.TRadiobutton", padding=(14, 10), background=COL_CARD, foreground=COL_TEXT, font=("DejaVu Sans", FS_TEXT))
            style.map("Big.TCheckbutton",
                      background=[("active", COL_CARD), ("pressed", COL_CARD), ("focus", COL_CARD)],
                      foreground=[("disabled", COL_MUTED), ("!disabled", COL_TEXT)])
            style.map("Big.TRadiobutton",
                      background=[("active", COL_CARD), ("pressed", COL_CARD), ("focus", COL_CARD)],
                      foreground=[("disabled", COL_MUTED), ("!disabled", COL_TEXT)])
        except Exception:
            pass
        # === INICIO: Estilos para Scrollbar y otros widgets ===
        style = ttk.Style()
        try:
            # Intentar usar 'clam' (permite personalización amplia). Si no está disponible, seguimos con el tema actual.
            try:
                style.theme_use("clam")
            except Exception:
                pass

            # Scrollbar vertical y horizontal (anchos táctiles + paleta de la UI)
            style.configure("Vertical.TScrollbar",
                            width=30,
                            troughcolor=COL_CARD,
                            background=COL_ACCENT,
                            bordercolor=COL_CARD,
                            arrowcolor="white")
            style.map("Vertical.TScrollbar",
                      background=[("active", COL_ACCENT_LIGHT), ("!active", COL_ACCENT)])

            style.configure("Horizontal.TScrollbar",
                            width=30,
                            troughcolor=COL_CARD,
                            background=COL_ACCENT,
                            bordercolor=COL_CARD,
                            arrowcolor="white")
            style.map("Horizontal.TScrollbar",
                      background=[("active", COL_ACCENT_LIGHT), ("!active", COL_ACCENT)])

            # Controles grandes para táctil
            style.configure("Big.TCheckbutton", padding=(14, 10), background=COL_CARD, foreground=COL_TEXT, font=("DejaVu Sans", FS_TEXT))
            style.configure("Big.TRadiobutton", padding=(14, 10), background=COL_CARD, foreground=COL_TEXT, font=("DejaVu Sans", FS_TEXT))
            style.map("Big.TCheckbutton",
                      background=[("active", COL_CARD), ("pressed", COL_CARD), ("focus", COL_CARD)],
                      foreground=[("disabled", COL_MUTED), ("!disabled", COL_TEXT)])
            style.map("Big.TRadiobutton",
                      background=[("active", COL_CARD), ("pressed", COL_CARD), ("focus", COL_CARD)],
                      foreground=[("disabled", COL_MUTED), ("!disabled", COL_TEXT)])
        except Exception as e:
            print(f"No se pudo aplicar el estilo a los widgets ttk: {e}")
        # === FIN: Estilos ===



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
        self.notebook = ttk.Notebook(main_container, style='Settings.TNotebook')
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
        style.map('Settings.TNotebook.Tab',
                 background=[('selected', COL_ACCENT)],
                 foreground=[('selected', 'white')])
        
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

    # ---- handlers: Theme section ----
    def _apply_theme(self):
        """Aplica permanentemente el tema seleccionado"""
        try:
            # Cancelar preview si estaba programado
            if hasattr(self, '_preview_timeout') and self._preview_timeout:
                try:
                    self.after_cancel(self._preview_timeout)
                except Exception:
                    pass
                self._preview_timeout = None

            theme_name = (self.var_theme_ui.get() or '').strip()
            try:
                from bascula.config.themes import get_theme_manager, THEMES, update_color_constants
            except ImportError:
                get_theme_manager = THEMES = update_color_constants = None

            if THEMES is not None:
                if theme_name not in THEMES:
                    self.toast.show("Selecciona un tema válido", 1200, COL_WARN)
                    return
                theme_manager = get_theme_manager()
                if theme_manager.set_theme(theme_name):
                    theme_manager.apply_to_root(self.winfo_toplevel())
                    update_color_constants()
                    cfg = self.app.get_cfg()
                    cfg['ui_theme'] = theme_name
                    cfg['theme_scanlines'] = bool(self.var_scanlines.get()) if hasattr(self, 'var_scanlines') else False
                    cfg['theme_glow'] = bool(self.var_glow.get()) if hasattr(self, 'var_glow') else False
                    self.app.save_cfg()
                    display_name = getattr(THEMES[theme_name], 'display_name', theme_name)
                    if hasattr(self, 'theme_status_label'):
                        self.theme_status_label.config(text=f"Tema actual: {display_name}")
                    self._recreate_screens()
                    self.toast.show(f"Tema aplicado: {display_name}", 1500, COL_SUCCESS)
                else:
                    self.toast.show("Error aplicando tema", 1500, COL_DANGER)
                return

            # Fallback: tema retro único
            from bascula.config import theme as retro_theme
            cfg = self.app.get_cfg()
            cfg['ui_theme'] = theme_name or 'retro'
            cfg['theme_scanlines'] = bool(self.var_scanlines.get()) if hasattr(self, 'var_scanlines') else False
            cfg['theme_glow'] = bool(self.var_glow.get()) if hasattr(self, 'var_glow') else False
            self.app.save_cfg()
            retro_theme.ENABLE_SCANLINES = cfg['theme_scanlines']
            retro_theme.apply_theme(self.winfo_toplevel())
            if hasattr(self, 'theme_status_label'):
                self.theme_status_label.config(text=f"Tema actual: Retro Verde")
            self._recreate_screens()
            self.toast.show("Tema aplicado: Retro Verde", 1200)
        except Exception as e:
            try:
                self.toast.show(f"Error: {e}", 1500, COL_DANGER)
            except Exception:
                pass

    def _preview_theme(self):
        """Muestra una vista previa temporal del tema seleccionado"""
        try:
            theme_name = (self.var_theme_ui.get() or '').strip()
            try:
                from bascula.config.themes import get_theme_manager, THEMES, update_color_constants
            except ImportError:
                get_theme_manager = THEMES = update_color_constants = None

            if THEMES is not None:
                if theme_name not in THEMES:
                    self.toast.show("Tema no válido", 1200, COL_WARN)
                    return
                theme_manager = get_theme_manager()
                original_theme = theme_manager.current_theme_name
                theme_manager.set_theme(theme_name)
                theme_manager.apply_to_root(self.winfo_toplevel())
                update_color_constants()
                self.update_idletasks()
                self.toast.show(f"Vista previa: {getattr(THEMES[theme_name], 'display_name', theme_name)}", 2000)
                self._preview_timeout = self.after(3000, lambda: self._restore_theme(original_theme))
                return

            # Fallback: aplicar directamente el retro
            from bascula.config import theme as retro_theme
            retro_theme.ENABLE_SCANLINES = bool(self.var_scanlines.get()) if hasattr(self, 'var_scanlines') else False
            retro_theme.apply_theme(self.winfo_toplevel())
            self.update_idletasks()
            self.toast.show("Vista previa aplicada (retro)", 900)
        except Exception as e:
            try:
                self.toast.show(f"Error en preview: {e}", 1500, COL_DANGER)
            except Exception:
                pass

    def _reset_theme(self):
        """Restaura el tema por defecto (Dark Modern)"""
        try:
            # Intentar vía gestor de temas
            try:
                from bascula.config.themes import THEMES
            except ImportError:
                THEMES = None
            if THEMES is not None and 'dark_modern' in THEMES:
                if hasattr(self, 'var_theme_ui'):
                    self.var_theme_ui.set('dark_modern')
                self._apply_theme()
                self.toast.show("Tema restaurado a Dark Modern", 1200)
                return

            # Fallback a retro
            if hasattr(self, 'var_theme_ui'):
                self.var_theme_ui.set('retro')
            try:
                cfg = self.app.get_cfg(); cfg['ui_theme'] = 'retro'; cfg['theme_scanlines'] = False; cfg['theme_glow'] = False; self.app.save_cfg()
            except Exception:
                pass
            try:
                from bascula.config import theme as retro_theme
                retro_theme.ENABLE_SCANLINES = False
                retro_theme.apply_theme(self.winfo_toplevel())
            except Exception:
                pass
            if hasattr(self, 'theme_status_label'):
                self.theme_status_label.config(text="Tema actual: Retro Verde")
            self.toast.show("Tema restaurado (retro)", 1200)
        except Exception as e:
            try:
                self.toast.show(f"Error: {e}", 1500, COL_DANGER)
            except Exception:
                pass

    def _restore_theme(self, theme_name: str):
        """Restaura un tema específico (usado después de preview)"""
        try:
            try:
                from bascula.config.themes import get_theme_manager, update_color_constants
            except ImportError:
                get_theme_manager = update_color_constants = None
            if get_theme_manager is not None:
                theme_manager = get_theme_manager()
                theme_manager.set_theme(theme_name)
                theme_manager.apply_to_root(self.winfo_toplevel())
                update_color_constants()
                if hasattr(self, 'var_theme_ui'):
                    self.var_theme_ui.set(theme_name)
                self.update_idletasks()
                return

            # Fallback: retro
            from bascula.config import theme as retro_theme
            retro_theme.apply_theme(self.winfo_toplevel())
            if hasattr(self, 'var_theme_ui'):
                self.var_theme_ui.set('retro')
        except Exception:
            pass

    def _toggle_scanlines(self):
        """Activa/desactiva el efecto scanlines"""
        try:
            enabled = bool(self.var_scanlines.get()) if hasattr(self, 'var_scanlines') else False
            try:
                from bascula.config.themes import get_theme_manager
            except ImportError:
                get_theme_manager = None
            if get_theme_manager is not None:
                theme_manager = get_theme_manager()
                if enabled:
                    theme_manager._apply_scanlines(self.winfo_toplevel())
                else:
                    theme_manager._remove_scanlines()
            else:
                # Fallback retro
                try:
                    from bascula.config import theme as retro_theme
                    retro_theme.ENABLE_SCANLINES = enabled
                    retro_theme.apply_theme(self.winfo_toplevel())
                except Exception:
                    pass

            cfg = self.app.get_cfg(); cfg['theme_scanlines'] = enabled; self.app.save_cfg()
            self.toast.show(f"Scanlines: {'ON' if enabled else 'OFF'}", 900)
        except Exception as e:
            try:
                self.toast.show(f"Error: {e}", 1500, COL_DANGER)
            except Exception:
                pass

    def _toggle_glow(self):
        """Activa/desactiva el efecto glow"""
        try:
            enabled = bool(self.var_glow.get()) if hasattr(self, 'var_glow') else False
            cfg = self.app.get_cfg(); cfg['theme_glow'] = enabled; self.app.save_cfg()
            self.toast.show(f"Efecto Glow: {'ON' if enabled else 'OFF'} (requiere reiniciar pantalla)", 1200)
        except Exception as e:
            try:
                self.toast.show(f"Error: {e}", 1500, COL_DANGER)
            except Exception:
                pass

    def _recreate_screens(self):
        """Recrea todas las pantallas para aplicar el nuevo tema"""
        try:
            current_screen_name = None
            try:
                for name, screen in list(self.app.screens.items()):
                    if screen == self.app.current_screen:
                        current_screen_name = name
                        break
            except Exception:
                pass

            # Destruir pantallas existentes
            try:
                for screen in list(self.app.screens.values()):
                    try:
                        screen.destroy()
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                self.app.screens.clear()
            except Exception:
                pass

            if current_screen_name:
                try:
                    self.app.show_screen(current_screen_name)
                except Exception:
                    pass
        except Exception as e:
            try:
                print(f"Error recreando pantallas: {e}")
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

    def _toggle_wakeword(self):
        try:
            cfg = self.app.get_cfg()
            cfg['wakeword_enabled'] = bool(self.var_wakeword.get())
            self.app.save_cfg()
            self.toast.show("Wake Word: " + ("ON" if cfg['wakeword_enabled'] else "OFF"), 900)
        except Exception:
            pass
    
    def _create_general_tab(self):
        """Pestaña de configuración general"""
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="🎯 General")
        
        # Nota: No forzamos la unidad a gramos aquí. La unidad se mantiene
        # según la configuración existente.

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
        sound_check = ttk.Checkbutton(sound_frame, text="Activado", variable=self.var_sound, command=self._toggle_sound, style='Big.TCheckbutton')
        sound_check.pack(side="left")
        
        # Tema de sonido
        self.var_theme = tk.StringVar(value=self.app.get_cfg().get('sound_theme', 'beep'))
        theme_combo = ttk.Combobox(sound_frame, textvariable=self.var_theme,
                                  values=["beep", "voice_es"], width=10, state="readonly")
        theme_combo.pack(side="left", padx=(20, 10))
        theme_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_sound_theme())
        
        test_btn = tk.Button(sound_frame, text="Probar", command=self._test_sound,
                           bg=COL_ACCENT, fg="white", font=("DejaVu Sans", FS_TEXT),
                           bd=0, relief="flat", cursor="hand2", padx=15)
        test_btn.pack(side="left")

        # Piper model (voz natural)
        piper_frame = self._create_option_row(scroll_frame)
        tk.Label(piper_frame, text="Modelo Piper (ruta .onnx):", bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(0,10))
        self.var_piper_model = tk.StringVar(value=str(self.app.get_cfg().get('piper_model','')))
        ent_pm = tk.Entry(piper_frame, textvariable=self.var_piper_model, bg=COL_CARD_HOVER, fg=COL_TEXT,
                          insertbackground=COL_TEXT, relief='flat', width=36)
        ent_pm.pack(side="left", padx=(0,10))
        tk.Button(piper_frame, text="Guardar", command=self._apply_piper_model,
                  bg=COL_ACCENT, fg='white', font=("DejaVu Sans", FS_TEXT), bd=0, relief='flat', cursor='hand2').pack(side='left')

        # Cámara: resolución para foto comida
        cam_frame = self._create_option_row(scroll_frame)
        tk.Label(cam_frame, text="Resolución foto comida:", bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(0,10))
        self.var_foodshot = tk.StringVar(value=str(self.app.get_cfg().get('foodshot_size','4608x2592')))
        cb_vals = ["4608x2592 (Alta)", "2304x1296 (Media)"]
        self._foodshot_val_map = {cb_vals[0]: "4608x2592", cb_vals[1]: "2304x1296"}
        self.cb_foodshot = ttk.Combobox(cam_frame, values=cb_vals, width=18, state='readonly')
        try:
            cur = self.var_foodshot.get()
            sel = cb_vals[0] if cur.startswith('4608') else (cb_vals[1] if cur.startswith('2304') else cb_vals[0])
            self.cb_foodshot.set(sel)
        except Exception:
            self.cb_foodshot.set(cb_vals[0])
        self.cb_foodshot.pack(side='left')
        tk.Button(cam_frame, text="Aplicar", command=self._apply_foodshot_size,
                  bg=COL_ACCENT, fg='white', font=("DejaVu Sans", FS_TEXT), bd=0, relief='flat', cursor='hand2').pack(side='left', padx=8)

        # Wake word toggle
        ww_frame = self._create_option_row(scroll_frame)
        tk.Label(ww_frame, text="Wake Word:", bg=COL_CARD, fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(0, 10))
        self.var_wakeword = tk.BooleanVar(value=bool(self.app.get_cfg().get('wakeword_enabled', False)))
        ttk.Checkbutton(ww_frame, text="Activado", variable=self.var_wakeword,
                        command=self._toggle_wakeword, style='Big.TCheckbutton').pack(side="left")
                        nsdef_frame = self._create_option_row(scroll_frame)
                        tk.Label(nsdef_frame, text="Enviar a Nightscout por defecto:", ... )
                        self.var_send_ns_def = tk.BooleanVar(value=bool(self.app.get_cfg().get('send_to_ns_default', False)))
                        ttk.Checkbutton(nsdef_frame, text="Activado", variable=self.var_send_ns_def, command=lambda: (self.app.get_cfg().update({'send_to_ns_default': bool(self.var_send_ns_def.get())}), self.app.save_cfg()), style='Big.TCheckbutton').pack(side="left")
        # Decimales
        decimal_frame = self._create_option_row(scroll_frame)
        tk.Label(decimal_frame, text="Decimales en peso:", bg=COL_CARD, fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(0, 10))
        
        self.var_decimals = tk.IntVar(value=self.app.get_cfg().get('decimals', 0))
        for i in range(2):
            rb = ttk.Radiobutton(decimal_frame, text=str(i), variable=self.var_decimals,
                               value=i, command=self._apply_decimals)
            rb.pack(side="left", padx=5)
        # (Unidades eliminadas; fijo g)

        # === NUEVA SECCIÓN: Tema de Interfaz ===
        try:
            self._add_section_header(scroll_frame, "🎨 Tema de Interfaz", top_pad=20)

            # Contenedor principal de la sección de temas
            theme_container = tk.Frame(scroll_frame, bg=COL_CARD)
            theme_container.pack(fill="x", pady=10)

            # Temas disponibles (adaptado a infraestructura actual)
            # Nota: actualmente sólo existe un tema retro; dejamos la estructura lista.
            try:
                cfg = self.app.get_cfg()
            except Exception:
                cfg = {}
            available_themes = {"retro": "Retro Verde"}
            current_theme = cfg.get('ui_theme', 'retro')
            if current_theme not in available_themes:
                current_theme = 'retro'

            # Sobrescribir con gestor si está disponible
            try:
                from bascula.config.themes import get_theme_manager, THEMES
                theme_manager = get_theme_manager()
                available_themes = {k: v.display_name for k, v in THEMES.items()}
                current_theme = theme_manager.current_theme_name
            except Exception:
                pass

            # Variable de selección
            self.var_theme_ui = tk.StringVar(value=current_theme)

            # Grid para opciones de tema (2 columnas)
            themes_grid = tk.Frame(theme_container, bg=COL_CARD)
            themes_grid.pack(fill="x", padx=10)

            row = 0
            col = 0
            max_cols = 2
            for theme_name, display_name in available_themes.items():
                theme_frame = tk.Frame(themes_grid, bg=COL_CARD)
                theme_frame.grid(row=row, column=col, padx=5, pady=5, sticky="w")

                rb = ttk.Radiobutton(
                    theme_frame,
                    text=display_name,
                    variable=self.var_theme_ui,
                    value=theme_name,
                    command=lambda: self._preview_theme(),
                    style='Big.TRadiobutton'
                )
                rb.pack(side="left")

                # Pequeña "preview" con colores actuales de la UI
                preview_frame = tk.Frame(theme_frame, bg=COL_CARD, width=60, height=20)
                preview_frame.pack(side="left", padx=(10, 0))
                preview_frame.pack_propagate(False)
                for i, color in enumerate([COL_CARD, COL_ACCENT, COL_TEXT]):
                    try:
                        color_box = tk.Frame(preview_frame, bg=color, width=18, height=18)
                        color_box.place(x=i*20, y=1)
                    except Exception:
                        pass

                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1

            # Acciones
            theme_actions = tk.Frame(theme_container, bg=COL_CARD)
            theme_actions.pack(fill="x", padx=10, pady=(10, 5))

            apply_btn = tk.Button(
                theme_actions,
                text="✓ Aplicar Tema",
                command=self._apply_theme,
                bg=COL_ACCENT,
                fg="white",
                font=("DejaVu Sans", FS_BTN_SMALL),
                bd=0,
                relief="flat",
                cursor="hand2",
                padx=15,
                pady=8
            )
            apply_btn.pack(side="left", padx=5)

            preview_btn = tk.Button(
                theme_actions,
                text="👁 Vista Previa",
                command=self._preview_theme,
                bg=COL_BORDER,
                fg=COL_TEXT,
                font=("DejaVu Sans", FS_BTN_SMALL),
                bd=0,
                relief="flat",
                cursor="hand2",
                padx=15,
                pady=8
            )
            preview_btn.pack(side="left", padx=5)

            reset_btn = tk.Button(
                theme_actions,
                text="↺ Tema por Defecto",
                command=self._reset_theme,
                bg=COL_BORDER,
                fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT),
                bd=0,
                relief="flat",
                cursor="hand2",
                padx=15,
                pady=8
            )
            reset_btn.pack(side="left", padx=5)

            # Info de estado
            theme_info = tk.Frame(theme_container, bg=COL_CARD)
            theme_info.pack(fill="x", padx=10, pady=5)

            self.theme_status_label = tk.Label(
                theme_info,
                text=f"Tema actual: {available_themes.get(current_theme, 'Desconocido')}",
                bg=COL_CARD,
                fg=COL_MUTED,
                font=("DejaVu Sans", FS_TEXT-1)
            )
            self.theme_status_label.pack(anchor="w")

            # Efectos visuales adicionales
            effects_frame = tk.Frame(theme_container, bg=COL_CARD)
            effects_frame.pack(fill="x", padx=10, pady=(10, 0))

            tk.Label(
                effects_frame,
                text="Efectos visuales:",
                bg=COL_CARD,
                fg=COL_TEXT,
                font=("DejaVu Sans", FS_TEXT)
            ).pack(side="left", padx=(0, 10))

            # Toggle de scanlines (si se usa el tema retro opcional)
            try:
                # Persistimos en cfg aunque el efecto dependa del tema aplicado
                scan_def = bool(cfg.get('theme_scanlines', cfg.get('scanlines', False)))
                self.var_scanlines = tk.BooleanVar(value=scan_def)
            except Exception:
                self.var_scanlines = tk.BooleanVar(value=False)
            scanlines_check = ttk.Checkbutton(
                effects_frame,
                text="Scanlines CRT",
                variable=self.var_scanlines,
                command=self._toggle_scanlines,
                style='Big.TCheckbutton'
            )
            scanlines_check.pack(side="left", padx=5)

            # Efecto glow (no-op visual por ahora; se persiste la preferencia)
            try:
                glow_def = bool(cfg.get('theme_glow', cfg.get('glow_effect', False)))
                self.var_glow = tk.BooleanVar(value=glow_def)
            except Exception:
                self.var_glow = tk.BooleanVar(value=False)
            glow_check = ttk.Checkbutton(
                effects_frame,
                text="Efecto Glow",
                variable=self.var_glow,
                command=self._toggle_glow,
                style='Big.TCheckbutton'
            )
            glow_check.pack(side="left", padx=5)
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
        dm_check = ttk.Checkbutton(dm_frame, text="Activar modo diabético (experimental)", variable=self.var_dm, command=self._toggle_dm, style='Big.TCheckbutton')
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
            # Asocia un teclado numérico oculto al tocar/foco según el tipo de parámetro
            try:
                # Permitir decimales sólo para los parámetros que pueden ser flotantes (ratio o DIA)
                decimals = 1 if any(sub in key.lower() for sub in ("ratio", "dia")) else 0
                bind_numeric_entry(entry, decimals=decimals)
            except Exception:
                pass
            
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
            # Utilizar el nuevo teclado numérico oculto (enteros para mg/dL)
            try:
                bind_numeric_entry(e, decimals=0)
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
        self.chk_bg_announce = ttk.Checkbutton(alerts_frame, text="Anunciar valor al entrar en alerta", variable=self.var_bg_announce)
        self.chk_bg_announce.pack(side="left", padx=12)
        self.chk_bg_every = ttk.Checkbutton(alerts_frame, text="Anunciar cada lectura", variable=self.var_bg_every, style='Big.TCheckbutton')
        self.chk_bg_every.pack(side="left", padx=12)
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
            # Asocia el teclado numérico oculto (sin decimales) a los campos de retención
            try:
                bind_numeric_entry(entry, decimals=0)
            except Exception:
                pass
            
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

        # === Datos y almacenamiento ===
        self._add_section_header(content, "Datos y almacenamiento", top_pad=30)

        store_frame = tk.Frame(content, bg=COL_CARD)
        store_frame.pack(fill="x", pady=8)
        grid = tk.Frame(store_frame, bg=COL_CARD)
        grid.pack(fill="x", padx=10)
        self._stat_labels = {}

        def _row(r, name, key_count, key_size):
            tk.Label(grid, text=name, bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT)).grid(row=r, column=0, sticky='w')
            lc = tk.Label(grid, text='-', bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_TEXT, 'bold'))
            lc.grid(row=r, column=1, padx=8)
            ls = tk.Label(grid, text='-', bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_TEXT, 'bold'))
            ls.grid(row=r, column=2, padx=8)
            self._stat_labels[key_count] = lc
            self._stat_labels[key_size] = ls

        _row(0, 'Recetas', 'recipes_count', 'recipes_size')
        _row(1, 'OFF Queue', 'offq_count', 'offq_size')
        _row(2, 'Fotos (staging)', 'photos_count', 'photos_size')

        btns2 = tk.Frame(content, bg=COL_CARD)
        btns2.pack(fill='x', pady=(8, 0))
        tk.Button(btns2, text='Refrescar', command=self._refresh_storage_stats, bg=COL_CARD_HOVER, fg=COL_TEXT,
                  font=("DejaVu Sans", FS_TEXT), bd=0, relief='flat', cursor='hand2', padx=15, pady=6).pack(side='left')
        tk.Button(btns2, text='Limpiar ahora (Recetas/Queue)', command=self._clean_now, bg=COL_WARN, fg='black',
                  font=("DejaVu Sans", FS_TEXT), bd=0, relief='flat', cursor='hand2', padx=15, pady=6).pack(side='left', padx=6)

        # primera carga
        try:
            self._refresh_storage_stats()
        except Exception:
            pass

        # === Fotos ===
        self._add_section_header(content, "Fotos Temporales", top_pad=30)
        
        photos_frame = self._create_option_row(content)
        self.var_keep_photos = tk.BooleanVar(value=self.app.get_cfg().get('keep_photos', False))
        photos_check = ttk.Checkbutton(photos_frame, 
                                      text="Mantener fotos entre reinicios",
                                      variable=self.var_keep_photos,
                                      command=self._apply_keep_photos)
        photos_check.pack(side="left")
        
        clear_photos_btn = tk.Button(photos_frame, text="Limpiar Fotos",
                                    command=self._clear_photos,
                                    bg=COL_DANGER, fg="white",
                                    font=("DejaVu Sans", FS_TEXT),
                                    bd=0, relief="flat", cursor="hand2", padx=15)
        clear_photos_btn.pack(side="right")

    def _refresh_storage_stats(self):
        try:
            base = Path.home() / '.config' / 'bascula'
            photos_dir = Path.home() / '.bascula' / 'photos' / 'staging'
            def _count_size(p: Path):
                if not p.exists():
                    return 0, 0
                try:
                    with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                        cnt = sum(1 for _ in f)
                except Exception:
                    cnt = 0
                try:
                    sz = p.stat().st_size
                except Exception:
                    sz = 0
                return cnt, sz
            rc, rs = _count_size(base / 'recipes.jsonl')
            oc, osz = _count_size(base / 'offqueue.jsonl')
            pc = 0; psz = 0
            try:
                if photos_dir.exists():
                    for p in photos_dir.glob('*.jpg'):
                        try:
                            psz += p.stat().st_size; pc += 1
                        except Exception:
                            pass
            except Exception:
                pass
            def _fmt_mb(b):
                try:
                    return f"{(b/1_000_000):.2f} MB"
                except Exception:
                    return "0 MB"
            # Límites para porcentaje
            recipes_lim = 20*1024*1024
            offq_lim = 50*1024*1024
            # Leer límite de fotos si existe
            p_lim = 2*1024*1024*1024
            try:
                cfgp = Path.home() / '.bascula' / 'photos' / 'config.json'
                if cfgp.exists():
                    import json as _json
                    p_lim = int((_json.loads(cfgp.read_text(encoding='utf-8')) or {}).get('max_bytes') or p_lim)
            except Exception:
                pass
            def _pct(v, lim):
                try:
                    return int((100.0 * float(v) / float(lim))) if lim > 0 else 0
                except Exception:
                    return 0
            def _fmt_with_pct(v, lim):
                return f"{_fmt_mb(v)} / {_fmt_mb(lim)} ({_pct(v, lim)}%)"
            def _color_for_pct(p):
                if p >= 95:
                    return COL_DANGER
                if p >= 80:
                    return COL_WARN
                return COL_ACCENT
            if hasattr(self, '_stat_labels'):
                self._stat_labels.get('recipes_count', tk.Label()).config(text=str(rc))
                p = _pct(rs, recipes_lim)
                self._stat_labels.get('recipes_size', tk.Label()).config(text=_fmt_with_pct(rs, recipes_lim), fg=_color_for_pct(p))
                self._stat_labels.get('offq_count', tk.Label()).config(text=str(oc))
                p2 = _pct(osz, offq_lim)
                self._stat_labels.get('offq_size', tk.Label()).config(text=_fmt_with_pct(osz, offq_lim), fg=_color_for_pct(p2))
                self._stat_labels.get('photos_count', tk.Label()).config(text=str(pc))
                p3 = _pct(psz, p_lim)
                self._stat_labels.get('photos_size', tk.Label()).config(text=_fmt_with_pct(psz, p_lim), fg=_color_for_pct(p3))
        except Exception:
            pass

    def _clean_now(self):
        """Prune recipes/offqueue JSONL con límites seguros por defecto."""
        try:
            base = Path.home() / '.config' / 'bascula'
            from bascula.services.retention import prune_jsonl
            prune_jsonl(base / 'recipes.jsonl', max_days=365, max_entries=1000, max_bytes=20*1024*1024)
            prune_jsonl(base / 'offqueue.jsonl', max_days=365, max_entries=10000, max_bytes=50*1024*1024)
            self._refresh_storage_stats()
            self.toast.show('Limpieza realizada', 900, COL_SUCCESS)
        except Exception as e:
            self.toast.show(f'Error limpiando: {e}', 1300, COL_DANGER)
    
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
        tk.Label(info_frame, text="Daniel Gonzalez Tellols", bg=COL_CARD, fg=COL_MUTED,
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


    def _set_ota_status(self, text: str):
        try:
            self._ota_status.set(text)
        except Exception:
            pass

    def _detect_upstream(self):
        """Devuelve '<remote>/<branch>' intentando deducir la rama remota por defecto.
        Soporta repos con main/master u otras ramas, y sin upstream configurado."""
        import subprocess
        cwd = str(self._repo_root())
        # 1) @{u} si existe
        try:
            up = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
                                         cwd=cwd, text=True).strip()
            if up:
                return up
        except Exception:
            pass
        # 2) refs/remotes/origin/HEAD -> origin/main|master
        try:
            ref = subprocess.check_output(["git", "symbolic-ref", "refs/remotes/origin/HEAD"], cwd=cwd, text=True).strip()
            # ref p.ej.: 'refs/remotes/origin/main'
            parts = ref.rsplit("/", 1)
            branch = parts[-1] if len(parts) >= 2 else "main"
            return f"origin/{branch}"
        except Exception:
            pass
        # 3) git remote show <remote> (prefer origin)
        try:
            remote = "origin"
            remotes = subprocess.check_output(["git", "remote"], cwd=cwd, text=True).strip().splitlines()
            if remotes:
                remote = "origin" if "origin" in remotes else remotes[0]
            out = subprocess.check_output(["git", "remote", "show", remote], cwd=cwd, text=True, stderr=subprocess.DEVNULL)
            # Buscar línea "HEAD branch: <name>"
            for line in out.splitlines():
                if "HEAD branch:" in line:
                    branch = line.split("HEAD branch:")[-1].strip()
                    if branch:
                        return f"{remote}/{branch}"
            # Fallback: probar main y master
            for br in ("main", "master"):
                try:
                    subprocess.check_output(["git", "rev-parse", f"{remote}/{br}"], cwd=cwd, text=True, stderr=subprocess.DEVNULL)
                    return f"{remote}/{br}"
                except Exception:
                    continue
        except Exception:
            pass
        # Último recurso
        return "origin/main"
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
            upstream = self._detect_upstream()
            local = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=cwd, text=True).strip()
            remote = subprocess.check_output(["git", "rev-parse", upstream], cwd=cwd, text=True).strip()
            if local == remote:
                self._set_ota_status(f"Sin novedades. {self._version_text()}")
            else:
                self._set_ota_status(f"Actualización disponible: {remote[:7]} (local {local[:7]})")
        except Exception as e:
            self._set_ota_status(f"Error al comprobar: {e}")

    def _ota_update(self):
        import threading
        self._enable_ota_buttons(False)
        self._set_ota_status("Actualizando...")
        threading.Thread(target=self._ota_update_bg, daemon=True).start()

    def _ota_update_bg(self):
        import subprocess, sys, os
        cwd = str(self._repo_root())
        py = sys.executable
        old_rev = None
        try:
            rc = subprocess.run(["git", "diff", "--quiet"], cwd=cwd).returncode
            if rc != 0:
                self.root.after(0, lambda: self._set_ota_status("Hay cambios locales; git limpio requerido."))
                return
            old_rev = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=cwd, text=True).strip()
            upstream = self._detect_upstream()
            subprocess.run(["git", "fetch", "--all", "--tags"], cwd=cwd, check=True)
            new_rev = subprocess.check_output(["git", "rev-parse", upstream], cwd=cwd, text=True).strip()
            if old_rev == new_rev:
                self.root.after(0, lambda: self._set_ota_status("Ya estás en la última versión."))
                return
            subprocess.run(["git", "reset", "--hard", new_rev], cwd=cwd, check=True)
            req = os.path.join(cwd, "requirements.txt")
            if os.path.exists(req):
                subprocess.run([py, "-m", "pip", "install", "--upgrade", "-r", req], cwd=cwd, check=False)
            code = "import importlib; import sys; m=importlib.import_module('bascula.ui.app'); print('OK')"
            p = subprocess.run([py, "-c", code], cwd=cwd, capture_output=True, text=True)
            if p.returncode != 0:
                raise RuntimeError(p.stderr.strip() or p.stdout.strip())
            self.root.after(0, lambda: self._about_version_var.set(self._version_text()))
            if bool(self._auto_restart_web.get()):
                # Intentar reiniciar mini-web automáticamente
                ok = self._restart_miniweb(bg=True)
                if ok:
                    self.root.after(0, lambda: self._set_ota_status("Actualizado y mini‑web reiniciada."))
                else:
                    self.root.after(0, lambda: self._set_ota_status("Actualizado. No se pudo reiniciar mini‑web automáticamente."))
            else:
                self.root.after(0, lambda: self._set_ota_status("Actualizado. Reinicia la aplicación para aplicar cambios."))
        except Exception as e:
            try:
                if old_rev:
                    subprocess.run(["git", "reset", "--hard", old_rev], cwd=cwd, check=True)
                    req = os.path.join(cwd, "requirements.txt")
                    if os.path.exists(req):
                        subprocess.run([py, "-m", "pip", "install", "--upgrade", "-r", req], cwd=cwd, check=False)
            except Exception:
                pass
            self.root.after(0, lambda: self._set_ota_status(f"Error y rollback aplicado: {e}"))
        finally:
            self.root.after(0, lambda: self._enable_ota_buttons(True))

    def _restart_miniweb(self, bg: bool = False) -> bool:
        """Reinicia bascula-web.service usando polkit. Si bg=True, no bloquea UI ni lanza toasts."""
        import subprocess
        try:
            p = subprocess.run(["systemctl", "restart", "bascula-web.service"], capture_output=True, text=True, timeout=10)
            ok = (p.returncode == 0)
            if not bg:
                if ok:
                    self.toast.show("Mini‑web reiniciada", 1200, COL_SUCCESS)
                else:
                    self.toast.show(f"Fallo al reiniciar mini‑web: {p.stderr.strip() or p.stdout.strip()}", 2500, COL_DANGER)
            return ok
        except Exception as e:
            if not bg:
                self.toast.show(f"Error al reiniciar mini‑web: {e}", 2500, COL_DANGER)
            return False

        def run(cmd):
            try:
                p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=4)
                if p.returncode == 0:
                    return (p.stdout or "").strip()
            except Exception:
                pass
            return None
        desc = run([ "git", "describe", "--tags", "--always", "--dirty" ])
        if desc:
            return desc
        short = run([ "git", "rev-parse", "--short", "HEAD" ])
        if short:
            return short
        return "v0-" + datetime.datetime.now().strftime("%Y%m%d")
    def _version_text(self):
        """Devuelve cadena de versión amigable.
        Intenta git describe; si falla, usa fecha y corto de commit. Tolerante a errores.
        """
        import subprocess, os, datetime
        cwd = str(getattr(self, "_repo_root", lambda: os.getcwd())())
        def run(cmd):
            try:
                p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=4)
                if p.returncode == 0:
                    return (p.stdout or "").strip()
            except Exception:
                pass
            return None
        desc = run([ "git", "describe", "--tags", "--always", "--dirty" ])
        if desc:
            return desc
        short = run([ "git", "rev-parse", "--short", "HEAD" ])
        if short:
            return short
        return "v0-" + datetime.datetime.now().strftime("%Y%m%d")

    def _apply_piper_model(self):
        try:
            path = (self.var_piper_model.get() or '').strip()
            cfg = self.app.get_cfg(); cfg['piper_model'] = path; self.app.save_cfg()
            au = getattr(self.app, 'get_audio', lambda: None)()
            if au:
                au.update_config(cfg)
            self.toast.show('Modelo Piper actualizado', 1000, COL_SUCCESS)
        except Exception as e:
            self.toast.show(f'Error: {e}', 1300, COL_DANGER)

    def _apply_foodshot_size(self):
        try:
            label = self.cb_foodshot.get()
            val = self._foodshot_val_map.get(label, '4608x2592')
            cfg = self.app.get_cfg(); cfg['foodshot_size'] = val; self.app.save_cfg()
            try:
                cam = getattr(self.app, 'camera', None)
                if cam and hasattr(cam, 'set_profile_size'):
                    parts = val.split('x'); cam.set_profile_size('foodshot', (int(parts[0]), int(parts[1])))
            except Exception:
                pass
            self.toast.show('Resoluci�n actualizada', 1000, COL_SUCCESS)
        except Exception as e:
            self.toast.show(f'Error: {e}', 1300, COL_DANGER)


# Bind helper methods to class (added at module level due to encoding constraints)
try:
    TabbedSettingsMenuScreen._apply_piper_model = _apply_piper_model
    TabbedSettingsMenuScreen._apply_foodshot_size = _apply_foodshot_size
except Exception:
    pass

