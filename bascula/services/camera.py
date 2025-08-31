# -*- coding: utf-8 -*-
"""
CameraService: integración con Picamera2 y vista previa en Tkinter.
Diseñado para Raspberry Pi (Bookworm). Fallback seguro si no hay cámara.
"""
from __future__ import annotations
import os, time
from typing import Optional, Callable

try:
    from picamera2 import Picamera2
    from libcamera import controls as libcam_controls  # opcional
    PICAM_AVAILABLE = True
except Exception:
    PICAM_AVAILABLE = False

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

class CameraUnavailable(Exception):
    pass

class CameraService:
    def __init__(self, width:int=1024, height:int=600, fps:int=15, save_dir:str="captures") -> None:
        self.width = int(width); self.height = int(height); self.fps = int(fps)
        self.interval_ms = int(1000 / max(1, fps))
        self.save_dir = os.path.abspath(save_dir)
        os.makedirs(self.save_dir, exist_ok=True)

        self.picam: Optional[Picamera2] = None
        self._previewing = False
        self._last_frame_tk = None  # referencia para evitar GC
        self._bound_widget = None

        if PICAM_AVAILABLE:
            self.picam = Picamera2()
            # Configuración de vídeo (fluida para preview) y still para capturas.
            video_config = self.picam.create_video_configuration(main={"size": (self.width, self.height)})
            self.picam.configure(video_config)
            try:
                self.picam.set_controls({"AwbEnable": True, "AeEnable": True})
            except Exception:
                pass
        else:
            self.picam = None

    def available(self) -> bool:
        return self.picam is not None and PICAM_AVAILABLE and PIL_AVAILABLE

    # ---------- Preview en Tkinter ----------
    def preview_to_tk(self, label_widget) -> Callable[[], None]:
        """Dibuja la preview en un `tk.Label`. Devuelve una función `stop()`.
        Requiere Pillow (PIL) instalado. Actualiza en el hilo de Tk via `after`.
        """
        if not PIL_AVAILABLE:
            raise CameraUnavailable("Pillow (PIL) no está disponible")
        if not self.picam:
            raise CameraUnavailable("Picamera2 no está disponible")
        self._bound_widget = label_widget
        if not self._previewing:
            self._previewing = True
            try:
                self.picam.start()
            except Exception:
                # Si ya estaba iniciada, ignoramos
                pass
            self._schedule_next()

        def stop():
            try:
                self._previewing = False
                self._bound_widget = None
                # no paramos la cámara aquí; la podemos reutilizar para la foto
                # Si se desea, se puede llamar a self.stop() explícitamente desde fuera.
            except Exception:
                pass
        return stop

    def _schedule_next(self):
        if not self._previewing or not self._bound_widget:
            return
        self._bound_widget.after(self.interval_ms, self._update_frame)

    def _update_frame(self):
        if not (self._previewing and self._bound_widget and self.picam):
            return
        try:
            arr = self.picam.capture_array()  # numpy array HxWx3
            # Convertimos a Image y ajustamos a tamaño del label (fit, sin recortar)
            img = Image.fromarray(arr)
            try:
                w = max(1, self._bound_widget.winfo_width())
                h = max(1, self._bound_widget.winfo_height())
            except Exception:
                w, h = self.width, self.height
            img = img.resize((w, h))
            photo = ImageTk.PhotoImage(image=img)
            self._last_frame_tk = photo
            self._bound_widget.configure(image=photo)
        except Exception:
            # Silencioso para robustez; reintentar siguiente frame
            pass
        finally:
            self._schedule_next()

    # ---------- Captura ----------
    def capture_still(self, path: Optional[str]=None) -> str:
        if not PIL_AVAILABLE:
            raise CameraUnavailable("Pillow (PIL) no está disponible")
        if not self.picam:
            raise CameraUnavailable("Picamera2 no está disponible")
        if path is None:
            ts = int(time.time())
            path = os.path.join(self.save_dir, f"capture_{ts}.jpg")
        # Intentamos captura directa a archivo; si falla, por array
        try:
            self.picam.capture_file(path)
        except Exception:
            try:
                arr = self.picam.capture_array()
                Image.fromarray(arr).save(path, format="JPEG", quality=90)
            except Exception as e:
                raise CameraUnavailable(f"Error capturando imagen: {e}")
        return path

    def stop(self):
        try:
            self._previewing = False
            if self.picam:
                self.picam.stop()
        except Exception:
            pass
