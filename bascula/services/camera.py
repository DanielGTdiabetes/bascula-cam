# -*- coding: utf-8 -*-
"""
CameraService actualizado para IMX708 Wide en Pi Zero 2W
Optimizado para tu configuración específica
"""
from __future__ import annotations
import os, time
from typing import Optional, Callable

try:
    from picamera2 import Picamera2
    from libcamera import controls as libcam_controls
    PICAM_AVAILABLE = True
except Exception:
    PICAM_AVAILABLE = False


class CameraError(Exception):
    pass


class CameraService:
    """
    Servicio de cámara con Picamera2.
    - Abre/cierra cámara.
    - Proporciona captura JPEG a disco.
    - Opcionalmente puede preparar una preview (no requerida para funcionar).
    """
    def __init__(
        self,
        width: int = 1536,
        height: int = 864,
        preview: bool = False,
        output_dir: str = "/tmp",
        on_debug: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.width = width
        self.height = height
        self.preview = preview
        self.output_dir = output_dir
        self.on_debug = on_debug or (lambda msg: None)
        self.picam: Optional[Picamera2] = None
        self._opened = False

        if not PICAM_AVAILABLE:
            raise CameraError("Picamera2 / libcamera no disponibles")

        if not os.path.isdir(self.output_dir):
            try:
                os.makedirs(self.output_dir, exist_ok=True)
            except Exception:
                pass

    def _log(self, msg: str) -> None:
        try:
            self.on_debug(msg)
        except Exception:
            pass

    def is_open(self) -> bool:
        return self._opened and self.picam is not None

    def open(self) -> None:
        if self.is_open():
            return
        try:
            self._init_camera()
            self._opened = True
        except Exception as e:
            raise CameraError(f"No se pudo abrir la cámara: {e}") from e

    def close(self) -> None:
        try:
            if self.picam:
                try:
                    self.picam.stop()
                except Exception:
                    pass
                try:
                    self.picam.close()
                except Exception:
                    pass
            self.picam = None
            self._opened = False
        except Exception:
            self.picam = None
            self._opened = False

    # ---------------------------------------------------------------------

    def _init_camera(self):
        """Inicialización específica para IMX708 Wide"""
        try:
            self.picam = Picamera2()
            
            # Configuración optimizada para IMX708 Wide
            # Usar modo nativo de 1536x864 para mejor rendimiento
            if self.width <= 1536 and self.height <= 864:
                sensor_mode = {"size": (1536, 864)}
            else:
                sensor_mode = {"size": (2304, 1296)}
            
            # Configuración de preview con formato RGB888 para mejor compatibilidad
            preview_cfg = self.picam.create_preview_configuration(
                main={"size": (self.width, self.height), "format": "RGB888"},
                raw=sensor_mode,
                buffer_count=2
            )
            self.picam.configure(preview_cfg)

            # Parámetros útiles (autoexposición, balance, etc.)
            try:
                self.picam.set_controls({
                    "AwbEnable": True,
                    "AeEnable": True,
                    "NoiseReductionMode": 2,   # Alto
                    "FrameRate": 30,
                })
            except Exception:
                pass

            # Si se quiere preview: arrancar
            if self.preview:
                self.picam.start()
            else:
                # Sin preview: arrancamos/parmos según captura
                pass

        except Exception as e:
            raise CameraError(f"Fallo inicializando Picamera2: {e}") from e

    # ---------------------------------------------------------------------

    def start_preview(self) -> None:
        if not self.is_open():
            self.open()
        try:
            self.picam.start()
        except Exception as e:
            raise CameraError(f"No se pudo iniciar preview: {e}") from e

    def stop_preview(self) -> None:
        if self.picam:
            try:
                self.picam.stop()
            except Exception:
                pass

    # ---------------------------------------------------------------------

    def capture_jpeg(self, filename: Optional[str] = None) -> str:
        """
        Captura un JPEG y devuelve la ruta.
        """
        if not self.is_open():
            self.open()

        # Arranca si no estaba arrancada
        need_stop = False
        try:
            if not self.picam.started:
                self.picam.start()
                need_stop = True
        except Exception:
            # Algunas versiones no tienen .started; intentamos igualmente
            try:
                self.picam.start()
                need_stop = True
            except Exception as e:
                raise CameraError(f"No se pudo iniciar la cámara: {e}") from e

        try:
            if filename is None:
                ts = int(time.time())
                filename = os.path.join(self.output_dir, f"capture_{ts}.jpg")
            self._log(f"[CAM] Capturando a {filename}")
            self.picam.capture_file(filename)
            return filename
        except Exception as e:
            raise CameraError(f"Error capturando imagen: {e}") from e
        finally:
            # Si nosotros la arrancamos, la paramos.
            if need_stop:
                try:
                    self.picam.stop()
                except Exception:
                    pass
