from __future__ import annotations
from typing import Optional, List

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

