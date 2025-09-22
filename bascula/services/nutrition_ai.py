"""Food recognition via OpenAI with local fallback heuristics."""
from __future__ import annotations

import base64
import json
import logging
import os
import random
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore

try:  # pragma: no cover - compatibility with legacy SDK
    import openai as openai_legacy  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    openai_legacy = None  # type: ignore


class NutritionAIError(RuntimeError):
    """Base exception for AI food analysis failures."""


class NutritionAIAuthError(NutritionAIError):
    """Raised when the OpenAI API key is invalid."""


class NutritionAIServiceError(NutritionAIError):
    """Raised when the remote AI service is unavailable."""


_SYSTEM_PROMPT = (
    "Eres un asistente nutricional. Recibirás una imagen de comida y el peso en gramos. "
    "Devuelve un JSON con estos campos obligatorios: name (string), carbs_g (float), "
    "protein_g (float), fat_g (float), gi (entero 0-110) y confidence (float entre 0 y 1). "
    "Si no puedes estimar un valor, usa null. No incluyas texto adicional."
)

_JSON_FIELDS = ("name", "carbs_g", "protein_g", "fat_g", "gi", "confidence", "source")


def analyze_food(
    image_bytes: bytes,
    weight_g: float,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Analyze a food picture and estimate its macros.

    Returns a dictionary with the schema ``{name, carbs_g, protein_g, fat_g, gi, confidence, source}``.
    When OpenAI is not available or disabled the function falls back to a lightweight heuristic.
    """

    weight = float(weight_g or 0.0)
    if weight < 0:
        weight = 0.0

    key = os.getenv("OPENAI_API_KEY", "").strip()
    client = _build_client(key)

    if client is None:
        return _local_stub(weight)

    payload = _prepare_payload(image_bytes, weight, description)
    attempts = 0
    last_error: Optional[Exception] = None
    while attempts < 3:
        attempts += 1
        try:
            raw = _invoke_openai(client, payload, timeout=10.0)
            return _parse_response(raw)
        except NutritionAIAuthError:
            raise
        except NutritionAIServiceError as exc:
            last_error = exc
            break
        except TimeoutError as exc:
            last_error = exc
            break
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Fallo analizando alimento (intento %s): %s", attempts, exc)
            last_error = exc
            time.sleep(0.5 * attempts)

    if isinstance(last_error, (NutritionAIServiceError, TimeoutError)):
        raise NutritionAIServiceError("Servicio de IA no disponible") from last_error

    logger.warning("Fallo persistente en IA, usando heurística local: %s", last_error)
    return _local_stub(weight)


def _build_client(key: str):
    if not key:
        return None
    if OpenAI is not None:
        try:
            return OpenAI(api_key=key, timeout=10.0)
        except TypeError:
            return OpenAI(api_key=key)
        except Exception as exc:  # pragma: no cover - optional dependency issues
            logger.warning("OpenAI SDK no disponible: %s", exc)
    if openai_legacy is not None:
        openai_legacy.api_key = key
        return openai_legacy
    return None


def _prepare_payload(
    image_bytes: Optional[bytes], weight: float, description: Optional[str]
) -> Dict[str, Any]:
    encoded = (
        base64.b64encode(image_bytes or b"").decode("ascii") if image_bytes else ""
    )
    return {
        "weight": round(weight, 2),
        "image_b64": encoded,
        "description": (description or "").strip(),
    }


def _invoke_openai(client, payload: Dict[str, Any], *, timeout: float) -> str:
    image_b64 = payload.get("image_b64")
    weight = payload.get("weight", 0)
    description = str(payload.get("description") or "").strip()
    messages = [
        {
            "role": "system",
            "content": [{"type": "text", "text": _SYSTEM_PROMPT}],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": _user_prompt(weight, description),
                },
            ],
        },
    ]
    if image_b64:
        messages[1]["content"].append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
            }
        )

    try:
        if OpenAI is not None and isinstance(client, OpenAI):
            response = client.responses.create(
                model="gpt-4o-mini",
                input=messages,
                max_output_tokens=400,
                temperature=0.1,
                response_format={"type": "json_object"},
                timeout=timeout,
            )
            return _extract_text_from_response(response)
        if openai_legacy is not None and client is openai_legacy:
            response = openai_legacy.ChatCompletion.create(  # type: ignore[attr-defined]
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.1,
                max_tokens=400,
                timeout=timeout,
            )
            return response["choices"][0]["message"]["content"]  # type: ignore[index]
    except Exception as exc:
        _handle_openai_exception(exc)
    raise NutritionAIServiceError("Servicio de IA no disponible")


def _user_prompt(weight: Any, description: str) -> str:
    try:
        weight_value = float(weight)
    except Exception:
        weight_value = 0.0
    text = (
        "Peso en báscula: %.2f g. Identifica los alimentos en la imagen y "
        "estima macronutrientes para este peso total." % weight_value
    )
    if description:
        text += f" Producto: {description}."
    return text


def _extract_text_from_response(response: Any) -> str:
    try:
        parts = []
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", "") == "output_text":
                for segment in getattr(item, "content", []) or []:
                    if getattr(segment, "type", "") == "output_text":
                        parts.append(getattr(segment, "text", ""))
                    elif isinstance(segment, dict):
                        parts.append(str(segment.get("text", "")))
            elif isinstance(item, dict) and item.get("type") == "output_text":
                parts.append(str(item.get("text", "")))
        if parts:
            return "\n".join(p for p in parts if p)
        # SDK <=1.1 compatibility
        if getattr(response, "choices", None):
            return response.choices[0].message["content"]  # type: ignore[index]
    except Exception:
        pass
    return str(getattr(response, "output_text", ""))


def _handle_openai_exception(exc: Exception) -> None:
    status = None
    try:
        status = getattr(exc, "status_code", None)
    except Exception:
        status = None
    if status is None:
        try:
            status = getattr(getattr(exc, "response", None), "status_code", None)
        except Exception:
            status = None
    if status in (401, 403):
        raise NutritionAIAuthError("Clave de OpenAI inválida. Revisa Ajustes → Red/IA.") from exc
    if status in (429,) or (isinstance(status, int) and status >= 500):
        raise NutritionAIServiceError("Servicio de IA no disponible") from exc
    if isinstance(exc, TimeoutError):
        raise TimeoutError("Servicio de IA no disponible") from exc
    raise NutritionAIServiceError("Servicio de IA no disponible") from exc


def _parse_response(text: str) -> Dict[str, Any]:
    try:
        data = json.loads(text or "{}")
    except Exception:
        logger.debug("Respuesta IA no válida: %s", text)
        return {"name": "Desconocido", "carbs_g": None, "protein_g": None, "fat_g": None, "gi": None, "confidence": None, "source": "ai_incomplete"}

    result: Dict[str, Any] = {}
    missing = False
    for field in _JSON_FIELDS:
        value = data.get(field)
        if field == "name":
            result[field] = str(value).strip() if isinstance(value, str) else "Desconocido"
            if not result[field]:
                missing = True
        elif field in {"carbs_g", "protein_g", "fat_g"}:
            try:
                result[field] = round(float(value), 2)
            except Exception:
                result[field] = None
                missing = True
        elif field == "gi":
            try:
                gi_val = int(value)
            except Exception:
                gi_val = None
            if gi_val is None:
                result[field] = None
                missing = True
            else:
                result[field] = max(0, min(110, gi_val))
        elif field == "confidence":
            try:
                conf = float(value)
                if conf > 1:
                    conf = conf / 100.0
            except Exception:
                conf = None
            if conf is None:
                missing = True
            else:
                conf = max(0.0, min(1.0, conf))
            result[field] = conf
        elif field == "source":
            result[field] = str(value or "openai")

    if missing:
        result["source"] = "ai_incomplete"
    return result


def _local_stub(weight: float) -> Dict[str, Any]:
    weight = max(0.0, float(weight or 0.0))
    base = max(1.0, weight)
    carbs = round(base * random.uniform(0.08, 0.16), 2)
    protein = round(base * random.uniform(0.05, 0.12), 2)
    fat = round(base * random.uniform(0.02, 0.08), 2)
    gi = int(random.uniform(40, 65))
    return {
        "name": "Estimación local",
        "carbs_g": carbs,
        "protein_g": protein,
        "fat_g": fat,
        "gi": gi,
        "confidence": 0.25,
        "source": "local_stub",
    }


__all__ = [
    "analyze_food",
    "NutritionAIError",
    "NutritionAIAuthError",
    "NutritionAIServiceError",
]
