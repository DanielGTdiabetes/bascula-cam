from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
from typing import List


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

