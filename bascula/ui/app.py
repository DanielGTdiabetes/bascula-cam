# -*- coding: utf-8 -*-
"""
bascula/ui/app.py
-----------------
App Tkinter estable (pantalla completa 1024x600) con panel de cámara.

Objetivo de este commit:
- Arreglar el flujo de cámara "no disponible" y su integración en la UI.
- Evitar dependencias rotas mientras recuperamos funcionalidad.
- Respetar arranque a pantalla completa sin bordes y sin parpadeos.
- Teclas útiles: F11 (toggle fullscreen), Ctrl+Q o ESC (salir).
"""
import os
import tkinter as tk
from tkinter import messagebox

try:
    from bascula.ui.screens import HomeScreen  # UI principal
except Exception:
    # Fallback relativo si el import absoluto falla
    from .screens import HomeScreen  # type: ignore

try:
    # Servicio de cámara robusto
    from bascula.services.camera import CameraService
except Exception:
    from ..services.camera import CameraService  # type: ignore

APP_TITLE = "Báscula Digital Pro"

class BasculaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.configure(bg="#101214")
        self._fullscreen = True
        self._borderless = True

        # Pantalla completa sin bordes (kiosk)
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        if self._borderless:
            try:
                self.overrideredirect(True)
            except Exception:
                pass
        self.geometry(f"{sw}x{sh}+0+0")
        self.update_idletasks()

        # Oculta cursor
        try:
            self.configure(cursor="none")
        except Exception:
            pass

        # Accesos rápidos
        self.bind("<Escape>", lambda e: self.safe_exit())
        self.bind("<Control-q>", lambda e: self.safe_exit())
        self.bind("<F11>", lambda e: self.toggle_fullscreen())

        # Servicios
        self.camera = CameraService(width=800, height=480, fps=10)

        # Contenedor y pantalla
        self.container = tk.Frame(self, bg="#101214")
        self.container.pack(fill="both", expand=True)

        self.home = HomeScreen(self.container, self)
        self.home.pack(fill="both", expand=True)

        # Intento de inicialización de cámara
        if not self.camera.is_available():
            msg = f"⚠️ Cámara no disponible ({self.camera.reason_unavailable()}).\n" \
                  "Comprueba: cable, libcamera, permisos y que no haya otro proceso usándola."
            self.home.set_camera_status(False, msg)
        else:
            self.after(300, self._start_camera_safe)

    # ---------- Cámara ----------
    def _start_camera_safe(self):
        try:
            self.home.attach_camera_preview(self.camera)
            self.camera.start()
            self.home.set_camera_status(True, f"Backend: {self.camera.backend_name()}")
        except Exception as e:
            self.home.set_camera_status(False, f"No se pudo iniciar la cámara: {e!s}")

    # ---------- Utilidades ----------
    def toggle_fullscreen(self):
        self._fullscreen = not self._fullscreen
        try:
            self.attributes("-fullscreen", self._fullscreen)
            if not self._fullscreen:
                sw = self.winfo_screenwidth()
                sh = self.winfo_screenheight()
                self.geometry(f"{sw}x{sh}+0+0")
        except Exception:
            pass

    def safe_exit(self):
        try:
            if hasattr(self, "camera") and self.camera:
                self.camera.stop()
        except Exception:
            pass
        self.destroy()

def run_app():
    app = BasculaApp()
    app.mainloop()

if __name__ == "__main__":
    run_app()
