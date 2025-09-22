import json

import pytest

from bascula.services import nutrition_ai


@pytest.mark.parametrize(
    "text, expected",
    [
        (
            json.dumps(
                {
                    "name": "Manzana",
                    "carbs_g": "12.345",
                    "protein_g": 0.8,
                    "fat_g": "0.22",
                    "gi": 120,
                    "confidence": 87,
                    "source": "openai",
                }
            ),
            {
                "name": "Manzana",
                "carbs_g": 12.35,
                "protein_g": 0.8,
                "fat_g": 0.22,
                "gi": 110,
                "confidence": 0.87,
                "source": "openai",
            },
        ),
        (
            json.dumps(
                {
                    "name": "  ",
                    "carbs_g": None,
                    "protein_g": "nope",
                    "fat_g": "??",
                    "gi": "??",
                    "confidence": None,
                }
            ),
            {
                "name": "",
                "carbs_g": None,
                "protein_g": None,
                "fat_g": None,
                "gi": None,
                "confidence": None,
                "source": "ai_incomplete",
            },
        ),
    ],
)
def test_parse_response_normalizes_values(text, expected):
    result = nutrition_ai._parse_response(text)

    assert result == expected


def test_parse_response_invalid_json_returns_default():
    result = nutrition_ai._parse_response("{not-json}")

    assert result["name"] == "Desconocido"
    assert result["source"] == "ai_incomplete"
    for macro in ("carbs_g", "protein_g", "fat_g", "gi", "confidence"):
        assert result[macro] is None
