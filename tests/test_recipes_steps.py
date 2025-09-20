from bascula.services import recipes as recipe_service


def test_coerce_steps_mixed_entries():
    raw_steps = [
        "Cortar",
        {"text": "Saltear", "timer": 60},
        {"step": "Servir"},
    ]
    result = recipe_service._coerce_steps(raw_steps)
    assert result == [
        {"text": "Cortar"},
        {"text": "Saltear", "timer_s": 60},
        {"text": "Servir"},
    ]


def test_sanitize_recipe_fallback_steps():
    sanitized = recipe_service._sanitize_recipe({"steps": None, "ingredients": []}, 2)
    assert sanitized["steps"] == [
        {"text": "Prepara los ingredientes."},
        {"text": "Mezcla/cocina y sirve."},
    ]


def test_coerce_steps_timer_string():
    result = recipe_service._coerce_steps([
        {"text": "Hornear", "timer": "90s"},
    ])
    assert result == [{"text": "Hornear", "timer_s": 90}]
