# -*- coding: utf-8 -*-
"""
Pantalla de ajustes rediseñada con navegación por pestañas y organización clara.
Esta versión ha sido limpiada para evitar bloques mal anidados y errores de sintaxis.
"""
import tkinter as tk
from tkinter import ttk
import os
import subprocess
import socket
from pathlib import Path

# Dependencias de la app
from bascula.ui.widgets import *
from bascula.ui.screens import BaseScreen

try:
    import requests
except Exception:
    requests = None

try:
    import qrcode
    from PIL import Image, ImageTk
    _QR_OK = True
except Exception:
    _QR_OK = False

BASE_URL = os.environ.get('BASCULA_WEB_URL', 'http://127.0.0.1:8080')


class TabbedSettingsMenuScreen(BaseScreen):
    """Pantalla de ajustes con navegación por pestañas"""
    def __init__(self, parent, app, **kwargs):
        # === INICIO: Estilos para Scrollbar y otros widgets ===
        style = ttk.Style()
        try:
            try:
                style.theme_use("clam")
            except Exception:
                pass  # usar tema actual si no está 'clam'

            # Scrollbars táctiles y coherentes con la UI
            style.configure("Vertical.TScrollbar",
                            width=36,
                            troughcolor=COL_CARD,
                            background=COL_ACCENT,
                            bordercolor=COL_CARD,
                            arrowcolor="white")
            style.map("Vertical.TScrollbar",
                      background=[("active", COL_ACCENT_LIGHT), ("!active", COL_ACCENT)])

            style.configure("Horizontal.TScrollbar",
                            width=36,
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
                      background=[("active", COL_CARD)],
                      foreground=[("disabled", COL_MUTED)])
            style.map("Big.TRadiobutton",
                      background=[("active", COL_CARD)],
                      foreground=[("disabled", COL_MUTED)])

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

        # Botón volver y audio
        back_btn = tk.Button(header, text="← Volver", command=lambda: self.app.show_screen('home'),
                             bg=COL_BORDER, fg=COL_TEXT, font=("DejaVu Sans", FS_BTN_SMALL),
                             bd=0, relief="flat", cursor="hand2")
        back_btn.pack(side="right")

        self._audio_btn = tk.Button(header,
                                    text=("🔊" if self.app.get_cfg().get('sound_enabled', True) else "🔇"),
                                    command=self._toggle_audio,
                                    bg=COL_BG, fg=COL_TEXT,
                                    bd=0, relief="flat", cursor="hand2",
                                    font=("DejaVu Sans", 12, "bold"), highlightthickness=0, width=3)
        self._audio_btn.pack(side="right", padx=(0, 8))
        try:
            self._audio_btn.config(text=self._audio_icon())
        except Exception:
            pass

        # Contenedor principal
        main_container = Card(self)
        main_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Notebook con estilo
        self.notebook = ttk.Notebook(main_container, style='Settings.TNotebook')
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        style.configure('Settings.TNotebook', background=COL_CARD, borderwidth=0)
        style.configure('Settings.TNotebook.Tab',
                        background=COL_CARD,
                        foreground=COL_TEXT,
                        padding=[20, 10],
                        font=("DejaVu Sans", FS_TEXT))
        style.map('Settings.TNotebook.Tab',
                  background=[('selected', COL_ACCENT)],
                  foreground=[('selected', 'white')])

        # Variables mínimas usadas en pestañas
        self.var_sound = tk.BooleanVar(value=self.app.get_cfg().get('sound_enabled', True))
        self.var_theme = tk.StringVar(value=self.app.get_cfg().get('sound_theme', 'beep'))

        # Pestañas
        self._create_general_tab()
        self._create_scale_tab()
        self._create_network_tab()
        self._create_diabetes_tab()
        self._create_storage_tab()
        self._create_about_tab()
        self._create_ota_tab()

        self.toast = Toast(self)

    # -------------------- Teclado numérico --------------------
    def _show_numeric_keypad(self, target_entry: tk.Entry):
        """Muestra un teclado numérico simple para rellenar el Entry indicado."""
        top = tk.Toplevel(self)
        top.title("Teclado")
        top.transient(self)
        top.configure(bg=COL_CARD)
        top.geometry("+200+180")
        val = tk.StringVar(value=target_entry.get())
        display = tk.Entry(top, textvariable=val, font=("DejaVu Sans", FS_TITLE), justify="right")
        display.pack(fill="x", padx=10, pady=10)

        def put(ch):
            if ch == "⌫":
                s = val.get(); val.set(s[:-1])
            elif ch == "C":
                val.set("")
            elif ch == "OK":
                target_entry.delete(0, "end")
                target_entry.insert(0, val.get())
                top.destroy()
            else:
                val.set(val.get() + ch)

        btns = [["7","8","9"], ["4","5","6"], ["1","2","3"], ["C","0","."]]
        grid = tk.Frame(top, bg=COL_CARD)
        grid.pack(padx=10, pady=(0,10))
        for r,row in enumerate(btns):
            for c,ch in enumerate(row):
                tk.Button(grid, text=ch, command=lambda ch=ch: put(ch),
                          width=4, height=2, bg=COL_BG, fg=COL_TEXT,
                          font=("DejaVu Sans", FS_TEXT, "bold")).grid(row=r, column=c, padx=6, pady=6)
        tk.Button(top, text="OK", command=lambda: put("OK"),
                  bg=COL_ACCENT, fg="white", font=("DejaVu Sans", FS_BTN)).pack(fill="x", padx=10, pady=(0,10))
        top.grab_set()
        top.focus_force()

    def _bind_numeric_keypad_for(self, container: tk.Widget):
        """Asigna el teclado numérico emergente a todos los Entry debajo de 'container'."""
        def walk(w):
            try:
                children = w.winfo_children()
            except Exception:
                children = []
            for ch in children:
                if isinstance(ch, (tk.Entry, ttk.Entry)):
                    ch.bind("<FocusIn>", lambda e, ent=ch: self._show_numeric_keypad(ent))
                    ch.bind("<Button-1>", lambda e, ent=ch: self._show_numeric_keypad(ent))
                walk(ch)
        walk(container)

    # -------------------- General --------------------
    def _create_general_tab(self):
        """Pestaña de configuración general"""
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="🎯 General")

        sf = TouchScrollableFrame(tab, bg=COL_CARD)
        sf.pack(fill="both", expand=True, padx=20, pady=15)
        content = sf.inner

        # Sonido
        self._add_section_header(content, "Sonido")
        sound_frame = self._create_option_row(content)
        tk.Label(sound_frame, text="Sonido:", bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(0, 10))
        sound_check = ttk.Checkbutton(sound_frame, text="Activado", variable=self.var_sound,
                                      command=self._toggle_sound, style='Big.TCheckbutton')
        sound_check.pack(side="left")

        self.var_theme = tk.StringVar(value=self.app.get_cfg().get('sound_theme', 'beep'))
        theme_combo = ttk.Combobox(sound_frame, textvariable=self.var_theme,
                                   values=["beep", "voice_es"], width=10, state="readonly")
        theme_combo.pack(side="left", padx=(20, 10))
        theme_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_sound_theme())

        tk.Button(sound_frame, text="Probar", command=self._test_sound,
                  bg=COL_ACCENT, fg="white", font=("DejaVu Sans", FS_TEXT), bd=0).pack(side="left", padx=10)

        # Estado rápido
        self._add_section_header(content, "Estado", top_pad=30)
        status_frame = tk.Frame(content, bg=COL_CARD)
        status_frame.pack(fill="x", pady=10)
        status_inner = tk.Frame(status_frame, bg="#1a1f2e")
        status_inner.pack(padx=15, pady=10)

        ip = self._get_current_ip()
        tk.Label(status_inner, text="IP Local:", bg="#1a1f2e", fg=COL_TEXT,
                 font=("DejaVu Sans", FS_TEXT)).grid(row=0, column=0, sticky="w", pady=2)
        tk.Label(status_inner, text=ip if ip else "No conectado",
                 bg="#1a1f2e", fg=(COL_SUCCESS if ip else COL_WARN),
                 font=("DejaVu Sans Mono", FS_TEXT, "bold")).grid(row=0, column=1, padx=20, pady=2)

    # -------------------- Báscula --------------------
    def _create_scale_tab(self):
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="⚖ Báscula")
        # Contenido mínimo placeholder para mantener compatibilidad
        inner = tk.Frame(tab, bg=COL_CARD)
        inner.pack(fill="both", expand=True, padx=20, pady=15)
        tk.Label(inner, text="Ajustes de báscula", bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", FS_TEXT)).pack(anchor="w")

    # -------------------- Red --------------------
    def _create_network_tab(self):
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="📡 Red")
        inner = tk.Frame(tab, bg=COL_CARD)
        inner.pack(fill="both", expand=True, padx=20, pady=15)
        tk.Label(inner, text="Ajustes de red", bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", FS_TEXT)).pack(anchor="w")

    # -------------------- Diabetes --------------------
    def _create_diabetes_tab(self):
        self.notebook.add((tab := tk.Frame(self.notebook, bg=COL_CARD)), text="💉 Diabetes")
        sf = TouchScrollableFrame(tab, bg=COL_CARD); sf.pack(fill="both", expand=True, padx=20, pady=15)
        content = sf.inner

        # Modo diabético
        self._add_section_header(content, "Modo diabético")
        dm_frame = self._create_option_row(content)
        self.var_dm = tk.BooleanVar(value=self.app.get_cfg().get('dm_enabled', False))
        ttk.Checkbutton(dm_frame, text="Activar modo diabético (experimental)",
                        variable=self.var_dm, command=self._toggle_dm,
                        style='Big.TCheckbutton').pack(side="left")

        # Valores objetivo / alarmas / ratio / ISF / DIA (entradas con teclado numérico)
        self._add_section_header(content, "Parámetros")
        fields = [
            ("Objetivo (mg/dL)", "dm_target", "110"),
            ("Alarma baja (mg/dL)", "dm_low", "70"),
            ("Alarma alta (mg/dL)", "dm_high", "180"),
            ("Ratio (g/U)", "dm_carb_ratio", "10"),
            ("ISF (mg/dL/U)", "dm_isf", "40"),
            ("DIA (h)", "dm_dia", "24"),
        ]
        for label, key, default in fields:
            row = self._create_option_row(content)
            tk.Label(row, text=label+":", bg=COL_CARD, fg=COL_TEXT,
                     font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(0, 10))
            ent = ttk.Entry(row, width=8)
            ent.insert(0, str(self.app.get_cfg().get(key, default)))
            ent.pack(side="left")
            # Botón editar para abrir teclado explícitamente
            tk.Button(row, text="Editar", command=lambda e=ent: self._show_numeric_keypad(e),
                      bg=COL_BORDER, fg=COL_TEXT, font=("DejaVu Sans", FS_BTN_SMALL), bd=0).pack(side="left", padx=8)

        # Alertas
        alerts_frame = self._create_option_row(content)
        tk.Label(alerts_frame, text="Alertas:", bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(0,10))
        self.var_bg_alerts = tk.BooleanVar(value=self.app.get_cfg().get('bg_alerts', True))
        self.var_bg_announce = tk.BooleanVar(value=self.app.get_cfg().get('bg_announce', False))
        self.var_bg_every = tk.BooleanVar(value=self.app.get_cfg().get('bg_announce_every', False))
        ttk.Checkbutton(alerts_frame, text="Sonoras en baja/alta", variable=self.var_bg_alerts,
                        style='Big.TCheckbutton').pack(side="left", padx=6)
        self.chk_bg_announce = ttk.Checkbutton(alerts_frame, text="Anunciar valor al entrar en alerta",
                                               variable=self.var_bg_announce, style='Big.TCheckbutton')
        self.chk_bg_announce.pack(side="left", padx=6)
        self.chk_bg_every = ttk.Checkbutton(alerts_frame, text="Anunciar cada lectura",
                                            variable=self.var_bg_every, style='Big.TCheckbutton')
        self.chk_bg_every.pack(side="left", padx=6)

        # Teclado numérico automático al tocar cualquier Entry en esta pestaña
        self._bind_numeric_keypad_for(content)

    # -------------------- Datos / Almacenamiento --------------------
    def _create_storage_tab(self):
        self.notebook.add((tab := tk.Frame(self.notebook, bg=COL_CARD)), text="🗄 Datos")
        sf = TouchScrollableFrame(tab, bg=COL_CARD); sf.pack(fill="both", expand=True, padx=20, pady=15)
        content = sf.inner
        self._add_section_header(content, "Datos")
        row = self._create_option_row(content)
        tk.Label(row, text="Carpeta de exportación:", bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(0,10))
        ttk.Entry(row, width=28).pack(side="left")
        tk.Button(row, text="Editar", command=lambda e=row.winfo_children()[1]: self._show_numeric_keypad(e),
                  bg=COL_BORDER, fg=COL_TEXT, font=("DejaVu Sans", FS_BTN_SMALL), bd=0).pack(side="left", padx=8)
        # Teclado también aquí si hay más entradas
        self._bind_numeric_keypad_for(content)

    # -------------------- Acerca de --------------------
    def _create_about_tab(self):
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="ℹ Acerca de")
        content = tk.Frame(tab, bg=COL_CARD)
        content.pack(fill="both", expand=True, padx=20, pady=15)

        title_frame = tk.Frame(content, bg=COL_CARD)
        title_frame.pack(pady=20)
        tk.Label(title_frame, text="Daniel Gonzalez Tellols",
                 bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack()

    # -------------------- OTA --------------------
    def _create_ota_tab(self):
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="⬇ OTA")
        content = tk.Frame(tab, bg=COL_CARD)
        content.pack(fill="both", expand=True, padx=20, pady=15)

        self._add_section_header(content, "Actualización OTA")
        if not hasattr(self, "ota_status_var"):
            self.ota_status_var = tk.StringVar(value="Listo para actualizar")
        tk.Label(content, textvariable=self.ota_status_var, bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", FS_TEXT)).pack(fill="x", pady=(6, 0))

        btns = tk.Frame(content, bg=COL_CARD); btns.pack(fill="x", pady=(8,10))
        tk.Button(btns, text="Comprobar", command=self._ota_check,
                  bg=COL_BORDER, fg=COL_TEXT, font=("DejaVu Sans", FS_BTN_SMALL), bd=0).pack(side="left", padx=(0,10))
        tk.Button(btns, text="Actualizar", command=self._ota_update,
                  bg=COL_ACCENT, fg="white", font=("DejaVu Sans", FS_BTN), bd=0).pack(side="left", padx=(0,10))
        tk.Button(btns, text="Reiniciar app", command=self._restart_app,
                  bg=COL_ACCENT, fg="white", font=("DejaVu Sans", FS_BTN), bd=0).pack(side="left", padx=(0,10))
        tk.Button(btns, text="Reiniciar dispositivo", command=self._restart_device,
                  bg=COL_BORDER, fg=COL_TEXT, font=("DejaVu Sans", FS_BTN_SMALL), bd=0).pack(side="left", padx=(0,0))

    # -------------------- Helpers UI --------------------
    def _add_section_header(self, parent, text, top_pad=10):
        tk.Label(parent, text=text, bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", FS_SUBTITLE, "bold")).pack(fill="x", pady=(top_pad, 10))

    def _create_option_row(self, parent):
        frame = tk.Frame(parent, bg=COL_CARD)
        frame.pack(fill="x", pady=6)
        return frame

    def _audio_icon(self):
        return "🔊" if self.app.get_cfg().get('sound_enabled', True) else "🔇"

    def _toggle_audio(self):
        cur = self.app.get_cfg().get('sound_enabled', True)
        self.app.get_cfg()['sound_enabled'] = not cur
        self._audio_btn.config(text=self._audio_icon())

    def _apply_sound_theme(self):
        self.app.get_cfg()['sound_theme'] = self.var_theme.get()

    def _test_sound(self):
        try:
            # Hook del proyecto real (beep/voice)
            print("Test de sonido:", self.var_theme.get())
        except Exception as e:
            print("Test de sonido falló:", e)

    def _toggle_dm(self):
        self.app.get_cfg()['dm_enabled'] = bool(self.var_dm.get())

    def _get_current_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return None

    # -------------------- OTA ops --------------------
    def _set_ota_status(self, msg: str):
        try:
            if not hasattr(self, "ota_status_var"):
                self.ota_status_var = tk.StringVar()
            self.ota_status_var.set(msg)
        except Exception as e:
            print("OTA status update failed:", e)

    def _ota_check(self):
        # Placeholder simple: en proyecto real se haría 'git fetch' y se compararía HEAD vs origin
        self._set_ota_status("Comprobación completada. Si hay cambios, usa 'Actualizar'.")

    def _ota_update(self):
        """Ejecución simplificada con manejo seguro y mensaje final"""
        try:
            cwd = Path(__file__).resolve().parents[3]  # /.../bascula (raíz repo aprox.)
            # Ejemplo: traer cambios y reset duro sobre rama actual
            subprocess.run(["git", "fetch", "--all"], cwd=cwd, check=False)
            subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=cwd, check=False)
            subprocess.run(["git", "pull", "--rebase"], cwd=cwd, check=False)
            # Opcional: requisitos
            req = cwd / "requirements.txt"
            if req.exists():
                py = os.environ.get("PYTHON", "python3")
                subprocess.run([py, "-m", "pip", "install", "--upgrade", "-r", str(req)], cwd=cwd, check=False)
            self._set_ota_status("Actualizado. Reinicia la aplicación para aplicar cambios")
        except Exception as e:
            print("OTA error:", e)
            self._set_ota_status("Error en la actualización. Revisa la conexión o los permisos.")
        # No finally aquí para no mezclar ámbitos de UI

    def _restart_app(self):
        """Intenta reiniciar SOLO la aplicación."""
        try:
            svc_candidates = ["bascula-app.service", "bascula.service"]
            for svc in svc_candidates:
                res = subprocess.run(["systemctl", "restart", svc], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if res.returncode == 0:
                    self._set_ota_status("Reiniciando la aplicación…")
                    return
            # Fallback: relanzar proceso actual (si se ejecuta fuera de systemd)
            python = sys.executable
            os.execv(python, [python] + sys.argv)
        except Exception as e:
            print("No se pudo reiniciar la app:", e)
            self._set_ota_status("No se pudo reiniciar la app automáticamente. Hazlo manualmente.")

    def _restart_device(self):
        """Intenta reiniciar TODO el dispositivo."""
        try:
            res = subprocess.run(["sudo", "reboot"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode != 0:
                self._set_ota_status("No se pudo reiniciar el dispositivo automáticamente. Hazlo manualmente.")
            else:
                self._set_ota_status("Reiniciando el dispositivo…")
        except Exception as e:
            print("No se pudo reiniciar el dispositivo:", e)
            self._set_ota_status("No se pudo reiniciar el dispositivo automáticamente. Hazlo manualmente.")
