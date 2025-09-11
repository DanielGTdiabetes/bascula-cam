# bascula/ui/overlay_scanner.py
import threading
import time
import tkinter as tk
from tkinter import ttk
from PIL import ImageTk
from typing import Optional

from bascula.config.themes import T
from bascula.services.camera import CameraService
from bascula.services import barcode as barcode_srv

from bascula.ui.anim_target import TargetLockAnimator

CRT_BG = T("bg", "#000000")
CRT_FG = T("fg", "#00ff46")
CRT_ACC = T("accent", "#00ff46")
CRT_GRID = T("grid", "#003300")
FONT = T("font", ("DejaVu Sans Mono", 12))

class ScannerOverlay(tk.Frame):
    """
    Overlay de escáner con preview de cámara, barra KITT y animación TargetLock al detectar.
    Uso:
        overlay = ScannerOverlay(root, on_detect=callable)
        overlay.open()
    """
    def __init__(self, master, on_detect=None, **kw):
        super().__init__(master, bg=CRT_BG, **kw)
        self.on_detect = on_detect
        self.cam: Optional[CameraService] = None
        self._running = False
        self._cancel = False
        self._imgtk = None

        # Layout
        self.top = tk.Frame(self, bg=CRT_BG)
        self.top.pack(fill="x", pady=8)

        self.lbl = tk.Label(self.top, text="ESCANEO CÓDIGO · 8s timeout", bg=CRT_BG, fg=CRT_FG, font=(FONT[0], 14, "bold"))
        self.lbl.pack(side="left", padx=12)

        self.btn_cancel = tk.Button(self.top, text="Cancelar", command=self.close, bg=CRT_BG, fg=CRT_FG)
        self.btn_cancel.pack(side="right", padx=12)

        self.canvas = tk.Canvas(self, width=480, height=360, bg=CRT_BG, highlightthickness=0)
        self.canvas.pack(expand=True, fill="both", padx=16, pady=10)

<<<<<<< HEAD
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
=======
        # Barra KITT
        self.kitt = tk.Canvas(self, height=8, bg=CRT_BG, highlightthickness=0)
        self.kitt.pack(fill="x", padx=16, pady=(0,14))
        self._kitt_pos = 0
>>>>>>> 9206998cceb5c78403970b63342eb58f4ff4921e

        # Animador Target Lock
        self.anim = TargetLockAnimator(self.master)

    def open(self):
        if self._running:
            return
        self._running = True
        self._cancel = False
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        # Cámara en modo barcode
        self.cam = CameraService()
        self.cam.start("barcode")
        # Loop UI
        self.after(0, self._loop_preview)
        self.after(0, self._loop_kitt)
        # Hilo de escaneo
        t = threading.Thread(target=self._scan_worker, daemon=True)
        t.start()

    def close(self):
        self._cancel = True
        self._running = False
        try:
<<<<<<< HEAD
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
=======
            if self.cam:
                self.cam.stop()
>>>>>>> 9206998cceb5c78403970b63342eb58f4ff4921e
        except Exception:
            pass
        self.cam = None
        self.place_forget()
        self.canvas.delete("all")

    # ---- Preview de cámara ----
    def _loop_preview(self):
        if not self._running: return
        frame = None
        try:
            frame = self.cam.grab_frame() if self.cam else None
        except Exception:
            frame = None
        if frame is not None:
            # ajustar a canvas
            cw = self.canvas.winfo_width() or 480
            ch = self.canvas.winfo_height() or 360
            fr = frame.copy().resize((cw, ch))
            self._imgtk = ImageTk.PhotoImage(fr)
            self.canvas.delete("all")
            self.canvas.create_image(cw//2, ch//2, image=self._imgtk)
            # crosshair
            self.canvas.create_line(0, ch//2, cw, ch//2, fill=CRT_GRID)
            self.canvas.create_line(cw//2, 0, cw//2, ch, fill=CRT_GRID)
        else:
            self.canvas.delete("all")
            self.canvas.create_text(10, 10, anchor="nw", text="Cámara inicializando…", fill=CRT_FG, font=(FONT[0], 12))

        self.after(66, self._loop_preview)  # ~15 FPS

    # ---- Barra KITT ----
    def _loop_kitt(self):
        if not self._running: return
        w = self.kitt.winfo_width() or 400
        self.kitt.delete("all")
        pos = (self._kitt_pos % (w-40))
        for trail in range(0, 28, 6):
            x1 = 10 + pos + trail
            self.kitt.create_rectangle(x1, 2, x1+12, 6, outline=CRT_ACC)
        self._kitt_pos += 12
        self.after(60, self._loop_kitt)

    # ---- Worker de escaneo ----
    def _scan_worker(self):
        deadline = time.time() + 8.0
        cancel_cb = lambda: (self._cancel or (not self._running) or time.time() > deadline)
        result = None
        try:
            # si barcode.scan soporta callback de cancelación
            result = barcode_srv.scan(timeout_s=8, cancel_cb=cancel_cb)
        except TypeError:
            # versión sin cancel_cb
            result = barcode_srv.scan(timeout_s=8)
        except Exception:
            result = None

        if not self._running:
            return
        if result is None:
            # timeout/cancel
            self.after(0, self.close)
            return

        # Mostrar animación de target lock
        poly = getattr(result, "polygon", None)
        rect = getattr(result, "rect", None)
        if poly:
            pts = [(p.x, p.y) for p in poly]
            self.anim.run(polygon=pts, label=self._label_from_result(result))
        elif rect:
            r = rect
            bbox = (r.left, r.top, r.left+r.width, r.top+r.height)
            self.anim.run(bbox=bbox, label=self._label_from_result(result))
        else:
            self.anim.run(label=self._label_from_result(result))

        # cerrar overlay tras animación y notificar
        def finalize():
            if callable(self.on_detect):
                try:
                    self.on_detect(result)
                except Exception:
                    pass
            self.close()
        self.after(900, finalize)

    def _label_from_result(self, result):
        try:
            sym = getattr(result, "type", "BARCODE")
            data = getattr(result, "data", b"").decode("utf-8", "ignore")
            if not data and hasattr(result, "data"):
                data = str(result.data)
            return f"{sym}: {data}" if data else sym
        except Exception:
            return "Objetivo detectado"
