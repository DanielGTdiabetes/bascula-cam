from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


CONFIG_DIR = Path.home() / ".config" / "bascula"
RECIPES_FILE = CONFIG_DIR / "recipes.jsonl"

logger = logging.getLogger(__name__)

_STEP_TEXT_KEYS = (
    "text",
    "step",
    "description",
    "desc",
    "instruction",
    "instructions",
    "contenido",
    "paso",
)
_STEP_TIMER_KEYS = (
    "timer_s",
    "timer",
    "seconds",
    "duration",
    "duration_s",
    "time",
    "duracion",
    "duracion_s",
)


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


def _parse_timer(value: Any) -> Optional[int]:
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


def _extract_step_text(data: Dict[str, Any]) -> str:
    for key in _STEP_TEXT_KEYS:
        if key in data and data.get(key) not in (None, ""):
            return str(data.get(key)).strip()
    return ""


def _step_targets(value: Any) -> List[str]:
    targets: List[str] = []
    if not isinstance(value, (list, tuple, set)):
        if value in (None, ""):
            return targets
        value = [value]
    for item in value:
        try:
            targets.append(str(item))
        except Exception:
            continue
    return targets


def _coerce_step_entry(value: Any, index: int) -> Tuple[Optional[Dict[str, Any]], bool]:
    migrated = False
    n = index + 1
    timer: Optional[int] = None
    targets: List[str] = []
    text = ""

    if isinstance(value, dict):
        text = _extract_step_text(value)
        text_field = value.get("text")
        if not isinstance(text_field, str):
            if text:
                migrated = True
        else:
            if text_field.strip() != text_field:
                migrated = True
        try:
            if value.get("n") not in (None, ""):
                n_val = int(value.get("n"))
                if n_val > 0:
                    n = n_val
        except Exception:
            migrated = True
        targets = _step_targets(value.get("targets"))
        for key in _STEP_TIMER_KEYS:
            if key in value:
                timer = _parse_timer(value.get(key))
                if timer is not None:
                    if key != "timer_s":
                        migrated = True
                    break
        if value.get("timer_s") not in (None, "") and timer is None:
            migrated = True
    else:
        text = str(value or "").strip()
        migrated = bool(text)

    text = text.strip()
    if not text:
        return None, migrated

    step = {
        "n": n if n > 0 else index + 1,
        "text": text,
        "timer_s": timer,
        "targets": targets,
    }
    return step, migrated or not isinstance(value, dict)


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
    raw_steps = d.get("steps") or []
    steps: List[Dict[str, Any]] = []
    migrated_any = False
    for idx, raw in enumerate(raw_steps):
        step, migrated = _coerce_step_entry(raw, idx)
        if step:
            steps.append(step)
        migrated_any = migrated_any or migrated
    if migrated_any and steps:
        logger.info("Migrated recipe %s steps to dict form", out["id"])
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
            if len(out) >= limit:
                break
        return out
    except Exception:
        return []


def delete_recipe(id: str) -> bool:
    _ensure_store()
    try:
        if not RECIPES_FILE.exists():
            return False
        lines = RECIPES_FILE.read_text(encoding="utf-8").splitlines()
        out: List[str] = []
        deleted = False
        for ln in lines:
            try:
                obj = json.loads(ln)
            except Exception:
                continue
            if str(obj.get("id")) == str(id):
                deleted = True
                continue
            out.append(json.dumps(obj, ensure_ascii=False))
        if deleted:
            RECIPES_FILE.write_text("\n".join(out) + ("\n" if out else ""), encoding="utf-8")
        return deleted
    except Exception:
        return False
