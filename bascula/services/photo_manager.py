#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PhotoManager — capturas con Picamera2 y ciclo de vida efímero (staging -> borrar).
- No crea ni gestiona la instancia de Picamera2: se la inyectas desde tu app.
- Guarda JPEGs en ~/.bascula/photos/staging/
- Al "usar" la foto (p.ej. tras envío a reconocimiento), se borra con mark_used().
- Incluye límites de seguridad por tamaño total y por número de archivos.
"""
from __future__ import annotations
import os, json, time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

HOME = Path(os.path.expanduser("~"))
BASE_DIR = HOME / ".bascula" / "photos"
STAGING_DIR = BASE_DIR / "staging"
META_DIR = BASE_DIR / "meta"
CFG_FILE = BASE_DIR / "config.json"

DEFAULT_MAX_COUNT = 500
DEFAULT_MAX_BYTES = 800 * 1024 * 1024  # 800 MB
DEFAULT_JPEG_QUALITY = 90
DEFAULT_FILENAME_PREFIX = "cap"  # cap-YYYYmmdd-HHMMSS-sss.jpg

@dataclass
class PhotoConfig:
    max_count: int = DEFAULT_MAX_COUNT
    max_bytes: int = DEFAULT_MAX_BYTES
    jpeg_quality: int = DEFAULT_JPEG_QUALITY
    filename_prefix: str = DEFAULT_FILENAME_PREFIX
    keep_last_n_after_use: int = 0

    @staticmethod
    def load() -> "PhotoConfig":
        try:
            if CFG_FILE.exists():
                data = json.loads(CFG_FILE.read_text(encoding="utf-8"))
                return PhotoConfig(**data)
        except Exception:
            pass
        return PhotoConfig()

    def save(self) -> None:
        BASE_DIR.mkdir(parents=True, exist_ok=True)
        CFG_FILE.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")


class PhotoManager:
    """
    Uso típico:
        pm = PhotoManager(logger=my_logger)
        pm.attach_camera(picam2)              # Reutiliza tu instancia existente
        path = pm.capture(label="add_item")   # Guarda JPEG y devuelve ruta
        # ... procesas ...
        pm.mark_used(path)                    # Borra al terminar
    """
    def __init__(self, logger=None, config: Optional[PhotoConfig] = None):
        self.log = logger or _NullLogger()
        self.cfg = config or PhotoConfig.load()
        BASE_DIR.mkdir(parents=True, exist_ok=True)
        STAGING_DIR.mkdir(parents=True, exist_ok=True)
        META_DIR.mkdir(parents=True, exist_ok=True)
        self.picam2 = None
        self._ensure_permissions()

    def attach_camera(self, picam2) -> None:
        self.picam2 = picam2
        self.log.info("PhotoManager: cámara adjuntada.")

    def capture(self, label: str = "manual") -> Path:
        if self.picam2 is None:
            raise RuntimeError("PhotoManager: no hay cámara adjunta (attach_camera(picam2)).")
        ts = time.strftime("%Y%m%d-%H%M%S", time.localtime())
        ms = int((time.time() % 1) * 1000)
        fname = f"{self.cfg.filename_prefix}-{ts}-{ms:03d}-{_slug(label)}.jpg"
        out_path = STAGING_DIR / fname
        # Intento 1: captura directa a fichero (rápido y eficiente)
        try:
            self.picam2.capture_file(str(out_path), format="jpeg", quality=self.cfg.jpeg_quality)
        except Exception:
            # Fallback: array -> Pillow
            self._capture_via_pillow(out_path)
        self._write_meta(out_path, {"label": label, "ts": time.time()})
        self._enforce_limits()
        self.log.info(f"PhotoManager: captura guardada en {out_path}")
        return out_path

    def mark_used(self, path: Path | str) -> None:
        p = Path(path)
        try:
            if self.cfg.keep_last_n_after_use > 0:
                self._keep_n_latest(self.cfg.keep_last_n_after_use)
            else:
                if p.exists():
                    p.unlink()
                    self.log.info(f"PhotoManager: foto borrada tras uso: {p}")
            mp = self._meta_path(p)
            if mp.exists():
                mp.unlink()
        except Exception as e:
            self.log.error(f"PhotoManager: error al borrar {p}: {e}")

    def cleanup(self) -> None:
        self._enforce_limits()

    # ----------------- Internos -----------------
    def _capture_via_pillow(self, out_path: Path) -> None:
        from PIL import Image
        arr = self.picam2.capture_array()  # RGB
        Image.fromarray(arr).save(out_path, format="JPEG", quality=self.cfg.jpeg_quality, optimize=True)

    def _ensure_permissions(self) -> None:
        for d in (BASE_DIR, STAGING_DIR, META_DIR):
            try:
                os.chmod(d, 0o700)
            except Exception:
                pass

    def _write_meta(self, photo_path: Path, meta_obj: dict) -> None:
        self._meta_path(photo_path).write_text(json.dumps(meta_obj, ensure_ascii=False), encoding="utf-8")

    def _meta_path(self, photo_path: Path) -> Path:
        return META_DIR / (photo_path.stem + ".json")

    def _enforce_limits(self) -> None:
        files = sorted(STAGING_DIR.glob("*.jpg"), key=lambda p: p.stat().st_mtime)
        if len(files) > self.cfg.max_count:
            to_rm = len(files) - self.cfg.max_count
            for p in files[:to_rm]:
                _safe_unlink(p); _safe_unlink(self._meta_path(p))
                self.log.warning(f"PhotoManager: límite count -> borrada {p}")
        total = sum((p.stat().st_size for p in STAGING_DIR.glob("*.jpg")), 0)
        if total > self.cfg.max_bytes:
            files = sorted(STAGING_DIR.glob("*.jpg"), key=lambda p: p.stat().st_mtime)
            i = 0
            while total > self.cfg.max_bytes and i < len(files):
                p = files[i]
                sz = p.stat().st_size
                _safe_unlink(p); _safe_unlink(self._meta_path(p))
                total -= sz; i += 1
                self.log.warning(f"PhotoManager: límite bytes -> borrada {p}")

    def _keep_n_latest(self, n: int) -> None:
        files = sorted(STAGING_DIR.glob("*.jpg"), key=lambda p: p.stat().st_mtime)
        if len(files) <= n:
            return
        for p in files[:-n]:
            _safe_unlink(p); _safe_unlink(self._meta_path(p))
            self.log.info(f"PhotoManager: conservando últimas {n}, borrada {p}")


def _slug(text: str) -> str:
    s = "".join((c.lower() if c.isalnum() else "-") for c in text)
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-") or "x"

def _safe_unlink(p: Path) -> None:
    try:
        if p.exists():
            p.unlink()
    except Exception:
        pass

class _NullLogger:
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def error(self, *a, **k): pass
