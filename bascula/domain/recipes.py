from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional


CONFIG_DIR = Path.home() / ".config" / "bascula"
RECIPES_FILE = CONFIG_DIR / "recipes.jsonl"


# Data model (dict-compatible via asdict)
@dataclass
class Ingredient:
    name: str
    qty: str = ""
    alt: List[str] = field(default_factory=list)
    barcode: Optional[str] = None
    matched: bool = False


@dataclass
class Step:
    n: int
    text: str
    timer_s: Optional[int] = None
    targets: List[str] = field(default_factory=list)


@dataclass
class Recipe:
    id: str
    title: str
    servings: int
    ingredients: List[Ingredient]
    steps: List[Step]
    notes: str = ""
    nutrition_per_serving: Dict[str, Any] = field(default_factory=lambda: {
        "kcal": 0,
        "carbs": 0,
        "protein": 0,
        "fat": 0,
    })
    created_at: str = ""


def new_id() -> str:
    return uuid.uuid4().hex


def _ensure_store() -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not RECIPES_FILE.exists():
            RECIPES_FILE.write_text("", encoding="utf-8")
    except Exception:
        pass


def _coerce_recipe_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    # Minimal sanitization to keep schema coherent
    out: Dict[str, Any] = {}
    out["id"] = str(d.get("id") or new_id())
    out["title"] = str(d.get("title") or "Receta")
    try:
        out["servings"] = int(d.get("servings") or 2)
    except Exception:
        out["servings"] = 2
    # ingredients
    ings = []
    for it in (d.get("ingredients") or []):
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
    for st in (d.get("steps") or []):
        try:
            n = int(st.get("n") or (len(steps) + 1))
        except Exception:
            n = len(steps) + 1
        timer_val = st.get("timer_s")
        try:
            timer = int(timer_val) if timer_val is not None else None
            if timer is not None and timer < 0:
                timer = None
        except Exception:
            timer = None
        steps.append({
            "n": n,
            "text": str(st.get("text") or ""),
            "timer_s": timer,
            "targets": list(st.get("targets") or []),
        })
    out["steps"] = steps
    out["notes"] = str(d.get("notes") or "")
    nps = d.get("nutrition_per_serving") or {}
    out["nutrition_per_serving"] = {
        "kcal": _num(nps.get("kcal")),
        "carbs": _num(nps.get("carbs")),
        "protein": _num(nps.get("protein")),
        "fat": _num(nps.get("fat")),
    }
    out["created_at"] = str(d.get("created_at") or _now_iso())
    return out


def _now_iso() -> str:
    try:
        import datetime as _dt
        return _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    except Exception:
        return str(int(time.time()))


def _num(v: Any) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def save_recipe(recipe: Dict[str, Any]) -> None:
    """Upsert recipe by id into JSONL store.

    Safe for offline use; ignores IO errors silently.
    """
    _ensure_store()
    try:
        rid = str(recipe.get("id") or new_id())
        recipe = dict(_coerce_recipe_dict(dict(recipe)))
        recipe["id"] = rid
        # Load all
        lines = RECIPES_FILE.read_text(encoding="utf-8").splitlines() if RECIPES_FILE.exists() else []
        out: List[str] = []
        seen = False
        for ln in lines:
            try:
                obj = json.loads(ln)
            except Exception:
                continue
            if str(obj.get("id")) == rid:
                out.append(json.dumps(recipe, ensure_ascii=False))
                seen = True
            else:
                out.append(json.dumps(obj, ensure_ascii=False))
        if not seen:
            out.append(json.dumps(recipe, ensure_ascii=False))
        RECIPES_FILE.write_text("\n".join(out) + ("\n" if out else ""), encoding="utf-8")
        # Prune file to keep size and entries under control
        try:
            from bascula.services.retention import prune_jsonl
            prune_jsonl(RECIPES_FILE, max_entries=1000, max_bytes=20*1024*1024, max_days=365)
        except Exception:
            pass
    except Exception:
        pass


def load_recipe(id: str) -> Optional[Dict[str, Any]]:
    _ensure_store()
    try:
        if not RECIPES_FILE.exists():
            return None
        for ln in RECIPES_FILE.read_text(encoding="utf-8").splitlines():
            try:
                obj = json.loads(ln)
                if str(obj.get("id")) == str(id):
                    return _coerce_recipe_dict(obj)
            except Exception:
                continue
        return None
    except Exception:
        return None


def list_recipes(limit: int = 50) -> List[Dict[str, Any]]:
    _ensure_store()
    out: List[Dict[str, Any]] = []
    try:
        if not RECIPES_FILE.exists():
            return []
        for ln in RECIPES_FILE.read_text(encoding="utf-8").splitlines():
            try:
                obj = json.loads(ln)
                out.append(_coerce_recipe_dict(obj))
            except Exception:
                continue
        # sort by created_at desc when possible
        def _key(o: Dict[str, Any]) -> Any:
            return (o.get("created_at") or "", o.get("id") or "")
        out.sort(key=_key, reverse=True)
        return out[: max(1, int(limit))]
    except Exception:
        return []


def delete_recipe(id: str) -> bool:
    """Elimina una receta por id del almacén JSONL.

    Retorna True si se eliminó alguna entrada.
    """
    _ensure_store()
    rid = str(id or "").strip()
    if not rid or not RECIPES_FILE.exists():
        return False
    try:
        lines = RECIPES_FILE.read_text(encoding="utf-8").splitlines()
        out: List[str] = []
        removed = False
        for ln in lines:
            try:
                obj = json.loads(ln)
            except Exception:
                continue
            if str(obj.get("id")) == rid:
                removed = True
                continue
            out.append(json.dumps(obj, ensure_ascii=False))
        if removed:
            RECIPES_FILE.write_text("\n".join(out) + ("\n" if out else ""), encoding="utf-8")
        return removed
    except Exception:
        return False


# Manual check helper (not a unit test framework)
if __name__ == "__main__":
    r = {
        "id": new_id(),
        "title": "Prueba Pollo al curry",
        "servings": 2,
        "ingredients": [
            {"name": "Pechuga de pollo", "qty": "300 g", "alt": ["muslo"], "barcode": None, "matched": False},
            {"name": "Curry", "qty": "1 cda", "alt": []},
        ],
        "steps": [
            {"n": 1, "text": "Cortar pollo", "timer_s": None, "targets": ["pollo"]},
            {"n": 2, "text": "Saltear 5 minutos", "timer_s": 300, "targets": ["sartén"]},
        ],
        "notes": "", "nutrition_per_serving": {"kcal": 420, "carbs": 15, "protein": 38, "fat": 20}
    }
    save_recipe(r)
    lst = list_recipes()
    print("Guardadas:", len(lst))
    if lst:
        first_id = lst[0]["id"]
        print("Load first: ", load_recipe(first_id) is not None)
