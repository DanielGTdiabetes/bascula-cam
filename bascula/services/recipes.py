from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from bascula.domain.recipes import (
    new_id,
    save_recipe as _save,
    load_recipe as _load,
    list_recipes as _list,
)


def parse_recipe_json(text_or_json: Any) -> Dict[str, Any]:
    """Parse and sanitize a recipe JSON object or JSON string.

    - Tries strict JSON parsing; if it fails, attempts simple cleanup like
      removing code fences and trailing commas.
    - Guarantees presence of required fields with sane defaults.
    """
    data: Dict[str, Any]
    if isinstance(text_or_json, dict):
        data = dict(text_or_json)
    else:
        s = str(text_or_json or "").strip()
        # cleanup common patterns from LLMs
        s = re.sub(r"^```(json)?", "", s, flags=re.IGNORECASE | re.MULTILINE)
        s = re.sub(r"```$", "", s, flags=re.MULTILINE)
        s = s.strip()
        # remove trailing commas in objects/arrays
        s = re.sub(r",\s*(\]|\})", r"\1", s)
        try:
            data = json.loads(s)
        except Exception:
            # last resort: try to capture JSON block
            m = re.search(r"\{[\s\S]*\}\s*$", s)
            if m:
                try:
                    data = json.loads(m.group(0))
                except Exception:
                    data = {}
            else:
                data = {}

    # Sanitize fields
    out: Dict[str, Any] = {}
    out["title"] = str(data.get("title") or "Receta")
    try:
        out["servings"] = int(data.get("servings") or 2)
    except Exception:
        out["servings"] = 2
    # ingredients
    ings = []
    for it in (data.get("ingredients") or []):
        try:
            ings.append({
                "name": str(it.get("name") or ""),
                "qty": str(it.get("qty") or ""),
                "alt": list(it.get("alt") or []),
                "barcode": (str(it.get("barcode")).strip() if it.get("barcode") else None),
                "matched": bool(it.get("matched", False)),
            })
        except Exception:
            pass
    out["ingredients"] = ings
    # steps
    steps = []
    for st in (data.get("steps") or []):
        try:
            n = int(st.get("n") or (len(steps) + 1))
        except Exception:
            n = len(steps) + 1
        t = st.get("timer_s")
        try:
            t = int(t) if t is not None else None
            if t is not None and t < 0:
                t = None
        except Exception:
            t = None
        steps.append({
            "n": n,
            "text": str(st.get("text") or ""),
            "timer_s": t,
            "targets": list(st.get("targets") or []),
        })
    out["steps"] = steps
    out["notes"] = str(data.get("notes") or "")
    nps = data.get("nutrition_per_serving") or {}
    out["nutrition_per_serving"] = {
        "kcal": _num(nps.get("kcal")),
        "carbs": _num(nps.get("carbs")),
        "protein": _num(nps.get("protein")),
        "fat": _num(nps.get("fat")),
    }
    return out


def _num(v: Any) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def generate_recipe(query: str, servings: int = 2, api_key: Optional[str] = None) -> Dict[str, Any]:
    """Generate a recipe using ChatGPT if possible; otherwise fallback templates.

    - Returns a sanitized recipe dict with id and created_at, already saved.
    - Robust to offline/no-API conditions.
    """
    q = (query or "").strip()
    if not q:
        q = "Receta sencilla de pollo al curry"
    servings = int(servings or 2)

    recipe: Dict[str, Any] = {}

    # Try OpenAI if API key and library present
    if api_key and os.environ.get("NO_NET") != "1":
        try:
            import openai  # type: ignore
            client = openai.OpenAI(api_key=api_key) if hasattr(openai, 'OpenAI') else None
        except Exception:
            client = None
        if client is not None:
            prompt = (
                "Genera una receta paso a paso en JSON VALIDO sin comentarios ni texto extra, con ESTE ESQUEMA EXACTO: \n"
                "{\n"
                "  \"title\": \"...\", \"servings\": %d,\n"
                "  \"ingredients\":[{\"name\":\"...\",\"qty\":\"...\",\"alt\":[\"...\"]}],\n"
                "  \"steps\":[{\"n\":1,\"text\":\"...\",\"timer_s\":null,\"targets\":[\"...\"]}],\n"
                "  \"notes\":\"...\", \"nutrition_per_serving\":{\"kcal\":0,\"carbs\":0,\"protein\":0,\"fat\":0}\n"
                "}\n"
                f"Petición del usuario: {q}. Idioma: español."
            ) % servings
            try:
                # Compatible with both legacy and new SDKs
                resp = client.chat.completions.create(
                    model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                    messages=[
                        {"role": "system", "content": "Responde SOLO con JSON válido."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.7,
                    max_tokens=800,
                )
                txt = (resp.choices[0].message.content or "").strip()
                recipe = parse_recipe_json(txt)
            except Exception:
                recipe = {}

    # Fallback if no API or failure
    if not recipe:
        recipe = _fallback_template(q, servings)

    # Stamp id and created_at, then save
    recipe["id"] = new_id()
    try:
        import datetime as _dt
        recipe["created_at"] = _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    except Exception:
        recipe["created_at"] = ""
    _save(recipe)
    return recipe


def _fallback_template(query: str, servings: int) -> Dict[str, Any]:
    q = query.lower()
    if "curry" in q or "pollo" in q:
        return {
            "title": "Pollo al curry rápido",
            "servings": servings,
            "ingredients": [
                {"name": "Pechuga de pollo", "qty": "300 g", "alt": ["muslo de pollo"]},
                {"name": "Cebolla", "qty": "1 ud", "alt": ["chalota"]},
                {"name": "Ajo", "qty": "1 diente", "alt": []},
                {"name": "Curry en polvo", "qty": "1 cda", "alt": ["pasta de curry"]},
                {"name": "Leche de coco", "qty": "200 ml", "alt": ["nata", "yogur"]},
                {"name": "Aceite de oliva", "qty": "1 cda", "alt": []},
                {"name": "Sal", "qty": "al gusto", "alt": []},
            ],
            "steps": [
                {"n": 1, "text": "Corta el pollo en dados.", "timer_s": None, "targets": ["pollo"]},
                {"n": 2, "text": "Pica cebolla y ajo.", "timer_s": None, "targets": ["cebolla", "ajo"]},
                {"n": 3, "text": "Sofríe cebolla y ajo 5 min.", "timer_s": 300, "targets": ["sartén"]},
                {"n": 4, "text": "Añade el pollo y dora 5 min.", "timer_s": 300, "targets": ["pollo"]},
                {"n": 5, "text": "Agrega curry y leche de coco. Cuece 8 min.", "timer_s": 480, "targets": ["sartén"]},
                {"n": 6, "text": "Ajusta de sal y sirve.", "timer_s": None, "targets": []},
            ],
            "notes": "Sirve con arroz basmati.",
            "nutrition_per_serving": {"kcal": 520, "carbs": 20, "protein": 40, "fat": 30},
        }
    # Generic template
    return {
        "title": f"Receta: {query}",
        "servings": servings,
        "ingredients": [
            {"name": "Ingrediente principal", "qty": "200 g", "alt": []},
            {"name": "Especia o salsa", "qty": "1 cda", "alt": []},
        ],
        "steps": [
            {"n": 1, "text": "Prepara ingredientes.", "timer_s": None, "targets": []},
            {"n": 2, "text": "Cocina 10 minutos.", "timer_s": 600, "targets": []},
            {"n": 3, "text": "Sirve y disfruta.", "timer_s": None, "targets": []},
        ],
        "notes": "", "nutrition_per_serving": {"kcal": 350, "carbs": 25, "protein": 20, "fat": 15},
    }


def list_saved(limit: int = 50) -> List[Dict[str, Any]]:
    return _list(limit)


def load(id: str) -> Optional[Dict[str, Any]]:
    return _load(id)


# Simple manual checks
if __name__ == "__main__":
    r = generate_recipe("Pollo al curry", servings=2, api_key=None)
    print("Generated:", r.get("id"), r.get("title"))
    lst = list_saved()
    print("Saved count:", len(lst))
    if lst:
        got = load(lst[0]["id"])
        print("Load ok:", bool(got))

