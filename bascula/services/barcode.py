from __future__ import annotations
from typing import Optional, List, Callable

try:
    # Optional import for CameraService typing
    from bascula.services.camera import CameraService  # type: ignore
except Exception:
    CameraService = None  # type: ignore

try:
    from pyzbar.pyzbar import decode
except Exception:  # pragma: no cover
    decode = None

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None


def decode_image(pil_image) -> List[str]:
    """Return decoded barcode strings from a PIL image or numpy array."""

    if decode is None or pil_image is None:
        return []

    img = pil_image

    # Some camera backends provide numpy arrays instead of PIL images.  Convert
    # them on the fly when Pillow is available.  The conversion is best-effort;
    # failures simply skip decoding so the caller can retry with another frame.
    if Image is not None and not isinstance(img, Image.Image):  # type: ignore[attr-defined]
        try:
            img = Image.fromarray(img)
        except Exception:
            return []

    try:
        results = decode(img)
    except Exception:
        return []

    out: List[str] = []
    for item in results or []:
        try:
            out.append(item.data.decode("utf-8"))
        except Exception:
            continue
    return out


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
