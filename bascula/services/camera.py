# -*- coding: utf-8 -*-
"""
bascula/services/camera.py (Versión robusta)
--------------------------------------------
Servicio de cámara con Picamera2/OpenCV + preview Tkinter.
- Tolerante a builds sin atributo `.started`.
- Preview se actualiza aunque se cree el label después de `start()`.
"""
from __future__ import annotations
from typing import Optional
import time

try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except Exception:
    _PIL_OK = False

try:
    from picamera2 import Picamera2
    _PICAM2_OK = True
except Exception as e:
    _PICAM2_OK = False
    _PICAM2_ERR = str(e)

try:
    import cv2
    _OPENCV_OK = True
except Exception as e:
    _OPENCV_OK = False
    _OPENCV_ERR = str(e)


class CameraService:
    def __init__(self, width:int=800, height:int=480, fps:int=15) -> None:
        self.width, self.height, self.fps = width, height, fps
        self.interval_ms = max(1, int(1000 / max(1, self.fps)))
        self.backend: Optional[str] = None
        self._running = False
        self._tk_label = None
        self._tk_img_ref = None
        self.picam: Optional["Picamera2"] = None
        self._opencv_cap = None
        self._reason_unavailable = ""
        self._select_backend()

    # --- Info ---
    def is_available(self): return self.backend is not None
    def reason_unavailable(self): return self._reason_unavailable
    def backend_name(self): return self.backend or "none"

    # --- Preview TK ---
    def attach_preview(self, parent):
        import tkinter as tk
        self._tk_label = tk.Label(parent, bd=0, bg="#000000")
        self._tk_label.pack(fill="both", expand=True)
        # Si ya estaba corriendo, programa frames ahora
        if self._running:
            self._schedule_next_frame()

    def detach_preview(self):
        self._running = False
        if self._tk_label:
            try:
                self._tk_label.destroy()
            except Exception:
                pass
        self._tk_label = None
        self._tk_img_ref = None

    # --- Ciclo ---
    def _is_started(self) -> bool:
        """Algunas builds no tienen atributo .started. Usamos getattr con fallback."""
        if self.backend != "picam2" or not self.picam:
            return False
        return bool(getattr(self.picam, "started", False))

    def start(self):
        if self._running or not self.is_available():
            return
        self._running = True
        if self.backend == "picam2" and self.picam and not self._is_started():
            try:
                self.picam.start()
            except Exception:
                # Si falla, desactiva running
                self._running = False
                raise
        # Programa frames aunque el label se cree después; attach_preview los activará también.
        if self._tk_label:
            self._schedule_next_frame()

    def stop(self):
        self._running = False
        if self.backend == "picam2" and self.picam:
            if self._is_started():
                try:
                    self.picam.stop()
                except Exception:
                    pass
        elif self.backend == "opencv" and self._opencv_cap:
            try:
                self._opencv_cap.release()
            except Exception:
                pass
            self._opencv_cap = None

    def capture_photo(self, path: str):
        if not self.is_available():
            raise RuntimeError("Cámara no disponible.")
        if self.backend == "picam2" and self.picam:
            # Picamera2 puede capturar sin parar preview
            self.picam.capture_file(path)
            return path
        elif self.backend == "opencv" and self._opencv_cap and _PIL_OK:
            ok, bgr = self._opencv_cap.read()
            if not ok:
                raise RuntimeError("Fallo al capturar frame de OpenCV.")
            img = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            Image.fromarray(img).save(path)
            return path
        else:
            raise RuntimeError("Backend de cámara no válido para captura.")

    # --- Backend selection ---
    def _select_backend(self):
        if _PICAM2_OK:
            try:
                self.picam = Picamera2()
                cfg = self.picam.create_preview_configuration(
                    main={"size": (self.width, self.height)}
                )
                self.picam.configure(cfg)
                self.backend = "picam2"
                return
            except Exception as e:
                self._reason_unavailable = f"Picamera2 falló: {e}"
        if _OPENCV_OK:
            try:
                cap = cv2.VideoCapture(0)
                if cap.isOpened():
                    self._opencv_cap = cap
                    self.backend = "opencv"
                    return
                else:
                    cap.release()
            except Exception as e:
                self._reason_unavailable += f" / OpenCV falló: {e}"
        if not self.backend:
            self._reason_unavailable = self._reason_unavailable or "No se encontraron backends de cámara."

    # --- Render loop ---
    def _schedule_next_frame(self):
        if self._running and self._tk_label:
            try:
                self._tk_label.after(self.interval_ms, self._update_frame)
            except Exception:
                pass

    def _update_frame(self):
        if not self._running or not self._tk_label:
            return
        frame = None
        try:
            if self.backend == "picam2" and self.picam:
                frame = self.picam.capture_array("main")
            elif self.backend == "opencv" and self._opencv_cap:
                ok, bgr = self._opencv_cap.read()
                if ok:
                    frame = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        except Exception:
            frame = None

        if frame is not None and _PIL_OK:
            try:
                img = ImageTk.PhotoImage(Image.fromarray(frame))
                self._tk_label.configure(image=img)
                self._tk_img_ref = img  # Evita GC
            except Exception:
                pass
        self._schedule_next_frame()

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass
