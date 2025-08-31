# -*- coding: utf-8 -*-
"""
CameraService (lazy-init) para Raspberry Pi Zero 2W + Camera Module 3 Wide.
"""
from __future__ import annotations
import os, time
from typing import Optional, Callable

try:
    from picamera2 import Picamera2  # type: ignore
    PICAM_AVAILABLE = True
except Exception:
    Picamera2 = None  # type: ignore
    PICAM_AVAILABLE = False

try:
    from PIL import Image, ImageTk  # type: ignore
    PIL_AVAILABLE = True
except Exception:
    Image = ImageTk = None  # type: ignore
    PIL_AVAILABLE = False

class CameraUnavailable(Exception): pass

class CameraService:
    def __init__(self, width:int=1024, height:int=600, fps:int=10, save_dir:str="captures") -> None:
        self.width, self.height = int(width), int(height)
        self.fps = max(1, min(int(fps), 15))
        self.interval_ms = int(1000 / self.fps)
        self.save_dir = os.path.abspath(save_dir); os.makedirs(self.save_dir, exist_ok=True)
        self.picam: Optional[Picamera2] = None
        self._previewing = False; self._bound_widget = None; self._last_frame_tk = None
        self._frames = 0  # contador de frames, útil para saber si hay preview

    def _ensure_camera(self) -> None:
        if not PICAM_AVAILABLE:
            raise CameraUnavailable("Picamera2 no está disponible (instala python3-picamera2)")
        if self.picam is None:
            self.picam = Picamera2()  # type: ignore
            cfg = self.picam.create_video_configuration(main={"size": (self.width, self.height), "format": "RGB888"})  # type: ignore
            self.picam.configure(cfg)  # type: ignore
            try: self.picam.set_controls({"AwbEnable": True, "AeEnable": True})  # type: ignore
            except Exception: pass

    def _start_if_needed(self)->bool:
        if not self.picam: self._ensure_camera()
        try: started = getattr(self.picam, "_Picamera2__started", False)
        except Exception: started = False
        if not started:
            self.picam.start()  # type: ignore
            return True
        return False

    def _stop_if_started_here(self, started_now: bool)->None:
        if started_now and self.picam:
            try: self.picam.stop()  # type: ignore
            except Exception: pass

    def available(self)->bool:
        return PICAM_AVAILABLE

    # --- preview ---
    def preview_to_tk(self, label_widget)->Callable[[], None]:
        if not PIL_AVAILABLE: raise CameraUnavailable("Pillow (python3-pil) no está disponible para la vista previa.")
        self._ensure_camera()
        self._bound_widget = label_widget
        self._frames = 0
        if not self._previewing:
            self._previewing = True
            try: self.picam.start()  # type: ignore
            except Exception: pass
            self._schedule_next()
        def stop():
            self._previewing = False; self._bound_widget = None
        return stop

    def _schedule_next(self):
        if self._previewing and self._bound_widget:
            self._bound_widget.after(self.interval_ms, self._update_frame)

    def _update_frame(self):
        if not (self._previewing and self._bound_widget and self.picam): return
        try:
            arr = self.picam.capture_array()  # type: ignore
            img = Image.fromarray(arr)  # type: ignore
            try:
                w = max(1, self._bound_widget.winfo_width()); h = max(1, self._bound_widget.winfo_height())
            except Exception:
                w, h = self.width, self.height
            img = img.resize((w, h))
            photo = ImageTk.PhotoImage(image=img)  # type: ignore
            self._last_frame_tk = photo
            self._bound_widget.configure(image=photo, text="")
            self._frames += 1
        except Exception as e:
            # Si algo falla, mostramos un mensaje pero mantenemos botones
            try:
                self._bound_widget.configure(text=f"Error preview:\n{e}", fg="#ffffff", bg="#000000")
            except Exception:
                pass
        finally:
            self._schedule_next()

    # --- captura ---
    def capture_still(self, path:Optional[str]=None)->str:
        if not PICAM_AVAILABLE: raise CameraUnavailable("Picamera2 no está disponible (instala python3-picamera2)")
        self._ensure_camera()
        if path is None:
            path = os.path.join(self.save_dir, f"capture_{int(time.time())}.jpg")
        started_now = self._start_if_needed()
        try:
            self.picam.capture_file(path)  # type: ignore
        finally:
            self._stop_if_started_here(started_now)
        return path

    def stop(self)->None:
        try:
            if self.picam: self.picam.stop()  # type: ignore
        except Exception: pass
