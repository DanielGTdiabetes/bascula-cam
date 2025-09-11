# -*- coding: utf-8 -*-
from __future__ import annotations

import tkinter as tk

from bascula.ui.widgets import COL_CARD, COL_TEXT, COL_ACCENT


def add_tab(screen, notebook):
    tab = tk.Frame(notebook, bg=COL_CARD)
    notebook.add(tab, text="Red")

    inner = tk.Frame(tab, bg=COL_CARD)
    inner.pack(fill="both", expand=True, padx=16, pady=12)

    ip_var = tk.StringVar(value=screen.get_current_ip() or 'No conectada')
    tk.Label(inner, textvariable=ip_var, bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 14)).pack(anchor='w')

    def url_text():
        ip = ip_var.get()
        base = ip if ip and ip != 'No conectada' else 'localhost'
        return f"Panel Web: http://{base}:8080"

    url_var = tk.StringVar(value=url_text())
    tk.Label(inner, textvariable=url_var, bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 12)).pack(anchor='w', pady=(6, 0))

    # PIN de emparejamiento (si existe)
    pin_row = tk.Frame(inner, bg=COL_CARD); pin_row.pack(fill='x', pady=(8,0))
    tk.Label(pin_row, text='PIN:', bg=COL_CARD, fg=COL_TEXT).pack(side='left')
    pin_var = tk.StringVar(value=screen.read_pin())
    tk.Label(pin_row, textvariable=pin_var, bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans Mono", 12)).pack(side='left', padx=6)

    def on_refresh():
        ip = screen.get_current_ip() or 'No conectada'
        ip_var.set(ip)
        url_var.set(url_text())
        pin_var.set(screen.read_pin())

    tk.Button(inner, text='Refrescar', command=on_refresh, bg=COL_ACCENT, fg='white', bd=0, relief='flat', cursor='hand2').pack(anchor='w', pady=6)

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
        u = url_text().replace('Panel Web: ', '')
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
