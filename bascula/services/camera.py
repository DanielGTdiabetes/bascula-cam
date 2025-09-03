# -*- coding: utf-8 -*-
import os, time
from typing import Optional, Callable

try:
    from picamera2 import Picamera2
except Exception:
    Picamera2 = None

try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except Exception:
    _PIL_OK = False

class CameraService:
    def __init__(self, width:int=800, height:int=480, fps:int=10, jpeg_quality:int=90, save_dir:str="/tmp"):
        self._ok = False
        self._status = "init"
        self.picam: Optional["Picamera2"] = None
        self._preview_label = None
        self._preview_after_id = None
        self._preview_running = False
        self._preview_image_ref = None
        self._jpeg_quality = int(jpeg_quality)
        self._fps = max(1, min(int(fps), 30))
        self._interval_ms = int(1000 / self._fps)
        self._save_dir = os.path.abspath(save_dir)

        if Picamera2 is None:
            self._status = "Picamera2 no disponible (instala python3-picamera2)"
            return

        os.makedirs(self._save_dir, exist_ok=True)

        try:
            self.picam = Picamera2()
            cfg = self.picam.create_preview_configuration(main={"size": (int(width), int(height))})
            self.picam.configure(cfg)
            self.picam.start()
            time.sleep(0.2)
            self._ok = True
            self._status = "ready"
        except Exception as e:
            self._status = f"error init: {e}"
            self.picam = None
            self._ok = False

    def available(self) -> bool:
        return bool(self._ok and self.picam is not None)

    def explain_status(self) -> str:
        return self._status

    def preview_to_tk(self, container) -> Callable[[], None]:
        import tkinter as tk
        if not self.available():
            lbl = tk.Label(container, text="Cámara no disponible", bg="#000", fg="#f55")
            lbl.pack(expand=True, fill="both")
            return lambda: None

        if not _PIL_OK:
            lbl = tk.Label(container, text="Pillow no disponible (sin preview)", bg="#000", fg="#f55")
            lbl.pack(expand=True, fill="both")
            return lambda: None

        if self._preview_label is None or self._preview_label.winfo_exists() == 0:
            self._preview_label = tk.Label(container, bg="#000")
            self._preview_label.pack(expand=True, fill="both")

        self._preview_running = True
        self._preview_image_ref = None

        def _update():
            if not self._preview_running:
                return
            try:
                arr = self.picam.capture_array()
                img = Image.fromarray(arr)
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                w = max(1, self._preview_label.winfo_width())
                h = max(1, self._preview_label.winfo_height())
                if w > 1 and h > 1:
                    img = img.resize((w, h))
                photo = ImageTk.PhotoImage(img)
                self._preview_label.configure(image=photo)
                self._preview_image_ref = photo
            except Exception:
                pass
            finally:
                try:
                    self._preview_after_id = self._preview_label.after(self._interval_ms, _update)
                except Exception:
                    self._preview_running = False

        _update()

        def stop():
            try:
                self._preview_running = False
                if self._preview_label and self._preview_after_id:
                    try:
                        self._preview_label.after_cancel(self._preview_after_id)
                    except Exception:
                        pass
            finally:
                self._preview_after_id = None

        return stop

    def capture_still(self, path: Optional[str] = None) -> str:
        if not self.available():
            raise RuntimeError("Cámara no disponible")

        if path is None:
            ts = int(time.time())
            path = os.path.join(self._save_dir, f"capture_{ts}.jpg")

        try:
            self.picam.capture_file(path, format="jpeg", quality=self._jpeg_quality)
            return path
        except Exception:
            if not _PIL_OK:
                raise
            arr = self.picam.capture_array()
            img = Image.fromarray(arr)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.save(path, "JPEG", quality=self._jpeg_quality, optimize=True)
            return path

    def stop(self):
        self._preview_running = False
        try:
            if self._preview_label and self._preview_after_id:
                try:
                    self._preview_label.after_cancel(self._preview_after_id)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if self.picam:
                self.picam.stop()
        except Exception:
            pass
        finally:
            self._ok = False
            self._status = "stopped"
