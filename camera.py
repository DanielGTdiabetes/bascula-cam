# -*- coding: utf-8 -*-
import time
from typing import Optional, Tuple
try:
    from PIL import Image, ImageTk
except Exception:
    Image = None; ImageTk = None
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
        self.backend = 'none'
        self.resolution = resolution
        self._tk_parent = None; self._tk_label = None; self._tk_img_ref = None
        self._loop_after_id = None; self._running = False
        self._start_backend(prefer_backend)

    def _start_backend(self, prefer_backend: Optional[str]):
        if prefer_backend == 'picamera2' and _HAS_PICAMERA2: return self._init_picamera2()
        if prefer_backend == 'opencv' and _HAS_OPENCV and self._init_opencv(): return
        if _HAS_PICAMERA2: return self._init_picamera2()
        if _HAS_OPENCV and self._init_opencv(): return
        self.backend = 'none'

    def _init_picamera2(self):
        try:
            self.picam = Picamera2()
            cfg = self.picam.create_video_configuration(main={'size': self.resolution})
            self.picam.configure(cfg); self.picam.start()
            self.backend = 'picamera2'
        except Exception:
            self.backend = 'none'

    def _init_opencv(self) -> bool:
        try:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened(): return False
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            self.backend = 'opencv'; return True
        except Exception:
            return False

    def close(self):
        self.detach_preview()
        if self.backend == 'picamera2':
            try: self.picam.stop()
            except Exception: pass
            try: self.picam.close()
            except Exception: pass
        elif self.backend == 'opencv':
            try: self.cap.release()
            except Exception: pass
        self.backend = 'none'

    def attach_preview(self, tk_container):
        import tkinter as tk
        self.detach_preview()
        self._tk_parent = tk_container
        self._tk_label = tk.Label(self._tk_parent, bg='#000'); self._tk_label.pack(fill='both', expand=True)
        self._running = True
        self._schedule(30)

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
        if not self._running or not self._tk_label: return
        frame = self._grab_rgb()
        if frame is not None and Image is not None:
            try:
                img = Image.fromarray(frame)
                w = max(100, self._tk_parent.winfo_width()); h = max(100, self._tk_parent.winfo_height())
                img.thumbnail((w,h))
                img_tk = ImageTk.PhotoImage(img); self._tk_label.configure(image=img_tk); self._tk_img_ref = img_tk
            except Exception: pass
        self._schedule(60)

    def _grab_rgb(self):
        if self.backend == 'picamera2':
            try: return self.picam.capture_array()
            except Exception: return None
        if self.backend == 'opencv':
            try:
                ret, frame = self.cap.read()
                if not ret: return None
                return frame[:, :, ::-1]
            except Exception: return None
        return None

    def capture_jpeg(self, path: Optional[str]) -> Optional[str]:
        if self.backend == 'picamera2':
            try: self.picam.capture_file(path); return path
            except Exception: return None
        if self.backend == 'opencv':
            try:
                ret, frame = self.cap.read()
                if not ret: return None
                cv2.imwrite(path, frame); return path
            except Exception: return None
        return None

    def is_available(self) -> bool:
        return self.backend in ('picamera2','opencv')
