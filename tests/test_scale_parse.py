import math

from bascula.core.scale_serial import parse_weight_line


def assert_close(a: float, b: float, tol: float = 1e-3):
    assert math.isclose(a, b, abs_tol=tol)


def test_parse_simple_grams():
    grams, stable = parse_weight_line("0.00 g")
    assert_close(grams, 0.0)
    assert stable is None


def test_parse_spaces():
    grams, _ = parse_weight_line(" 123.4 g\n")
    assert_close(grams, 123.4)


def test_parse_stable_prefix():
    grams, stable = parse_weight_line("ST,GS, 0.50 g")
    assert_close(grams, 0.5)
    assert stable is True


def test_parse_kilograms():
    grams, _ = parse_weight_line("W: 1.234 kg")
    assert_close(grams, 1234.0)


def test_parse_compact():
    grams, _ = parse_weight_line("+000123g")
    assert_close(grams, 123.0)


def test_parse_pounds():
    grams, stable = parse_weight_line("US,NT,+1.00 lb")
    assert_close(grams, 453.59237)
    assert stable is False
