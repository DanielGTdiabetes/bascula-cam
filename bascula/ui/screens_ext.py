"""
Pantallas extendidas que consumen el mini‑web (wifi_config.py) por HTTP.
Si la API no está disponible, se hace fallback a nmcli/archivos locales.
"""

# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk
import os, json, subprocess, socket
from pathlib import Path

from bascula.ui.widgets import *  # Card, BigButton, GhostButton, Toast, bind_touch_scroll, SoftKeyPopup
from bascula.ui.screens import BaseScreen  # reutilizamos BaseScreen

SHOW_SCROLLBAR = True

try:
    import requests  # opcional
except Exception:
    requests = None
try:
    import qrcode
    from PIL import Image, ImageTk
    _QR_OK = True
except Exception:
    _QR_OK = False

BASE_URL = os.environ.get('BASCULA_WEB_URL', 'http://127.0.0.1:8080')
from bascula.services.retention import prune_jsonl


class SettingsMenuScreenLegacy(BaseScreen):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app)
        # Gatear por modo diabético
        if not bool(self.app.get_cfg().get('diabetic_mode', False)):
            header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=10)
            tk.Label(header, text="Nightscout", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=14)
            # Volver a inicio para evitar bucle al estar en 'settingsmenu'
            GhostButton(header, text="< Atrás", command=lambda: self.app.show_screen('home'), micro=True).pack(side="right", padx=14)
            body = Card(self); body.pack(fill="both", expand=True, padx=14, pady=10)
            tk.Label(body, text="Activa el modo diabtico para configurar Nightscout", bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT)).pack(anchor='w', padx=10, pady=10)
            # No retornamos: mostramos igualmente el menú de ajustes general
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="Ajustes", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="< Volver a Inicio", command=lambda: self.app.show_screen('home'), micro=True).pack(side="right", padx=14)
        container = Card(self); container.pack(fill="both", expand=True, padx=14, pady=10)
        # Mostrar PIN actual (desde ~/.config/bascula/pin.txt)
        top_row = tk.Frame(container, bg=COL_CARD); top_row.pack(fill="x", pady=(6, 4))
        tk.Label(top_row, text="PIN actual:", bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(6, 4))
        self._pin_var = tk.StringVar(value=self._read_pin())
        tk.Label(top_row, textvariable=self._pin_var, bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT, "bold")).pack(side="left")
        tk.Label(top_row, text=" · Úsalo para entrar desde el móvil", bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(6, 0))
        GhostButton(top_row, text="Refrescar", command=self._refresh_info, micro=True).pack(side="right", padx=6)
        # URL LAN de la mini‑web
        url_row = tk.Frame(container, bg=COL_CARD); url_row.pack(fill="x", pady=(0, 6))
        tk.Label(url_row, text="Mini‑web:", bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(6, 4))
        self._url_var = tk.StringVar(value=self._detect_lan_url())
        tk.Label(url_row, textvariable=self._url_var, bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT)).pack(side="left")
        # QR de la URL
        self._qr_img_ref = None
        self._qr_label = tk.Label(container, bg=COL_CARD)
        self._qr_label.pack(anchor="w", padx=14, pady=(0,6))
        # Texto de ayuda bajo el QR
        self._qr_text = tk.Label(container, text="Escanea con tu móvil para abrir la mini‑web", bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT))
        self._qr_text.pack(anchor="w", padx=14, pady=(0,8))
        self._render_qr(self._url_var.get())
        # Toggle Modo diabetico
        dm_row = tk.Frame(container, bg=COL_CARD); dm_row.pack(fill="x", pady=(4, 8))
        self.var_dm = tk.BooleanVar(value=self.app.get_cfg().get('diabetic_mode', False))
        tk.Label(dm_row, text="Modo diabético:", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(10,6))
        chk = ttk.Checkbutton(dm_row, text="Activado", variable=self.var_dm, command=self._toggle_dm)
        chk.pack(side="left")
        tk.Label(dm_row, text="Modo experimental; no es consejo médico.", bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=8)

        # Asesor de bolo (experimental)
        adv_row = tk.Frame(container, bg=COL_CARD); adv_row.pack(fill="x", pady=(0, 8))
        self.var_adv = tk.BooleanVar(value=bool(self.app.get_cfg().get('advisor_enabled', False)))
        tk.Label(adv_row, text="Asesor bolo (experimental):", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(10,6))
        ttk.Checkbutton(adv_row, text="Activado", variable=self.var_adv, command=self._toggle_adv).pack(side="left")
        tk.Label(adv_row, text="Muestra sugerencias de timing/división en 'Finalizar' (no es consejo médico)", bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=8)

        # Tema de sonido
        snd_row = tk.Frame(container, bg=COL_CARD); snd_row.pack(fill="x", pady=(0, 8))
        tk.Label(snd_row, text="Sonido:", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=(10,6))
        self.var_theme = tk.StringVar(value=str(self.app.get_cfg().get('sound_theme', 'beep')))
        cb = ttk.Combobox(snd_row, textvariable=self.var_theme, values=["beep", "voice_es"], width=10, state="readonly")
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self._apply_sound_theme())
        GhostButton(snd_row, text="Probar", command=self._test_sound, micro=True).pack(side="left", padx=6)

        # Retención de histórico (meals.jsonl)
        ret = tk.Frame(container, bg=COL_CARD); ret.pack(fill="x", pady=(0, 8))
        tk.Label(ret, text="Histórico comidas:", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_TEXT, "bold")).grid(row=0, column=0, sticky='w', padx=10, pady=(6,2), columnspan=4)
        # Campos
        tk.Label(ret, text="Días máx:", bg=COL_CARD, fg=COL_TEXT).grid(row=1, column=0, sticky='w', padx=(10,4))
        self.var_days = tk.StringVar(value=str(self.app.get_cfg().get('meals_max_days', 180)))
        tk.Entry(ret, textvariable=self.var_days, width=6, bg=COL_CARD_HOVER, fg=COL_TEXT, relief='flat').grid(row=1, column=1, sticky='w')
        tk.Label(ret, text="Entradas máx:", bg=COL_CARD, fg=COL_TEXT).grid(row=1, column=2, sticky='w', padx=(10,4))
        self.var_entries = tk.StringVar(value=str(self.app.get_cfg().get('meals_max_entries', 1000)))
        tk.Entry(ret, textvariable=self.var_entries, width=8, bg=COL_CARD_HOVER, fg=COL_TEXT, relief='flat').grid(row=1, column=3, sticky='w')
        tk.Label(ret, text="Tamaño máx (MB):", bg=COL_CARD, fg=COL_TEXT).grid(row=1, column=4, sticky='w', padx=(10,4))
        self.var_mb = tk.StringVar(value=str(int((self.app.get_cfg().get('meals_max_bytes', 5_000_000) or 0)//1_000_000)))
        tk.Entry(ret, textvariable=self.var_mb, width=6, bg=COL_CARD_HOVER, fg=COL_TEXT, relief='flat').grid(row=1, column=5, sticky='w')
        # Botones
        GhostButton(ret, text="Aplicar", command=self._apply_retention, micro=True).grid(row=2, column=0, padx=10, pady=(6,6), sticky='w')
        GhostButton(ret, text="Limpiar histórico", command=self._prune_now, micro=True).grid(row=2, column=1, padx=6, pady=(6,6), sticky='w')
        self._ret_info = tk.Label(ret, text="", bg=COL_CARD, fg=COL_MUTED)
        self._ret_info.grid(row=2, column=2, padx=10, pady=(6,6), sticky='w', columnspan=4)
        self.after(200, self._refresh_ret_info)

        # Fotos (staging)
        photos = tk.Frame(container, bg=COL_CARD); photos.pack(fill="x", pady=(0, 8))
        tk.Label(photos, text="Fotos (staging):", bg=COL_CARD, fg=COL_ACCENT, font=("DejaVu Sans", FS_TEXT, "bold")).grid(row=0, column=0, sticky='w', padx=10, pady=(6,2), columnspan=2)
        self.var_keep_photos = tk.BooleanVar(value=bool(self.app.get_cfg().get('keep_photos', False)))
        ttk.Checkbutton(photos, text="Mantener fotos entre reinicios", variable=self.var_keep_photos, command=self._apply_keep_photos).grid(row=0, column=2, sticky='w', padx=10)
        GhostButton(photos, text="Limpiar fotos", command=self._clear_photos, micro=True).grid(row=0, column=3, sticky='e', padx=10)
        self._photos_info = tk.Label(photos, text="", bg=COL_CARD, fg=COL_MUTED)
        self._photos_info.grid(row=1, column=0, padx=10, pady=(4,8), sticky='w', columnspan=4)
        self.after(250, self._refresh_photos_info)
        grid = tk.Frame(container, bg=COL_CARD); grid.pack(expand=True)
        for i in range(2): grid.rowconfigure(i, weight=1); grid.columnconfigure(i, weight=1)
        btn_map = [("Calibración", 'calib'), ("Wi-Fi", 'wifi'), ("API Key", 'apikey'), ("Nightscout", 'nightscout'), ("Diabetes", 'diabetes')]
        for i, (text, target) in enumerate(btn_map):
            BigButton(grid, text=text, command=(lambda t=target: self.app.show_screen(t)), small=True).grid(row=i//2, column=i%2, sticky="nsew", padx=6, pady=6)
        self.toast = Toast(self)

    # --- Helpers específicos del menú de ajustes ---
    def _read_pin(self) -> str:
        try:
            p = Path.home() / ".config" / "bascula" / "pin.txt"
            if p.exists():
                return p.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            pass
        return "N/D"

    def _detect_lan_url(self) -> str:
        port = os.environ.get('BASCULA_WEB_PORT', '8080')
        ip = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.2)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        except Exception:
            pass
        finally:
            try:
                s.close()
            except Exception:
                pass
        if not ip:
            try:
                out = subprocess.check_output(["/bin/sh", "-lc", "hostname -I | awk '{print $1}'"], text=True, timeout=1).strip()
                ip = out or None
            except Exception:
                ip = None
        return f"http://{ip}:{port}/" if ip else f"http://<IP>:{port}/"

    def _refresh_info(self):
        try:
            self._pin_var.set(self._read_pin())
            url = self._detect_lan_url()
            self._url_var.set(url)
            self._render_qr(url)
        except Exception:
            pass

    def _render_qr(self, url: str):
        try:
            if _QR_OK and isinstance(url, str) and url.startswith("http"):
                qr = qrcode.QRCode(border=1, box_size=4)
                qr.add_data(url); qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
                img = img.resize((180, 180))
                photo = ImageTk.PhotoImage(img)
                self._qr_img_ref = photo
                self._qr_label.configure(image=photo, text="")
            else:
                self._qr_label.configure(image="", text="Instala 'qrcode' para mostrar QR")
        except Exception:
            try:
                self._qr_label.configure(image="", text=url)
            except Exception:
                pass

    # --- Toggles y acciones para SettingsMenuScreen ---
    def _toggle_dm(self):
        try:
            cfg = self.app.get_cfg()
            cfg['diabetic_mode'] = bool(self.var_dm.get())
            self.app.save_cfg()
            self.toast.show("Modo diabético: " + ("ON" if cfg['diabetic_mode'] else "OFF"), 900)
        except Exception:
            pass

    def _toggle_adv(self):
        try:
            cfg = self.app.get_cfg()
            if not cfg.get('diabetic_mode', False) and self.var_adv.get():
                self.var_adv.set(False)
                self.toast.show("Activa modo diabético primero", 1200, COL_WARN)
                return
            cfg['advisor_enabled'] = bool(self.var_adv.get())
            self.app.save_cfg()
            self.toast.show("Asesor bolo: " + ("ON" if cfg['advisor_enabled'] else "OFF"), 900)
        except Exception:
            pass

    def _apply_sound_theme(self):
        try:
            theme = self.var_theme.get().strip()
            if theme not in ("beep", "voice_es"):
                return
            cfg = self.app.get_cfg(); cfg['sound_theme'] = theme; self.app.save_cfg()
            if hasattr(self.app, 'get_audio') and self.app.get_audio():
                self.app.get_audio().set_theme(theme)
            self.toast.show("Tema sonido: " + theme, 900)
        except Exception:
            pass

    def _test_sound(self):
        try:
            if hasattr(self.app, 'get_audio') and self.app.get_audio():
                self.app.get_audio().play_event('boot_ready')
        except Exception:
            pass

    # ---- Retención ----
    def _apply_retention(self):
        try:
            days = max(0, int(self.var_days.get()))
            entries = max(0, int(self.var_entries.get()))
            mb = max(0, int(self.var_mb.get()))
            cfg = self.app.get_cfg()
            cfg['meals_max_days'] = days
            cfg['meals_max_entries'] = entries
            cfg['meals_max_bytes'] = mb * 1_000_000
            self.app.save_cfg()
            self.toast.show("Retención aplicada", 900)
            self._refresh_ret_info()
        except Exception as e:
            self.toast.show(f"Error: {e}", 1300, COL_DANGER)

    def _meals_path(self) -> Path:
        return Path.home() / '.config' / 'bascula' / 'meals.jsonl'

    def _refresh_ret_info(self):
        try:
            p = self._meals_path()
            if not p.exists():
                self._ret_info.config(text="Sin histórico")
                return
            size = p.stat().st_size
            try:
                with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                    count = sum(1 for _ in f)
            except Exception:
                count = 0
            self._ret_info.config(text=f"Entradas: {count} · Tamaño: {size/1_000_000:.2f} MB")
        except Exception:
            pass

    def _prune_now(self):
        try:
            p = self._meals_path()
            if not p.exists():
                self.toast.show("Sin histórico", 900)
                return
            cfg = self.app.get_cfg()
            prune_jsonl(
                p,
                max_days=int(cfg.get('meals_max_days', 0) or 0),
                max_entries=int(cfg.get('meals_max_entries', 0) or 0),
                max_bytes=int(cfg.get('meals_max_bytes', 0) or 0),
            )
            self.toast.show("Histórico limpiado", 1000, COL_SUCCESS)
            self._refresh_ret_info()
        except Exception as e:
            self.toast.show(f"Error: {e}", 1300, COL_DANGER)

    # ---- Fotos ----
    def _photos_staging(self) -> Path:
        return Path.home() / '.bascula' / 'photos' / 'staging'

    def _refresh_photos_info(self):
        try:
            st = self._photos_staging()
            if not st.exists():
                self._photos_info.config(text="Sin fotos")
                return
            files = list(st.glob('*.jpg'))
            size = sum(p.stat().st_size for p in files) if files else 0
            self._photos_info.config(text=f"Fotos: {len(files)} · Tamaño: {size/1_000_000:.2f} MB")
        except Exception:
            pass

    def _apply_keep_photos(self):
        try:
            cfg = self.app.get_cfg()
            cfg['keep_photos'] = bool(self.var_keep_photos.get())
            self.app.save_cfg()
            self.toast.show("Fotos: " + ("mantener" if cfg['keep_photos'] else "no guardar"), 900)
        except Exception:
            pass

    def _clear_photos(self):
        try:
            st = self._photos_staging(); mt = Path.home() / '.bascula' / 'photos' / 'meta'
            n = 0
            if st.exists():
                for p in st.glob('*.jpg'):
                    try:
                        stem = p.stem
                        p.unlink()
                        n += 1
                        mp = mt / f"{stem}.json"
                        try:
                            if mp.exists():
                                mp.unlink()
                        except Exception:
                            pass
                    except Exception:
                        pass
            self.toast.show(f"Fotos eliminadas: {n}", 900)
            self._refresh_photos_info()
        except Exception:
            pass


class DiabetesSettingsScreen(BaseScreen):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="Ajustes de Diabetes", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="< Atrás", command=lambda: self.app.show_screen('settingsmenu'), micro=True).pack(side="right", padx=14)
        body = Card(self); body.pack(fill="both", expand=True, padx=14, pady=10)

        # Modo diabético + aviso
        top = tk.Frame(body, bg=COL_CARD); top.pack(fill="x", padx=10, pady=(6,6))
        self.var_dm = tk.BooleanVar(value=bool(self.app.get_cfg().get('diabetic_mode', False)))
        ttk.Checkbutton(top, text="Modo diabético (experimental)", variable=self.var_dm, command=self._toggle_dm).pack(side="left")
        tk.Label(top, text="No es consejo médico.", bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT)).pack(side="left", padx=10)

        nsrow = tk.Frame(body, bg=COL_CARD); nsrow.pack(fill="x", padx=10, pady=(0,6))
        self._btn_ns = GhostButton(nsrow, text="Configurar Nightscout", command=lambda: self.app.show_screen('nightscout'), micro=True)
        self._btn_ns.pack(side="left", padx=4)
        self._update_ns_btn()

        # Parámetros de bolo
        frm = tk.Frame(body, bg=COL_CARD); frm.pack(fill="x", padx=10, pady=(6,10))
        tk.Label(frm, text="Objetivo (mg/dL)", bg=COL_CARD, fg=COL_TEXT).grid(row=0, column=0, sticky='w')
        tk.Label(frm, text="ISF (mg/dL/U)", bg=COL_CARD, fg=COL_TEXT).grid(row=0, column=1, sticky='w', padx=(10,0))
        tk.Label(frm, text="Ratio HC (g/U)", bg=COL_CARD, fg=COL_TEXT).grid(row=0, column=2, sticky='w', padx=(10,0))
        tk.Label(frm, text="DIA (h)", bg=COL_CARD, fg=COL_TEXT).grid(row=0, column=3, sticky='w', padx=(10,0))
        self.var_tbg = tk.StringVar(value=str(self.app.get_cfg().get('target_bg_mgdl', 110)))
        self.var_isf = tk.StringVar(value=str(self.app.get_cfg().get('isf_mgdl_per_u', 50)))
        self.var_carb = tk.StringVar(value=str(self.app.get_cfg().get('carb_ratio_g_per_u', 10)))
        self.var_dia = tk.StringVar(value=str(self.app.get_cfg().get('dia_hours', 4)))
        tk.Entry(frm, textvariable=self.var_tbg, width=8, bg=COL_CARD_HOVER, fg=COL_TEXT, relief='flat').grid(row=1, column=0)
        tk.Entry(frm, textvariable=self.var_isf, width=8, bg=COL_CARD_HOVER, fg=COL_TEXT, relief='flat').grid(row=1, column=1, padx=(10,0))
        tk.Entry(frm, textvariable=self.var_carb, width=8, bg=COL_CARD_HOVER, fg=COL_TEXT, relief='flat').grid(row=1, column=2, padx=(10,0))
        tk.Entry(frm, textvariable=self.var_dia, width=6, bg=COL_CARD_HOVER, fg=COL_TEXT, relief='flat').grid(row=1, column=3, padx=(10,0))

        ctr = tk.Frame(body, bg=COL_CARD); ctr.pack(fill='x', padx=10, pady=(6,6))
        BigButton(ctr, text="Guardar", command=self._apply, micro=True).pack(side='left', padx=4)

        self.toast = Toast(self)

    def _toggle_dm(self):
        try:
            cfg = self.app.get_cfg(); cfg['diabetic_mode'] = bool(self.var_dm.get()); self.app.save_cfg()
            self.toast.show("Modo diabético: " + ("ON" if cfg['diabetic_mode'] else "OFF"), 900)
            self._update_ns_btn()
        except Exception:
            pass

    def _update_ns_btn(self):
        try:
            dm = bool(self.app.get_cfg().get('diabetic_mode', False))
            state = ("normal" if dm else "disabled")
            self._btn_ns.configure(state=state)
        except Exception:
            pass

    def _apply(self):
        try:
            cfg = self.app.get_cfg()
            cfg['target_bg_mgdl'] = max(60, int(float(self.var_tbg.get())) if self.var_tbg.get() else 110)
            cfg['isf_mgdl_per_u'] = max(5, int(float(self.var_isf.get())) if self.var_isf.get() else 50)
            cfg['carb_ratio_g_per_u'] = max(2, int(float(self.var_carb.get())) if self.var_carb.get() else 10)
            cfg['dia_hours'] = max(2, int(float(self.var_dia.get())) if self.var_dia.get() else 4)
            self.app.save_cfg()
            self.toast.show("Parámetros guardados", 1000, COL_SUCCESS)
        except Exception as e:
            self.toast.show(f"Error: {e}", 1300, COL_DANGER)

    def _toggle_dm(self):
        try:
            cfg = self.app.get_cfg()
            cfg['diabetic_mode'] = bool(self.var_dm.get())
            self.app.save_cfg()
            self.toast.show("Modo diabetico: " + ("ON" if cfg['diabetic_mode'] else "OFF"), 900)
        except Exception:
            pass

    def _toggle_adv(self):
        try:
            cfg = self.app.get_cfg()
            if not cfg.get('diabetic_mode', False) and self.var_adv.get():
                self.var_adv.set(False)
                self.toast.show("Activa modo diabético primero", 1200, COL_WARN)
                return
            cfg['advisor_enabled'] = bool(self.var_adv.get())
            self.app.save_cfg()
            self.toast.show("Asesor bolo: " + ("ON" if cfg['advisor_enabled'] else "OFF"), 900)
        except Exception:
            pass

    def _apply_sound_theme(self):
        try:
            theme = self.var_theme.get().strip()
            if theme not in ("beep", "voice_es"): return
            cfg = self.app.get_cfg(); cfg['sound_theme'] = theme; self.app.save_cfg()
            if hasattr(self.app, 'get_audio') and self.app.get_audio():
                self.app.get_audio().set_theme(theme)
            self.toast.show("Tema sonido: " + theme, 900)
        except Exception:
            pass

    def _test_sound(self):
        try:
            if hasattr(self.app, 'get_audio') and self.app.get_audio():
                self.app.get_audio().play_event('boot_ready')
        except Exception:
            pass

    # ---- Retención ----
    def _apply_retention(self):
        try:
            days = max(0, int(self.var_days.get()))
            entries = max(0, int(self.var_entries.get()))
            mb = max(0, int(self.var_mb.get()))
            cfg = self.app.get_cfg()
            cfg['meals_max_days'] = days
            cfg['meals_max_entries'] = entries
            cfg['meals_max_bytes'] = mb * 1_000_000
            self.app.save_cfg()
            self.toast.show("Retención aplicada", 900)
            self._refresh_ret_info()
        except Exception as e:
            self.toast.show(f"Error: {e}", 1300, COL_DANGER)

    def _meals_path(self) -> Path:
        return Path.home() / '.config' / 'bascula' / 'meals.jsonl'

    def _refresh_ret_info(self):
        try:
            p = self._meals_path()
            if not p.exists():
                self._ret_info.config(text="Sin histórico")
                return
            size = p.stat().st_size
            try:
                with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                    count = sum(1 for _ in f)
            except Exception:
                count = 0
            self._ret_info.config(text=f"Entradas: {count} • Tamaño: {size/1_000_000:.2f} MB")
        except Exception:
            pass

    def _prune_now(self):
        try:
            p = self._meals_path()
            if not p.exists():
                self.toast.show("Sin histórico", 900)
                return
            cfg = self.app.get_cfg()
            prune_jsonl(
                p,
                max_days=int(cfg.get('meals_max_days', 0) or 0),
                max_entries=int(cfg.get('meals_max_entries', 0) or 0),
                max_bytes=int(cfg.get('meals_max_bytes', 0) or 0),
            )
            self.toast.show("Histórico limpiado", 1000, COL_SUCCESS)
            self._refresh_ret_info()
        except Exception as e:
            self.toast.show(f"Error: {e}", 1300, COL_DANGER)

    # ---- Fotos ----
    def _photos_staging(self) -> Path:
        return Path.home() / '.bascula' / 'photos' / 'staging'

    def _refresh_photos_info(self):
        try:
            st = self._photos_staging()
            if not st.exists():
                self._photos_info.config(text="Sin fotos")
                return
            files = list(st.glob('*.jpg'))
            size = sum(p.stat().st_size for p in files) if files else 0
            self._photos_info.config(text=f"Fotos: {len(files)} • Tamaño: {size/1_000_000:.2f} MB")
        except Exception:
            pass

    def _apply_keep_photos(self):
        try:
            cfg = self.app.get_cfg()
            cfg['keep_photos'] = bool(self.var_keep_photos.get())
            self.app.save_cfg()
            self.toast.show("Fotos: " + ("mantener" if cfg['keep_photos'] else "no guardar"), 900)
        except Exception:
            pass

    def _clear_photos(self):
        try:
            st = self._photos_staging(); mt = Path.home() / '.bascula' / 'photos' / 'meta'
            n = 0
            if st.exists():
                for p in st.glob('*.jpg'):
                    try:
                        stem = p.stem
                        p.unlink()
                        n += 1
                        mp = mt / f"{stem}.json"
                        try:
                            if mp.exists():
                                mp.unlink()
                        except Exception:
                            pass
                    except Exception:
                        pass
            self.toast.show(f"Eliminadas {n} fotos", 1200, COL_SUCCESS)
            self._refresh_photos_info()
        except Exception as e:
            self.toast.show(f"Error: {e}", 1300, COL_DANGER)

    def _apply_bolus_params(self):
        try:
            cfg = self.app.get_cfg()
            cfg['target_bg_mgdl'] = max(60, int(float(getattr(self, 'var_tbg', tk.StringVar(value=cfg.get('target_bg_mgdl', 110))).get())))
            cfg['isf_mgdl_per_u'] = max(5, int(float(getattr(self, 'var_isf', tk.StringVar(value=cfg.get('isf_mgdl_per_u', 50))).get())))
            cfg['carb_ratio_g_per_u'] = max(2, int(float(getattr(self, 'var_carb', tk.StringVar(value=cfg.get('carb_ratio_g_per_u', 10))).get())))
            cfg['dia_hours'] = max(2, int(float(getattr(self, 'var_dia', tk.StringVar(value=cfg.get('dia_hours', 4))).get())))
            self.app.save_cfg()
            self.toast.show("Parámetros bolo guardados", 1000, COL_SUCCESS)
        except Exception as e:
            self.toast.show(f"Error: {e}", 1300, COL_DANGER)

    def _need_dm(self):
        self.toast.show("Activa modo diabético para configurar Nightscout", 1500, COL_MUTED)

    def _read_pin(self) -> str:
        try:
            p = Path.home() / ".config" / "bascula" / "pin.txt"
            if p.exists():
                return p.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            pass
        return "N/D"

    def _detect_lan_url(self) -> str:
        port = os.environ.get('BASCULA_WEB_PORT', '8080')
        ip = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.2)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        except Exception:
            pass
        finally:
            try:
                s.close()
            except Exception:
                pass
        if not ip:
            try:
                out = subprocess.check_output(["/bin/sh", "-lc", "hostname -I | awk '{print $1}'"], text=True, timeout=1).strip()
                ip = out or None
            except Exception:
                ip = None
        return f"http://{ip}:{port}/" if ip else f"http://<IP>:{port}/"

    def _refresh_info(self):
        self._pin_var.set(self._read_pin())
        url = self._detect_lan_url()
        self._url_var.set(url)
        self._render_qr(url)

    def _render_qr(self, url: str):
        try:
            if _QR_OK and isinstance(url, str) and url.startswith("http"):
                qr = qrcode.QRCode(border=1, box_size=4)
                qr.add_data(url); qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
                # Redimensionar a tamaño amigable (180x180 aprox.)
                img = img.resize((180, 180))
                photo = ImageTk.PhotoImage(img)
                self._qr_img_ref = photo
                self._qr_label.configure(image=photo, text="")
            else:
                self._qr_label.configure(image="", text="Instala 'qrcode' para mostrar QR")
        except Exception:
            try:
                self._qr_label.configure(image="", text=url)
            except Exception:
                pass


class WifiScreen(BaseScreen):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="Conexión Wi‑Fi", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="< Atrás", command=lambda: self.app.show_screen('settingsmenu'), micro=True).pack(side="right", padx=14)

        body = Card(self); body.pack(fill="both", expand=True, padx=14, pady=10)

        top = tk.Frame(body, bg=COL_CARD); top.pack(fill="x", pady=(6,8))
        GhostButton(top, text="Actualizar redes", command=self._scan, micro=True).pack(side="left", padx=6)
        self.lbl_status = tk.Label(top, text="", bg=COL_CARD, fg=COL_MUTED, font=("DejaVu Sans", FS_TEXT))
        self.lbl_status.pack(side="left", padx=10)

        main = tk.Frame(body, bg=COL_CARD); main.pack(fill="both", expand=True)
        main.grid_rowconfigure(0, weight=1); main.grid_columnconfigure(0, weight=3); main.grid_columnconfigure(1, weight=2)

        # Lista redes
        left = tk.Frame(main, bg=COL_CARD); left.grid(row=0, column=0, sticky="nsew", padx=(6,3), pady=6)
        style = ttk.Style(self); style.theme_use('clam')
        style.configure('Dark.Treeview', background='#1a1f2e', foreground=COL_TEXT, fieldbackground='#1a1f2e', rowheight=28, font=("DejaVu Sans", FS_LIST_ITEM))
        style.map('Dark.Treeview', background=[('selected', '#2a3142')])
        tree_fr = tk.Frame(left, bg=COL_CARD); tree_fr.pack(fill="both", expand=True)
        tree_fr.grid_rowconfigure(0, weight=1); tree_fr.grid_columnconfigure(0, weight=1)
        self.tv = ttk.Treeview(tree_fr, columns=("ssid","signal","sec"), show="headings", style='Dark.Treeview', selectmode="browse")
        self.tv.heading("ssid", text="SSID"); self.tv.column("ssid", anchor="w", width=260, stretch=True)
        self.tv.heading("signal", text="Señal"); self.tv.column("signal", anchor="center", width=80)
        self.tv.heading("sec", text="Seguridad"); self.tv.column("sec", anchor="center", width=120)
        bind_touch_scroll(self.tv, units_divisor=1, min_drag_px=3)
        self.tv.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(tree_fr, orient="vertical", command=self.tv.yview); self.tv.configure(yscrollcommand=sb.set)
        if SHOW_SCROLLBAR: sb.grid(row=0, column=1, sticky="ns")
        self.tv.bind("<Double-1>", self._on_connect_selected)

        # Panel conexión
        right = tk.Frame(main, bg=COL_CARD); right.grid(row=0, column=1, sticky="nsew", padx=(3,6), pady=6)
        tk.Label(right, text="SSID seleccionado:", bg=COL_CARD, fg=COL_TEXT).pack(anchor="w", padx=8, pady=(4,0))
        self.var_ssid = tk.StringVar()
        row_ssid = tk.Frame(right, bg=COL_CARD); row_ssid.pack(fill="x", padx=8)
        ent_ssid = tk.Entry(row_ssid, textvariable=self.var_ssid, bg=COL_CARD_HOVER, fg=COL_TEXT, relief="flat")
        ent_ssid.pack(side="left", expand=True, fill="x")
        try:
            bind_text_popup(ent_ssid, title="SSID")
        except Exception:
            pass
        GhostButton(row_ssid, text="Editar", command=lambda: self._edit_text(self.var_ssid, "SSID"), micro=True).pack(side="left", padx=6)

        tk.Label(right, text="Contraseña:", bg=COL_CARD, fg=COL_TEXT).pack(anchor="w", padx=8, pady=(6,0))
        row_psk = tk.Frame(right, bg=COL_CARD); row_psk.pack(fill="x", padx=8)
        self.var_psk = tk.StringVar()
        ent_psk = tk.Entry(row_psk, textvariable=self.var_psk, show="*", bg=COL_CARD_HOVER, fg=COL_TEXT, relief="flat")
        ent_psk.pack(side="left", expand=True, fill="x")
        try:
            bind_text_popup(ent_psk, title="Contraseña", password=True)
        except Exception:
            pass
        GhostButton(row_psk, text="Teclado", command=lambda: self._edit_text(self.var_psk, "Contraseña", password=True), micro=True).pack(side="left", padx=6)

        ctr = tk.Frame(right, bg=COL_CARD); ctr.pack(fill="x", pady=8, padx=8)
        BigButton(ctr, text="Conectar", command=self._connect, micro=True).pack(side="left", padx=4)
        GhostButton(ctr, text="Actualizar", command=self._scan, micro=True).pack(side="left", padx=4)

        self.toast = Toast(self)
        self.after(200, self._scan)

    def _edit_text(self, var, title, password=False):
        def _acc(val): var.set(val)
        SoftKeyPopup(self, title=title, initial=var.get(), password=password, on_accept=_acc)

    def _has(self, cmd):
        try:
            subprocess.check_call(["/usr/bin/env", "which", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    def _scan(self):
        self.lbl_status.config(text="Buscando redes...")
        self.update_idletasks()
        self.tv.delete(*self.tv.get_children())
        nets = []
        # Intento HTTP
        if requests is not None:
            try:
                r = requests.get(f"{BASE_URL}/api/wifi_scan", timeout=6)
                if r.ok and r.json().get("ok"):
                    nets = r.json().get("nets", [])
                else:
                    self.lbl_status.config(text=f"Servicio web: {r.status_code}")
            except Exception:
                pass
        # Fallback nmcli
        if not nets:
            try:
                if self._has('nmcli'):
                    out = subprocess.check_output(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list"], stderr=subprocess.STDOUT, text=True, timeout=8)
                    for line in out.splitlines():
                        if not line.strip():
                            continue
                        parts = line.split(":")
                        while len(parts) < 3:
                            parts.append("")
                        ssid, signal, sec = parts[0], parts[1], parts[2]
                        if not ssid:
                            continue
                        nets.append({"ssid": ssid, "signal": signal or "", "sec": sec or ""})
                else:
                    self.lbl_status.config(text="nmcli no disponible.")
            except Exception as e:
                self.lbl_status.config(text=f"Error al escanear: {e}")
                nets = []
        for n in nets:
            self.tv.insert("", "end", values=(n.get("ssid",""), n.get("signal",""), n.get("sec","")))
        self.lbl_status.config(text=f"Redes: {len(nets)}")

    def _on_connect_selected(self, _evt=None):
        sel = self.tv.selection()
        if not sel:
            return
        vals = self.tv.item(sel[0], "values")
        ssid = vals[0]
        self.var_ssid.set(ssid)
        self._edit_text(self.var_psk, f"Contraseña para '{ssid}'", password=True)

    def _connect(self):
        ssid = self.var_ssid.get().strip(); psk = self.var_psk.get().strip()
        if not ssid or not psk:
            self.toast.show("Introduce SSID y clave", 1400, COL_WARN); return
        self.lbl_status.config(text=f"Conectando a {ssid}..."); self.update_idletasks()
        # Intento HTTP
        if requests is not None:
            try:
                r = requests.post(f"{BASE_URL}/api/wifi", headers={"Content-Type": "application/json"}, json={"ssid": ssid, "psk": psk}, timeout=10)
                if r.ok and r.json().get("ok"):
                    self.toast.show("Conectado / guardado", 1400, COL_SUCCESS); self._scan(); return
            except Exception:
                pass
        # Fallback nmcli
        if not self._has('nmcli'):
            self.toast.show("nmcli no está disponible", 1600, COL_DANGER); return
        try:
            rc = subprocess.call(["nmcli", "dev", "wifi", "connect", ssid, "password", psk])
            if rc == 0:
                self.toast.show("Conectado / guardado", 1400, COL_SUCCESS)
                self._scan()
            else:
                self.toast.show(f"Fallo (rc={rc})", 1600, COL_DANGER)
        except Exception as e:
            self.toast.show(f"Error: {e}", 1600, COL_DANGER)


class ApiKeyScreen(BaseScreen):
    CFG_DIR = Path.home() / ".config" / "bascula"
    API_FILE = CFG_DIR / "apikey.json"

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="API Key OpenAI", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="< Atrás", command=lambda: self.app.show_screen('settingsmenu'), micro=True).pack(side="right", padx=14)
        body = Card(self); body.pack(fill="both", expand=True, padx=14, pady=10)
        tk.Label(body, text="Introduce tu API Key (sk-...)", bg=COL_CARD, fg=COL_TEXT).pack(anchor="w", padx=10, pady=(6,2))
        row = tk.Frame(body, bg=COL_CARD); row.pack(fill="x", padx=10, pady=6)
        self.var_key = tk.StringVar(value=self._load_key())
        ent = tk.Entry(row, textvariable=self.var_key, show="*", bg=COL_CARD_HOVER, fg=COL_TEXT, relief="flat")
        ent.pack(side="left", expand=True, fill="x")
        try:
            bind_text_popup(ent, title="API Key", password=True)
        except Exception:
            pass
        GhostButton(row, text="Teclado", command=self._edit_key, micro=True).pack(side="left", padx=6)
        ctr = tk.Frame(body, bg=COL_CARD); ctr.pack(fill="x", padx=10, pady=6)
        BigButton(ctr, text="Guardar", command=self._save, micro=True).pack(side="left", padx=4)
        GhostButton(ctr, text="Probar", command=self._test, micro=True).pack(side="left", padx=4)
        self.lbl = tk.Label(body, text="", bg=COL_CARD, fg=COL_MUTED)
        self.lbl.pack(anchor="w", padx=10, pady=4)
        self.toast = Toast(self)

    def _edit_key(self):
        def _acc(val): self.var_key.set(val)
        SoftKeyPopup(self, title="API Key", initial=self.var_key.get(), password=True, on_accept=_acc)

    def _load_key(self):
        try:
            if self.API_FILE.exists():
                data = json.loads(self.API_FILE.read_text(encoding="utf-8"))
                return data.get("openai_api_key", "")
        except Exception:
            pass
        return ""

    def _save(self):
        key = self.var_key.get().strip()
        # HTTP
        if requests is not None:
            try:
                r = requests.post(f"{BASE_URL}/api/apikey", headers={"Content-Type": "application/json"}, json={"key": key}, timeout=6)
                if r.ok and r.json().get("ok"):
                    self.toast.show("Guardado", 1200, COL_SUCCESS); return
            except Exception:
                pass
        # Fichero
        try:
            self.CFG_DIR.mkdir(parents=True, exist_ok=True)
            self.API_FILE.write_text(json.dumps({"openai_api_key": key}), encoding="utf-8")
            try: os.chmod(self.API_FILE, 0o600)
            except Exception: pass
            self.toast.show("Guardado (local)", 1200, COL_SUCCESS)
        except Exception as e:
            self.toast.show(f"Error: {e}", 1600, COL_DANGER)

    def _test(self):
        key = self.var_key.get().strip()
        if not key:
            self.lbl.config(text="Clave vacía"); return
        if not (key.startswith("sk-") and len(key) > 20):
            self.lbl.config(text="Formato de clave sospechoso"); return
        self.lbl.config(text="Formato OK. Guardada y lista para uso.")


class NightscoutScreen(BaseScreen):
    CFG_DIR = Path.home() / ".config" / "bascula"
    NS_FILE = CFG_DIR / "nightscout.json"

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="Nightscout", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="< Atrás", command=lambda: self.app.show_screen('settingsmenu'), micro=True).pack(side="right", padx=14)
        body = Card(self); body.pack(fill="both", expand=True, padx=14, pady=10)

        data = self._load()
        self.var_url = tk.StringVar(value=data.get("url", ""))
        self.var_token = tk.StringVar(value=data.get("token", ""))

        tk.Label(body, text="URL de Nightscout (https://...)", bg=COL_CARD, fg=COL_TEXT).pack(anchor="w", padx=10, pady=(6,2))
        row1 = tk.Frame(body, bg=COL_CARD); row1.pack(fill="x", padx=10)
        ent_url = tk.Entry(row1, textvariable=self.var_url, bg=COL_CARD_HOVER, fg=COL_TEXT, relief="flat")
        ent_url.pack(side="left", expand=True, fill="x")
        GhostButton(row1, text="Teclado", command=lambda: self._edit(self.var_url, "URL"), micro=True).pack(side="left", padx=6)

        tk.Label(body, text="Token", bg=COL_CARD, fg=COL_TEXT).pack(anchor="w", padx=10, pady=(8,2))
        row2 = tk.Frame(body, bg=COL_CARD); row2.pack(fill="x", padx=10)
        ent_tok = tk.Entry(row2, textvariable=self.var_token, show="*", bg=COL_CARD_HOVER, fg=COL_TEXT, relief="flat")
        ent_tok.pack(side="left", expand=True, fill="x")
        GhostButton(row2, text="Teclado", command=lambda: self._edit(self.var_token, "Token", password=True), micro=True).pack(side="left", padx=6)

        ctr = tk.Frame(body, bg=COL_CARD); ctr.pack(fill="x", padx=10, pady=8)
        BigButton(ctr, text="Guardar", command=self._save, micro=True).pack(side="left", padx=4)
        GhostButton(ctr, text="Probar", command=self._test, micro=True).pack(side="left", padx=4)

        self.lbl = tk.Label(body, text="", bg=COL_CARD, fg=COL_MUTED)
        self.lbl.pack(anchor="w", padx=10, pady=4)
        self.toast = Toast(self)

    def _edit(self, var, title, password=False):
        def _acc(val): var.set(val)
        SoftKeyPopup(self, title=title, initial=var.get(), password=password, on_accept=_acc)

    def _load(self):
        # HTTP
        if requests is not None:
            try:
                r = requests.get(f"{BASE_URL}/api/nightscout", timeout=6)
                if r.ok and r.json().get("ok"):
                    return r.json().get("data", {})
            except Exception:
                pass
        # Fichero
        try:
            if self.NS_FILE.exists():
                return json.loads(self.NS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save(self):
        data = {"url": self.var_url.get().strip(), "token": self.var_token.get().strip()}
        # HTTP
        if requests is not None:
            try:
                r = requests.post(f"{BASE_URL}/api/nightscout", headers={"Content-Type": "application/json"}, json=data, timeout=6)
                if r.ok and r.json().get("ok"):
                    self.toast.show("Guardado", 1200, COL_SUCCESS); return
            except Exception:
                pass
        # Fichero
        try:
            self.CFG_DIR.mkdir(parents=True, exist_ok=True)
            self.NS_FILE.write_text(json.dumps(data), encoding="utf-8")
            try: os.chmod(self.NS_FILE, 0o600)
            except Exception: pass
            self.toast.show("Guardado (local)", 1200, COL_SUCCESS)
        except Exception as e:
            self.toast.show(f"Error: {e}", 1600, COL_DANGER)

    def _test(self):
        url = self.var_url.get().strip().rstrip('/')
        token = self.var_token.get().strip()
        if not url:
            self.lbl.config(text="Falta URL"); return
        try:
            import requests as rq2
        except Exception:
            self.lbl.config(text="Instala 'requests' para probar"); return
        try:
            r = rq2.get(f"{url}/api/v1/status.json", params={"token": token}, timeout=5)
            if r.ok:
                self.lbl.config(text=f"OK: {r.json().get('apiEnabled', True)}")
            else:
                self.lbl.config(text=f"HTTP {r.status_code}")
        except Exception as e:
            self.lbl.config(text=f"Error: {e}")
