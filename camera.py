# -*- coding: utf-8 -*-
"""
Servicio de cámara con Picamera2 (RGB888) o OpenCV como fallback.
Preview embebido en Tkinter (PIL) y captura a JPEG.
"""
import time
from typing import Optional, Tuple

# PIL para Tkinter
try:
    from PIL import Image, ImageTk
except Exception:
    Image = None; ImageTk = None

# Backends
try:
    from picamera2 import Picamera2
    _HAS_PICAMERA2 = True
except Exception:
    Picamera2 = None; _HAS_PICAMERA2 = False

try:
    import cv2
    _HAS_OPENCV = True
except Exception:
    cv2 = None; _HAS_OPENCV = False

class CameraService:
    def __init__(self, prefer_backend: Optional[str] = None, resolution: Tuple[int,int]=(640,480)):
        self.backend = "none"
        self.resolution = resolution
        self._tk_parent = None; self._tk_label = None; self._tk_img_ref = None
        self._loop_after_id = None; self._running = False
        self._warm = False
        self._start_backend(prefer_backend)

    # ---------- Backend ----------
    def _start_backend(self, prefer_backend: Optional[str]):
        if prefer_backend == "picamera2" and _HAS_PICAMERA2:
            self._init_picam(); return
        if prefer_backend == "opencv" and _HAS_OPENCV and self._init_opencv(): return
        if _HAS_PICAMERA2:
            self._init_picam(); return
        if _HAS_OPENCV and self._init_opencv():
            return
        self.backend = "none"

    def _init_picam(self):
        try:
            self.picam = Picamera2()
            cfg = self.picam.create_preview_configuration(main={"size": self.resolution, "format": "RGB888"})
            self.picam.configure(cfg)
            self.picam.start()
            self.backend = "picamera2"
            self._warm = True
            time.sleep(0.3)  # pequeño warmup
        except Exception:
            self.backend = "none"

    def _init_opencv(self) -> bool:
        try:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                return False
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            self.backend = "opencv"
            self._warm = True
            time.sleep(0.3)
            return True
        except Exception:
            return False

    def close(self):
        self.detach_preview()
        if self.backend == "picamera2":
            try: self.picam.stop()
            except Exception: pass
            try: self.picam.close()
            except Exception: pass
        elif self.backend == "opencv":
            try: self.cap.release()
            except Exception: pass
        self.backend = "none"

    # ---------- Preview Tk ----------
    def attach_preview(self, tk_container):
        self.detach_preview()
        import tkinter as tk
        self._tk_parent = tk_container
        self._tk_label = tk.Label(self._tk_parent, bg="#000")  # fondo negro
        self._tk_label.pack(fill="both", expand=True)
        self._running = True
        self._schedule(60)

    def detach_preview(self):
        self._running = False
        if self._tk_parent and self._loop_after_id:
            try: self._tk_parent.after_cancel(self._loop_after_id)
            except Exception: pass
        self._loop_after_id = None
        if self._tk_label:
            try: self._tk_label.destroy()
            except Exception: pass
        self._tk_label = None; self._tk_parent = None; self._tk_img_ref = None

    def _schedule(self, ms):
        if self._tk_parent:
            try: self._loop_after_id = self._tk_parent.after(ms, self._update)
            except Exception: self._loop_after_id = None

    def _update(self):
        if not self._running or not self._tk_label:
            return
        frame = self._grab_rgb()
        if frame is not None and Image is not None:
            try:
                img = Image.fromarray(frame)
                w = max(100, self._tk_parent.winfo_width()); h = max(100, self._tk_parent.winfo_height())
                img.thumbnail((w, h))
                img_tk = ImageTk.PhotoImage(img)
                self._tk_label.configure(image=img_tk)
                self._tk_img_ref = img_tk
            except Exception:
                pass
        elif Image is None:
            # sin PIL, mostrar texto para diagnosticar
            try: self._tk_label.configure(text="PIL no disponible", fg="#ccc")
            except Exception: pass
        self._schedule(60)

    def _grab_rgb(self):
        if self.backend == "picamera2":
            try:
                return self.picam.capture_array()  # RGB888
            except Exception:
                return None
        if self.backend == "opencv":
            try:
                ret, frame = self.cap.read()
                if not ret: return None
                return frame[:, :, ::-1]  # BGR -> RGB
            except Exception:
                return None
        return None

    # ---------- Captura ----------
    def capture_jpeg(self, path: Optional[str]) -> Optional[str]:
        if self.backend == "picamera2":
            try:
                self.picam.capture_file(path, fileformat="jpg")
                return path
            except Exception:
                return None
        if self.backend == "opencv":
            try:
                ret, frame = self.cap.read()
                if not ret: return None
                import cv2
                cv2.imwrite(path, frame)
                return path
            except Exception:
                return None
        return None

    def is_available(self) -> bool:
        return self.backend in ("picamera2", "opencv")
