from __future__ import annotations
from dataclasses import dataclass


@dataclass
class TreatmentCalc:
    bolus: float
    peak_time_min: int


def calc_bolus(grams_carbs: float, target_bg: int, current_bg: int, isf: float, ratio: float) -> TreatmentCalc:
    """Cálculo simple de bolo: carbs/ratio + (current-target)/isf.
    Returns bolus and a rough time-to-peak (mins)."""
    carbs_bolus = max(0.0, float(grams_carbs) / max(1e-6, float(ratio)))
    correction = max(0.0, (float(current_bg) - float(target_bg)) / max(1e-6, float(isf)))
    bolus = round(carbs_bolus + correction, 2)
    # Rough heuristics for peak time
    peak = 60  # default
    if grams_carbs > 60:
        peak = 90
    elif grams_carbs < 20:
        peak = 45
    return TreatmentCalc(bolus=bolus, peak_time_min=peak)

