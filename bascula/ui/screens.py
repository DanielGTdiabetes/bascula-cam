# -*- coding: utf-8 -*-
"""
bascula/ui/screens.py
---------------------
Pantalla principal minimalista con:
  - Panel de peso (placeholder)
  - Panel de cámara (usa CameraService.attach_preview)

Nota: Esta versión evita dependencias a widgets propios para recuperar
la funcionalidad básica y estabilizar el sistema.
"""
import tkinter as tk

class HomeScreen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg="#101214")
        self.app = app

        # Layout columnas
        self.grid_columnconfigure(0, weight=1, uniform="cols")
        self.grid_columnconfigure(1, weight=1, uniform="cols")
        self.grid_rowconfigure(0, weight=1)

        # Panel de peso
        left = tk.Frame(self, bg="#14171a", bd=0, highlightthickness=1, highlightbackground="#2b2f36")
        left.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        tk.Label(left, text="Peso actual", fg="#e6edf3", bg="#14171a",
                 font=("DejaVu Sans", 20, "bold")).pack(anchor="w", padx=16, pady=(16,8))
        self.lbl_weight = tk.Label(left, text="— g", fg="#e6edf3", bg="#14171a",
                                   font=("DejaVu Sans Mono", 56, "bold"))
        self.lbl_weight.pack(expand=True)

        # Panel de cámara
        right = tk.Frame(self, bg="#14171a", bd=0, highlightthickness=1, highlightbackground="#2b2f36")
        right.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)

        header = tk.Frame(right, bg="#14171a")
        header.pack(fill="x")
        tk.Label(header, text="Cámara", fg="#e6edf3", bg="#14171a",
                 font=("DejaVu Sans", 20, "bold")).pack(side="left", padx=16, pady=(16,8))
        self.lbl_cam_status = tk.Label(header, text="", fg="#9da7b3", bg="#14171a",
                                       font=("DejaVu Sans", 12))
        self.lbl_cam_status.pack(side="right", padx=16, pady=(16,8))

        self.camera_container = tk.Frame(right, bg="#000000")
        self.camera_container.pack(fill="both", expand=True, padx=12, pady=(0,12))

        # Botonera inferior
        bottom = tk.Frame(self, bg="#101214")
        bottom.grid(row=1, column=0, columnspan=2, sticky="ew")
        bottom.grid_columnconfigure(0, weight=1)
        tk.Button(bottom, text="Salir (ESC)", command=app.safe_exit).grid(row=0, column=0, sticky="e", padx=12, pady=8)

        # Demo: actualiza peso a 1 g de resolución
        self._demo_weight = 0
        self.after(1000, self._tick_fake_weight)

    def _tick_fake_weight(self):
        # Placeholder de peso (quitar cuando conectes HX711)
        self._demo_weight = (self._demo_weight + 1) % 5000
        self.lbl_weight.configure(text=f"{self._demo_weight:d} g")
        self.after(250, self._tick_fake_weight)

    def attach_camera_preview(self, camera):
        lbl = camera.attach_preview(self.camera_container)
        try:
            lbl.configure(bg="#000000", bd=0, highlightthickness=0)
        except Exception:
            pass

    def set_camera_status(self, ok:bool, msg:str):
        color = "#28a745" if ok else "#ff6666"
        self.lbl_cam_status.configure(text=msg, fg=color)
