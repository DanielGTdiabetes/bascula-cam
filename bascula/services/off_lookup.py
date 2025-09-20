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
    # Prefer OFF v2; keep tolerant handling
    url = f"https://world.openfoodfacts.org/api/v2/product/{code}.json"
    try:
        r = requests.get(url, timeout=4)
        if 200 <= getattr(r, "status_code", 0) < 300:
            data = r.json()
            # v2 returns product in 'product'; status=1 means found in v0; be tolerant
            if (data or {}).get("status") == 1 or (data or {}).get("product"):
                return (data.get("product") or data)
        return None
    except Exception:
        return None


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def product_to_per100g(product: Dict[str, Any]) -> Dict[str, float]:
    """Normaliza un producto OFF a macros por 100 g."""

    if not isinstance(product, dict):
        return {}

    nutr = product.get("nutriments") or {}
    if not isinstance(nutr, dict):
        return {}

    def pick(*keys: str) -> Optional[float]:
        for key in keys:
            if key in nutr:
                val = _to_float(nutr.get(key))
                if val is not None:
                    return val
            alt = key.replace("-", "_")
            if alt in nutr:
                val = _to_float(nutr.get(alt))
                if val is not None:
                    return val
        return None

    per100: Dict[str, float] = {}

    carbs = pick("carbohydrates_100g", "carbs_100g", "carbohydrate_100g")
    if carbs is not None:
        per100["carbs"] = carbs

    kcal = pick("energy-kcal_100g", "energy_kcal_100g", "energy-kcal_value")
    if kcal is None:
        energy_kj = pick("energy_100g", "energy-kj_100g", "energy-kj_value")
        if energy_kj is not None:
            kcal = energy_kj / 4.184
    if kcal is not None:
        per100["kcal"] = kcal

    protein = pick("proteins_100g", "protein_100g")
    if protein is not None:
        per100["protein"] = protein

    fat = pick("fat_100g", "fats_100g")
    if fat is not None:
        per100["fat"] = fat

    return per100
