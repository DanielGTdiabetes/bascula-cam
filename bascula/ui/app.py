#!/usr/bin/env python3
import os
import sys
import time
import threading
import logging
from pathlib import Path
import tkinter as tk

# Importa tus módulos reales aquí (ajusta si difieren en tu repo)
try:
    from bascula.ui.screens import HomeScreen
    from bascula.services.scale import HX711Service
    from bascula.services.camera import CameraService
    from bascula.services.storage import StorageService
    from bascula.services.logging import setup_logging
except Exception:
    # Fallbacks opcionales si algunos módulos no existen en esta fase
    def setup_logging(): logging.basicConfig(level=logging.INFO)
    class HomeScreen(tk.Frame):
        def __init__(self, root, app): super().__init__(root)
    class HX711Service: pass
    class CameraService: pass
    class StorageService: pass

log = logging.getLogger(__name__)

class BasculaAppTk:
    def __init__(self, root=None):
        self.root = root or tk.Tk()
        self.root.withdraw()  # ocultar ventana hasta que todo esté listo

        self.scale = None
        self.camera = None
        self.storage = None
        # Cargar configuración persistente
        from utils import load_config, save_config
        self._cfg = load_config()
        self._save_config_fn = save_config

        # Iniciar servicios en segundo plano
        self._init_services_bg()

    def _init_services_bg(self):
        t = threading.Thread(target=self._on_services_ready, daemon=True)
        t.start()

    def _on_services_ready(self):
        try:
            log.info("Servicios listos; construyendo UI...")
            self.scale = HX711Service()
            self.camera = CameraService()
            self.storage = StorageService()
            self._build_ui()
            log.info("UI construida con éxito.")
        except Exception as e:
            log.error("Error al construir la UI: %s", e, exc_info=True)
            return

        try:
            self.root.deiconify()
            self.root.focus_force()
            log.info("Ventana principal mostrada.")
        except Exception as e:
            log.warning("No se pudo mostrar la ventana principal: %s", e)

        # ✅ Heartbeat para el servicio de health-check
        def _heartbeat():
            p = Path("/run/bascula.alive")
            while True:
                try:
                    p.touch()  # actualiza el mtime (latido)
                except Exception as ex:
                    log.warning("Heartbeat failed: %s", ex)
                time.sleep(5)

        threading.Thread(target=_heartbeat, daemon=True).start()

        # Flag de arranque correcto (si lo usas con safe_run)
        try:
            (Path.home() / ".bascula_boot_ok").touch()
        except Exception:
            pass

    def _build_ui(self):
        self.main = HomeScreen(self.root, self)
        self.main.pack(fill="both", expand=True)

    def run(self):
        self.root.mainloop()


    # ---- Configuración ----
    def get_cfg(self) -> dict:
        """
        Devuelve el diccionario de configuración actual (mutable).
        Modifica los valores a través de este objeto y llama a save_cfg() para persistirlos.
        """
        return self._cfg

    def save_cfg(self) -> None:
        """
        Guarda la configuración actual en disco de forma segura.
        """
        try:
            self._save_config_fn(self._cfg)
        except Exception as ex:
            log.warning("No se pudo guardar la configuración: %s", ex)

if __name__ == "__main__":
    setup_logging()
    app = BasculaAppTk()
    app.run()
