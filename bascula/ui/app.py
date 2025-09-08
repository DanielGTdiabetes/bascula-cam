#!/usr/bin/env python3
import os
import sys
import time
import threading
import logging
from pathlib import Path
import tkinter as tk

# --- CORRECCIÓN: Importaciones en el ámbito del módulo ---
from bascula import utils
from bascula.ui.screens import HomeScreen
from bascula.services.scale import HX711Service
from bascula.services.camera import CameraService
from bascula.services.storage import StorageService
from bascula.services.logging import setup_logging

log = logging.getLogger(__name__)

class BasculaAppTk:
    def __init__(self, root=None):
        self.root = root or tk.Tk()
        self.root.withdraw()

        self.scale = None
        self.camera = None
        self.storage = None
        self._cfg = utils.load_config()

        self._init_services_bg()

    def get_cfg(self) -> dict:
        return self._cfg

    def save_cfg(self) -> None:
        try:
            utils.save_config(self._cfg)
        except Exception as ex:
            log.warning("No se pudo guardar la configuración: %s", ex)

    def _init_services_bg(self):
        t = threading.Thread(target=self._on_services_ready, daemon=True)
        t.start()

    def _on_services_ready(self):
        try:
            log.info("Iniciando servicios...")
            self.scale = HX711Service()
            self.camera = CameraService()
            self.storage = StorageService()

            if not self.scale:
                raise RuntimeError("El servicio de báscula (scale) no pudo iniciarse.")

            log.info("Servicios listos; construyendo UI...")
            self._build_ui()
            log.info("UI construida con éxito.")

        except Exception as e:
            log.error("Error fatal al iniciar servicios o construir la UI: %s", e, exc_info=True)
            return

        try:
            self.root.deiconify()
            self.root.focus_force()
            log.info("Ventana principal mostrada.")
        except Exception as e:
            log.warning("No se pudo mostrar la ventana principal: %s", e)

        def _heartbeat():
            p = Path("/run/bascula.alive")
            while True:
                try:
                    p.touch()
                except Exception as ex:
                    log.warning("Heartbeat failed: %s", ex)
                time.sleep(5)
        threading.Thread(target=_heartbeat, daemon=True).start()

        try:
            (Path.home() / ".bascula_boot_ok").touch()
        except Exception:
            pass

    def _build_ui(self):
        self.main = HomeScreen(self.root, self)
        self.main.pack(fill="both", expand=True)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    setup_logging()
    app = BasculaAppTk()
    app.run()
