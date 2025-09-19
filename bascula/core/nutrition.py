"""Nutrition helper utilities."""
from __future__ import annotations

from typing import Dict, Iterable


def compute_totals(items: Iterable[dict]) -> Dict[str, float]:
    totals = {"carbs": 0.0, "kcal": 0.0, "protein": 0.0, "fat": 0.0, "weight": 0.0}
    for item in items:
        grams = float(item.get("grams", 0.0))
        per_100g = item.get("per_100g") or {}
        totals["weight"] += grams
        factor = grams / 100.0
        for key in ("carbs", "kcal", "protein", "fat"):
            try:
                value = float(per_100g.get(key, 0.0)) * factor
            except (TypeError, ValueError):
                value = 0.0
            totals[key] += value
    return {key: round(value, 1) for key, value in totals.items()}


__all__ = ["compute_totals"]
