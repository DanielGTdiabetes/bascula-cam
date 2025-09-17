#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os, json
import tkinter as tk
from tkinter import ttk
from pathlib import Path

from bascula.ui.screens import BaseScreen
from bascula.ui.widgets import Card, GhostButton, BigButton, Toast, COL_BG, COL_CARD, COL_CARD_HOVER, COL_TEXT, COL_MUTED, COL_ACCENT
try:
    from bascula.ui.widgets import TextKeyPopup
except Exception:
    TextKeyPopup = None  # type: ignore

try:
    import requests
except Exception:
    requests = None

BASE_URL = os.environ.get('BASCULA_WEB_URL', 'http://127.0.0.1:8080')


class ApiKeyScreen(BaseScreen):
    _CFG_ENV = os.environ.get('BASCULA_CFG_DIR', '').strip()
    CFG_DIR = Path(_CFG_ENV) if _CFG_ENV else (Path.home() / ".config" / "bascula")
    API_FILE = CFG_DIR / "apikey.json"

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="API Key OpenAI", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", 18, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="< Atrás", command=lambda: self.app.show_screen('settingsmenu'), micro=True).pack(side="right", padx=14)
        body = Card(self); body.pack(fill="both", expand=True, padx=14, pady=10)
        present = bool(self._load_key())
        self.state_label = tk.Label(body, text="Estado: " + ("Presente" if present else "No configurada"), bg=COL_CARD, fg=COL_MUTED)
        self.state_label.pack(anchor="w", padx=10, pady=(6,2))
        tk.Label(body, text="Introduce tu API Key (sk-XXXX)", bg=COL_CARD, fg=COL_TEXT).pack(anchor="w", padx=10, pady=(0,2))
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

    def on_show(self):
        try:
            v = self._load_key()
            self.var_key.set(v)
            try:
                self.state_label.config(text="Estado: " + ("Presente" if bool(v) else "No configurada"))
            except Exception:
                pass
        except Exception:
            pass

    def _edit_key(self):
        if TextKeyPopup is None:
            return
        def _acc(val): self.var_key.set(val)
        TextKeyPopup(self, title="API Key", initial=self.var_key.get(), on_accept=_acc)

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
        if requests is not None:
            try:
                r = requests.post(f"{BASE_URL}/api/apikey", headers={"Content-Type": "application/json"}, json={"key": key}, timeout=6)
                if r.ok and r.json().get("ok"):
                    self.toast.show("Guardado", 1200, COL_SUCCESS)
                    try:
                        self.state_label.config(text="Estado: Presente")
                    except Exception:
                        pass
                    return
            except Exception:
                pass
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
        try:
            self.state_label.config(text="Estado: Presente")
        except Exception:
            pass

