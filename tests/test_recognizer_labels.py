from __future__ import annotations

from pathlib import Path

from recognizer.vision import LabelsCache, VisionRecognizer, normalize_text


def test_normalize_text_strips_punctuation() -> None:
    assert normalize_text("  Café, listo! ") == "cafe listo"
    assert normalize_text("HELLO-WORLD") == "hello world"


def test_labels_cache_persists(monkeypatch, tmp_path: Path) -> None:
    labels_path = tmp_path / "labels.json"
    monkeypatch.setenv("BASCULA_LABELS_PATH", str(labels_path))

    cache = LabelsCache()
    assert labels_path.exists()
    assert cache.lookup("Manzana") is None

    cache.update("Manzana", food_id=42, food_name="Manzana Roja")
    entry = cache.lookup("  manzana   ")
    assert entry is not None
    assert entry["id"] == "42"
    assert entry["name"] == "Manzana Roja"

    cache_bis = LabelsCache(path=labels_path)
    entry_bis = cache_bis.lookup("MANZÁNA!!!")
    assert entry_bis is not None
    assert entry_bis["name"] == "Manzana Roja"

    monkeypatch.delenv("BASCULA_LABELS_PATH", raising=False)


def test_vision_recognizer_uses_cache(tmp_path: Path) -> None:
    labels_path = tmp_path / "labels.json"
    cache = LabelsCache(path=labels_path)
    cache.update("Leche entera", food_id="abc", food_name="Leche Entera")

    recognizer = VisionRecognizer(labels_cache=cache)
    result = recognizer.recognize(weight=120, ocr_text="Leché entera!!")
    assert result is not None
    assert result["name"] == "Leche Entera"
    assert result["source"] == "vision-cache"
    assert result["grams"] == 120
    assert result["food_id"] == "abc"

    recognizer.record_correction("Yogurt", food_id="y1", food_name="Yogurt Natural")
    correction = cache.lookup("yogurt")
    assert correction is not None
    assert correction["name"] == "Yogurt Natural"
