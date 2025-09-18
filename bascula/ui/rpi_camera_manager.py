"""Camera helper tuned for the Raspberry Pi preview requirements."""
from __future__ import annotations

import logging
import time
import tkinter as tk
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from .theme_crt import CRT_COLORS, mono

logger = logging.getLogger("bascula.ui.rpi_camera")

try:  # Optional dependency
    from bascula.services.camera import CameraService
except Exception:  # pragma: no cover - optional on CI
    CameraService = None  # type: ignore


@dataclass(slots=True)
class PreviewHandle:
    stop: Callable[[], None]
    widget: tk.Widget


class RpiCameraManager:
    def __init__(self, *, preview_size: Tuple[int, int] = (320, 240), timeout_s: int = 4) -> None:
        self.preview_size = preview_size
        self.timeout_s = max(3, min(timeout_s, 5))
        self._service: Optional[CameraService] = None
        self._handle: Optional[PreviewHandle] = None
        self._timeout_job: Optional[str] = None
        self._root: Optional[tk.Misc] = None
        self._last_capture_path: Optional[str] = None
        if CameraService is not None:
            try:
                self._service = CameraService(width=preview_size[0], height=preview_size[1], fps=12)
            except Exception:
                logger.exception("No se pudo inicializar CameraService")
                self._service = None

    def available(self) -> bool:
        return bool(self._service and getattr(self._service, "available", lambda: False)())

    def start_preview(self, parent: tk.Widget) -> None:
        if parent is None:
            return
        self._root = parent.winfo_toplevel()
        if not self.available():
            self._show_placeholder(parent, "Cámara no disponible")
            return
        try:
            stop = self._service.preview_to_tk(parent)
            self._handle = PreviewHandle(stop=stop, widget=parent)
            self._schedule_timeout()
        except Exception:
            logger.exception("Fallo al iniciar preview")
            self._show_placeholder(parent, "Preview no disponible")

    def _show_placeholder(self, parent: tk.Widget, text: str) -> None:
        label = tk.Label(
            parent,
            text=text,
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["muted"],
            font=mono("sm"),
            bd=0,
            highlightthickness=2,
            highlightbackground=CRT_COLORS["divider"],
        )
        label.place(relx=0.5, rely=0.5, anchor="center")
        self._handle = PreviewHandle(stop=lambda: label.destroy(), widget=label)

    def _schedule_timeout(self) -> None:
        if self._root is None:
            return
        if self._timeout_job is not None:
            try:
                self._root.after_cancel(self._timeout_job)
            except Exception:
                pass
        self._timeout_job = self._root.after(int(self.timeout_s * 1000), self.stop_preview)

    def stop_preview(self) -> None:
        if self._handle is not None:
            try:
                self._handle.stop()
            except Exception:
                pass
            self._handle = None
        if self._timeout_job is not None and self._root is not None:
            try:
                self._root.after_cancel(self._timeout_job)
            except Exception:
                pass
            self._timeout_job = None

    def capture(self, path: Optional[str] = None) -> Optional[str]:
        if not self.available():
            return None
        try:
            start = time.monotonic()
            result = self._service.capture_still(path)
            elapsed = time.monotonic() - start
            if elapsed > self.timeout_s:
                logger.warning("Captura superó el timeout configurado: %.2fs", elapsed)
            self._last_capture_path = result
            return result
        except Exception:
            logger.exception("Error capturando foto")
            return None

    def last_capture(self) -> Optional[str]:
        return self._last_capture_path

