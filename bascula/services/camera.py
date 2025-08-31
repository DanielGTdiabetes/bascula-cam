# -*- coding: utf-8 -*-
"""
bascula/services/camera.py
---------------------------------
Servicio de cámara robusto para Raspberry Pi.
VERSIÓN FINAL Y CORREGIDA con el método detach_preview().
"""
from __future__ import annotations

import time
from typing import Optional

try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

_PICAM2_OK = False
_PICAM2_ERR = ""
_OPENCV_OK = False
_OPENCV_ERR = ""

try:
    from picamera2 import Picamera2
    from libcamera import controls as libcam_controls
    _PICAM2_OK = True
except ImportError as e:
    _PICAM2_ERR = f"Picamera2/libcamera no disponible: {e!s}"

try:
    import cv2
    _OPENCV_OK = True
except ImportError as e:
    _OPENCV_ERR = f"OpenCV no disponible: {e!s}"


class CameraService:
    def __init__(self, width:int=800, height:int=480, fps:int=10, device_index:int=0) -> None:
        self.width = int(width)
        self.height = int(height)
        self.fps = max(1, min(int(fps), 30))
        self.interval_ms = int(1000 / self.fps)
        self.device_index = device_index

        self.backend: Optional[str] = None
        self._reason_unavailable: str = ""
        self._running = False
        self._tk_parent = None
        self._tk_label = None
        self._tk_img_ref = None

        self.picam: Optional["Picamera2"] = None
        self._opencv_cap = None

        self._select_backend()

    # ---------- API Pública ----------
    def is_available(self) -> bool:
        return self.backend is not None

    def reason_unavailable(self) -> str:
        return self._reason_unavailable or "Desconocido"

    def backend_name(self) -> str:
        return self.backend or "none"

    def attach_preview(self, parent):
        """Crea y devuelve un tk.Label dentro de tu contenedor para mostrar la preview."""
        import tkinter as tk
        if self._tk_label is None or self._tk_parent is not parent:
            self._tk_parent = parent
            self._tk_label = tk.Label(parent, bd=0, highlightthickness=0, bg="#000000")
            self._tk_label.pack(fill="both", expand=True)
        return self._tk_label

    # --- MÉTODO AÑADIDO Y CRUCIAL ---
    def detach_preview(self) -> None:
        """Detiene el bucle de frames y destruye el widget de la preview."""
        self._running = False  # Detiene el bucle de after()
        if self._tk_label is not None:
            try:
                self._tk_label.destroy()
            except Exception:
                pass
        self._tk_label = None
        self._tk_parent = None
        self._tk_img_ref = None

    def start(self) -> None:
        if not self.is_available():
            raise RuntimeError(f"Cámara no disponible: {self.reason_unavailable()}")
        if self._running:
            return

        if self.backend == "picam2" and self.picam and not self.picam.started:
            try:
                self.picam.start()
            except Exception:
                time.sleep(0.2)
                self.picam.start()

        self._running = True
        if self._tk_label is not None:
            self._schedule_next_frame()

    def stop(self) -> None:
        """Detiene completamente la cámara y libera el hardware."""
        self._running = False
        if self.backend == "picam2" and self.picam:
            try:
                if self.picam.started:
                    self.picam.stop()
            except Exception:
                pass
        elif self.backend == "opencv" and self._opencv_cap is not None:
            try:
                self._opencv_cap.release()
            except Exception:
                pass

    def capture_photo(self, path:str) -> str:
        if not self.is_available():
            raise RuntimeError(f"Cámara no disponible: {self.reason_unavailable()}")

        if self.backend == "picam2" and self.picam:
            # Para capturar, es mejor detener la preview, configurar para foto, capturar y reanudar.
            was_running = self.picam.started
            if was_running:
                self.picam.stop()
            
            still_config = self.picam.create_still_configuration(main={"size": (self.width, self.height)})
            self.picam.switch_mode_and_capture_file(still_config, path)
            
            if was_running:
                # Vuelve a la configuración de video para la preview
                preview_config = self.picam.create_preview_configuration(main={"size": (self.width, self.height), "format": "RGB888"})
                self.picam.configure(preview_config)
                self.picam.start()
            return path
            
        elif self.backend == "opencv" and self._opencv_cap is not None and _PIL_OK:
            ok, bgr = self._opencv_cap.read()
            if not ok:
                raise RuntimeError("No se pudo capturar imagen desde la cámara USB")
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            Image.fromarray(rgb).save(path)
            return path
        else:
            raise RuntimeError("Backend de cámara no está activo o no se pudo capturar.")

    # ---------- Métodos Internos ----------
    def _select_backend(self) -> None:
        if _PICAM2_OK:
            try:
                self.picam = Picamera2()
                preview_config = self.picam.create_preview_configuration(main={"size": (self.width, self.height), "format": "RGB888"})
                self.picam.configure(preview_config)
                self.backend = "picam2"
                return
            except Exception as e:
                self.picam = None
                self._reason_unavailable = f"Fallo al inicializar Picamera2: {e!s}"
        
        if _OPENCV_OK:
            try:
                cap = cv2.VideoCapture(self.device_index)
                if cap.isOpened():
                    self._opencv_cap = cap
                    self.backend = "opencv"
                    return
                else:
                    cap.release()
                    self._reason_unavailable = "La cámara USB no devuelve frames."
            except Exception as e:
                self._reason_unavailable = f"Fallo al inicializar OpenCV: {e!s}"
        
        if not self.backend:
             self._reason_unavailable = f"No se encontraron backends de cámara. Picamera2: {_PICAM2_ERR} / OpenCV: {_OPENCV_ERR}"

    def _schedule_next_frame(self) -> None:
        if self._tk_label is None or not self._running:
            return
        try:
            self._tk_label.after(self.interval_ms, self._update_frame)
        except Exception:
            self._running = False

    def _update_frame(self) -> None:
        if not self._running or self._tk_label is None:
            return
        frame = None
        try:
            if self.backend == "picam2" and self.picam:
                frame = self.picam.capture_array("main")
            elif self.backend == "opencv" and self._opencv_cap is not None:
                ok, bgr = self._opencv_cap.read()
                if ok:
                    frame = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        except Exception:
            frame = None

        if frame is not None and _PIL_OK:
            img = Image.fromarray(frame) # El reescalado lo hace el backend de la cámara
            tkimg = ImageTk.PhotoImage(img)
            self._tk_label.configure(image=tkimg)
            self._tk_img_ref = tkimg
        
        self._schedule_next_frame()

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass
