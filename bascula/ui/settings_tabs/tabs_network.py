# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tkinter as tk

from bascula.ui.widgets import COL_CARD, COL_TEXT, COL_ACCENT
from bascula.ui.settings_tabs.utils import create_scrollable_tab


WEB_PORT = os.environ.get('BASCULA_WEB_PORT', os.environ.get('FLASK_RUN_PORT', '8080')).strip() or '8080'


def add_tab(screen, notebook):
    inner = create_scrollable_tab(notebook, "Red")

    ip_var = tk.StringVar(value=screen.get_current_ip() or 'No conectada')
    tk.Label(inner, textvariable=ip_var, bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 14)).pack(anchor='w')

    def current_url():
        ip = ip_var.get()
        base = ip if ip and ip != 'No conectada' else 'localhost'
        return f"http://{base}:{WEB_PORT}"

    def url_text():
        return f"Mini-web en {current_url()}"

    url_var = tk.StringVar(value=url_text())
    tk.Label(inner, textvariable=url_var, bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 12)).pack(anchor='w', pady=(6, 0))

    # PIN mini-web y opciones de regeneración
    pin_row = tk.Frame(inner, bg=COL_CARD); pin_row.pack(fill='x', pady=(8,0))
    pin_var = tk.StringVar(value=screen.get_miniweb_pin_text())
    tk.Label(
        pin_row,
        textvariable=pin_var,
        bg=COL_CARD,
        fg=COL_TEXT,
        font=("DejaVu Sans", 13, "bold"),
    ).pack(side='left', padx=6)

    def update_pin_label() -> None:
        pin_var.set(screen.get_miniweb_pin_text())

    def on_regenerate_pin() -> None:
        if screen.regenerate_miniweb_pin():
            update_pin_label()

    def on_refresh():
        ip = screen.get_current_ip() or 'No conectada'
        ip_var.set(ip)
        url_var.set(url_text())
        update_pin_label()

    tk.Button(inner, text='Refrescar', command=on_refresh, bg=COL_ACCENT, fg='white', bd=0, relief='flat', cursor='hand2').pack(anchor='w', pady=6)

    tk.Button(
        pin_row,
        text='Regenerar PIN',
        command=on_regenerate_pin,
        bg=COL_ACCENT,
        fg='white',
        bd=0,
        relief='flat',
        cursor='hand2',
    ).pack(side='left', padx=(12, 0))

    # QR del panel web (si hay dependencias)
    qr_frame = tk.Frame(inner, bg=COL_CARD)
    qr_frame.pack(anchor='w', pady=(8,0))
    qr_label = tk.Label(qr_frame, text='', bg=COL_CARD)
    qr_label.pack()

    def show_qr():
        try:
            import qrcode
            from PIL import Image, ImageTk
        except Exception:
            try:
                screen.toast.show('Instala qrcode y Pillow para mostrar QR', 1600)
            except Exception:
                pass
            return
        # generar a partir de la URL actual
        u = current_url()
        try:
            img = qrcode.make(u)
            img = img.resize((160, 160))
            ph = ImageTk.PhotoImage(img)
            qr_label.configure(image=ph)
            qr_label.image = ph
        except Exception:
            pass

    tk.Button(inner, text='Mostrar QR', command=show_qr, bg=COL_ACCENT, fg='white', bd=0, relief='flat', cursor='hand2').pack(anchor='w', pady=6)

    fr = tk.Frame(inner, bg=COL_CARD)
    fr.pack(pady=12)
    tk.Button(fr, text="Configurar Wi‑Fi", command=lambda: screen.app.show_screen('wifi'), bg="#3b82f6", fg='white', bd=0, relief='flat', cursor='hand2').pack(side='left', padx=6)
    tk.Button(fr, text="API Key", command=lambda: screen.app.show_screen('apikey'), bg="#6b7280", fg='white', bd=0, relief='flat', cursor='hand2').pack(side='left', padx=6)
