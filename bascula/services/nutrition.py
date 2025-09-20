from __future__ import annotations

from typing import Dict

from bascula.domain.gi_index import lookup_gi
from bascula.domain.session import SessionItem


def make_item(name: str, grams: float, per100g: Dict[str, float], source: str = "off") -> SessionItem:
    ratio = max(0.0, float(grams)) / 100.0
    carbs = (per100g.get("carbs") or per100g.get("carbohydrates") or 0.0) * ratio
    kcal = (per100g.get("kcal") or 0.0) * ratio
    protein = (per100g.get("protein") or 0.0) * ratio
    fat = (per100g.get("fat") or 0.0) * ratio
    gi = lookup_gi(name)
    return SessionItem(
        name=name,
        grams=float(grams or 0.0),
        carbs_g=float(carbs or 0.0),
        kcal=float(kcal or 0.0),
        protein_g=float(protein or 0.0),
        fat_g=float(fat or 0.0),
        gi=gi,
        source=str(source or "manual"),
    )
