from __future__ import annotations
from typing import Optional, List, Callable

try:
    # Optional import for CameraService typing
    from bascula.services.camera import CameraService  # type: ignore
except Exception:
    CameraService = None  # type: ignore

try:
    from pyzbar.pyzbar import decode
    from PIL import Image
except Exception:  # pragma: no cover
    decode = None
    Image = None


def decode_image(pil_image) -> List[str]:
    """Return decoded barcode strings from a PIL image. Empty if not available."""
    if decode is None:
        return []


def scan(camera: "CameraService", timeout_s: int = 8, cancel_cb: Optional[Callable[[], bool]] = None) -> Optional[str]:
    """Escanea usando frames de la cámara durante `timeout_s` segundos.

    - Bloqueante; usarlo desde un hilo. Devuelve el primer código leído o None.
    - `cancel_cb` si devuelve True aborta de inmediato.
    """
    import time as _t
    if camera is None or not getattr(camera, 'available', lambda: False)():
        return None
    t0 = _t.time(); deadline = t0 + max(1, int(timeout_s))
    try:
        if hasattr(camera, 'set_mode'):
            try:
                camera.set_mode('barcode')
            except Exception:
                pass
    except Exception:
        pass
    while _t.time() < deadline:
        if cancel_cb and cancel_cb():
            return None
        try:
            img = getattr(camera, 'grab_frame', lambda: None)()
            if img is not None:
                codes = decode_image(img)
                if codes:
                    return codes[0]
        except Exception:
            pass
        _t.sleep(0.2)
    return None
    try:
        res = decode(pil_image)
        out = []
        for r in res:
            try:
                out.append(r.data.decode('utf-8'))
            except Exception:
                pass
        return out
    except Exception:
        return []
