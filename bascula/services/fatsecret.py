from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

try:  # pragma: no cover - optional dependency
    import tomllib  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - optional dependency
    tomllib = None  # type: ignore

try:  # pragma: no cover - optional dependency
    import requests  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    requests = None  # type: ignore

logger = logging.getLogger(__name__)

CONFIG_PATH = Path.home() / ".config" / "bascula" / "keys.toml"
CACHE_PATH = Path.home() / ".cache" / "bascula" / "barcodes.sqlite"

TOKEN_URL = "https://oauth.fatsecret.com/connect/token"
API_URL = "https://platform.fatsecret.com/rest/server.api"


class FatSecretError(RuntimeError):
    """Base exception for FatSecret failures."""


class FatSecretAuthError(FatSecretError):
    """Raised when credentials are invalid or missing."""


class FatSecretNotFound(FatSecretError):
    """Raised when a barcode is not found in FatSecret."""


class FatSecretUnavailable(FatSecretError):
    """Raised when the remote API is temporarily unavailable."""


@dataclass
class Credentials:
    client_id: str
    client_secret: str


def _load_credentials(path: Path = CONFIG_PATH) -> Credentials:
    if tomllib is None:
        raise FatSecretAuthError("Soporte TOML no disponible (tomllib)")
    try:
        data = path.read_bytes()
    except FileNotFoundError as exc:
        raise FatSecretAuthError(
            f"Credenciales FatSecret no encontradas en {path}. Usa chmod 600."
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise FatSecretAuthError(f"No se pudo leer {path}: {exc}") from exc

    try:
        parsed = tomllib.loads(data.decode("utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        raise FatSecretAuthError(f"keys.toml inválido: {exc}") from exc

    section = parsed.get("fatsecret") if isinstance(parsed, dict) else None
    if isinstance(section, dict):
        source = section
    else:
        source = parsed if isinstance(parsed, dict) else {}

    key_candidates = [
        source.get("key"),
        source.get("client_id"),
        source.get("fatsecret_key"),
        parsed.get("fatsecret_key") if isinstance(parsed, dict) else None,
    ]
    secret_candidates = [
        source.get("secret"),
        source.get("client_secret"),
        source.get("fatsecret_secret"),
        parsed.get("fatsecret_secret") if isinstance(parsed, dict) else None,
    ]

    client_id = next((str(v).strip() for v in key_candidates if v), "")
    client_secret = next((str(v).strip() for v in secret_candidates if v), "")

    if not client_id or not client_secret:
        raise FatSecretAuthError("Configura fatsecret.key y fatsecret.secret en keys.toml")

    try:
        mode = path.stat().st_mode & 0o777
        if mode & 0o077:
            logger.warning("Permisos inseguros en %s (usa chmod 600)", path)
    except Exception:
        pass

    return Credentials(client_id=client_id, client_secret=client_secret)


def _to_float(value: Any) -> Optional[float]:
    try:
        if value in (None, "", "null"):
            return None
        return float(value)
    except Exception:
        return None


def _grams_from_description(text: str) -> Optional[float]:
    if not text:
        return None
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(g|gram|grams)", text.lower())
    if match:
        try:
            return float(match.group(1))
        except Exception:
            return None
    return None


class _Cache:
    def __init__(self, path: Path = CACHE_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS barcodes (code TEXT PRIMARY KEY, payload TEXT NOT NULL, ts REAL NOT NULL)"
            )

    def get(self, code: str) -> Optional[Dict[str, Any]]:
        try:
            with sqlite3.connect(self.path) as conn:
                cur = conn.execute("SELECT payload FROM barcodes WHERE code=?", (code,))
                row = cur.fetchone()
        except Exception:
            return None
        if not row:
            return None
        try:
            data = json.loads(row[0])
        except Exception:
            return None
        if isinstance(data, dict) and data.get("__status__") == "missing":
            return None
        return data if isinstance(data, dict) else None

    def put(self, code: str, payload: Dict[str, Any]) -> None:
        try:
            data = json.dumps(payload, ensure_ascii=False)
        except Exception:
            return
        try:
            with sqlite3.connect(self.path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO barcodes(code, payload, ts) VALUES (?, ?, ?)",
                    (code, data, time.time()),
                )
        except Exception:
            pass

    def remember_missing(self, code: str) -> None:
        self.put(code, {"__status__": "missing"})


class FatSecretClient:
    def __init__(self, credentials: Credentials, cache: Optional[_Cache] = None) -> None:
        self.credentials = credentials
        self.cache = cache or _Cache()
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0

    # ------------------------------------------------------------------
    def lookup_barcode(self, code: str) -> Optional[Dict[str, Any]]:
        code = (code or "").strip()
        if not code:
            return None
        cached = self.cache.get(code)
        if cached:
            return cached
        if requests is None:
            raise FatSecretUnavailable("requests no disponible")
        try:
            data = self._fetch_remote(code)
        except FatSecretNotFound:
            self.cache.remember_missing(code)
            return None
        self.cache.put(code, data)
        return data

    # ------------------------------------------------------------------
    def _fetch_remote(self, code: str) -> Dict[str, Any]:
        lookup = self._request("food.find_id_for_barcode", {"barcode": code})
        food_id = self._extract_food_id(lookup)
        if not food_id:
            raise FatSecretNotFound(f"Código {code} no encontrado")
        detail = self._request("food.get.v3", {"food_id": food_id})
        parsed = self._parse_food(detail)
        if not parsed:
            raise FatSecretNotFound(f"Macros no disponibles para {code}")
        parsed["code"] = code
        parsed["ts"] = time.time()
        return parsed

    # ------------------------------------------------------------------
    def _ensure_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expiry - 30:
            return self._token
        auth = (self.credentials.client_id, self.credentials.client_secret)
        try:
            response = requests.post(
                TOKEN_URL,
                data={"grant_type": "client_credentials", "scope": "basic"},
                auth=auth,
                timeout=8,
            )
        except Exception as exc:  # pragma: no cover - network dependent
            raise FatSecretUnavailable("No se pudo obtener token FatSecret") from exc
        if response.status_code == 401:
            raise FatSecretAuthError("Credenciales FatSecret inválidas")
        try:
            payload = response.json()
        except Exception as exc:
            raise FatSecretUnavailable("Respuesta token inválida") from exc
        token = payload.get("access_token")
        expires_in = _to_float(payload.get("expires_in")) or 3600
        if not token:
            raise FatSecretUnavailable("Token FatSecret no proporcionado")
        self._token = str(token)
        self._token_expiry = now + max(60.0, float(expires_in))
        return self._token

    # ------------------------------------------------------------------
    def _request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        token = self._ensure_token()
        payload = {"method": method, "format": "json"}
        payload.update(params)
        headers = {"Authorization": f"Bearer {token}"}
        try:
            response = requests.post(API_URL, data=payload, headers=headers, timeout=8)
        except Exception as exc:  # pragma: no cover - network dependent
            raise FatSecretUnavailable("No se pudo contactar FatSecret") from exc
        if response.status_code == 401:
            self._token = None
            raise FatSecretAuthError("Token FatSecret inválido o expirado")
        if response.status_code == 404:
            raise FatSecretNotFound("Producto no encontrado")
        if response.status_code >= 500:
            raise FatSecretUnavailable("FatSecret no disponible")
        try:
            data = response.json()
        except Exception as exc:
            raise FatSecretUnavailable("Respuesta FatSecret inválida") from exc
        error = data.get("error") if isinstance(data, dict) else None
        if isinstance(error, dict):
            code = str(error.get("code") or "").lower()
            if code in {"no_food", "food_not_found"}:
                raise FatSecretNotFound(error.get("message") or "Sin resultados")
            if code in {"access_token_expired", "invalid_token"}:
                self._token = None
                raise FatSecretAuthError(error.get("message") or "Token inválido")
            raise FatSecretUnavailable(error.get("message") or "Error en FatSecret")
        return data if isinstance(data, dict) else {}

    # ------------------------------------------------------------------
    def _extract_food_id(self, data: Dict[str, Any]) -> Optional[str]:
        if not isinstance(data, dict):
            return None
        for key in ("food_id", "foodId"):
            value = data.get(key)
            if value:
                return str(value)
        for key in ("food", "foods"):
            value = data.get(key)
            if isinstance(value, dict):
                result = self._extract_food_id(value)
                if result:
                    return result
            elif isinstance(value, list):
                for item in value:
                    result = self._extract_food_id(item)
                    if result:
                        return result
        return None

    # ------------------------------------------------------------------
    def _parse_food(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        food = data.get("food") if isinstance(data, dict) else None
        if isinstance(food, list):
            food = food[0] if food else None
        if not isinstance(food, dict):
            foods = data.get("foods") if isinstance(data, dict) else None
            if isinstance(foods, dict):
                food = foods.get("food")
                if isinstance(food, list):
                    food = food[0] if food else None
        if not isinstance(food, dict):
            food = data if isinstance(data, dict) else None
        if not isinstance(food, dict):
            return None

        food_name = str(food.get("food_name") or food.get("food_description") or "").strip()
        brand = str(food.get("brand_name") or "").strip() or None
        label = food_name
        if brand and brand.lower() not in (food_name or "").lower():
            label = f"{brand} {food_name}".strip()
        elif brand and not food_name:
            label = brand
        elif not label:
            label = "Producto"

        servings = food.get("servings") if isinstance(food, dict) else None
        serving_entry: Optional[Dict[str, Any]] = None
        grams = None
        if isinstance(servings, dict):
            serving_data = servings.get("serving")
            candidates = serving_data if isinstance(serving_data, list) else [serving_data]
        elif isinstance(servings, list):
            candidates = servings
        else:
            candidates = []
        for candidate in candidates or []:
            if not isinstance(candidate, dict):
                continue
            weight = _to_float(
                candidate.get("metric_serving_amount")
                or candidate.get("metric_serving_size")
                or candidate.get("serving_weight_grams")
            )
            unit = str(candidate.get("metric_serving_unit") or "").lower()
            if weight and (not unit or unit in {"g", "gram", "grams"}):
                serving_entry = candidate
                grams = weight
                break
        if serving_entry is None:
            for candidate in candidates or []:
                if not isinstance(candidate, dict):
                    continue
                desc = str(candidate.get("serving_description") or "")
                grams = _grams_from_description(desc)
                if grams:
                    serving_entry = candidate
                    break
        if serving_entry is None and candidates:
            candidate = next((c for c in candidates if isinstance(c, dict)), None)
            if candidate is not None:
                serving_entry = candidate
                grams = _to_float(candidate.get("serving_weight_grams"))

        if serving_entry is None:
            return {
                "name": label,
                "brand": brand,
                "per_gram": {},
                "serving": {},
            }

        grams = grams or _to_float(serving_entry.get("metric_serving_amount")) or 0.0
        carbs = _to_float(serving_entry.get("carbohydrate") or serving_entry.get("carbohydrates"))
        protein = _to_float(serving_entry.get("protein"))
        fat = _to_float(serving_entry.get("fat"))

        per_gram: Dict[str, Optional[float]] = {}
        for key, value in (("carbs_g", carbs), ("protein_g", protein), ("fat_g", fat)):
            if value is None or not grams:
                per_gram[key] = None
            else:
                per_gram[key] = value / grams

        return {
            "name": label,
            "brand": brand,
            "raw_name": food_name,
            "per_gram": per_gram,
            "serving": {
                "grams": grams,
                "description": serving_entry.get("serving_description"),
                "carbs_g": carbs,
                "protein_g": protein,
                "fat_g": fat,
            },
        }


_client: Optional[FatSecretClient] = None


def get_client(refresh: bool = False) -> Optional[FatSecretClient]:
    global _client
    if _client is not None and not refresh:
        return _client
    try:
        credentials = _load_credentials()
    except FatSecretAuthError as exc:
        logger.debug("FatSecret deshabilitado: %s", exc)
        return None
    _client = FatSecretClient(credentials)
    return _client


def lookup_barcode(code: str) -> Optional[Dict[str, Any]]:
    client = get_client()
    if client is None:
        return None
    try:
        return client.lookup_barcode(code)
    except FatSecretError as exc:
        logger.debug("lookup_barcode falló: %s", exc)
        return None


def macros_for_weight(code: str, weight_g: float) -> Optional[Dict[str, Any]]:
    weight = max(0.0, float(weight_g or 0.0))
    food = lookup_barcode(code)
    if not food:
        return None
    per_gram = food.get("per_gram") or {}
    result = {
        "code": code,
        "name": food.get("name") or food.get("raw_name") or str(code),
        "brand": food.get("brand"),
        "weight_g": weight,
        "carbs_g": None,
        "protein_g": None,
        "fat_g": None,
        "resolved": False,
        "raw": food,
    }
    if weight <= 0:
        return result
    for key in ("carbs_g", "protein_g", "fat_g"):
        value = per_gram.get(key)
        if isinstance(value, (int, float)):
            result[key] = round(value * weight, 2)
            result["resolved"] = True
    return result


__all__ = [
    "FatSecretClient",
    "FatSecretError",
    "FatSecretAuthError",
    "FatSecretNotFound",
    "FatSecretUnavailable",
    "get_client",
    "lookup_barcode",
    "macros_for_weight",
]
