import pytest

from bascula.services import treatments


@pytest.mark.parametrize(
    "grams, target, current, isf, ratio, expected_units, expected_peak",
    [
        (50, 110, 200, 45, 10, 7.0, 60),
        (10, 100, 90, 40, 12, 0.83, 45),
        (70, 110, 160, 50, 15, 5.67, 90),
    ],
)
def test_calc_bolus_common_scenarios(
    grams, target, current, isf, ratio, expected_units, expected_peak
):
    calc = treatments.calc_bolus(grams, target, current, isf, ratio)

    assert calc.bolus == pytest.approx(expected_units, rel=1e-3)
    assert calc.peak_time_min == expected_peak


def test_calc_bolus_never_negative():
    calc = treatments.calc_bolus(grams_carbs=-10, target_bg=110, current_bg=70, isf=100, ratio=15)

    assert calc.bolus == 0.0
    assert calc.peak_time_min == 45
