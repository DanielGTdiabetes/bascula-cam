#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from bascula.ui.screens import BaseScreen
from bascula.ui.widgets import Card, BigButton, GhostButton, Toast, COL_BG, COL_CARD, COL_CARD_HOVER, COL_TEXT, COL_MUTED


class DiabetesSettingsScreen(BaseScreen):
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app)
        header = tk.Frame(self, bg=COL_BG); header.pack(side="top", fill="x", pady=10)
        tk.Label(header, text="Ajustes de Diabetes", bg=COL_BG, fg=COL_TEXT, font=("DejaVu Sans", 18, "bold")).pack(side="left", padx=14)
        GhostButton(header, text="< Atrás", command=lambda: self.app.show_screen('settingsmenu'), micro=True).pack(side="right", padx=14)
        body = Card(self); body.pack(fill="both", expand=True, padx=14, pady=10)

        # Modo diabético + aviso
        top = tk.Frame(body, bg=COL_CARD); top.pack(fill="x", padx=10, pady=(6,6))
        self.var_dm = tk.BooleanVar(value=bool(self.app.get_cfg().get('diabetic_mode', False)))
        ttk.Checkbutton(top, text="Modo diabético (experimental)", variable=self.var_dm, command=self._toggle_dm).pack(side="left")
        tk.Label(top, text="No es consejo médico.", bg=COL_CARD, fg=COL_MUTED).pack(side="left", padx=10)

        nsrow = tk.Frame(body, bg=COL_CARD); nsrow.pack(fill="x", padx=10, pady=(0,6))
        GhostButton(nsrow, text="Configurar Nightscout", command=lambda: self.app.show_screen('nightscout'), micro=True).pack(side="left", padx=4)

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
        except Exception:
            pass

    def _apply(self):
        try:
            cfg = self.app.get_cfg()
            cfg['target_bg_mgdl'] = max(60, int(float(self.var_tbg.get() or 110)))
            cfg['isf_mgdl_per_u'] = max(5, int(float(self.var_isf.get() or 50)))
            cfg['carb_ratio_g_per_u'] = max(2, int(float(self.var_carb.get() or 10)))
            cfg['dia_hours'] = max(2, int(float(self.var_dia.get() or 4)))
            self.app.save_cfg()
            self.toast.show("Parámetros guardados", 1000, COL_SUCCESS)
        except Exception as e:
            self.toast.show(f"Error: {e}", 1300, COL_DANGER)

