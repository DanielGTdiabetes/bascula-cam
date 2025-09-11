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


# --- Favorites + Save + Suggest ---

def save_food(item: Dict[str, Any]) -> bool:
    """Guarda/actualiza un alimento en foods.json (no JSONL) con clave id o name.

    Estructura mínima: {id?, name, kcal, carbs, protein, fat, favorite?}
    """
    try:
        p = _db_path(); p.parent.mkdir(parents=True, exist_ok=True)
        data: List[Dict[str, Any]] = []
        try:
            if p.exists():
                data = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            data = []
        iid = str(item.get('id') or item.get('name') or '').strip()
        if not iid:
            return False
        out = []; seen = False
        for d in data:
            if str(d.get('id') or d.get('name')) == iid:
                out.append({
                    'id': iid,
                    'name': item.get('name') or d.get('name') or iid,
                    'kcal': float(item.get('kcal', d.get('kcal', 0))),
                    'carbs': float(item.get('carbs', d.get('carbs', 0))),
                    'protein': float(item.get('protein', d.get('protein', 0))),
                    'fat': float(item.get('fat', d.get('fat', 0))),
                    'favorite': bool(item.get('favorite', d.get('favorite', False))),
                })
                seen = True
            else:
                out.append(d)
        if not seen:
            out.append({
                'id': iid, 'name': item.get('name') or iid,
                'kcal': float(item.get('kcal', 0)), 'carbs': float(item.get('carbs', 0)),
                'protein': float(item.get('protein', 0)), 'fat': float(item.get('fat', 0)),
                'favorite': bool(item.get('favorite', False)),
            })
        p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
        return True
    except Exception:
        return False


def toggle_favorite(food_id: str, value: Optional[bool] = None) -> bool:
    try:
        p = _db_path()
        if not p.exists():
            return False
        data = json.loads(p.read_text(encoding='utf-8'))
        out = []; changed = False
        for d in data:
            if str(d.get('id') or d.get('name')) == str(food_id):
                fav = bool(d.get('favorite', False)) if value is None else bool(value)
                if value is None:
                    fav = not bool(d.get('favorite', False))
                d['favorite'] = fav; changed = True
            out.append(d)
        if changed:
            p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
        return changed
    except Exception:
        return False


def suggest(query: str, limit: int = 20, prefer_favorites: bool = True) -> List[Food]:
    foods = load_foods()
    q = (query or '').strip().lower()
    # Load favorite flags from JSON (if present)
    favs: Dict[str, bool] = {}
    try:
        data = json.loads(_db_path().read_text(encoding='utf-8'))
        for d in data:
            fid = str(d.get('id') or d.get('name'))
            if fid:
                favs[fid] = bool(d.get('favorite', False))
    except Exception:
        pass
    scored: List[tuple[float, Food]] = []
    for f in foods:
        name = f.name.lower()
        score = 0.0
        if not q:
            score = 0.1
        else:
            if q in name:
                score = 1.0 if name.startswith(q) else 0.6
        if prefer_favorites and favs.get(f.id) or favs.get(f.name):
            score += 0.5
        scored.append((score, f))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [f for _, f in scored[:max(1, int(limit))]]


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
