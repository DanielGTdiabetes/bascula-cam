# -*- coding: utf-8 -*-
import os, time, logging, importlib
from typing import Optional, Callable, Literal

try:
    from picamera2 import Picamera2
except Exception:
    Picamera2 = None

# Pillow se importa de forma diferida para evitar falsos negativos
Image = None  # type: ignore
ImageTk = None  # type: ignore
_PIL_OK: Optional[bool] = None
logger = logging.getLogger(__name__)


def _ensure_pillow() -> bool:
    """Importa Pillow de forma perezosa con reintento."""
    global Image, ImageTk, _PIL_OK
    if _PIL_OK:
        return True
    try:
        from PIL import Image as _Image, ImageTk as _ImageTk  # type: ignore
        Image = _Image
        ImageTk = _ImageTk
        _PIL_OK = True
        return True
    except Exception:
        try:
            Image = importlib.import_module("PIL.Image")  # type: ignore
            ImageTk = importlib.import_module("PIL.ImageTk")  # type: ignore
            _PIL_OK = True
            return True
        except Exception as e:
            _PIL_OK = False
            Image = None
            ImageTk = None
            logger.warning("Pillow no disponible: %s", e)
            return False

# Controles libcamera (autofoco) opcionales
try:
    from libcamera import controls as _LC  # type: ignore
except Exception:
    _LC = None

class CameraService:
    MODES = ("idle", "barcode", "ocr", "foodshot")

    def __init__(self, width:int=800, height:int=480, fps:int=10, jpeg_quality:int=90, save_dir:str="/tmp"):
        self._ok = False
        self._status = "init"
        self.picam: Optional["Picamera2"] = None
        self._mode: Literal['idle','barcode','ocr','foodshot'] = 'idle'
        self._preview_label = None
        self._preview_after_id = None
        self._preview_running = False
        self._preview_image_ref = None
        self._jpeg_quality = int(jpeg_quality)
        self._fps = max(1, min(int(fps), 30))
        self._interval_ms = int(1000 / self._fps)
        self._save_dir = os.path.abspath(save_dir)

        # Resolution profiles por modo (rápido para barcode, alta para foodshot)
        # IMX708 (Cam Module 3) tamaños típicos: full ~4608x2592 (16:9)
        self._mode_profiles = {
            'idle':    { 'size': (1280, 720) },
            'barcode': { 'size': (640, 480) },
            'ocr':     { 'size': (1536, 864) },
            'foodshot':{ 'size': (4608, 2592) },
        }

        # Leer tamaño foodshot desde config/env si está establecido
        try:
            fs_env = os.environ.get('BASCULA_FOODSHOT_SIZE', '').strip()
            fs = fs_env
            try:
                from bascula.utils import load_config as _load_cfg  # type: ignore
                cfg = _load_cfg()
                fs_cfg = str(cfg.get('foodshot_size') or '').strip()
                if fs_cfg:
                    fs = fs_cfg
            except Exception:
                pass
            if fs and 'x' in fs:
                parts = fs.lower().split('x')
                w = int(parts[0]); h = int(parts[1])
                if w > 0 and h > 0:
                    self._mode_profiles['foodshot'] = {'size': (w, h)}
        except Exception:
            pass

        if Picamera2 is None:
            self._status = "Picamera2 no disponible (instala python3-picamera2)"
            return

        os.makedirs(self._save_dir, exist_ok=True)

        try:
            self.picam = Picamera2()
            # Config inicial acorde a 'idle'
            _w, _h = self._mode_profiles['idle']['size']
            cfg = self.picam.create_preview_configuration(main={"size": (_w, _h)})
            self.picam.configure(cfg)
            self.picam.start()
            time.sleep(0.2)
            self._ok = True
            self._status = "ready"
            # Enfocar en continuo si está disponible (mejor para táctil/escáner)
            self._apply_af_defaults('idle')
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
        logger.debug("preview_to_tk solicitado")
        if not self.available():
            lbl = tk.Label(container, text="Cámara no disponible", bg="#000", fg="#f55")
            lbl.pack(expand=True, fill="both")
            return lambda: None

        if not _ensure_pillow():
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
            except Exception as e:
                logger.debug("preview capture error: %s", e)
            finally:
                try:
                    self._preview_after_id = self._preview_label.after(self._interval_ms, _update)
                except Exception as e:
                    logger.debug("after scheduling failed: %s", e)
                    self._preview_running = False

        _update()

        def stop():
            logger.debug("preview_to_tk stop")
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
            try:
                self.picam.capture_file(path, format="jpeg", quality=self._jpeg_quality)
            except TypeError:
                # Picamera2 >= 0.5 removed the 'quality' argument
                self.picam.capture_file(path, format="jpeg")
            return path
        except Exception:
            if not _ensure_pillow():
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

    # --- Dynamic modes and utility capture ---
    def start(self, mode: Literal['idle','barcode','ocr','foodshot'] = 'idle') -> bool:
        if not self.available():
            return False
        self.set_mode(mode)
        return True

    def set_mode(self, mode: Literal['idle','barcode','ocr','foodshot']) -> None:
        if mode not in self.MODES:
            return
        if mode == self._mode:
            return
        self._mode = mode
        # Aplicar perfil de resolución si es posible (no bloqueante largo)
        try:
            if not self.available() or self.picam is None:
                return
            prof = self._mode_profiles.get(mode) or {}
            size = prof.get('size')
            if isinstance(size, (tuple, list)) and len(size) == 2:
                # Reconfiguración ligera de preview
                self.picam.stop()
                cfg = self.picam.create_preview_configuration(main={"size": (int(size[0]), int(size[1]))})
                self.picam.configure(cfg)
                self.picam.start()
                self._status = f"ready ({mode} {size[0]}x{size[1]})"
            # Ajustar AF adecuado al modo
            self._apply_af_defaults(mode)
        except Exception as e:
            # Mantener estado previo si falla
            self._status = f"mode set failed: {e}"

    def set_profile_size(self, mode: Literal['idle','barcode','ocr','foodshot'], size: tuple[int, int]) -> None:
        """Actualiza el perfil de resolución para un modo concreto. Aplica si es el modo actual."""
        try:
            w, h = int(size[0]), int(size[1])
            if mode in self.MODES and w > 0 and h > 0:
                self._mode_profiles[mode] = {'size': (w, h)}
                if mode == self._mode:
                    # reconfigurar de inmediato
                    self.set_mode(mode)
        except Exception:
            pass

    def grab_frame(self):
        """Return a PIL Image for the current frame or None."""
        if not self.available() or not _ensure_pillow():
            return None
        try:
            arr = self.picam.capture_array()
            img = Image.fromarray(arr)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            return img
        except Exception:
            return None

    def capture(self, label: str = "capture") -> Optional[str]:
        """Capture a still image and return its path.

        Mode hints:
          - barcode: quick capture with default quality
          - ocr: ensure full RGB and best quality
          - foodshot: same as ocr; naming reflects UX
        """
        if not self.available():
            return None
        ts = int(time.time())
        name = f"{label}_{self._mode}_{ts}.jpg" if self._mode != 'idle' else f"{label}_{ts}.jpg"
        path = os.path.join(self._save_dir, name)
        try:
            # Ajustar temporalmente la resolución si el modo lo requiere
            if self._mode in ("ocr", "foodshot") and self.picam is not None:
                # Asegurar resolución alta antes del disparo
                prof = self._mode_profiles.get(self._mode) or {}
                size = prof.get('size')
                if isinstance(size, (tuple, list)) and len(size) == 2:
                    try:
                        self.picam.stop()
                        cfg = self.picam.create_preview_configuration(main={"size": (int(size[0]), int(size[1]))})
                        self.picam.configure(cfg)
                        self.picam.start()
                        time.sleep(0.05)
                    except Exception:
                        pass
            # Autofoco: macro para barcode, continuo/norm para foodshot/ocr
            self._af_prepare_shot()
            # Captura JPEG
            self.picam.capture_file(path, format="jpeg", quality=self._jpeg_quality)
        except Exception:
            if not _ensure_pillow():
                return None
            img = self.grab_frame()
            if img is None:
                return None
            img.save(path, "JPEG", quality=self._jpeg_quality, optimize=True)
        return path

    # --- Autofoco helpers (opcionales) ---
    def _apply_af_defaults(self, mode: str) -> None:
        if _LC is None or not self.available() or self.picam is None:
            return
        try:
            ctrl = {"AfMode": _LC.AfModeEnum.Continuous}
            if mode == 'barcode' and hasattr(_LC, 'AfRangeEnum'):
                # Macro mejora códigos cercanos
                ctrl["AfRange"] = getattr(_LC, 'AfRangeEnum').Macro
            else:
                if hasattr(_LC, 'AfRangeEnum'):
                    ctrl["AfRange"] = getattr(_LC, 'AfRangeEnum').Normal
            self.picam.set_controls(ctrl)
        except Exception:
            pass

    def _af_prepare_shot(self) -> None:
        if _LC is None or not self.available() or self.picam is None:
            return
        try:
            # Pequeña activación del trigger de AF antes del disparo
            if hasattr(_LC, 'AfTrigger'):
                self.picam.set_controls({"AfTrigger": _LC.AfTrigger.Start})
                # Breve espera; ajusta por modo
                wait = 0.18 if self._mode == 'barcode' else 0.35
                time.sleep(wait)
        except Exception:
            pass
