from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict


@dataclass
class SessionItem:
    name: str
    grams: float
    carbs_g: float
    kcal: float
    protein_g: float
    fat_g: float
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
        total = {"grams": 0.0, "carbs_g": 0.0, "kcal": 0.0, "protein_g": 0.0, "fat_g": 0.0}
        for it in self.items:
            total["grams"] += float(it.grams or 0.0)
            total["carbs_g"] += float(it.carbs_g or 0.0)
            total["kcal"] += float(it.kcal or 0.0)
            total["protein_g"] += float(it.protein_g or 0.0)
            total["fat_g"] += float(it.fat_g or 0.0)
        return total
