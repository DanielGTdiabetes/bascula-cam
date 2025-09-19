from __future__ import annotations

import pytest

from bascula.ui.theme_classic import coerce_int


@pytest.mark.parametrize(
    "value, expected",
    [
        ("10", 10),
        (12.9, 12),
        (None, 7),
        (True, 7),
        ("abc", 7),
    ],
)
def test_coerce_int(value, expected) -> None:
    assert coerce_int(value, 7) == expected
