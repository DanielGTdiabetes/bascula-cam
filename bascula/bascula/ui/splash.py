# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk
import itertools

class SplashScreen(tk.Toplevel):
    def __init__(self, master, title="Báscula Digital Pro", subtitle="Iniciando...", *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        # Ventana sin bordes, por encima de todo
        self.overrideredirect(True)
        self.configure(bg="#0a0e1a")
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass

        # Centrar en pantalla
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = 480, 260
        x, y = (sw - w) // 2, (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        container = tk.Frame(self, bg="#0a0e1a")
        container.pack(expand=True, fill="both", padx=24, pady=24)

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
            self.pb.start(25)
        except Exception:
            pass

        self._dots_lbl = tk.Label(container, text="", font=("Helvetica", 12),
                                  fg="#9fb3c8", bg="#0a0e1a")
        self._dots_lbl.pack()
        self._dots_cycle = itertools.cycle(["", ".", "..", "..."])
        self._dots_after = None
        self._animate()

        # Forzar visibilidad
        self.update_idletasks()
        self.deiconify()
        try:
            self.lift()
            self.focus_force()
        except Exception:
            pass

    def _animate(self):
        self._dots_lbl.config(text=next(self._dots_cycle))
        self._dots_after = self.after(300, self._animate)

    def set_status(self, text: str):
        self.subtitle_var.set(text)
        self.update_idletasks()

    def close(self):
        try:
            if self._dots_after:
                self.after_cancel(self._dots_after)
        except Exception:
            pass
        try:
            self.pb.stop()
        except Exception:
            pass
        self.destroy()
