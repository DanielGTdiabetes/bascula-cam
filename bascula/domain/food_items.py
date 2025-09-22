"""Dataclasses representing recognized food entries."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import time
import uuid


@dataclass
class FoodItem:
    id: str
    name: str
    weight_g: float
    carbs_g: Optional[float]
    protein_g: Optional[float]
    fat_g: Optional[float]
    gi: Optional[int]
    source: str
    ts: float

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex

    @classmethod
    def from_ai(cls, weight_g: float, data: dict) -> "FoodItem":
        name = str(data.get("name") or "Desconocido").strip() or "Desconocido"
        def _num(key: str):
            value = data.get(key)
            try:
                return round(float(value), 2)
            except Exception:
                return None

        def _gi() -> Optional[int]:
            value = data.get("gi")
            try:
                if value in (None, ""):
                    return None
                return max(0, min(110, int(value)))
            except Exception:
                return None

        return cls(
            id=data.get("id") or cls.new_id(),
            name=name,
            weight_g=float(weight_g or 0.0),
            carbs_g=_num("carbs_g"),
            protein_g=_num("protein_g"),
            fat_g=_num("fat_g"),
            gi=_gi(),
            source=str(data.get("source") or "unknown"),
            ts=float(data.get("ts") or time.time()),
        )


__all__ = ["FoodItem"]
