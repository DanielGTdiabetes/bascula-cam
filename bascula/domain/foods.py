from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json, time
from typing import List, Dict, Any, Optional


@dataclass
class Food:
    id: str
    name: str
    kcal: float
    carbs: float
    protein: float
    fat: float


def _db_path() -> Path:
    return Path.home() / '.config' / 'bascula' / 'foods.json'


def load_foods() -> List[Food]:
    p = _db_path()
    if not p.exists():
        return [
            Food('apple', 'Manzana', 52, 14, 0.3, 0.2),
            Food('banana', 'Banana', 96, 23, 1.2, 0.3),
            Food('rice_cooked', 'Arroz cocido', 130, 28, 2.4, 0.2),
        ]
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
        out = []
        for d in data:
            out.append(Food(
                d.get('id') or d.get('name'),
                d.get('name', ''),
                float(d.get('kcal', 0)),
                float(d.get('carbs', 0)),
                float(d.get('protein', 0)),
                float(d.get('fat', 0)),
            ))
        return out
    except Exception:
        return []


def search(query: str, foods: List[Food]) -> List[Food]:
    q = (query or '').strip().lower()
    if not q:
        return foods[:]
    return [f for f in foods if q in f.name.lower()]


# --- OFF integration (append-only JSONL) ---

def _db_jsonl_path() -> Path:
    return Path.home() / ".config" / "bascula" / "foods.jsonl"


def upsert_from_off(product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Insert or update a food entry from an OpenFoodFacts product.

    Writes to ~/.config/bascula/foods.jsonl with source="off" and a minimal structure:
    { id, name, source, barcode, brands, macros_100: {kcal, carbs, protein, fat}, ts }
    Returns the stored dict or None on invalid input.
    """
    if not isinstance(product, dict):
        return None

    code = (product.get("code") or product.get("_id") or product.get("id") or "").strip()
    name = (product.get("product_name") or product.get("generic_name") or product.get("product_name_es") or "").strip()
    brands = (product.get("brands") or "").strip()
    nutr = product.get("nutriments") or {}

    def _num(x) -> float:
        try:
            return float(x)
        except Exception:
            return 0.0

    kcal = _num(nutr.get("energy-kcal_100g") or nutr.get("energy-kcal_value"))
    carbs = _num(nutr.get("carbohydrates_100g") or nutr.get("carbohydrates_value"))
    protein = _num(nutr.get("proteins_100g") or nutr.get("proteins_value"))
    fat = _num(nutr.get("fat_100g") or nutr.get("fat_value"))

    if not code and not name:
        return None

    entry = {
        "id": code or name,
        "name": name or code,
        "source": "off",
        "barcode": code,
        "brands": brands,
        "macros_100": {
            "kcal": kcal,
            "carbs": carbs,
            "protein": protein,
            "fat": fat,
        },
        "ts": time.time(),
    }

    path = _db_jsonl_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    # Upsert: read existing lines and rewrite without previous same id/barcode from source off
    keep: List[str] = []
    try:
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    d = json.loads(line)
                except Exception:
                    keep.append(line)
                    continue
                if isinstance(d, dict) and d.get("source") == "off":
                    same = False
                    if code and (d.get("barcode") == code or d.get("id") == code):
                        same = True
                    elif name and d.get("name") == name:
                        same = True
                    if same:
                        # drop previous
                        continue
                keep.append(line)
    except Exception:
        keep = []

    try:
        body = "\n".join(keep + [json.dumps(entry, ensure_ascii=False)]) + "\n"
        path.write_text(body, encoding="utf-8")
    except Exception:
        # Best-effort only
        pass
    return entry

