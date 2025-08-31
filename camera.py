# -*- coding: utf-8 -*-
"""
camera.py - Servicio de cámara robusto con Picamera2 y fallback a OpenCV.
- Preview embebido en Tk con PIL (si está disponible).
- Captura a JPEG.
- Mensajes de estado para diagnosticar ausencias de dependencias.
"""
from typing import Optional, Tuple

# Dependencias
try:
    from PIL import Image, ImageTk
    _HAS_PIL = True
except Exception:
    Image = None; ImageTk = None
    _HAS_PIL = False

try:
    from picamera2 import Picamera2
    _HAS_PICAM2 = True
except Exception:
    Picamera2 = None
    _HAS_PICAM2 = False

try:
    import cv2
    _HAS_OPENCV = True
except Exception:
    cv2 = None
    _HAS_OPENCV = False

class CameraService:
    def __init__(self, prefer_backend: Optional[str] = None, resolution: Tuple[int,int]=(1024,768)):
        self.backend = "none"
        self._status = []
        self._pil_needed = "Instala python3-pil para ver la vista previa."
        self.resolution = resolution
        self._tk_parent = None; self._tk_label = None; self._tk_img_ref = None
        self._after_id = None
        self._start(prefer_backend)

    # ---------- Estado ----------
    def explain_status(self) -> str:
        if self.backend == "none":
            msgs = []
            if not _HAS_PICAM2 and not _HAS_OPENCV:
                msgs.append("No hay backend de cámara disponible.")
            if not _HAS_PICAM2:
                msgs.append("Falta python3-picamera2 (Picamera2).")
            if not _HAS_OPENCV:
                msgs.append("Falta opencv-python (para USB/UVC).")
            if not _HAS_PIL:
                msgs.append(self._pil_needed)
            return " | ".join(msgs) or "Cámara no disponible."
        if not _HAS_PIL:
            return self._pil_needed + " (captura posible, preview no)"
        return "Cámara lista."

    # ---------- Arranque backend ----------
    def _start(self, prefer_backend: Optional[str]):
        # permitir forzar backend por variable de entorno
        import os
        env_pref = os.environ.get("BASCULA_CAM_BACKEND", "").strip().lower()
        if env_pref in ("picamera2","opencv"):
            prefer_backend = env_pref

        if prefer_backend == "picamera2" and _HAS_PICAM2:
            if self._start_picam(): return
        if prefer_backend == "opencv" and _HAS_OPENCV:
            if self._start_opencv(): return

        # auto
        if _HAS_PICAM2 and self._start_picam(): return
        if _HAS_OPENCV and self._start_opencv(): return
        self.backend = "none"

    def _start_picam(self) -> bool:
        try:
            self.picam = Picamera2()
            cfg = self.picam.create_preview_configuration(main={"size": self.resolution, "format": "RGB888"})
            self.picam.configure(cfg)
            self.picam.start()
            self.backend = "picamera2"
            return True
        except Exception as e:
            self._status.append(f"Picamera2 error: {e}")
            return False

    def _start_opencv(self) -> bool:
        try:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                self._status.append("OpenCV: no se pudo abrir /dev/video0")
                return False
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            self.backend = "opencv"
            return True
        except Exception as e:
            self._status.append(f"OpenCV error: {e}")
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
        import tkinter as tk
        self.detach_preview()
        self._tk_parent = tk_container
        # Si no hay PIL, mostramos texto explicativo en vez de nada
        if not _HAS_PIL:
            lbl = tk.Label(self._tk_parent, text=self._pil_needed, bg="#1a1f2e", fg="#cccccc")
            lbl.pack(fill="both", expand=True)
            self._tk_label = lbl
            return
        self._tk_label = tk.Label(self._tk_parent, bg="#000000")
        self._tk_label.pack(fill="both", expand=True)

        def _tick():
            if not self._tk_label:
                return
            frame = self._grab_rgb()
            if frame is not None:
                try:
                    img = Image.fromarray(frame)
                    w = max(100, self._tk_label.winfo_width()); h = max(100, self._tk_label.winfo_height())
                    img.thumbnail((w, h))
                    tkimg = ImageTk.PhotoImage(img)
                    self._tk_label.configure(image=tkimg)
                    self._tk_img_ref = tkimg
                except Exception:
                    pass
            self._after_id = self._tk_label.after(60, _tick)
        _tick()

    def detach_preview(self):
        if self._tk_label and self._after_id:
            try: self._tk_label.after_cancel(self._after_id)
            except Exception: pass
        if self._tk_label:
            try: self._tk_label.destroy()
            except Exception: pass
        self._after_id = None; self._tk_label = None; self._tk_parent = None; self._tk_img_ref = None

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
                return frame[:, :, ::-1]  # BGR->RGB
            except Exception:
                return None
        return None

    # ---------- Captura ----------
    def capture_jpeg(self, path: str) -> Optional[str]:
        if self.backend == "picamera2":
            try:
                still = self.picam.create_still_configuration(main={"size": (2304,1296)})
                self.picam.switch_mode_and_capture_file(still, path)
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
