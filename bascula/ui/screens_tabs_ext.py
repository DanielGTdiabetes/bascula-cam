# -*- coding: utf-8 -*-
"""
Pantalla de ajustes con navegación por pestañas (versión corregida)
- Estilo ttk centralizado y único (self.style)
- Eliminado código de estilos duplicado
- Evitado NameError con 'style' no inicializado
- Eliminada la forzada de unidad "g" en _create_general_tab
"""
import os
import json
import socket
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk

# Dependencias internas del proyecto (colores, widgets, BaseScreen, etc.)
# Se asume que existen en tu repo tal y como estaban.
from bascula.ui.widgets import (
    Card, Toast, LabeledEntry, LabeledCombobox, LabeledCheck,
    Section, SeparatorH, InfoRow, ButtonPrimary, ButtonSecondary,
    COL_BG, COL_TEXT, COL_ACCENT, COL_CARD, COL_BORDER,
    FS_TITLE, FS_SUBTITLE, FS_TEXT, FS_BTN_SMALL
)
from bascula.ui.screens import BaseScreen

try:
    import requests
except Exception:
    requests = None

try:
    import qrcode  # opcional (About → QR en el futuro)
    from PIL import Image, ImageTk
    _QR_OK = True
except Exception:
    _QR_OK = False


BASE_URL = os.environ.get('BASCULA_WEB_URL', 'http://127.0.0.1:8080')


class TabbedSettingsMenuScreen(BaseScreen):
    """Pantalla de ajustes con navegación por pestañas."""

    def __init__(self, parent, app, **kwargs):
        # 1) Estilo ttk único y centralizado
        self.style = ttk.Style()
        try:
            self.style.theme_use('clam')
        except Exception:
            pass
        self._configure_styles()  # Estilos en un solo sitio

        # 2) Inicialización estándar de BaseScreen (construye el frame principal)
        super().__init__(parent, app, **kwargs)

        # 3) Cabecera
        header = tk.Frame(self, bg=COL_BG)
        header.pack(fill="x", padx=20, pady=(15, 10))

        tk.Label(header, text="⚙", bg=COL_BG, fg=COL_ACCENT,
                 font=("DejaVu Sans", 28)).pack(side="left")

        tk.Label(header, text="Configuración", bg=COL_BG, fg=COL_TEXT,
                 font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=10)

        back_btn = tk.Button(
            header, text="← Volver",
            command=lambda: self.app.show_screen('home'),
            bg=COL_BORDER, fg=COL_TEXT, font=("DejaVu Sans", FS_BTN_SMALL),
            bd=0, relief="flat", cursor="hand2"
        )
        back_btn.pack(side="right")

        # 4) Botón de audio conmutador (no obligatorio; respeta cfg)
        self._audio_btn = tk.Button(
            header,
            text=("🔊" if self.app.get_cfg().get('sound_enabled', True) else "🔇"),
            command=self._toggle_audio,
            bg=COL_BG, fg=COL_TEXT,
            bd=0, relief="flat", cursor="hand2",
            font=("DejaVu Sans", 12, "bold"), highlightthickness=0, width=3
        )
        self._audio_btn.pack(side="right", padx=(0, 8))

        # 5) Contenedor principal + Notebook
        main_container = Card(self)
        main_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self.notebook = ttk.Notebook(main_container, style='Settings.TNotebook')
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Estilo de tab (reutiliza self.style)
        try:
            self.style.configure('Settings.TNotebook', background=COL_CARD, borderwidth=0)
            self.style.configure('Settings.TNotebook.Tab',
                                 background=COL_CARD,
                                 foreground=COL_TEXT,
                                 padding=[16, 8],
                                 font=("DejaVu Sans", FS_TEXT))
            self.style.map('Settings.TNotebook.Tab',
                           background=[('selected', COL_ACCENT)],
                           foreground=[('selected', 'white')])
        except Exception:
            pass

        # 6) Pestañas
        self._create_general_tab()
        self._create_scale_tab()
        self._create_network_tab()
        self._create_diabetes_tab()
        self._create_storage_tab()
        self._create_about_tab()
        self._create_ota_tab()

        # 7) Toast
        self.toast = Toast(self)

    # ---------------------------------------------------------------------
    # Estilos centralizados (única fuente de verdad)
    # ---------------------------------------------------------------------
    def _configure_styles(self):
        style = self.style

        # Scrollbar (vertical/horizontal) — un único bloque
        try:
            style.configure('Vertical.TScrollbar',
                            troughcolor=COL_CARD,
                            background=COL_ACCENT,
                            bordercolor=COL_BORDER,
                            lightcolor=COL_CARD,
                            darkcolor=COL_BORDER,
                            arrowsize=16)
            style.configure('Horizontal.TScrollbar',
                            troughcolor=COL_CARD,
                            background=COL_ACCENT,
                            bordercolor=COL_BORDER,
                            lightcolor=COL_CARD,
                            darkcolor=COL_BORDER,
                            arrowsize=16)
        except Exception:
            pass

        # Checkbutton / Radiobutton
        try:
            style.configure('TCheckbutton',
                            background=COL_CARD,
                            foreground=COL_TEXT,
                            font=("DejaVu Sans", FS_TEXT))
            style.configure('TRadiobutton',
                            background=COL_CARD,
                            foreground=COL_TEXT,
                            font=("DejaVu Sans", FS_TEXT))
        except Exception:
            pass

        # Buttons base (por si widgets usa ttk.Button en algún lugar)
        try:
            style.configure('TButton',
                            font=("DejaVu Sans", FS_TEXT))
        except Exception:
            pass

    # ---------------------------------------------------------------------
    # Utilidades varias
    # ---------------------------------------------------------------------
    def _audio_icon(self):
        return "🔊" if self.app.get_cfg().get('sound_enabled', True) else "🔇"

    def _toggle_audio(self):
        cfg = self.app.get_cfg()
        current = cfg.get('sound_enabled', True)
        cfg['sound_enabled'] = not current
        self.app.save_cfg(cfg)
        try:
            self._audio_btn.config(text=self._audio_icon())
        except Exception:
            pass
        self.toast.show("Sonido: " + ("activado" if cfg['sound_enabled'] else "desactivado"))

    def _add_section_header(self, parent, text, top_pad=8):
        frame = tk.Frame(parent, bg=COL_CARD)
        frame.pack(fill="x", pady=(top_pad, 4))
        tk.Label(frame, text=text, bg=COL_CARD, fg=COL_TEXT,
                 font=("DejaVu Sans", FS_SUBTITLE, "bold")).pack(anchor="w")
        SeparatorH(parent).pack(fill="x", pady=(2, 8))

    # ---------------------------------------------------------------------
    # Pestaña: General
    # ---------------------------------------------------------------------
    def _create_general_tab(self):
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="General")

        content = tk.Frame(tab, bg=COL_CARD)
        content.pack(fill="both", expand=True, padx=16, pady=16)

        self._add_section_header(content, "Idioma y apariencia")

        # Idioma (no se fuerza ninguna unidad aquí)
        lang = self.app.get_cfg().get('language', 'es')
        self.var_language = tk.StringVar(value=lang)
        LabeledCombobox(content, "Idioma", values=["es", "en"], textvariable=self.var_language).pack(fill="x", pady=4)

        # Decimales mostrados
        decimals = int(self.app.get_cfg().get('decimals', 1))
        self.var_decimals = tk.StringVar(value=str(decimals))
        LabeledCombobox(content, "Decimales en pantalla", values=["0", "1", "2"], textvariable=self.var_decimals).pack(fill="x", pady=4)

        # Sonido general
        snd = bool(self.app.get_cfg().get('sound_enabled', True))
        self.var_sound_enabled = tk.BooleanVar(value=snd)
        LabeledCheck(content, "Sonido activado", variable=self.var_sound_enabled).pack(anchor="w", pady=4)

        # Botones guardar/cancelar
        btns = tk.Frame(content, bg=COL_CARD)
        btns.pack(fill="x", pady=(10, 0))

        ButtonPrimary(btns, text="Guardar",
                      command=self._save_general).pack(side="left")
        ButtonSecondary(btns, text="Cancelar",
                        command=lambda: self.app.show_screen('home')).pack(side="left", padx=8)

    def _save_general(self):
        cfg = self.app.get_cfg()
        cfg['language'] = self.var_language.get()
        try:
            cfg['decimals'] = int(self.var_decimals.get())
        except Exception:
            cfg['decimals'] = 1
        cfg['sound_enabled'] = bool(self.var_sound_enabled.get())
        self.app.save_cfg(cfg)
        self.toast.show("Configuración general guardada")

    # ---------------------------------------------------------------------
    # Pestaña: Báscula
    # ---------------------------------------------------------------------
    def _create_scale_tab(self):
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="Báscula")

        content = tk.Frame(tab, bg=COL_CARD)
        content.pack(fill="both", expand=True, padx=16, pady=16)

        self._add_section_header(content, "Calibración y unidades")

        # Unidades — OJO: NO forzamos "g" aquí
        unit = self.app.get_cfg().get('unit', 'g')
        self.var_unit = tk.StringVar(value=unit)
        LabeledCombobox(content, "Unidad", values=["g", "kg"], textvariable=self.var_unit).pack(fill="x", pady=4)

        # Botones
        btns = tk.Frame(content, bg=COL_CARD)
        btns.pack(fill="x", pady=(10, 0))

        ButtonPrimary(btns, text="Guardar",
                      command=self._save_scale).pack(side="left")

        ButtonSecondary(btns, text="Recalibrar",
                        command=self._recalibrate).pack(side="left", padx=8)

    def _save_scale(self):
        cfg = self.app.get_cfg()
        cfg['unit'] = self.var_unit.get()
        self.app.save_cfg(cfg)
        self.toast.show("Unidades guardadas")

    def _recalibrate(self):
        # Llamada placeholder; tu proyecto tendrá rutina real
        try:
            subprocess.Popen(["/usr/bin/env", "bash", "-lc", "echo 'recalibrating'"])
            self.toast.show("Iniciando recalibración…")
        except Exception as e:
            self.toast.show(f"Error al recalibrar: {e}")

    # ---------------------------------------------------------------------
    # Pestaña: Red
    # ---------------------------------------------------------------------
    def _create_network_tab(self):
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="Red")

        content = tk.Frame(tab, bg=COL_CARD)
        content.pack(fill="both", expand=True, padx=16, pady=16)

        self._add_section_header(content, "Conexión")

        ip = self._get_ip_address() or "—"
        InfoRow(content, "IP actual", ip).pack(fill="x", pady=2)

        ButtonSecondary(content, text="Reiniciar servicios de red",
                        command=self._restart_network).pack(anchor="w", pady=(8, 0))

    def _get_ip_address(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return None

    def _restart_network(self):
        try:
            subprocess.run(["/usr/bin/env", "bash", "-lc", "sudo systemctl restart NetworkManager || sudo systemctl restart networking"], check=False)
            self.toast.show("Red reiniciada")
        except Exception as e:
            self.toast.show(f"Error: {e}")

    # ---------------------------------------------------------------------
    # Pestaña: Diabetes
    # ---------------------------------------------------------------------
    def _create_diabetes_tab(self):
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="Diabetes")

        content = tk.Frame(tab, bg=COL_CARD)
        content.pack(fill="both", expand=True, padx=16, pady=16)

        self._add_section_header(content, "Nightscout")

        api_url = self.app.get_cfg().get('nightscout_url', '')
        self.var_ns_url = tk.StringVar(value=api_url)
        LabeledEntry(content, "URL Nightscout", textvariable=self.var_ns_url).pack(fill="x", pady=4)

        # Anunciar valor al entrar en alerta — asegurar asignación (evita AttributeError)
        announce = bool(self.app.get_cfg().get('bg_announce_on_alert', False))
        self.var_bg_announce = tk.BooleanVar(value=announce)
        self.chk_bg_announce = LabeledCheck(content, "Anunciar valor al entrar en alerta",
                                            variable=self.var_bg_announce)
        self.chk_bg_announce.pack(anchor="w", pady=4)

        btns = tk.Frame(content, bg=COL_CARD)
        btns.pack(fill="x", pady=(10, 0))
        ButtonPrimary(btns, text="Guardar", command=self._save_diabetes).pack(side="left")

    def _save_diabetes(self):
        cfg = self.app.get_cfg()
        cfg['nightscout_url'] = self.var_ns_url.get().strip()
        cfg['bg_announce_on_alert'] = bool(self.var_bg_announce.get())
        self.app.save_cfg(cfg)
        self.toast.show("Ajustes de diabetes guardados")

    # ---------------------------------------------------------------------
    # Pestaña: Almacenamiento
    # ---------------------------------------------------------------------
    def _create_storage_tab(self):
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="Almacenamiento")

        content = tk.Frame(tab, bg=COL_CARD)
        content.pack(fill="both", expand=True, padx=16, pady=16)

        self._add_section_header(content, "Registros y espacio")

        ButtonSecondary(content, text="Limpiar logs antiguos",
                        command=self._prune_logs).pack(anchor="w", pady=4)

    def _prune_logs(self):
        # Placeholder: tu proyecto original tenía prune_jsonl en bascula.services.retention (si existe)
        try:
            from bascula.services.retention import prune_jsonl  # type: ignore
        except Exception:
            prune_jsonl = None
        if prune_jsonl:
            try:
                n = prune_jsonl()
                self.toast.show(f"Limpieza completada: {n} entradas")
            except Exception as e:
                self.toast.show(f"Error limpiando logs: {e}")
        else:
            self.toast.show("Función de limpieza no disponible")

    # ---------------------------------------------------------------------
    # Pestaña: Acerca de
    # ---------------------------------------------------------------------
    def _create_about_tab(self):
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="Acerca de")

        content = tk.Frame(tab, bg=COL_CARD)
        content.pack(fill="both", expand=True, padx=16, pady=16)

        self._add_section_header(content, "Información")

        InfoRow(content, "Versión", self.app.get_version()).pack(fill="x", pady=2)
        InfoRow(content, "Web", BASE_URL).pack(fill="x", pady=2)

    # ---------------------------------------------------------------------
    # Pestaña: OTA / Actualizaciones
    # ---------------------------------------------------------------------
    def _create_ota_tab(self):
        tab = tk.Frame(self.notebook, bg=COL_CARD)
        self.notebook.add(tab, text="Actualización")

        content = tk.Frame(tab, bg=COL_CARD)
        content.pack(fill="both", expand=True, padx=16, pady=16)

        self._add_section_header(content, "Actualizar desde GitHub")

        ButtonPrimary(content, text="Actualizar (git pull)", command=self._do_git_pull).pack(anchor="w", pady=4)

    def _do_git_pull(self):
        try:
            # Respeta preferencia del usuario: actualizar siempre desde GitHub (no crear archivos en vivo)
            cmd = "cd ~/bascula-cam && git pull --rebase --autostash"
            subprocess.run(["/usr/bin/env", "bash", "-lc", cmd], check=False)
            self.toast.show("Actualización ejecutada (revisa logs)")
        except Exception as e:
            self.toast.show(f"Error en actualización: {e}")
