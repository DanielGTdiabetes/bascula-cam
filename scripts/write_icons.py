#!/usr/bin/env python3
"""Generate fallback PNG icons from an embedded manifest."""
from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path
from typing import Dict, Iterable, List

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT_DIR / "assets" / "icons"

_BASE_ICON = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAOklEQVR4nO3TMQoAIBADwfv/p7UWm4MzjcxC+mlSJd2t8FqAVAAAAE8Ak58DAAD8AZgEAADQBiQnHW1G"
    "pptlW1krWgAAAABJRU5ErkJggg=="
)

_REQUIRED_NAMES: List[str] = [
    "back",
    "ok",
    "cancel",
    "save",
    "delete",
    "settings",
    "camera",
    "home",
    "plus",
    "minus",
    "refresh",
    "info",
    "warning",
    "menu",
    "weight",
    "tare",
    "zero",
    "print",
    "calibrate",
    # UI specific spanish aliases
    "tara",
    "cero",
    "swap",
    "food",
    "recipe",
    "timer",
    "alarm",
    "bell",
    "bg",
    "speaker",
    "wifi",
]

ICON_MANIFEST: Dict[str, str] = {name: _BASE_ICON for name in _REQUIRED_NAMES}


def _load_validation_helpers():  # pragma: no cover - imported lazily
    if __package__:
        from .validate_assets import ValidationError, validate_icon_file  # type: ignore
    else:  # pragma: no cover - execution as script
        from validate_assets import ValidationError, validate_icon_file  # type: ignore

    return ValidationError, validate_icon_file


def _is_valid_icon(path: Path) -> bool:
    ValidationError = None
    validate_icon_file = None
    try:
        ValidationError, validate_icon_file = _load_validation_helpers()
    except Exception:
        pass

    if validate_icon_file is not None and ValidationError is not None:
        try:
            validate_icon_file(path)
            return True
        except ValidationError:
            return False

    try:
        with path.open("rb") as handle:
            if handle.read(len(PNG_SIGNATURE)) != PNG_SIGNATURE:
                return False
        from PIL import Image  # type: ignore

        with Image.open(path) as img:
            img.verify()
        with Image.open(path) as img:
            img.load()
            width, height = img.size
        return width >= 1 and height >= 1
    except Exception:
        return False


def _needs_regeneration(path: Path, force: bool) -> bool:
    if not path.exists():
        return True
    if force:
        return True
    return not _is_valid_icon(path)


def _decode_icon(data: str) -> bytes:
    try:
        return base64.b64decode(data)
    except Exception as exc:  # pragma: no cover - manifest is constant
        raise RuntimeError(f"No se pudo decodificar PNG embebido: {exc}") from exc


def _write_icon(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    os.chmod(path, 0o644)


def generate_icons(out_dir: Path, force: bool = False) -> List[Path]:
    created: List[Path] = []
    for name, data in ICON_MANIFEST.items():
        target = out_dir / f"{name}.png"
        if not _needs_regeneration(target, force):
            continue
        payload = _decode_icon(data)
        _write_icon(target, payload)
        created.append(target)
    return created


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera iconos PNG de fallback")
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUTPUT),
        help="Directorio destino para los iconos (por defecto assets/icons)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerar iconos incluso si parecen válidos",
    )
    args = parser.parse_args(argv)

    out_dir = Path(args.out).resolve()
    created = generate_icons(out_dir, force=args.overwrite)

    for path in created:
        print(path)

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
