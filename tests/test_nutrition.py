from __future__ import annotations

from bascula.core.nutrition import compute_totals


def test_compute_totals_rounding() -> None:
    items = [
        {"name": "manzana", "grams": 120, "per_100g": {"carbs": 11.4, "kcal": 52, "protein": 0.3, "fat": 0.2}},
        {"name": "yogur", "grams": 90, "per_100g": {"carbs": 4.7, "kcal": 61, "protein": 3.5, "fat": 3.3}},
    ]
    totals = compute_totals(items)
    assert totals["carbs"] == 17.9
    assert totals["kcal"] == 117.3
    assert totals["protein"] == 3.5
    assert totals["fat"] == 3.2
    assert totals["weight"] == 210.0
