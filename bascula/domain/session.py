from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Optional, List, Dict


@dataclass
class SessionItem:
    name: str
    grams: float
    carbs_g: float
    kcal: float
    protein_g: float
    fat_g: float
    fiber_g: float = 0.0
    gi: Optional[int] = None
    source: str = "off|vision|gpt|manual"


@dataclass
class WeighSession:
    items: List[SessionItem] = field(default_factory=list)

    def add(self, it: SessionItem) -> None:
        self.items.append(it)

    def remove(self, index: int) -> None:
        if 0 <= index < len(self.items):
            self.items.pop(index)

    def clear(self) -> None:
        self.items.clear()

    def totals(self) -> Dict[str, float]:
        total = {
            "grams": 0.0,
            "carbs_g": 0.0,
            "kcal": 0.0,
            "protein_g": 0.0,
            "fat_g": 0.0,
            "fiber_g": 0.0,
        }
        for it in self.items:
            total["grams"] += _number(it.grams)
            total["carbs_g"] += _number(it.carbs_g)
            total["kcal"] += _number(it.kcal)
            total["protein_g"] += _number(it.protein_g)
            total["fat_g"] += _number(it.fat_g)
            total["fiber_g"] += _number(getattr(it, "fiber_g", 0.0))
        return total


def _number(value: object) -> float:
    try:
        num = float(value)
    except Exception:
        return 0.0
    if not math.isfinite(num):
        return 0.0
    return num


__all__ = ["SessionItem", "WeighSession", "_number"]
