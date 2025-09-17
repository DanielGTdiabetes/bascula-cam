#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import tkinter as tk
import itertools
from bascula.ui.widgets import COL_BG, COL_CARD, COL_TEXT, COL_ACCENT, COL_BORDER, FS_TITLE, FS_TEXT


class SplashScreen(tk.Toplevel):
    """Splash con estética retro (CRT) y barra KITT.

    - Usa la paleta de colores actual (bascula.ui.widgets).
    - Animaciones no bloqueantes con after().
    """

    def __init__(self, master, title="Báscula Digital Pro", subtitle="Iniciando…", *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        # Ventana sin bordes, por encima de todo
        self.overrideredirect(True)
        self.configure(bg=COL_BG)
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass

        # Centrar en pantalla
        sw = self.winfo_screenwidth(); sh = self.winfo_screenheight()
        w, h = 520, 280
        x, y = (sw - w) // 2, (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        # Marco exterior tipo CRT
        outer = tk.Frame(self, bg=COL_BG, highlightbackground=COL_BORDER, highlightthickness=2)
        outer.pack(expand=True, fill="both", padx=10, pady=10)

        container = tk.Frame(outer, bg=COL_CARD, highlightbackground=COL_BORDER, highlightthickness=1)
        container.pack(expand=True, fill="both", padx=14, pady=14)

        title_lbl = tk.Label(container, text=title, font=("DejaVu Sans Mono", max(16, FS_TITLE), "bold"),
                             fg=COL_ACCENT, bg=COL_CARD)
        title_lbl.pack(pady=(8, 4), anchor="w")

        # ASCII mini‑logo alusivo a diabetes (drop + texto)
        ascii_logo = (
            "    __  _     _           _        \n"
            "   / _|| |__ (_)___ _ _   | |__ ___ \n"
            "  | |_ | '_ \\| / -_) ' \\  | / /(_-<\n"
            "  |  _||_.__// \\___|_||_| |_|_\\/__/\n"
            "             |__/   diabetes        "
        )
        self.logo_lbl = tk.Label(container, text=ascii_logo,
                                  font=("DejaVu Sans Mono", max(10, FS_TEXT-3)),
                                  fg=COL_ACCENT, bg=COL_CARD, justify="left")
        self.logo_lbl.pack(pady=(0, 6), anchor="w")

        self.subtitle_var = tk.StringVar(value=subtitle)
        subtitle_lbl = tk.Label(container, textvariable=self.subtitle_var,
                                font=("DejaVu Sans Mono", max(12, FS_TEXT)),
                                fg=COL_TEXT, bg=COL_CARD)
        subtitle_lbl.pack(pady=(0, 12), anchor="w")

        # Canvas con scanlines y barra KITT
        self.canvas = tk.Canvas(container, bg=COL_CARD, highlightthickness=0, bd=0)
        self.canvas.pack(expand=True, fill="both")
        self._kitt_pos = 0
        self._anim_after = None

        self._dots_lbl = tk.Label(container, text="", font=("DejaVu Sans Mono", max(12, FS_TEXT)),
                                  fg=COL_TEXT, bg=COL_CARD)
        self._dots_lbl.pack(anchor="e")
        self._dots_cycle = itertools.cycle(["", ".", "..", "…"])

        # Forzar visibilidad
        self.update_idletasks(); self.deiconify()
        try:
            self.lift(); self.focus_force()
        except Exception:
            pass

        # Arrancar animación
        self._tick()

    def _draw(self):
        w = self.canvas.winfo_width() or 400
        h = self.canvas.winfo_height() or 120
        c = self.canvas
        c.delete("all")
        # Líneas horizontales (scanlines suaves)
        try:
            for y in range(0, h, 4):
                c.create_line(0, y, w, y, fill=COL_BORDER)
        except Exception:
            pass
        # Barra KITT
        bar_h = 8
        y0 = h - bar_h - 6
        try:
            c.create_rectangle(10, y0, w-10, y0+bar_h, outline=COL_BORDER)
            pos = (self._kitt_pos % max(1, (w-40)))
            for trail in range(0, 26, 6):
                x1 = 14 + pos + trail
                c.create_rectangle(x1, y0+2, x1+10, y0+bar_h-2, outline=COL_ACCENT)
        except Exception:
            pass

    def _tick(self):
        # puntos
        try:
            self._dots_lbl.config(text=next(self._dots_cycle))
        except Exception:
            pass
        # animación
        self._kitt_pos += 10
        self._draw()
        try:
            self._anim_after = self.after(60, self._tick)
        except Exception:
            pass

    def set_status(self, text: str):
        self.subtitle_var.set(text)
        try:
            self.update_idletasks()
        except Exception:
            pass

    def close(self):
        try:
            if self._anim_after:
                self.after_cancel(self._anim_after)
        except Exception:
             pass
        self.destroy()
