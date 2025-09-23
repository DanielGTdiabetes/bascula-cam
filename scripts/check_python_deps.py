#!/usr/bin/env python3
"""Verificador de dependencias Python críticas para la UI."""

from __future__ import annotations

import importlib
import os
import sys
from typing import Iterable, Tuple

MODULES: Tuple[Tuple[str, str], ...] = (
    ("flask", "Flask"),
    ("PIL", "Pillow"),
    ("numpy", "NumPy"),
    ("cv2", "OpenCV"),
    ("tkinter", "tkinter"),
    ("prctl", "python-prctl"),
)

OPTIONAL_MODULES: Tuple[Tuple[str, str], ...] = (
    ("tflite_runtime.interpreter", "tflite_runtime"),
)


def iter_modules() -> Iterable[Tuple[str, str, bool]]:
    optional_flag = os.getenv("TFLITE_OPTIONAL", "0") == "1"
    for module_name, label in MODULES:
        yield module_name, label, False
    for module_name, label in OPTIONAL_MODULES:
        yield module_name, label, optional_flag


def main() -> int:
    missing: list[str] = []
    optional_missing: list[str] = []

    for module_name, friendly, is_optional in iter_modules():
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - diagnóstico interactivo
            target = f"{friendly} ({module_name}): {exc}"
            if is_optional:
                optional_missing.append(target)
            else:
                missing.append(target)

    if missing:
        print("[ERR] Dependencias ausentes:\n - " + "\n - ".join(missing), file=sys.stderr)
        if optional_missing:
            print(
                "[WARN] Dependencias opcionales no disponibles:\n - "
                + "\n - ".join(optional_missing),
                file=sys.stderr,
            )
        return 1

    if optional_missing:
        print(
            "[WARN] Dependencias opcionales no disponibles:\n - "
            + "\n - ".join(optional_missing),
            file=sys.stderr,
        )

    print("[OK] Dependencias Python verificadas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
