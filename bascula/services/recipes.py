from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from bascula.domain import recipes as domain_recipes

_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}\s*$")
_CODE_FENCE_RE = re.compile(r"```(?:json)?|```", re.IGNORECASE)
_NUMBER_KEYS = ("grams", "kcal", "carbs", "protein", "fat")
_TEXT_KEYS = (
    "text",
    "step",
    "description",
    "desc",
    "instruction",
    "instructions",
    "contenido",
    "paso",
)
_TIMER_KEYS = (
    "timer_s",
    "timer",
    "seconds",
    "duration",
    "duration_s",
    "time",
    "duracion",
    "duracion_s",
)

_DUMMY_BASE = {
    "title": "Ensalada de pollo sencilla",
    "servings": 2,
    "steps": [
        {"text": "Corta la pechuga de pollo en tiras finas y saltéala hasta que esté dorada."},
        {"text": "Lava y seca la lechuga, el pepino y los tomates; mezcla en un bol grande."},
        {"text": "Añade el pollo, aliña con aceite de oliva y zumo de limón, mezcla y sirve."},
    ],
    "ingredients": [
        {"name": "Pechuga de pollo cocida", "grams": 220, "kcal": 360, "carbs": 0, "protein": 66, "fat": 8},
        {"name": "Lechuga romana", "grams": 120, "kcal": 20, "carbs": 4, "protein": 2, "fat": 0},
        {"name": "Pepino", "grams": 100, "kcal": 12, "carbs": 3, "protein": 1, "fat": 0},
        {"name": "Tomate cherry", "grams": 120, "kcal": 24, "carbs": 5, "protein": 1, "fat": 0},
        {"name": "Aceite de oliva virgen extra", "grams": 20, "kcal": 178, "carbs": 0, "protein": 0, "fat": 20},
        {"name": "Zumo de limón", "grams": 20, "kcal": 6, "carbs": 2, "protein": 0, "fat": 0},
    ],
    "tts": "Ensalada de pollo lista para servir.",
}


def _ensure_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _parse_timer_to_seconds(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            seconds = int(value)
        else:
            text = str(value).strip().lower()
            if not text:
                return None
            text = text.replace("segundos", "s").replace("seg", "s")
            text = text.replace("secs", "s").replace("seconds", "s")
            if ":" in text:
                parts = text.split(":")
                total = 0
                for part in parts:
                    total = total * 60 + int(part or 0)
                seconds = total
            else:
                match = re.search(r"(\d+)", text)
                if not match:
                    return None
                seconds = int(match.group(1))
        if seconds < 0:
            return None
        return seconds
    except Exception:
        return None


def _coerce_step(value: Any) -> Dict[str, Any]:
    text = ""
    timer: Optional[int] = None

    if isinstance(value, dict):
        for key in _TEXT_KEYS:
            if key in value and value.get(key) not in (None, ""):
                text = str(value.get(key)).strip()
                break
        else:
            text = ""
        for key in _TIMER_KEYS:
            if key in value:
                timer = _parse_timer_to_seconds(value.get(key))
                if timer is not None:
                    break
    else:
        text = str(value or "").strip()

    if not text:
        text = ""
    step: Dict[str, Any] = {"text": text}
    if timer is not None:
        step["timer_s"] = timer
    return step


def _coerce_steps(seq: Any) -> List[Dict[str, Any]]:
    if seq is None:
        return []
    if not isinstance(seq, (list, tuple)):
        seq = [seq]
    steps: List[Dict[str, Any]] = []
    for item in seq:
        step = _coerce_step(item)
        if step.get("text"):
            steps.append(step)
    return steps


def _parse_json_like(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict):
        return dict(payload)
    text = str(payload or "").strip()
    if not text:
        return {}
    text = _CODE_FENCE_RE.sub("", text).strip()
    text = re.sub(r",\s*(\]|\})", r"\1", text)
    try:
        return json.loads(text)
    except Exception:
        pass
    match = _JSON_BLOCK_RE.search(text)
    if match:
        snippet = match.group(0)
        try:
            return json.loads(snippet)
        except Exception:
            return {}
    return {}


def _sanitize_recipe(raw: Dict[str, Any], requested_servings: int) -> Dict[str, Any]:
    servings = max(1, int(requested_servings or 1))
    out: Dict[str, Any] = {
        "title": str(raw.get("title") or "Receta casera"),
        "servings": servings,
    }
    try:
        srv = int(raw.get("servings") or servings)
        if srv > 0:
            out["servings"] = srv
    except Exception:
        pass

    steps_raw = raw.get("steps")
    steps = _coerce_steps(steps_raw)
    if not steps:
        steps = [
            {"text": "Prepara los ingredientes."},
            {"text": "Mezcla/cocina y sirve."},
        ]
    out["steps"] = steps

    totals = {k: 0.0 for k in _NUMBER_KEYS}
    ingredients: List[Dict[str, Any]] = []
    for item in raw.get("ingredients") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        ing = {"name": name}
        for key in _NUMBER_KEYS:
            ing[key] = _ensure_float(item.get(key))
            totals[key] += ing[key]
        ingredients.append(ing)
    out["ingredients"] = ingredients

    provided_totals = raw.get("totals") or {}
    for key in _NUMBER_KEYS:
        if provided_totals.get(key) not in (None, ""):
            totals[key] = _ensure_float(provided_totals.get(key))
    if ingredients and not any(totals.values()):
        for key in _NUMBER_KEYS:
            totals[key] = sum(float(ing[key]) for ing in ingredients)
    out["totals"] = {key: round(totals[key], 2) for key in _NUMBER_KEYS}

    out["tts"] = str(raw.get("tts") or out["title"])
    return out


def _dummy_recipe(servings: int) -> Dict[str, Any]:
    servings = max(1, int(servings or 1))
    factor = servings / float(_DUMMY_BASE["servings"] or 1)
    ingredients: List[Dict[str, Any]] = []
    totals = {k: 0.0 for k in _NUMBER_KEYS}
    for item in _DUMMY_BASE["ingredients"]:
        scaled = {"name": item["name"]}
        for key in _NUMBER_KEYS:
            value = round(item[key] * factor, 2)
            scaled[key] = value
            totals[key] += value
        ingredients.append(scaled)
    totals = {k: round(v, 2) for k, v in totals.items()}
    return {
        "title": _DUMMY_BASE["title"],
        "servings": servings,
        "steps": [dict(step) for step in _DUMMY_BASE["steps"]],
        "ingredients": ingredients,
        "totals": totals,
        "tts": _DUMMY_BASE["tts"],
    }


def _request_openai(prompt: str, servings: int) -> Dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {}
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    user_prompt = (
        "Genera una receta en JSON con los campos title, servings, steps, ingredients, totals y tts. "
        f"Quiero una receta basada en: {prompt or 'receta sencilla'}. "
        f"Debe rendir exactamente {servings} raciones. "
        "Cada elemento de ingredients debe incluir name, grams, kcal, carbs, protein y fat numéricos. "
        "Los pasos deben ser oraciones cortas en español. Responde solo con JSON válido."
    )
    messages = [
        {"role": "system", "content": "Responde solo con JSON válido siguiendo el esquema indicado."},
        {"role": "user", "content": user_prompt},
    ]
    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=api_key)
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.4,
                max_tokens=800,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content if response.choices else ""
            return _parse_json_like(content)
        except Exception:
            response = client.responses.create(
                model=model,
                input=messages,
                response_format={"type": "json_object"},
            )
            content = ""
            try:
                if getattr(response, "output", None):
                    first = response.output[0]
                    if getattr(first, "content", None):
                        content = first.content[0].text  # type: ignore[assignment]
            except Exception:
                content = getattr(response, "output_text", "")
            return _parse_json_like(content)
    except Exception:
        pass

    try:
        import openai  # type: ignore

        openai.api_key = api_key
        response = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            temperature=0.4,
            max_tokens=800,
        )
        content = response.choices[0].message["content"] if response.choices else ""
        return _parse_json_like(content)
    except Exception:
        return {}


def generate_recipe(prompt: str, servings: int = 2) -> Dict[str, Any]:
    prompt = (prompt or "").strip()
    servings = max(1, int(servings or 1))
    raw = _request_openai(prompt, servings)
    if raw:
        try:
            sanitized = _sanitize_recipe(raw, servings)
            return sanitized
        except Exception:
            pass
    return _dummy_recipe(servings)


def save_recipe(recipe: Dict[str, Any]) -> None:
    domain_recipes.save_recipe(recipe)


def load_recipe(recipe_id: str):
    return domain_recipes.load_recipe(recipe_id)


def list_recipes(limit: int = 50) -> List[Dict[str, Any]]:
    return domain_recipes.list_recipes(limit)


def delete_recipe(recipe_id: str) -> bool:
    return domain_recipes.delete_recipe(recipe_id)


if __name__ == "__main__":
    print(json.dumps(generate_recipe("ensalada de pollo", 2), ensure_ascii=False, indent=2))
