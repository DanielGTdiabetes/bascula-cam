# -*- coding: utf-8 -*-
"""
bascula/services/camera.py (Versión Definitiva)
------------------------------------------------
Servicio de cámara con todas las funciones necesarias, incluyendo detach_preview().
"""
from __future__ import annotations
import time
from typing import Optional

try: from PIL import Image, ImageTk; _PIL_OK = True
except ImportError: _PIL_OK = False

try: from picamera2 import Picamera2; _PICAM2_OK = True
except ImportError as e: _PICAM2_OK = False; _PICAM2_ERR = str(e)

try: import cv2; _OPENCV_OK = True
except ImportError as e: _OPENCV_OK = False; _OPENCV_ERR = str(e)

class CameraService:
    def __init__(self, width:int=800, height:int=480, fps:int=15) -> None:
        self.width, self.height, self.fps = width, height, fps
        self.interval_ms = int(1000 / self.fps)
        self.backend: Optional[str] = None
        self._running = False
        self._tk_label = None; self._tk_img_ref = None
        self.picam: Optional["Picamera2"] = None
        self._opencv_cap = None
        self._reason_unavailable = ""
        self._select_backend()

    def is_available(self): return self.backend is not None
    def reason_unavailable(self): return self._reason_unavailable
    def backend_name(self): return self.backend or "none"

    def attach_preview(self, parent):
        import tkinter as tk
        self._tk_label = tk.Label(parent, bd=0, bg="#000000")
        self._tk_label.pack(fill="both", expand=True)

    def detach_preview(self):
        self._running = False
        if self._tk_label:
            try: self._tk_label.destroy()
            except Exception: pass
        self._tk_label, self._tk_img_ref = None, None

    def start(self):
        if self._running or not self.is_available(): return
        self._running = True
        if self.backend == "picam2" and self.picam and not self.picam.started:
            self.picam.start()
        if self._tk_label:
            self._schedule_next_frame()

    def stop(self):
        self._running = False
        if self.backend == "picam2" and self.picam and self.picam.started:
            self.picam.stop()
        elif self.backend == "opencv" and self._opencv_cap:
            self._opencv_cap.release()

    def capture_photo(self, path:str):
        if not self.is_available(): raise RuntimeError("Cámara no disponible.")
        
        if self.backend == "picam2" and self.picam:
            return self.picam.capture_file(path) # Picamera2 gestiona los modos automáticamente
        
        elif self.backend == "opencv" and self._opencv_cap and _PIL_OK:
            ok, bgr = self._opencv_cap.read()
            if not ok: raise RuntimeError("Fallo al capturar frame de OpenCV.")
            Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)).save(path)
            return path
        else:
            raise RuntimeError("Backend de cámara no válido para captura.")

    def _select_backend(self):
        if _PICAM2_OK:
            try:
                self.picam = Picamera2()
                config = self.picam.create_preview_configuration(main={"size": (self.width, self.height)})
                self.picam.configure(config)
                self.backend = "picam2"; return
            except Exception as e:
                self._reason_unavailable = f"Picamera2 falló: {e}"
        if _OPENCV_OK:
            try:
                cap = cv2.VideoCapture(0)
                if cap.isOpened():
                    self._opencv_cap = cap
                    self.backend = "opencv"; return
                else:
                    cap.release()
            except Exception as e:
                self._reason_unavailable += f" / OpenCV falló: {e}"
        if not self.backend:
             self._reason_unavailable = f"No se encontraron backends. P2: {_PICAM2_ERR if not _PICAM2_OK else 'OK'}, CV2: {_OPENCV_ERR if not _OPENCV_OK else 'OK'}"

    def _schedule_next_frame(self):
        if self._running and self._tk_label:
            self._tk_label.after(self.interval_ms, self._update_frame)

    def _update_frame(self):
        if not self._running or not self._tk_label: return
        frame = None
        try:
            if self.backend == "picam2": frame = self.picam.capture_array("main")
            elif self.backend == "opencv": ok, bgr = self._opencv_cap.read(); frame = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB) if ok else None
        except Exception: frame = None
        if frame is not None and _PIL_OK:
            img = ImageTk.PhotoImage(Image.fromarray(frame))
            self._tk_label.configure(image=img)
            self._tk_img_ref = img
        self._schedule_next_frame()
    
    def __del__(self): self.stop()
