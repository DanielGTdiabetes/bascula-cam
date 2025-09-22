from __future__ import annotations

import io
import logging
import time
from typing import Callable, List, Optional

try:  # Optional import for CameraService typing
    from bascula.services.camera import CameraService  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    CameraService = None  # type: ignore

try:  # pragma: no cover - optional dependency
    from pyzbar.pyzbar import decode as _pyzbar_decode
except Exception:  # pragma: no cover - optional dependency
    _pyzbar_decode = None

try:  # pragma: no cover - optional dependency
    from PIL import Image as _PILImage
except Exception:  # pragma: no cover - optional dependency
    _PILImage = None

logger = logging.getLogger(__name__)


def _ensure_image(obj):
    """Best effort to obtain a Pillow image from ``obj``."""

    if obj is None or _PILImage is None:
        return None
    if isinstance(obj, _PILImage.Image):
        return obj
    try:
        return _PILImage.fromarray(obj)
    except Exception:
        return None


def _decode_pil_image(img) -> List[str]:
    if _pyzbar_decode is None or img is None:
        return []
    try:
        if img.mode not in ("L", "LA"):
            img = img.convert("L")
    except Exception:
        pass
    try:
        results = _pyzbar_decode(img)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("pyzbar decode falló: %s", exc)
        return []
    codes: List[str] = []
    for res in results or []:
        data = getattr(res, "data", b"")
        if isinstance(data, bytes):
            try:
                text = data.decode("utf-8").strip()
            except Exception:
                text = data.decode("latin-1", errors="ignore").strip()
            if text:
                codes.append(text)
        elif data:
            text = str(data).strip()
            if text:
                codes.append(text)
    return codes


def decode_image(image) -> List[str]:
    """Decode barcodes from a Pillow image or ndarray."""

    pil = _ensure_image(image)
    if pil is None:
        return []
    return _decode_pil_image(pil)


def decode_bytes(data: bytes) -> List[str]:
    """Decode barcode strings from raw image bytes."""

    if not data or _PILImage is None:
        return []
    try:
        with io.BytesIO(data) as buffer:
            img = _PILImage.open(buffer)
            img.load()
    except Exception:
        return []
    return _decode_pil_image(img)


def decode_snapshot(camera: "CameraService") -> Optional[str]:
    """Capture a snapshot and return the first decoded barcode."""

    if camera is None or not getattr(camera, "available", lambda: False)():
        return None
    jpeg: Optional[bytes] = None
    try:
        if hasattr(camera, "set_mode"):
            try:
                camera.set_mode("barcode")
            except Exception:
                pass
        if hasattr(camera, "capture_snapshot"):
            jpeg, _thumb = camera.capture_snapshot(timeout_s=4)
    except Exception as exc:  # pragma: no cover - hardware dependent
        logger.debug("snapshot barcode falló: %s", exc)
    if jpeg:
        codes = decode_bytes(jpeg)
        if codes:
            return codes[0]
    try:
        frame = getattr(camera, "grab_frame", lambda: None)()
    except Exception:
        frame = None
    codes = decode_image(frame)
    return codes[0] if codes else None


def scan(
    camera: "CameraService",
    timeout_s: int = 8,
    cancel_cb: Optional[Callable[[], bool]] = None,
    *,
    snapshot_fallback: bool = True,
) -> Optional[str]:
    """Scan barcodes using continuous frames from ``camera``."""

    if camera is None or not getattr(camera, "available", lambda: False)():
        return None

    deadline = time.time() + max(1, int(timeout_s))
    if hasattr(camera, "set_mode"):
        try:
            camera.set_mode("barcode")
        except Exception:
            pass

    while time.time() < deadline:
        if cancel_cb and cancel_cb():
            return None
        try:
            frame = getattr(camera, "grab_frame", lambda: None)()
        except Exception:
            frame = None
        codes = decode_image(frame)
        if codes:
            return codes[0]
        time.sleep(0.2)

    if snapshot_fallback:
        return decode_snapshot(camera)
    return None


__all__ = ["decode_image", "decode_bytes", "decode_snapshot", "scan"]
