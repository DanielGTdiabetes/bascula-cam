from __future__ import annotations

import json
import os
import re
import threading
import unicodedata
from pathlib import Path
from typing import Any, Dict, Optional

__all__ = ["LabelsCache", "VisionRecognizer", "normalize_text"]

_DEFAULT_PATH = Path("/opt/bascula/shared/userdata/labels.json")
_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def _resolve_path(path: Optional[os.PathLike[str] | str] = None) -> Path:
    if path is not None:
        return Path(path)
    env = os.environ.get("BASCULA_LABELS_PATH")
    if env:
        return Path(env)
    return _DEFAULT_PATH


def normalize_text(text: Optional[str]) -> str:
    """Return a normalized key for OCR text.

    The normalization rules remove surrounding whitespace, convert to lowercase,
    strip diacritics, and collapse non-alphanumeric characters (basic
    punctuation) to single spaces.
    """

    if not text:
        return ""

    value = unicodedata.normalize("NFKD", str(text))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().strip()
    if not value:
        return ""
    value = _NORMALIZE_RE.sub(" ", value)
    return " ".join(value.split())


class LabelsCache:
    """Simple JSON-based cache for mapping OCR text to food identifiers."""

    def __init__(self, path: Optional[os.PathLike[str] | str] = None) -> None:
        self.path: Path = _resolve_path(path)
        self._lock = threading.RLock()
        self._data: Dict[str, Dict[str, Any]] = {}
        self._load()

    # ------------------------------------------------------------------
    def _load(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        should_rewrite = False
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except FileNotFoundError:
            raw = {}
            should_rewrite = True
        except json.JSONDecodeError:
            raw = {}
            should_rewrite = True
        except Exception:
            raw = {}
            should_rewrite = True

        if not isinstance(raw, dict):
            raw = {}
            should_rewrite = True

        cleaned: Dict[str, Dict[str, Any]] = {}
        for key, value in raw.items():
            if not isinstance(key, str) or not isinstance(value, dict):
                continue
            cleaned[key] = {
                "id": value.get("id"),
                "name": value.get("name"),
            }

        self._data = cleaned
        if should_rewrite or not self.path.exists():
            self._write_locked()

    # ------------------------------------------------------------------
    def _write_locked(self) -> None:
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tmp_path.open("w", encoding="utf-8") as fh:
                json.dump(self._data, fh, ensure_ascii=False, indent=2, sort_keys=True)
            os.replace(tmp_path, self.path)
            try:
                os.chmod(self.path, 0o644)
            except Exception:
                pass
        except Exception:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass

    # ------------------------------------------------------------------
    @property
    def data(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {k: v.copy() for k, v in self._data.items()}

    @property
    def labels_path(self) -> Path:
        return self.path

    # ------------------------------------------------------------------
    def lookup(self, text: Optional[str]) -> Optional[Dict[str, Any]]:
        key = normalize_text(text)
        if not key:
            return None
        with self._lock:
            entry = self._data.get(key)
            if not entry:
                return None
            result = entry.copy()
            result.setdefault("name", entry.get("id") or key)
            result["normalized"] = key
            return result

    # ------------------------------------------------------------------
    def update(
        self,
        text: Optional[str],
        *,
        food_id: Optional[Any] = None,
        food_name: Optional[str] = None,
    ) -> bool:
        key = normalize_text(text)
        if not key:
            return False

        entry: Dict[str, Any] = {}
        if food_id is not None:
            entry["id"] = str(food_id)
        if food_name:
            entry["name"] = str(food_name)
        if "name" not in entry:
            if "id" in entry:
                entry["name"] = str(entry["id"])
            else:
                entry["name"] = key

        with self._lock:
            if self._data.get(key) == entry:
                return False
            self._data[key] = entry
            self._write_locked()
        return True


class VisionRecognizer:
    """Lightweight helper to resolve OCR text using the cached labels."""

    def __init__(self, labels_cache: Optional[LabelsCache] = None) -> None:
        self.labels_cache = labels_cache or LabelsCache()
        self._last_raw_text: Optional[str] = None

    # ------------------------------------------------------------------
    def recognize(
        self,
        *,
        image_path: Optional[str] = None,
        weight: Optional[float] = None,
        ocr_text: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        del image_path  # Reserved for future use
        self._last_raw_text = ocr_text or None
        if not ocr_text:
            return None

        cached = self.labels_cache.lookup(ocr_text)
        if not cached:
            return None

        result: Dict[str, Any] = {
            "name": cached.get("name") or ocr_text,
            "grams": float(weight or 0.0),
            "source": "vision-cache",
            "ocr_text": ocr_text,
            "normalized_text": cached.get("normalized") or normalize_text(ocr_text),
        }
        if cached.get("id") is not None:
            result["food_id"] = cached.get("id")
        return result

    # ------------------------------------------------------------------
    def record_correction(
        self,
        raw_text: Optional[str],
        *,
        food_id: Optional[Any] = None,
        food_name: Optional[str] = None,
    ) -> bool:
        if not raw_text:
            return False
        return self.labels_cache.update(raw_text, food_id=food_id, food_name=food_name)

    # ------------------------------------------------------------------
    @property
    def last_raw_text(self) -> Optional[str]:
        return self._last_raw_text
