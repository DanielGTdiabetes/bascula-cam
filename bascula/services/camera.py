# -*- coding: utf-8 -*-
"""
CameraService (lazy-init) para Raspberry Pi Zero 2W + Camera Module 3 Wide.

- NO crea Picamera2 en __init__: solo cuando realmente hace falta (preview/captura).
- Sin 'sensor={...}' en configuraciones -> compatibilidad con distintas versiones de Picamera2.
- FPS moderado para Zero 2W.
- Preview Tk con PIL (opcional). Si no hay PIL, la captura sigue funcionando.
"""

from __future__ import annotations
import os
import time
from typing import Optional, Callable

# Picamera2 opcional (puede no estar instalada)
try:
    from picamera2 import Picamera2
    PICAM_AVAILABLE = True
except Exception:
    Picamera2 = None  # type: ignore
    PICAM_AVAILABLE = False

# PIL opcional (solo para preview)
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    Image = ImageTk = None  # type: ignore
    PIL_AVAILABLE = False


class CameraUnavailable(Exception):
    pass


class CameraService:
    def __init__(self, width: int = 1024, height: int = 600, fps: int = 10, save_dir: str = "captures") -> None:
        # Lazy-init: aquí no tocamos la cámara
        self.width = int(width)
        self.height = int(height)
        self.fps = max(1, min(int(fps), 15))  # Zero 2W: 8–12 estable
        self.interval_ms = int(1000 / self.fps)

        self.save_dir = os.path.abspath(save_dir)
        os.makedirs(self.save_dir, exist_ok=True)

        self.picam: Optional[Picamera2] = None
        self._previewing: bool = False
        self._bound_widget = None
        self._last_frame_tk = None

    # ---------- utilidades internas ----------

    def _ensure_camera(self) -> None:
        """Crea y configura Picamera2 SOLO si aún no existe."""
        if not PICAM_AVAILABLE:
            raise CameraUnavailable("Picamera2 no está disponible (instala python3-picamera2)")
        if self.picam is None:
            self.picam = Picamera2()
            # Config de vídeo sencilla; sin 'sensor={...}'
            video_cfg = self.picam.create_video_configuration(
                main={"size": (self.width, self.height), "format": "RGB888"}
            )
            self.picam.configure(video_cfg)
            try:
                self.picam.set_controls({"AwbEnable": True, "AeEnable": True})
            except Exception:
                pass

    def _start_if_needed(self) -> bool:
        """Arranca la cámara si no estaba arrancada. Devuelve True si la arrancó ahora."""
        if not self.picam:
            self._ensure_camera()
        try:
            started = getattr(self.picam, "_Picamera2__started", False)
        except Exception:
            started = False
        if not started:
            self.picam.start()
            return True
        return False

    def _stop_if_started_here(self, started_now: bool) -> None:
        """Para la cámara solo si la arrancamos en esta llamada."""
        if started_now and self.picam:
            try:
                self.picam.stop()
            except Exception:
                pass

    # ---------- estado ----------

    def available(self) -> bool:
        """Disponible si Picamera2 está instalada (preview puede requerir PIL)."""
        return PICAM_AVAILABLE

    # ---------- preview en Tk ----------

    def preview_to_tk(self, label_widget) -> Callable[[], None]:
        """Dibuja la preview en un tk.Label. Devuelve stop(). Requiere Pillow."""
        if not PIL_AVAILABLE:
            raise CameraUnavailable("Pillow (python3-pil) no está disponible para la vista previa.")
        self._ensure_camera()

        self._bound_widget = label_widget
        if not self._previewing:
            self._previewing = True
            try:
                self.picam.start()
            except Exception:
                pass
            self._schedule_next()

        def stop():
            try:
                self._previewing = False
                self._bound_widget = None
                # no paramos aquí: se puede capturar justo después
            except Exception:
                pass
        return stop

    def _schedule_next(self):
        if self._previewing and self._bound_widget:
            self._bound_widget.after(self.interval_ms, self._update_frame)

    def _update_frame(self):
        if not (self._previewing and self._bound_widget and self.picam):
            return
        try:
            arr = self.picam.capture_array()
            img = Image.fromarray(arr)  # type: ignore
            try:
                w = max(1, self._bound_widget.winfo_width())
                h = max(1, self._bound_widget.winfo_height())
            except Exception:
                w, h = self.width, self.height
            img = img.resize((w, h))
            photo = ImageTk.PhotoImage(image=img)  # type: ignore
            self._last_frame_tk = photo
            self._bound_widget.configure(image=photo)
        except Exception:
            pass
        finally:
            self._schedule_next()

    # ---------- captura ----------

    def capture_still(self, path: Optional[str] = None) -> str:
        """Captura un JPEG. Arranca/parará la cámara temporalmente si hace falta."""
        if not PICAM_AVAILABLE:
            raise CameraUnavailable("Picamera2 no está disponible (instala python3-picamera2)")
        self._ensure_camera()
        if path is None:
            ts = int(time.time())
            path = os.path.join(self.save_dir, f"capture_{ts}.jpg")

        started_now = self._start_if_needed()
        try:
            # sin reconfigurar a 'still' para máxima compatibilidad
            self.picam.capture_file(path)
        except Exception as e:
            raise CameraUnavailable(f"Error capturando imagen: {e}")
        finally:
            self._stop_if_started_here(started_now)

        return path

    # ---------- liberar ----------

    def stop(self):
        """Detiene la cámara si está corriendo."""
        try:
            if self.picam:
                self.picam.stop()
        except Exception:
            pass
