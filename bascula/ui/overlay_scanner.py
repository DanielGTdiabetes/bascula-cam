import tkinter as tk
import time
from bascula.ui.overlay_base import OverlayBase
from bascula.ui.widgets import COL_CARD, COL_TEXT, COL_ACCENT
from bascula.services.barcode import decode_image

try:
    from PIL import Image
except Exception:
    Image = None


class ScannerOverlay(OverlayBase):
    """Overlay de escaneo con stream de cámara real y timeout configurable."""
    def __init__(self, parent, app, on_result=None, on_timeout=None, timeout_ms: int = 12000, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app
        self._on_result = on_result or (lambda s: None)
        self._on_timeout = on_timeout or (lambda: None)
        self._timeout_ms = int(timeout_ms)
        self._deadline = 0.0
        self._decode_after = None
        self._stop_preview = None

        c = self.content(); c.configure(padx=12, pady=12)
        top = tk.Frame(c, bg=COL_CARD); top.pack(fill='x')
        tk.Label(top, text='Escáner', bg=COL_CARD, fg=COL_ACCENT).pack(side='left')
        self.count_lbl = tk.Label(top, text='', bg=COL_CARD, fg=COL_TEXT)
        self.count_lbl.pack(side='right')

        self.preview_container = tk.Frame(c, bg=COL_CARD)
        self.preview_container.pack(padx=6, pady=8, fill='both', expand=True)

        btns = tk.Frame(c, bg=COL_CARD); btns.pack(fill='x')
        tk.Button(btns, text='Cancelar', command=self.hide).pack(side='right')

    def show(self):
        super().show()
        self._start_stream()
        self._deadline = time.time() + (self._timeout_ms / 1000.0)
        self._poll_decode()

    def hide(self):
        super().hide()
        if self._decode_after:
            try: self.after_cancel(self._decode_after)
            except Exception: pass
            self._decode_after = None
        if self._stop_preview:
            try: self._stop_preview()
            except Exception: pass
            self._stop_preview = None

    def _start_stream(self):
        try:
            cam = getattr(self.app, 'camera', None)
            if cam and getattr(cam, 'available', lambda: False)():
                try:
                    # Hint camera mode for better pipeline choices
                    if hasattr(cam, 'set_mode'):
                        cam.set_mode('barcode')
                except Exception:
                    pass
                self._stop_preview = cam.preview_to_tk(self.preview_container)
            else:
                self._show_unavailable()
        except Exception:
            self._show_unavailable()

    def _show_unavailable(self):
        for w in self.preview_container.winfo_children():
            w.destroy()
        tk.Label(self.preview_container, text='Cámara no disponible', bg=COL_CARD, fg=COL_TEXT).pack(expand=True, fill='both')

    def _poll_decode(self):
        # Timeout handling
        remaining = max(0.0, self._deadline - time.time())
        self.count_lbl.configure(text=f"{int(remaining)}s")
        if remaining <= 0:
            self._on_timeout()
            self.hide()
            return

        # Try decode every tick (lightweight)
        try:
            cam = getattr(self.app, 'camera', None)
            if cam and getattr(cam, 'available', lambda: False)():
                img = None
                if hasattr(cam, 'grab_frame'):
                    img = cam.grab_frame()
                elif cam.picam is not None and Image:
                    try:
                        arr = cam.picam.capture_array()
                        img = Image.fromarray(arr)
                    except Exception:
                        img = None
                if img is not None:
                    codes = decode_image(img)
                    if codes:
                        self._on_result(codes[0])
                        self.hide()
                        return
        except Exception:
            pass

        self._decode_after = self.after(500, self._poll_decode)
