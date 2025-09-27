#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os, json
import tkinter as tk
from tkinter import ttk
from pathlib import Path

from bascula.ui.screens import BaseScreen
from bascula.ui.widgets import Card, GhostButton, BigButton, Toast, COL_BG, COL_CARD, COL_CARD_HOVER, COL_TEXT, COL_MUTED
try:
    from bascula.ui.keyboard import TextKeyPopup
except Exception:
    TextKeyPopup = None  # type: ignore

try:
    import requests
except Exception:
    requests = None

_PORT_RAW = os.environ.get('BASCULA_WEB_PORT') or os.environ.get('FLASK_RUN_PORT') or '8080'
_PORT = _PORT_RAW.strip() if isinstance(_PORT_RAW, str) else '8080'
if not _PORT:
    _PORT = '8080'
_HOST_RAW = os.environ.get('BASCULA_WEB_HOST', '127.0.0.1').strip()
_HOST = _HOST_RAW if _HOST_RAW and _HOST_RAW != '0.0.0.0' else '127.0.0.1'
BASE_URL = os.environ.get('BASCULA_WEB_URL', f'http://{_HOST}:{_PORT}')


class NightscoutScreen(BaseScreen):
    _CFG_ENV = os.environ.get('BASCULA_CFG_DIR', '').strip()
    CFG_DIR = Path(_CFG_ENV) if _CFG_ENV else (Path.home() / ".config" / "bascula")
    NS_FILE = CFG_DIR / "nightscout.json"

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="Nightscout", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", 18, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="🏠 Inicio", command=lambda: self.app.show_screen('home'), micro=True).pack(side="right", padx=(0, 14))
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
        GhostButton(row2, text="Teclado", command=lambda: self._edit(self.var_token, "Token"), micro=True).pack(side="left", padx=6)

        ctr = tk.Frame(body, bg=COL_CARD); ctr.pack(fill="x", padx=10, pady=8)
        BigButton(ctr, text="Guardar", command=self._save, micro=True).pack(side="left", padx=4)
        GhostButton(ctr, text="Probar", command=self._test, micro=True).pack(side="left", padx=4)

        self.lbl = tk.Label(body, text="", bg=COL_CARD, fg=COL_MUTED)
        self.lbl.pack(anchor="w", padx=10, pady=4)
        self.toast = Toast(self)

    def on_show(self):
        try:
            data = self._load()
            self.var_url.set(data.get("url", ""))
            self.var_token.set(data.get("token", ""))
        except Exception:
            pass

    def _edit(self, var, title, password=False):
        if TextKeyPopup is None:
            return
        def _acc(val): var.set(val)
        TextKeyPopup(self, title=title, initial=var.get(), on_accept=_acc)

    def _load(self):
        if requests is not None:
            try:
                r = requests.get(f"{BASE_URL}/api/nightscout", timeout=6)
                if r.ok and r.json().get("ok"):
                    return r.json().get("data", {})
            except Exception:
                pass
        try:
            if self.NS_FILE.exists():
                return json.loads(self.NS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save(self):
        data = {"url": self.var_url.get().strip(), "token": self.var_token.get().strip()}
        if requests is not None:
            try:
                r = requests.post(f"{BASE_URL}/api/nightscout", headers={"Content-Type": "application/json"}, json=data, timeout=6)
                if r.ok and r.json().get("ok"):
                    self.toast.show("Guardado", 1200, COL_SUCCESS)
                    try:
                        home = self.app.screens.get('home') if hasattr(self.app, 'screens') else None
                        if home and hasattr(home, '_start_bg_poll'):
                            home._start_bg_poll()
                    except Exception:
                        pass
                    return
            except Exception:
                pass
        try:
            self.CFG_DIR.mkdir(parents=True, exist_ok=True)
            self.NS_FILE.write_text(json.dumps(data), encoding="utf-8")
            try: os.chmod(self.NS_FILE, 0o600)
            except Exception: pass
            self.toast.show("Guardado (local)", 1200, COL_SUCCESS)
            try:
                home = self.app.screens.get('home') if hasattr(self.app, 'screens') else None
                if home and hasattr(home, '_start_bg_poll'):
                    home._start_bg_poll()
            except Exception:
                pass
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

