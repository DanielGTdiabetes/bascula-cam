#!/usr/bin/env python3
"""Smoke test para verificar imports clave de la UI."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MODULES = [
    "bascula.ui.app",
    "bascula.ui.widgets",
    "bascula.ui.overlay_recipe",
]


def main() -> int:
    for name in MODULES:
        try:
            importlib.import_module(name)
        except Exception as exc:
            print(f"[err] No se pudo importar {name}: {exc}")
            return 1
    print("[ok] Imports UI verificados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
