from __future__ import annotations

import csv
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "gi_table.csv"


def _normalize(text: str) -> str:
    txt = unicodedata.normalize("NFKD", (text or "")).encode("ascii", "ignore").decode("ascii")
    txt = txt.lower().strip()
    for ch in ("-", "_", "+"):
        txt = txt.replace(ch, " ")
    txt = " ".join(txt.split())
    if txt.endswith("es") and len(txt) > 4:
        txt = txt[:-2]
    elif txt.endswith("s") and len(txt) > 3:
        txt = txt[:-1]
    return txt


@lru_cache(maxsize=1)
def load_gi_table() -> Dict[str, int]:
    table: Dict[str, int] = {}
    if not _DATA_PATH.exists():
        return table
    try:
        with _DATA_PATH.open("r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                name = row.get("name")
                gi_raw = row.get("gi")
                if not name:
                    continue
                try:
                    gi = int(float(gi_raw)) if gi_raw not in (None, "") else None
                except (ValueError, TypeError):
                    gi = None
                if gi is None:
                    continue
                norm = _normalize(name)
                if not norm:
                    continue
                table.setdefault(norm, gi)
        return table
    except Exception:
        return {}


def lookup_gi(name: str) -> Optional[int]:
    norm = _normalize(name)
    if not norm:
        return None
    table = load_gi_table()
    if norm in table:
        return table[norm]
    # Buscar variantes simples
    for variant in (norm.replace(" ", ""), norm.replace(" ", "-")):
        if variant in table:
            return table[variant]
    # Búsqueda parcial tolerante
    for key, value in table.items():
        if norm in key or key in norm:
            return value
    return None
