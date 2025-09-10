#!/usr/bin/env python3
"""
Diagnóstico de imports y backend serie.
Ejecutar desde la raíz del repo:  python3 scripts/diagnose_scale_import.py
"""
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
print("="*60)
print(f"Repo root: {repo_root}")
py_backend = repo_root / "python_backend"
print(f"python_backend: {py_backend}  (exists={py_backend.exists()})")
if str(py_backend) not in sys.path:
    sys.path.insert(0, str(py_backend))
print("sys.path HEAD:", sys.path[:3])

ok = False
err = None
try:
    from serial_scale import SerialScale  # type: ignore
    ok = True
    print("[OK] Importado serial_scale.SerialScale")
except Exception as e:
    err = e
    print("[ERROR] No se pudo importar SerialScale:", repr(e))

if ok:
    try:
        s = SerialScale(port="/dev/serial0", baud=115200)
        print("[OK] Instanciado SerialScale(port=/dev/serial0, baud=115200)")
    except Exception as e2:
        print("[ERROR] Fallo al instanciar SerialScale:", repr(e2))

print("="*60)
