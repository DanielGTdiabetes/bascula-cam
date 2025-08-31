# -*- coding: utf-8 -*-
"""
bascula/services/camera.py
---------------------------------
Servicio de cámara robusto para Raspberry Pi Zero 2W.

Prioriza Picamera2/libcamera (IMX708 / Cámara Módulo 3) y
hace fallback a OpenCV (UVC/USB) si no está disponible.

Uso (en tu UI Tkinter ya existente):
    from bascula.services.camera import CameraService
    cam = CameraService(width=800, height=480, fps=10)
    lbl = cam.attach_preview(container_widget)  # un tk.Frame de tu UI
    cam.start()
    ...
    cam.stop()  # al cerrar
"""
from __future__ import annotations

import time
from typing import Optional

try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except Exception:
    _PIL_OK = False

_PICAM2_OK = False
_PICAM2_ERR = ""
_OPENCV_OK = False
_OPENCV_ERR = ""

try:
    from picamera2 import Picamera2
    from libcamera import controls as libcam_controls  # type: ignore
    _PICAM2_OK = True
except Exception as e:
    _PICAM2_OK = False
    _PICAM2_ERR = f"Picamera2/libcamera no disponible: {e!s}"

try:
    import cv2  # type: ignore
    _OPENCV_OK = True
except Exception as e:
    _OPENCV_OK = False
    _OPENCV_ERR = f"OpenCV no disponible: {e!s}"


class CameraService:
    def __init__(self, width:int=800, height:int=480, fps:int=10, device_index:int=0) -> None:
        self.width  = int(width)
        self.height = int(height)
        self.fps    = max(1, min(int(fps), 30))
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

    # ---------- API ----------
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

    def detach_preview(self) -> None:
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

        if self.backend == "picam2" and self.picam:
            try:
                self.picam.start()
            except Exception:
                time.sleep(0.2)
                self.picam.start()

        self._running = True
        if self._tk_label is not None:
            self._schedule_next_frame()

    def stop(self) -> None:
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
            still = self.picam.create_still_configuration(main={"size": (self.width, self.height)})
            self.picam.switch_mode_and_capture_file(still, path)
            return path
        elif self.backend == "opencv" and self._opencv_cap is not None and _PIL_OK:
            import cv2
            ok, bgr = self._opencv_cap.read()
            if not ok:
                raise RuntimeError("No se pudo capturar imagen desde UVC")
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            Image.fromarray(rgb).save(path)
            return path
        else:
            raise RuntimeError("Backend de cámara no activo")

    # ---------- Internos ----------
    def _select_backend(self) -> None:
        # 1) Picamera2
        if _PICAM2_OK:
            try:
                self.picam = Picamera2()
                preview_config = self.picam.create_preview_configuration(
                    main={"size": (self.width, self.height), "format": "RGB888"},
                    buffer_count=2
                )
                self.picam.configure(preview_config)
                # No todos los sensores soportan AF; mejor en try/except.
                try:
                    self.picam.set_controls({
                        "AfMode": libcam_controls.AfModeEnum.Continuous,
                        "AfSpeed": libcam_controls.AfSpeedEnum.Normal,
                    })
                except Exception:
                    pass
                self.backend = "picam2"
                self._reason_unavailable = ""
                return
            except Exception as e:
                self.picam = None
                self._reason_unavailable = f"Fallo inicializando Picamera2: {e!s}"

        # 2) OpenCV (UVC)
        if _OPENCV_OK:
            try:
                import cv2
                cap = cv2.VideoCapture(self.device_index)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                cap.set(cv2.CAP_PROP_FPS,          self.fps)
                ok, _ = cap.read()
                if ok:
                    self._opencv_cap = cap
                    self.backend = "opencv"
                    self._reason_unavailable = ""
                    return
                else:
                    cap.release()
                    self._reason_unavailable = "La cámara UVC no devuelve frames."
            except Exception as e:
                self._reason_unavailable = f"Fallo inicializando OpenCV: {e!s}"

        # 3) Sin backend
        if not self.backend:
            reasons = []
            if not _PICAM2_OK:
                reasons.append(_PICAM2_ERR or "Picamera2 no disponible")
            if not _OPENCV_OK:
                reasons.append(_OPENCV_ERR or "OpenCV no disponible")
            if self._reason_unavailable:
                reasons.append(self._reason_unavailable)
            self._reason_unavailable = " / ".join(reasons) or "Sin backend de cámara disponible"

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
                import cv2
                ok, bgr = self._opencv_cap.read()
                if ok:
                    frame = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        except Exception:
            frame = None

        if frame is not None and _PIL_OK:
            img = Image.fromarray(frame).resize((self.width, self.height))
            tkimg = ImageTk.PhotoImage(img)
            self._tk_label.configure(image=tkimg, text="")
            self._tk_img_ref = tkimg  # evitar GC
        elif self._tk_label is not None:
            self._tk_label.configure(image="", text="Cámara sin señal", fg="#ffffff", bg="#000000")

        self._schedule_next_frame()

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass
