#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import subprocess
import tkinter as tk
from tkinter import ttk
from pathlib import Path

from bascula.ui.screens import BaseScreen
from bascula.ui.widgets import (
    Card, BigButton, GhostButton, Toast, bind_touch_scroll,
    COL_BG, COL_CARD, COL_CARD_HOVER, COL_TEXT, COL_MUTED
)
try:
    from bascula.ui.widgets import TextKeyPopup
except Exception:
    TextKeyPopup = None  # type: ignore

try:
    import requests  # optional
except Exception:
    requests = None

SHOW_SCROLLBAR = True
BASE_URL = os.environ.get('BASCULA_WEB_URL', 'http://127.0.0.1:8080')


class WifiScreen(BaseScreen):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="Conexión Wi‑Fi", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", 18, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="< Atrás", command=lambda: self.app.show_screen('settingsmenu'), micro=True).pack(side="right", padx=14)

        body = Card(self); body.pack(fill="both", expand=True, padx=14, pady=10)

        top = tk.Frame(body, bg=COL_CARD); top.pack(fill="x", pady=(6,8))
        GhostButton(top, text="Actualizar redes", command=self._scan, micro=True).pack(side="left", padx=6)
        self.lbl_status = tk.Label(top, text="", bg=COL_CARD, fg=COL_MUTED)
        self.lbl_status.pack(side="left", padx=10)

        main = tk.Frame(body, bg=COL_CARD); main.pack(fill="both", expand=True)
        main.grid_rowconfigure(0, weight=1); main.grid_columnconfigure(0, weight=3); main.grid_columnconfigure(1, weight=2)

        # Lista redes
        left = tk.Frame(main, bg=COL_CARD); left.grid(row=0, column=0, sticky="nsew", padx=(6,3), pady=6)
        style = ttk.Style(self)
        try: style.theme_use('clam')
        except Exception: pass
        style.configure('Dark.Treeview', background=COL_CARD_HOVER, foreground=COL_TEXT, fieldbackground=COL_CARD_HOVER, rowheight=28)
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
        self.tv.bind("<<TreeviewSelect>>", self._on_select_ssid)

        # Panel conexión
        right = tk.Frame(main, bg=COL_CARD); right.grid(row=0, column=1, sticky="nsew", padx=(3,6), pady=6)
        tk.Label(right, text="SSID seleccionado:", bg=COL_CARD, fg=COL_TEXT).pack(anchor="w", padx=8, pady=(4,0))
        self.var_ssid = tk.StringVar()
        row_ssid = tk.Frame(right, bg=COL_CARD); row_ssid.pack(fill="x", padx=8)
        ent_ssid = tk.Entry(row_ssid, textvariable=self.var_ssid, bg=COL_CARD_HOVER, fg=COL_TEXT, relief="flat")
        ent_ssid.pack(side="left", expand=True, fill="x")
        self.ent_ssid = ent_ssid
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
        if TextKeyPopup is None:
            return
        def _acc(val): var.set(val)
        TextKeyPopup(self, title=title, initial=var.get(), on_accept=_acc)

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

    def _on_select_ssid(self, _evt=None):
        try:
            sel = self.tv.selection()
            if not sel:
                return
            vals = self.tv.item(sel[0], "values")
            ssid = vals[0]
            if ssid:
                self.var_ssid.set(ssid)
                try:
                    self.var_psk.set("")
                except Exception:
                    pass
                try:
                    if hasattr(self, 'ent_ssid'):
                        self.ent_ssid.focus_set()
                except Exception:
                    pass
        except Exception:
            pass

    def _connect(self):
        ssid = self.var_ssid.get().strip(); psk = self.var_psk.get().strip()
        if not ssid or not psk:
            self.toast.show("Introduce SSID y clave", 1400, COL_WARN); return
        self.lbl_status.config(text=f"Conectando a {ssid}..."); self.update_idletasks()
        # HTTP
        if requests is not None:
            try:
                r = requests.post(f"{BASE_URL}/api/wifi", headers={"Content-Type": "application/json"}, json={"ssid": ssid, "psk": psk}, timeout=10)
                if r.ok and r.json().get("ok"):
                    self.toast.show("Conectado / guardado", 1400, COL_SUCCESS); self._scan(); return
            except Exception:
                pass
        # nmcli
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

