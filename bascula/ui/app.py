# -*- coding: utf-8 -*-
"""
bascula/ui/app.py
-----------------
App Tkinter estable (pantalla completa) con panel de cámara.
Incluye compatibilidad con antiguos entrypoints (BasculaAppTk, run()).
"""
import tkinter as tk

from bascula.services.camera import CameraService
from bascula.ui.screens import HomeScreen

APP_TITLE = "Báscula Digital Pro"


class BasculaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.configure(bg="#101214")

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        try:
            self.overrideredirect(True)
        except Exception:
            pass
        self.geometry(f"{sw}x{sh}+0+0")
        self.update_idletasks()
        try:
            self.configure(cursor="none")
        except Exception:
            pass

        self.bind("<Escape>", lambda e: self.safe_exit())
        self.bind("<Control-q>", lambda e: self.safe_exit())
        self.bind("<F11>", lambda e: self.toggle_fullscreen())

        self.camera = CameraService(width=800, height=480, fps=10)

        self.container = tk.Frame(self, bg="#101214")
        self.container.pack(fill="both", expand=True)

        self.home = HomeScreen(self.container, self)
        self.home.pack(fill="both", expand=True)

        if not self.camera.is_available():
            msg = f"⚠️ Cámara no disponible ({self.camera.reason_unavailable()}).\n" \
                  "Comprueba: cable, libcamera, permisos y que no haya otro proceso usándola."
            self.home.set_camera_status(False, msg)
        else:
            self.after(300, self._start_camera_safe)

    def _start_camera_safe(self):
        try:
            self.home.attach_camera_preview(self.camera)
            self.camera.start()
            self.home.set_camera_status(True, f"Backend: {self.camera.backend_name()}")
        except Exception as e:
            self.home.set_camera_status(False, f"No se pudo iniciar la cámara: {e!s}")

    def toggle_fullscreen(self):
        try:
            val = not bool(self.attributes("-fullscreen"))
            self.attributes("-fullscreen", val)
        except Exception:
            pass

    def safe_exit(self):
        try:
            if hasattr(self, "camera") and self.camera:
                self.camera.stop()
        except Exception:
            pass
        self.destroy()

    def run(self):
        self.mainloop()


def run_app():
    app = BasculaApp()
    app.mainloop()


BasculaAppTk = BasculaApp
def run():
    return run_app()
