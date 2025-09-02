"""
Pantallas extendidas que consumen el mini‑web (wifi_config.py) por HTTP.
Si la API no está disponible, se hace fallback a nmcli/archivos locales.
"""

# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk
import os, json, subprocess
from pathlib import Path

from bascula.ui.widgets import *  # Card, BigButton, GhostButton, Toast, bind_touch_scroll, SoftKeyPopup
from bascula.ui.screens import BaseScreen  # reutilizamos BaseScreen

SHOW_SCROLLBAR = False

try:
    import requests  # opcional
except Exception:
    requests = None

BASE_URL = os.environ.get('BASCULA_WEB_URL', 'http://127.0.0.1:8080')


class SettingsMenuScreen(BaseScreen):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="Ajustes", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", FS_TITLE, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="< Volver a Inicio", command=lambda: self.app.show_screen('home'), micro=True).pack(side="right", padx=14)
        container = Card(self); container.pack(fill="both", expand=True, padx=14, pady=10)
        grid = tk.Frame(container, bg=COL_CARD); grid.pack(expand=True)
        for i in range(2): grid.rowconfigure(i, weight=1); grid.columnconfigure(i, weight=1)
        btn_map = [("Calibración", 'calib'), ("Wi‑Fi", 'wifi'), ("API Key", 'apikey'), ("Nightscout", 'nightscout')]
        for i, (text, target) in enumerate(btn_map):
            BigButton(grid, text=text, command=(lambda t=target: self.app.show_screen(t)), small=True).grid(row=i//2, column=i%2, sticky="nsew", padx=6, pady=6)
        self.toast = Toast(self)


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
        GhostButton(row_ssid, text="Editar", command=lambda: self._edit_text(self.var_ssid, "SSID"), micro=True).pack(side="left", padx=6)

        tk.Label(right, text="Contraseña:", bg=COL_CARD, fg=COL_TEXT).pack(anchor="w", padx=8, pady=(6,0))
        row_psk = tk.Frame(right, bg=COL_CARD); row_psk.pack(fill="x", padx=8)
        self.var_psk = tk.StringVar()
        ent_psk = tk.Entry(row_psk, textvariable=self.var_psk, show="*", bg=COL_CARD_HOVER, fg=COL_TEXT, relief="flat")
        ent_psk.pack(side="left", expand=True, fill="x")
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
