import tkinter as tk
import time
from bascula.ui.overlay_base import OverlayBase
from bascula.ui.widgets import COL_CARD, COL_TEXT, COL_ACCENT, COL_BORDER
from bascula.services.barcode import decode_image
from bascula.ui.anim_target import TargetAnimator

try:
    from PIL import Image, ImageTk
except Exception:
    Image = ImageTk = None


class ScannerOverlay(OverlayBase):
    """Overlay de escaneo con recuadro y animaciones."""
    def __init__(self, parent, app, on_result=None, on_timeout=None, timeout_ms: int = 12000, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app
        self._on_result = on_result or (lambda s: None)
        self._on_timeout = on_timeout or (lambda: None)
        self._timeout_ms = int(timeout_ms)
        self._deadline = 0.0
        self._decode_after = None
        self._frame_photo = None
        self.target_rect = None
        self.anim: TargetAnimator | None = None
        self._scanlines = bool(getattr(app, 'get_cfg', lambda: {})().get('theme_scanlines', False))

        # canvas a pantalla completa
        try:
            self._content.destroy()
        except Exception:
            pass
        self.canvas = tk.Canvas(self._frame, bg=COL_CARD, highlightthickness=0, bd=0)
        self.canvas.pack(fill='both', expand=True)
        self.bind('<Return>', lambda e: self._detect('mock'))

    def _setup(self) -> None:
        self.canvas.delete('all')
        w = self.canvas.winfo_width() or 320
        h = self.canvas.winfo_height() or 240
        if self._scanlines:
            try:
                for y in range(0, h, 4):
                    self.canvas.create_line(0, y, w, y, fill=COL_BORDER)
            except Exception:
                pass
        size = int(min(w, h) * 0.6)
        x1 = (w - size) // 2
        y1 = (h - size) // 2
        x2 = x1 + size
        y2 = y1 + size
        self.target_rect = (x1, y1, x2, y2)
        self.anim = TargetAnimator(self.canvas, self.target_rect, {'accent': COL_ACCENT})
        self.anim.pulse()

    def show(self) -> None:
        super().show()
        self.canvas.update_idletasks()
        self._setup()
        self._deadline = time.time() + (self._timeout_ms / 1000.0)
        self._poll_decode()
        try:
            self.focus_set()
        except Exception:
            pass

    def hide(self) -> None:
        super().hide()
        if self._decode_after:
            try:
                self.after_cancel(self._decode_after)
            except Exception:
                pass
            self._decode_after = None

    def _poll_decode(self) -> None:
        remaining = max(0.0, self._deadline - time.time())
        if remaining <= 0:
            self._on_timeout()
            self.hide()
            return
        try:
            cam = getattr(self.app, 'camera', None)
            if cam and getattr(cam, 'available', lambda: False)():
                img = None
                if hasattr(cam, 'grab_frame'):
                    img = cam.grab_frame()
                elif getattr(cam, 'picam', None) is not None and Image:
                    try:
                        arr = cam.picam.capture_array()
                        img = Image.fromarray(arr)
                    except Exception:
                        img = None
                if img is not None:
                    self._show_frame(img)
                    codes = decode_image(img)
                    if codes:
                        self._detect(codes[0])
                        return
        except Exception:
            pass
        self._decode_after = self.after(500, self._poll_decode)

    def _show_frame(self, img) -> None:
        if not self.target_rect:
            return
        x1, y1, x2, y2 = self.target_rect
        if ImageTk:
            try:
                thumb = img.copy()
                thumb.thumbnail((x2 - x1 - 4, y2 - y1 - 4))
                self._frame_photo = ImageTk.PhotoImage(thumb)
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                fid = getattr(self, '_frame_id', None)
                if fid:
                    self.canvas.delete(fid)
                self._frame_id = self.canvas.create_image(cx, cy, image=self._frame_photo)
            except Exception:
                pass
        else:
            fid = getattr(self, '_frame_id', None)
            if fid:
                self.canvas.delete(fid)
            self._frame_id = self.canvas.create_rectangle(x1 + 4, y1 + 4, x2 - 4, y2 - 4, outline='', fill=COL_ACCENT)
        if self.anim:
            try:
                self.canvas.tag_raise(self.anim.border_id)
            except Exception:
                pass

    def _detect(self, code: str = '') -> None:
        try:
            if self.anim:
                self.anim.sweep()
            if self.target_rect:
                x1, y1, x2, y2 = self.target_rect
                cx = (x1 + x2) // 2
                cy = y2 + 30
            else:
                cx = self.canvas.winfo_width() // 2
                cy = self.canvas.winfo_height() // 2
            self.canvas.create_text(cx, cy, text='Detectado', fill=COL_TEXT,
                                    font=('DejaVu Sans', 20, 'bold'))
        except Exception:
            pass
        self._on_result(code)
        self.after(450, self.hide)
