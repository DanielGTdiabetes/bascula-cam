"""Nutrition orchestration for the food recognition mode."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional

log = logging.getLogger(__name__)


@dataclass
class FoodEntry:
    name: str
    weight_g: float
    carbs_g: float
    protein_g: float
    fat_g: float
    glycemic_index: float
    source: str = "manual"


@dataclass
class Totals:
    weight_g: float = 0.0
    carbs_g: float = 0.0
    protein_g: float = 0.0
    fat_g: float = 0.0


class NutritionService:
    """Manage recognised food items and aggregate totals."""

    def __init__(self) -> None:
        self._entries: List[FoodEntry] = []
        self._listeners: List[Callable[[List[FoodEntry], Totals], None]] = []

    # ------------------------------------------------------------------
    def recognise(self, description: str, weight_g: float) -> FoodEntry:
        """Return a fake recognition result when remote AI is unavailable."""

        macros = _lookup_reference(description)
        entry = FoodEntry(
            name=description.title(),
            weight_g=weight_g,
            carbs_g=macros["carbs"] * weight_g / 100.0,
            protein_g=macros["protein"] * weight_g / 100.0,
            fat_g=macros["fat"] * weight_g / 100.0,
            glycemic_index=macros["gi"],
            source="local",
        )
        self.add_entry(entry)
        return entry

    def lookup_barcode(self, barcode: str, weight_g: float) -> FoodEntry:
        macros = _lookup_reference(barcode)
        entry = FoodEntry(
            name=f"Producto {barcode}",
            weight_g=weight_g,
            carbs_g=macros["carbs"] * weight_g / 100.0,
            protein_g=macros["protein"] * weight_g / 100.0,
            fat_g=macros["fat"] * weight_g / 100.0,
            glycemic_index=macros["gi"],
            source="barcode",
        )
        self.add_entry(entry)
        return entry

    # ------------------------------------------------------------------
    def add_entry(self, entry: FoodEntry) -> None:
        self._entries.append(entry)
        self._notify()

    def remove_entry(self, index: int) -> None:
        if 0 <= index < len(self._entries):
            del self._entries[index]
            self._notify()

    def clear(self) -> None:
        self._entries.clear()
        self._notify()

    def totals(self) -> Totals:
        total = Totals()
        for entry in self._entries:
            total.weight_g += entry.weight_g
            total.carbs_g += entry.carbs_g
            total.protein_g += entry.protein_g
            total.fat_g += entry.fat_g
        return total

    def entries(self) -> Iterable[FoodEntry]:
        return list(self._entries)

    def subscribe(self, callback: Callable[[List[FoodEntry], Totals], None]) -> None:
        self._listeners.append(callback)

    def _notify(self) -> None:
        totals = self.totals()
        for listener in list(self._listeners):
            try:
                listener(list(self._entries), totals)
            except Exception:  # pragma: no cover - defensive
                log.exception("Nutrition listener crashed")


def _lookup_reference(key: str) -> Dict[str, float]:
    key = (key or "").lower()
    reference: Dict[str, Dict[str, float]] = {
        "manzana": {"carbs": 14.0, "protein": 0.3, "fat": 0.2, "gi": 38.0},
        "pollo": {"carbs": 0.0, "protein": 27.0, "fat": 3.6, "gi": 0.0},
        "arroz": {"carbs": 28.0, "protein": 2.7, "fat": 0.3, "gi": 73.0},
    }
    if key in reference:
        return reference[key]
    return {"carbs": 10.0, "protein": 2.0, "fat": 1.0, "gi": 50.0}


__all__ = ["NutritionService", "FoodEntry", "Totals"]
