from __future__ import annotations
"""OpenFoodFacts lookup service.

fetch_off(barcode) -> dict | None
- Queries OFF public API for a given EAN/UPC barcode.
- Returns the product dict on success or None on errors/not found.
"""
import json
from typing import Optional, Dict, Any

try:
    import requests  # type: ignore
except Exception:
    requests = None


def fetch_off(barcode: str) -> Optional[Dict[str, Any]]:
    code = (str(barcode or "").strip())
    if not code:
        return None
    if requests is None:
        return None
    url = f"https://world.openfoodfacts.org/api/v0/product/{code}.json"
    try:
        r = requests.get(url, timeout=8)
        if 200 <= getattr(r, "status_code", 0) < 300:
            data = r.json()
            if (data or {}).get("status") == 1:
                return data.get("product") or None
        return None
    except Exception:
        return None

