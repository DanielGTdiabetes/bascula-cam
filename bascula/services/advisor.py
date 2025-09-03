# -*- coding: utf-8 -*-
"""
Asesor experimental de bolo (no es consejo médico).

Genera sugerencias textuales basadas en macros del plato y, opcionalmente,
estado/tendencia de glucosa. No calcula unidades de insulina.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class MealTotals:
    carbs: float
    protein: float
    fat: float
    kcal: float | None = None


def _pct(part: float, total: float) -> float:
    try:
        if total <= 0:
            return 0.0
        return max(0.0, min(100.0, 100.0 * part / total))
    except Exception:
        return 0.0


def _direction_arrow(direction: str | None) -> str:
    m = {
        'DoubleUp': '↑↑', 'SingleUp': '↑', 'FortyFiveUp': '↗',
        'Flat': '→', 'FortyFiveDown': '↘', 'SingleDown': '↓', 'DoubleDown': '↓↓'
    }
    return m.get((direction or '').strip(), '')


def recommend(meal: MealTotals, *, bg_mgdl: float | None = None, direction: str | None = None) -> str:
    """Devuelve un texto corto con sugerencias de timing/división del bolo.

    Política de seguridad: NO recomienda unidades. Mensaje enfocado a patrones
    (pre-bolo, división, prudencia) y SIEMPRE recuerda consultar al equipo médico.
    """
    c = max(0.0, float(meal.carbs))
    p = max(0.0, float(meal.protein))
    f = max(0.0, float(meal.fat))

    # Estimación simple de proporciones energéticas (aprox)
    kcal = (meal.kcal if meal.kcal and meal.kcal > 0 else 4*c + 4*p + 9*f)
    pct_c = _pct(4*c, kcal)
    pct_pf = _pct(4*p + 9*f, kcal)

    hints: list[str] = []

    # Composición del plato
    if c >= 60 or pct_c >= 55:
        hints.append("Hidratos altos → pre‑bolo 10–15 min.")
    else:
        hints.append("Hidratos moderados → timing prudente.")

    if f >= 30 or p >= 40 or pct_pf >= 45:
        hints.append("Grasa/proteína alta → dividir 60/40 en 1–2 h.")

    # Señales por glucosa actual/tendencia (si se facilita)
    if bg_mgdl is not None:
        arr = _direction_arrow(direction)
        if direction in ("SingleUp", "DoubleUp", "FortyFiveUp"):
            hints.append(f"BG {arr} → adelantar un poco el pre‑bolo.")
        elif direction in ("SingleDown", "DoubleDown", "FortyFiveDown"):
            hints.append(f"BG {arr} → prudencia/espera.")

    # Mensaje final con recordatorio de seguridad
    # Limitar a 2 frases para brevedad
    base = " ".join(hints[:2]) if hints else "Ajusta timing/división según tu experiencia."
    disclaimer = " (Experimental; no es consejo médico)"
    return base + disclaimer
