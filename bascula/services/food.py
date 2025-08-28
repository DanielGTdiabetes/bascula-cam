"""
Lightweight stub for a future FoodService.

This exists to satisfy imports from the modern UI while we design
actual food lookup and nutrition logic. The API is intentionally tiny
and safe: it should never raise on construction or common calls.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Dict, Any


@dataclass
class FoodItem:
    name: str
    tags: List[str]
    portion_g: float
    per_portion: Dict[str, float]  # keys: kcal, carbs, protein, fat


class FoodService:
    """
    Minimal placeholder implementation used by the modern UI.

    Methods return safe defaults so the UI can render without a
    configured food database.
    """

    def __init__(self, db_path: Optional[str] = None):
        # In the future we could load a local DB/CSV here.
        self.db_path = db_path

    def guess_from_weight(self, grams: float) -> Optional[FoodItem]:
        """Return None for now; placeholder for ML/lookup by weight."""
        return None

    def search(self, query: str) -> List[FoodItem]:
        """
        Trivial search stub: returns a single demo item when query is non-empty.
        This keeps the UI stable without real data.
        """
        q = (query or "").strip()
        if not q:
            return []
        demo = FoodItem(
            name=q.title(),
            tags=["demo", "placeholder"],
            portion_g=100.0,
            per_portion={"kcal": 100.0, "carbs": 10.0, "protein": 10.0, "fat": 3.0},
        )
        return [demo]

    @staticmethod
    def to_dict(item: FoodItem) -> Dict[str, Any]:
        """Helper to convert FoodItem to a plain dict expected by UI panels."""
        return {
            "name": item.name,
            "tags": list(item.tags),
            "portion_g": float(item.portion_g),
            "per_portion": {
                "kcal": float(item.per_portion.get("kcal", 0.0)),
                "carbs": float(item.per_portion.get("carbs", 0.0)),
                "protein": float(item.per_portion.get("protein", 0.0)),
                "fat": float(item.per_portion.get("fat", 0.0)),
            },
        }

