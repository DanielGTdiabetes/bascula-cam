#!/usr/bin/env python3
"""Validate PNG icon assets to ensure they are readable."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List

try:
    from PIL import Image  # noqa: WPS433 (import within try for helpful message)
except Exception as e:  # pragma: no cover - runtime guard
    import sys

    print(
        "ERROR: Pillow (PIL) no está instalado. Instálalo antes de validar assets. "
        "Hint: pip install Pillow",
        file=sys.stderr,
    )
    raise

try:
    if __package__:
        from .write_icons import ICON_MANIFEST  # type: ignore
    else:  # pragma: no cover - execution as script
        from write_icons import ICON_MANIFEST  # type: ignore
except Exception:  # pragma: no cover - fallback if package context unavailable
    ICON_MANIFEST = {}

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
ROOT_DIR = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT_DIR / "assets" / "icons"


class ValidationError(Exception):
    """Custom exception used for structured validation errors."""

    def __init__(self, path: Path, message: str) -> None:
        super().__init__(message)
        self.path = path
        self.message = message

    def __str__(self) -> str:  # pragma: no cover - trivial repr
        return f"{self.path}: {self.message}"


def _read_signature(path: Path) -> bytes:
    with path.open("rb") as handle:
        signature = handle.read(len(PNG_SIGNATURE))
    return signature


def validate_icon_file(path: Path) -> None:
    try:
        signature = _read_signature(path)
    except OSError as exc:
        raise ValidationError(path, f"no se pudo leer: {exc}") from exc

    if signature != PNG_SIGNATURE:
        raise ValidationError(path, "firma PNG inválida")

    try:
        with Image.open(path) as img:
            img.verify()
        with Image.open(path) as img:
            img.load()
            width, height = img.size
    except Exception as exc:
        raise ValidationError(path, f"Pillow no puede abrirlo: {exc}") from exc

    if width < 1 or height < 1:
        raise ValidationError(path, f"dimensiones inválidas: {width}x{height}")


def _iter_icon_files(base_dir: Path) -> Iterable[Path]:
    if not base_dir.exists():
        return []
    return sorted(p for p in base_dir.rglob("*.png") if p.is_file())


def validate_icons(base_dir: Path) -> List[ValidationError]:
    errors: List[ValidationError] = []
    if not base_dir.exists():
        errors.append(ValidationError(base_dir, "directorio inexistente"))
        return errors

    for icon_path in _iter_icon_files(base_dir):
        try:
            validate_icon_file(icon_path)
        except ValidationError as err:
            errors.append(err)

    for name in sorted(ICON_MANIFEST):
        expected = base_dir / f"{name}.png"
        if not expected.exists():
            errors.append(ValidationError(expected, "icono requerido ausente"))
            continue
        try:
            validate_icon_file(expected)
        except ValidationError as err:
            errors.append(err)

    return errors


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Valida los iconos PNG de assets/icons")
    parser.add_argument(
        "--path",
        default=str(ICON_DIR),
        help="Directorio base donde buscar iconos (por defecto assets/icons)",
    )
    args = parser.parse_args(argv)

    base_dir = Path(args.path).resolve()
    errors = validate_icons(base_dir)

    if errors:
        print("Iconos corruptos o faltantes:", file=sys.stderr)
        for err in errors:
            print(f" - {err}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
