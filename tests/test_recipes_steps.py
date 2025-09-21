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


def test_generate_recipe_without_api_returns_dummy(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    recipe = recipe_service.generate_recipe("ensalada", servings=3)
    assert recipe["servings"] == 3
    assert recipe["ingredients"]
    assert recipe["steps"]


def test_generate_recipe_sanitizes_remote_payload(monkeypatch):
    def fake_request(prompt, servings):
        assert prompt == "pollo"
        assert servings == 2
        return {
            "title": "Pollo test",
            "servings": 4,
            "steps": [
                {"instruction": "Preparar", "timer": "01:30"},
                "Servir",
            ],
            "ingredients": [
                {"name": "Pollo", "grams": "100", "kcal": "200"},
                {"name": "Aceite", "grams": 10, "kcal": 90},
            ],
            "totals": {"grams": "110"},
            "tts": "Listo",
        }

    monkeypatch.setattr(recipe_service, "_request_openai", fake_request)
    recipe = recipe_service.generate_recipe("pollo", servings=2)
    assert recipe["title"] == "Pollo test"
    assert recipe["servings"] == 4
    assert recipe["steps"][0]["timer_s"] == 90
    assert recipe["totals"]["grams"] == 110.0
