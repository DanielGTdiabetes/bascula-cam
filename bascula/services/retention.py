# -*- coding: utf-8 -*-
"""
Retención y limpieza de ficheros JSONL (meals.jsonl, etc.).

Reglas soportadas:
- max_days: descarta entradas con created_at más antiguas que N días.
- max_entries: conserva solo las N más recientes.
- max_bytes: limita el tamaño total del archivo (se recorta por el principio).

Operación segura: reescribe a un .tmp y luego reemplaza.
"""
from __future__ import annotations
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json


def _parse_ts(d: dict) -> datetime | None:
    ts = d.get('created_at') or d.get('ts')
    if not ts:
        return None
    try:
        s = str(ts)
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        return datetime.fromisoformat(s)
    except Exception:
        return None


def prune_jsonl(path: str | Path, *, max_days: int | None = None, max_entries: int | None = None, max_bytes: int | None = None) -> None:
    p = Path(path)
    if not p.exists():
        return
    try:
        lines = p.read_text(encoding='utf-8', errors='ignore').splitlines()
    except Exception:
        return
    now = datetime.now(timezone.utc)

    # 1) Filtrar por antigüedad
    if max_days and max_days > 0:
        cutoff = now - timedelta(days=int(max_days))
        kept = []
        for ln in lines:
            try:
                d = json.loads(ln)
            except Exception:
                continue
            ts = _parse_ts(d)
            if ts is None or ts >= cutoff:
                kept.append(ln)
        lines = kept

    # 2) Limitar número de entradas (conservar las últimas)
    if max_entries and max_entries > 0 and len(lines) > max_entries:
        lines = lines[-int(max_entries):]

    # 3) Limitar tamaño (caracteres UTF-8 ≈ bytes)
    if max_bytes and max_bytes > 0:
        total = sum(len(ln.encode('utf-8')) + 1 for ln in lines)  # +1 por \n
        if total > max_bytes:
            # recorta desde el principio hasta cumplir tamaño
            acc = 0
            cut = len(lines)
            for i in range(len(lines) - 1, -1, -1):
                acc += len(lines[i].encode('utf-8')) + 1
                if acc > max_bytes:
                    cut = i + 1
                    break
            lines = lines[cut:]

    # Reescritura atómica
    try:
        tmp = p.with_suffix(p.suffix + '.tmp')
        tmp.write_text("\n".join(lines) + ("\n" if lines else ""), encoding='utf-8')
        os.replace(tmp, p)
    except Exception:
        pass

