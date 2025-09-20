#!/usr/bin/env python3
"""Utility to migrate stored recipes steps to dict format."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, List

from bascula.domain import recipes as domain_recipes


def _convert_steps(raw_steps: Any) -> tuple[List[dict], bool]:
    if not isinstance(raw_steps, list):
        return [], False
    changed = False
    converted: List[dict] = []
    for item in raw_steps:
        if isinstance(item, dict):
            converted.append(item)
            continue
        text = str(item or "").strip()
        if not text:
            continue
        converted.append({"text": text})
        changed = True
    return converted, changed


def migrate_file(path: Path, dry_run: bool = False) -> int:
    if not path.exists():
        print(f"No se encontró archivo de recetas en {path}.")
        return 0

    lines = path.read_text(encoding="utf-8").splitlines()
    updated: List[str] = []
    migrated_count = 0

    for ln in lines:
        if not ln.strip():
            continue
        try:
            obj = json.loads(ln)
        except Exception:
            updated.append(ln)
            continue
        steps, changed = _convert_steps(obj.get("steps"))
        if changed:
            obj["steps"] = steps
            migrated_count += 1
        updated.append(json.dumps(obj, ensure_ascii=False))

    if migrated_count and not dry_run:
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        backup = path.with_suffix(path.suffix + f".bak{timestamp}")
        shutil.copy2(path, backup)
        path.write_text("\n".join(updated) + ("\n" if updated else ""), encoding="utf-8")
        print(f"Migradas {migrated_count} recetas. Copia de seguridad: {backup}")
    elif migrated_count:
        print(f"Se migrarían {migrated_count} recetas (dry-run).")
    else:
        print("No se requirió migración.")
    return migrated_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrar pasos de recetas a formato dict.")
    parser.add_argument("--dry-run", action="store_true", help="Mostrar cambios sin escribir archivo")
    args = parser.parse_args()
    migrate_file(domain_recipes.RECIPES_FILE, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
