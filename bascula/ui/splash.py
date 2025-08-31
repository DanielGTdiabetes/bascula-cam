# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk
import itertools

class SplashScreen(tk.Toplevel):
    """
    Splash minimalista pero vistoso para tapar el arranque:
    - Marca + título
    - Mensaje de estado actualizable
    - Barra de progreso indeterminada
    - Animación de puntos
    """
    def __init__(self, master, title="Báscula Digital Pro", subtitle="Iniciando...", *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.overrideredirect(True)
        self.configure(bg="#0a0e1a")
        self.attributes("-topmost", True)

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = 460, 260
        x, y = (sw - w) // 2, (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        container = tk.Frame(self, bg="#0a0e1a")
        container.pack(expand=True, fill="both", padx=24, pady=24)

        # "Logo" tipográfico
        title_lbl = tk.Label(container, text=title, font=("Helvetica", 20, "bold"),
                             fg="#e6edf7", bg="#0a0e1a")
        title_lbl.pack(pady=(10, 6))

        self.subtitle_var = tk.StringVar(value=subtitle)
        subtitle_lbl = tk.Label(container, textvariable=self.subtitle_var, font=("Helvetica", 12),
                                fg="#9fb3c8", bg="#0a0e1a")
        subtitle_lbl.pack(pady=(0, 18))

        self.pb = ttk.Progressbar(container, mode="indeterminate", length=360)
        self.pb.pack(pady=(0, 12))
        try:
            self.pb.start(20)  # velocidad de animación
        except Exception:
            pass

        self.dots_lbl = tk.Label(container, text="", font=("Helvetica", 12),
                                 fg="#9fb3c8", bg="#0a0e1a")
        self.dots_lbl.pack()

        self._dots_cycle = itertools.cycle(["", ".", "..", "..."])
        self._animate_id = None
        self._animate()

        # Sombra/desvanecido simple (seguro)
        try:
            self.attributes("-alpha", 0.0)
            self.after(10, self._fade_in)
        except Exception:
            pass

    def _fade_in(self, step=0.06):
        try:
            cur = self.attributes("-alpha")
            if cur < 1.0:
                self.attributes("-alpha", min(1.0, cur + step))
                self.after(10, self._fade_in)
        except Exception:
            pass

    def _animate(self):
        self.dots_lbl.config(text=next(self._dots_cycle))
        self._animate_id = self.after(300, self._animate)

    def set_status(self, text: str):
        self.subtitle_var.set(text)

    def close(self):
        # Detén animación/barra antes de cerrar
        try:
            if self._animate_id:
                self.after_cancel(self._animate_id)
        except Exception:
            pass
        try:
            self.pb.stop()
        except Exception:
            pass
        self.destroy()
