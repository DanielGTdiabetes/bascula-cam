"""Camera analysis pipeline with barcode, AI and offline fallbacks."""
from __future__ import annotations

import base64
import io
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from PIL import Image
import requests

try:  # Optional hardware dependency
    from picamera2 import Picamera2  # type: ignore
except Exception:  # pragma: no cover - not available in CI
    Picamera2 = None  # type: ignore

try:  # Optional barcode decoder
    from pyzbar.pyzbar import Decoded, decode  # type: ignore
except Exception:  # pragma: no cover
    Decoded = Any  # type: ignore
    decode = None  # type: ignore

logger = logging.getLogger("bascula.core.camera")

FOOD_RESULT = Dict[str, Any]


@dataclass
class FoodInfo:
    name: str
    per_100g: Dict[str, float]
    source: str

    def to_dict(self) -> FOOD_RESULT:
        return {"name": self.name, "per_100g": self.per_100g, "source": self.source}


class CameraScanner:
    def __init__(self, *, cache_dir: Path | None = None, local_db_path: Path | None = None) -> None:
        self.cache_dir = (cache_dir or Path.home() / ".bascula" / "cache" / "off").expanduser()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._session = requests.Session()
        self._picamera: Picamera2 | None = None  # type: ignore
        if Picamera2 is not None:
            try:
                self._picamera = Picamera2()
                self._picamera.configure(self._picamera.create_preview_configuration())
                self._picamera.start()
            except Exception:
                logger.warning("Cámara Pi no disponible", exc_info=True)
                self._picamera = None
        self._openai_client = self._init_openai()
        default_db = Path("data/local_food_db.json")
        self.local_db_path = (local_db_path or default_db).expanduser()
        self._local_db = self._load_local_db(self.local_db_path)

    # Public API ---------------------------------------------------------
    def analyze(self) -> FOOD_RESULT:
        image = self._capture_image()
        if image is not None:
            barcode_result = self._analyze_barcode(image)
            if barcode_result is not None:
                return barcode_result
        ai_result = self._analyze_with_openai(image)
        if ai_result is not None:
            return ai_result
        return self._offline_fallback()

    # Barcode ------------------------------------------------------------
    def _analyze_barcode(self, image: Image.Image) -> Optional[FOOD_RESULT]:
        if decode is None:
            return None
        try:
            decoded = decode(image)
        except Exception:
            logger.warning("Error decodificando código de barras", exc_info=True)
            return None
        if not decoded:
            return None
        code = decoded[0].data.decode("utf-8", errors="ignore").strip()
        if not code:
            return None
        logger.info("Código detectado: %s", code)
        off = self._lookup_openfoodfacts(code)
        if off:
            return off.to_dict()
        return None

    def _lookup_openfoodfacts(self, code: str) -> Optional[FoodInfo]:
        cache_path = self.cache_dir / f"{code}.json"
        data: dict[str, Any]
        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text("utf-8"))
            except Exception:
                logger.warning("Cache OFF corrupta en %s", cache_path, exc_info=True)
                cache_path.unlink(missing_ok=True)
            else:
                result = self._parse_openfoodfacts(data)
                if result:
                    result.source = "off"
                    return result
        url = f"https://world.openfoodfacts.org/api/v0/product/{code}.json"
        try:
            response = self._session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception:
            logger.warning("Fallo consultando OpenFoodFacts", exc_info=True)
            return None
        try:
            cache_path.write_text(json.dumps(data), "utf-8")
        except Exception:
            logger.debug("No se pudo escribir cache OFF", exc_info=True)
        result = self._parse_openfoodfacts(data)
        if result:
            result.source = "off"
        return result

    def _parse_openfoodfacts(self, data: dict[str, Any]) -> Optional[FoodInfo]:
        product = data.get("product") or {}
        nutriments = product.get("nutriments") or {}
        def fetch(key: str) -> float:
            value = nutriments.get(f"{key}_100g")
            try:
                return round(float(value), 1)
            except (TypeError, ValueError):
                return 0.0
        per_100g = {
            "carbs": fetch("carbohydrates"),
            "kcal": fetch("energy-kcal"),
            "protein": fetch("proteins"),
            "fat": fetch("fat"),
        }
        name = (product.get("product_name") or product.get("generic_name") or "Producto").strip() or "Producto"
        return FoodInfo(name=name.lower(), per_100g=per_100g, source="off")

    # OpenAI -------------------------------------------------------------
    def _init_openai(self):
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return None
        try:
            from openai import OpenAI  # type: ignore
        except Exception:
            logger.warning("SDK de OpenAI no disponible")
            return None
        try:
            return OpenAI()
        except Exception:
            logger.warning("No se pudo inicializar cliente OpenAI", exc_info=True)
            return None

    def _analyze_with_openai(self, image: Optional[Image.Image]) -> Optional[FOOD_RESULT]:
        if self._openai_client is None or image is None:
            return None
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        b64_image = base64.b64encode(buffered.getvalue()).decode("ascii")
        prompt = (
            "Describe el alimento en la imagen y devuelve un JSON con las claves "
            "name y per_100g (carbs, kcal, protein, fat). Responde solo el JSON."
        )
        try:
            response = self._openai_client.responses.create(
                model="gpt-4o-mini",
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "input_image", "image": {"base64": b64_image}},
                        ],
                    }
                ],
                temperature=0.3,
                max_output_tokens=400,
            )
            raw = response.output[0].content[0].text  # type: ignore[index]
        except Exception:
            logger.warning("Error llamando a OpenAI Vision", exc_info=True)
            return None
        try:
            parsed = json.loads(raw)
            name = str(parsed.get("name") or "alimento").strip().lower()
            per_100g = {
                "carbs": round(float(parsed.get("per_100g", {}).get("carbs", 0)), 1),
                "kcal": round(float(parsed.get("per_100g", {}).get("kcal", 0)), 1),
                "protein": round(float(parsed.get("per_100g", {}).get("protein", 0)), 1),
                "fat": round(float(parsed.get("per_100g", {}).get("fat", 0)), 1),
            }
        except Exception:
            logger.warning("Respuesta OpenAI inválida: %s", raw)
            return None
        return FoodInfo(name=name, per_100g=per_100g, source="openai").to_dict()

    # Offline fallback ---------------------------------------------------
    def _offline_fallback(self) -> FOOD_RESULT:
        if not self._local_db:
            logger.info("Base local vacía; devolviendo alimento genérico")
            return {"name": "alimento", "per_100g": {"carbs": 0.0, "kcal": 0.0, "protein": 0.0, "fat": 0.0}, "source": "local"}
        entry = self._local_db[0]
        return {"name": entry["name"], "per_100g": entry["per_100g"], "source": "local"}

    def _load_local_db(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            logger.warning("Base local %s no encontrada", path)
            return []
        try:
            data = json.loads(path.read_text("utf-8"))
        except Exception:
            logger.warning("Error leyendo base local %s", path, exc_info=True)
            return []
        entries: list[dict[str, Any]] = []
        for item in data:
            name = str(item.get("name") or "").strip().lower()
            if not name:
                continue
            per = item.get("per_100g") or {}
            try:
                entry = {
                    "name": name,
                    "per_100g": {
                        "carbs": round(float(per.get("carbs", 0.0)), 1),
                        "kcal": round(float(per.get("kcal", 0.0)), 1),
                        "protein": round(float(per.get("protein", 0.0)), 1),
                        "fat": round(float(per.get("fat", 0.0)), 1),
                    },
                }
            except (TypeError, ValueError):
                continue
            entries.append(entry)
        entries.sort(key=lambda item: item["name"])
        return entries

    # Image capture ------------------------------------------------------
    def _capture_image(self) -> Optional[Image.Image]:
        if self._picamera is None:
            logger.info("Cámara no inicializada; se omite captura")
            return None
        try:
            buffer = self._picamera.capture_array()
            image = Image.fromarray(buffer)
            return image
        except Exception:
            logger.warning("Error capturando imagen", exc_info=True)
            return None

    def close(self) -> None:
        if self._picamera is not None:
            try:
                self._picamera.close()
            except Exception:
                logger.debug("No se pudo cerrar cámara", exc_info=True)
            self._picamera = None


__all__ = ["CameraScanner", "FoodInfo"]
