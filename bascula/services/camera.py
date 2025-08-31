# -*- coding: utf-8 -*-
"""
Servicio de cámara para Raspberry Pi (Picamera2).
- Captura JPEG a fichero.
- Inicialización y cierre limpios.
- Sin vista previa obligatoria (tu UI no se rompe aunque no haya preview).
"""
from __future__ import annotations
import os
import time
import tempfile
from typing import Optional

try:
    from picamera2 import Picamera2
    from picamera2.encoders import JpegEncoder
    from picamera2.outputs import FileOutput
    PICAMERA2_OK = True
except Exception:
    Picamera2 = None  # type: ignore
    JpegEncoder = None  # type: ignore
    FileOutput = None  # type: ignore
    PICAMERA2_OK = False


class CameraError(RuntimeError):
    pass


class CameraService:
    def __init__(self) -> None:
        self._cam: Optional[Picamera2] = None
        self._opened: bool = False

    def open(self) -> None:
        """Inicializa la cámara si está disponible."""
        if self._opened:
            return
        if not PICAMERA2_OK:
            raise CameraError("Picamera2 no está disponible (instala python3-picamera2).")
        try:
            self._cam = Picamera2()
            # Configuración sencilla: una vista de preview + still (rápida)
            preview_cfg = self._cam.create_preview_configuration(main={"size": (800, 480)})
            self._cam.configure(preview_cfg)
            self._cam.start()
            self._opened = True
        except Exception as e:
            self._cam = None
            raise CameraError(f"No se pudo abrir la cámara: {e}")

    def is_open(self) -> bool:
        return self._opened and self._cam is not None

    def capture_jpeg(self, path: Optional[str] = None) -> str:
        """
        Captura una imagen JPEG y la guarda en 'path' (o en /tmp si no se indica).
        Devuelve la ruta del archivo.
        """
        if not self.is_open():
            self.open()

        assert self._cam is not None

        if path is None:
            fd, tmp = tempfile.mkstemp(prefix="bascula_", suffix=".jpg")
            os.close(fd)
            path = tmp

        # Reconfigurar a still para máxima calidad del disparo
        try:
            still_cfg = self._cam.create_still_configuration(main={"size": (2304, 1296)})
            self._cam.configure(still_cfg)
            # Encoder JPEG a fichero
            enc = JpegEncoder(q=90)
            self._cam.start()
            time.sleep(0.1)  # pequeño delay para estabilizar
            self._cam.start_encoder(enc, FileOutput(path))
            self._cam.capture_request().release()
            self._cam.stop_encoder()
            # Volver a preview lightweight (por si vuelves a capturar)
            preview_cfg = self._cam.create_preview_configuration(main={"size": (800, 480)})
            self._cam.configure(preview_cfg)
            self._cam.start()
        except Exception as e:
            raise CameraError(f"Fallo al capturar: {e}")

        return path

    def close(self) -> None:
        if self._cam is not None:
            try:
                self._cam.stop()
            except Exception:
                pass
            try:
                self._cam.close()
            except Exception:
                pass
        self._cam = None
        self._opened = False
